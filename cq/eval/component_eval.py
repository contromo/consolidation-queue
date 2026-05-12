from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from cq.eval.runner import (
    COMPONENT_EVAL_FAMILIES,
    FORCED_CONTRADICTION,
    generate_scenarios,
)
from cq.schemas.memory import CandidateUpdate, jsonable
from cq.schemas.scenario import EventKind, Scenario


QUALITY_GATES = {
    "candidate_detection_f1": 0.75,
    "claim_type_accuracy": 0.75,
    "scope_level_accuracy": 0.70,
    "scope_key_accuracy": 0.60,
    "canonicalization_b_cubed_f1": 0.65,
    "contradiction_f1": 0.75,
    "contradiction_precision": 0.75,
    "contradiction_recall": 0.70,
}
CANONICALIZATION_COVERAGE_THRESHOLD = QUALITY_GATES["candidate_detection_f1"]
FAILURE_EXAMPLE_LIMITS = {"per_type": 20}


@dataclass
class CandidateComponentPrediction:
    event_id: str
    candidate_id: str
    canonical_id: str
    claim_type: str
    scope_level: str
    scope_key: str
    contradicts: List[str] = field(default_factory=list)
    contradicts_event_ids: List[str] = field(default_factory=list)
    raw_claim: str = ""
    confidence: Optional[float] = None


@dataclass
class _BestPredictionSelection:
    prediction_by_event: Dict[str, CandidateComponentPrediction]
    duplicate_predictions: List[Tuple[str, CandidateComponentPrediction]]
    event_prediction_counts: List[int]


@dataclass
class _ComponentEvaluationClassification:
    scenario_count: int
    counters: Dict[str, int]
    canonical_gold: Dict[str, str]
    canonical_predicted: Dict[str, str]
    gold_contradictions: Set[Tuple[str, Tuple[str, str]]]
    predicted_contradictions: Set[Tuple[str, Tuple[str, str]]]
    prediction_counts_per_event: List[int]
    failure_example_candidates: List[Dict[str, object]]


def oracle_component_predictions(scenario: Scenario) -> List[CandidateComponentPrediction]:
    predictions = []
    for event in scenario.sorted_events():
        if event.kind != EventKind.OBSERVATION or event.candidate is None:
            continue
        predictions.append(_prediction_from_candidate(event.event_id, event.candidate))
    return predictions


def oracle_predictions_by_scenario(
    scenarios: Iterable[Scenario],
) -> Dict[str, List[CandidateComponentPrediction]]:
    return {
        scenario.scenario_id: oracle_component_predictions(scenario)
        for scenario in scenarios
    }


def evaluate_component_predictions(
    scenarios: Iterable[Scenario],
    predictions_by_scenario: Dict[str, List[CandidateComponentPrediction]],
    scenario_errors: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    scenario_errors = scenario_errors or {}
    classification = _classify_component_predictions(
        scenarios,
        predictions_by_scenario,
        scenario_errors=scenario_errors,
    )
    metrics = _metrics_from_classification(
        classification,
        scenario_error_count=len(scenario_errors),
    )
    failure_examples, failure_example_overflow = _limited_failure_examples(
        classification.failure_example_candidates,
    )
    return {
        "metrics": metrics,
        "quality_gates": evaluate_quality_gates(metrics),
        "failure_examples": failure_examples,
        "failure_example_count": len(failure_examples),
        "failure_example_limits": FAILURE_EXAMPLE_LIMITS,
        "failure_example_overflow": failure_example_overflow,
    }


def canonical_component_maps(
    scenarios: Iterable[Scenario],
    predictions_by_scenario: Dict[str, List[CandidateComponentPrediction]],
    *,
    scenario_errors: Optional[Dict[str, object]] = None,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return gold/predicted canonical maps; None scenario_errors is treated as no errors."""
    classification = _classify_component_predictions(
        scenarios,
        predictions_by_scenario,
        scenario_errors=scenario_errors or {},
    )
    return classification.canonical_gold, classification.canonical_predicted


def _classify_component_predictions(
    scenarios: Iterable[Scenario],
    predictions_by_scenario: Dict[str, List[CandidateComponentPrediction]],
    *,
    scenario_errors: Dict[str, object],
) -> _ComponentEvaluationClassification:
    counters = _new_counters()
    canonical_gold: Dict[str, str] = {}
    canonical_predicted: Dict[str, str] = {}
    gold_contradictions: Set[Tuple[str, Tuple[str, str]]] = set()
    predicted_contradictions: Set[Tuple[str, Tuple[str, str]]] = set()
    gold_contradiction_payloads: Dict[Tuple[str, Tuple[str, str]], Dict[str, object]] = {}
    predicted_contradiction_payloads: Dict[Tuple[str, Tuple[str, str]], Dict[str, object]] = {}
    prediction_counts_per_event: List[int] = []
    failure_example_candidates: List[Dict[str, object]] = []
    scenario_count = 0

    for scenario in scenarios:
        scenario_count += 1
        metadata = _scenario_metadata(scenario)
        event_text_by_id = _event_text_by_id(scenario)
        scenario_error = scenario_errors.get(scenario.scenario_id)
        if scenario_error is not None:
            failure_example_candidates.append(
                _failure_example(
                    component="scenario",
                    failure_type="scenario_error",
                    metadata=metadata,
                    event_text_by_id=event_text_by_id,
                    error=scenario_error,
                )
            )
        predictions = (
            []
            if scenario_error is not None
            else predictions_by_scenario.get(scenario.scenario_id, [])
        )
        gold_by_event = _gold_candidates_by_event(scenario)
        candidate_id_to_event_id = _candidate_id_to_event_id(scenario)
        selection = _best_predictions_by_event(
            predictions,
            gold_by_event,
        )
        prediction_by_event = selection.prediction_by_event
        prediction_counts_per_event.extend(selection.event_prediction_counts)
        gold_event_ids = set(gold_by_event)
        predicted_event_ids = set(prediction_by_event)
        true_positive_events = gold_event_ids.intersection(predicted_event_ids)

        counters["candidate_detection_tp"] += len(true_positive_events)
        counters["candidate_detection_fp"] += (
            len(predicted_event_ids - gold_event_ids)
            + len(selection.duplicate_predictions)
        )
        counters["candidate_detection_fn"] += len(gold_event_ids - predicted_event_ids)
        counters["extra_same_event_prediction_count"] += len(selection.duplicate_predictions)
        counters["claim_type_count"] += len(true_positive_events)
        counters["scope_level_count"] += len(true_positive_events)
        counters["scope_key_count"] += len(true_positive_events)

        for event_id in sorted(gold_event_ids - predicted_event_ids):
            failure_example_candidates.append(
                _failure_example(
                    component="candidate_detection",
                    failure_type="candidate_missing",
                    metadata=metadata,
                    event_text_by_id=event_text_by_id,
                    event_id=event_id,
                    gold=_candidate_claim_payload(event_id, gold_by_event[event_id]),
                )
            )

        for event_id in sorted(predicted_event_ids - gold_event_ids):
            failure_example_candidates.append(
                _failure_example(
                    component="candidate_detection",
                    failure_type="candidate_extra",
                    metadata=metadata,
                    event_text_by_id=event_text_by_id,
                    event_id=event_id,
                    predicted=_prediction_claim_payload(prediction_by_event[event_id]),
                )
            )

        for event_id, duplicate_prediction in selection.duplicate_predictions:
            failure_example_candidates.append(
                _failure_example(
                    component="candidate_detection",
                    failure_type="candidate_duplicate",
                    metadata=metadata,
                    event_text_by_id=event_text_by_id,
                    event_id=event_id,
                    predicted=_prediction_claim_payload(duplicate_prediction),
                )
            )

        for event_id in sorted(true_positive_events):
            gold = gold_by_event[event_id]
            predicted = prediction_by_event[event_id]
            gold_payload = _candidate_claim_payload(event_id, gold)
            predicted_payload = _prediction_claim_payload(predicted)
            claim_type_correct = predicted.claim_type == gold.claim_type.value
            scope_level_correct = predicted.scope_level == gold.scope_level.value
            scope_key_correct = predicted.scope_key == gold.scope_key
            counters["claim_type_correct"] += int(claim_type_correct)
            counters["scope_level_correct"] += int(scope_level_correct)
            counters["scope_key_correct"] += int(scope_key_correct)
            if not claim_type_correct:
                failure_example_candidates.append(
                    _failure_example(
                        component="claim_type",
                        failure_type="claim_type_mismatch",
                        metadata=metadata,
                        event_text_by_id=event_text_by_id,
                        event_id=event_id,
                        gold=gold_payload,
                        predicted=predicted_payload,
                    )
                )
            if not scope_level_correct:
                failure_example_candidates.append(
                    _failure_example(
                        component="scope_level",
                        failure_type="scope_level_mismatch",
                        metadata=metadata,
                        event_text_by_id=event_text_by_id,
                        event_id=event_id,
                        gold=gold_payload,
                        predicted=predicted_payload,
                    )
                )
            if not scope_key_correct:
                failure_example_candidates.append(
                    _failure_example(
                        component="scope_key",
                        failure_type="scope_key_mismatch",
                        metadata=metadata,
                        event_text_by_id=event_text_by_id,
                        event_id=event_id,
                        gold=gold_payload,
                        predicted=predicted_payload,
                    )
                )

        scenario_canonical_gold: Dict[str, str] = {}
        scenario_canonical_predicted: Dict[str, str] = {}
        scenario_gold_claim_payloads_by_item: Dict[str, Dict[str, object]] = {}
        scenario_predicted_claim_payloads_by_item: Dict[str, Dict[str, object]] = {}
        for event_id, gold in gold_by_event.items():
            item_id = _component_item_id(scenario.scenario_id, event_id)
            scenario_canonical_gold[item_id] = _scoped_canonical_label(
                scenario.scenario_id,
                gold.canonical_id,
            )
            scenario_gold_claim_payloads_by_item[item_id] = _candidate_claim_payload(event_id, gold)
            predicted = prediction_by_event.get(event_id)
            if predicted is not None:
                scenario_canonical_predicted[item_id] = _scoped_canonical_label(
                    scenario.scenario_id,
                    predicted.canonical_id,
                )
                scenario_predicted_claim_payloads_by_item[item_id] = _prediction_claim_payload(predicted)
            for target_id in gold.contradicts:
                target_event_id = candidate_id_to_event_id[target_id]
                edge = _contradiction_edge(
                    scenario.scenario_id,
                    event_id,
                    target_event_id,
                )
                gold_contradictions.add(edge)
                if edge not in gold_contradiction_payloads:
                    gold_contradiction_payloads[edge] = _contradiction_payload(
                        metadata,
                        event_id,
                        target_event_id,
                        _candidate_claim_payload(event_id, gold),
                        _candidate_claim_payload(target_event_id, gold_by_event[target_event_id]),
                        event_text_by_id,
                    )
        canonical_gold.update(scenario_canonical_gold)
        canonical_predicted.update(scenario_canonical_predicted)

        for predicted in predictions:
            edges_with_payloads = _predicted_contradiction_edges_with_payloads(
                scenario.scenario_id,
                predicted,
                candidate_id_to_event_id,
                event_text_by_id,
                metadata,
            )
            for edge, payload in edges_with_payloads.items():
                predicted_contradictions.add(edge)
                predicted_contradiction_payloads.setdefault(edge, payload)

        _add_canonicalization_failure_examples(
            failure_example_candidates,
            metadata=metadata,
            event_text_by_id=event_text_by_id,
            canonical_gold=scenario_canonical_gold,
            canonical_predicted=scenario_canonical_predicted,
            gold_claim_payloads_by_item=scenario_gold_claim_payloads_by_item,
            predicted_claim_payloads_by_item=scenario_predicted_claim_payloads_by_item,
        )

    contradiction_missing = gold_contradictions - predicted_contradictions
    contradiction_extra = predicted_contradictions - gold_contradictions
    for edge in sorted(contradiction_missing):
        failure_example_candidates.append(
            _failure_example_from_contradiction(
                failure_type="contradiction_missing",
                component="contradiction",
                payload=gold_contradiction_payloads[edge],
            )
        )
    for edge in sorted(contradiction_extra):
        failure_example_candidates.append(
            _failure_example_from_contradiction(
                failure_type="contradiction_extra",
                component="contradiction",
                payload=predicted_contradiction_payloads[edge],
            )
        )

    return _ComponentEvaluationClassification(
        scenario_count=scenario_count,
        counters=counters,
        canonical_gold=canonical_gold,
        canonical_predicted=canonical_predicted,
        gold_contradictions=gold_contradictions,
        predicted_contradictions=predicted_contradictions,
        prediction_counts_per_event=prediction_counts_per_event,
        failure_example_candidates=failure_example_candidates,
    )


def _metrics_from_classification(
    classification: _ComponentEvaluationClassification,
    *,
    scenario_error_count: int,
) -> Dict[str, object]:
    counters = classification.counters
    gold_contradictions = classification.gold_contradictions
    predicted_contradictions = classification.predicted_contradictions
    prediction_counts_per_event = classification.prediction_counts_per_event
    contradiction_tp = len(gold_contradictions.intersection(predicted_contradictions))
    contradiction_fp = len(predicted_contradictions - gold_contradictions)
    contradiction_fn = len(gold_contradictions - predicted_contradictions)
    candidate_precision = _safe_divide(
        counters["candidate_detection_tp"],
        counters["candidate_detection_tp"] + counters["candidate_detection_fp"],
    )
    candidate_recall = _safe_divide(
        counters["candidate_detection_tp"],
        counters["candidate_detection_tp"] + counters["candidate_detection_fn"],
    )
    contradiction_precision = _safe_divide(
        contradiction_tp,
        contradiction_tp + contradiction_fp,
    )
    contradiction_recall = _safe_divide(
        contradiction_tp,
        contradiction_tp + contradiction_fn,
    )
    contradiction_applicability = _contradiction_applicability(
        gold_contradictions,
        predicted_contradictions,
    )
    if contradiction_applicability == "not_applicable":
        contradiction_precision = None
        contradiction_recall = None
        contradiction_f1 = None
    else:
        contradiction_f1 = _f1(contradiction_precision, contradiction_recall)
    b_cubed = _b_cubed(classification.canonical_gold, classification.canonical_predicted)

    return {
        "scenario_count": classification.scenario_count,
        "scenario_error_count": scenario_error_count,
        "predicted_event_count": len(prediction_counts_per_event),
        "extra_same_event_prediction_count": counters["extra_same_event_prediction_count"],
        "predictions_per_event_p50": _percentile(prediction_counts_per_event, 0.50),
        "predictions_per_event_p95": _percentile(prediction_counts_per_event, 0.95),
        "predictions_per_event_max": max(prediction_counts_per_event)
        if prediction_counts_per_event
        else 0,
        "candidate_detection_tp": counters["candidate_detection_tp"],
        "candidate_detection_fp": counters["candidate_detection_fp"],
        "candidate_detection_fn": counters["candidate_detection_fn"],
        "candidate_detection_precision": candidate_precision,
        "candidate_detection_recall": candidate_recall,
        "candidate_detection_f1": _f1(candidate_precision, candidate_recall),
        "claim_type_correct": counters["claim_type_correct"],
        "claim_type_count": counters["claim_type_count"],
        "claim_type_accuracy": _accuracy(
            counters["claim_type_correct"],
            counters["claim_type_count"],
        ),
        "scope_level_correct": counters["scope_level_correct"],
        "scope_level_count": counters["scope_level_count"],
        "scope_level_accuracy": _accuracy(
            counters["scope_level_correct"],
            counters["scope_level_count"],
        ),
        "scope_key_correct": counters["scope_key_correct"],
        "scope_key_count": counters["scope_key_count"],
        "scope_key_accuracy": _accuracy(
            counters["scope_key_correct"],
            counters["scope_key_count"],
        ),
        "canonicalization_b_cubed_precision": b_cubed["precision"],
        "canonicalization_b_cubed_recall": b_cubed["recall"],
        "canonicalization_b_cubed_f1": b_cubed["f1"],
        "canonicalization_coverage": b_cubed["coverage"],
        "canonicalization_coverage_threshold": CANONICALIZATION_COVERAGE_THRESHOLD,
        "contradiction_tp": contradiction_tp,
        "contradiction_fp": contradiction_fp,
        "contradiction_fn": contradiction_fn,
        "contradiction_applicability": contradiction_applicability,
        "contradiction_precision": contradiction_precision,
        "contradiction_recall": contradiction_recall,
        "contradiction_f1": contradiction_f1,
    }


def evaluate_quality_gates(metrics: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    gates = {}
    for metric_name, threshold in QUALITY_GATES.items():
        value = metrics.get(metric_name)
        if (
            metric_name.startswith("contradiction_")
            and metrics.get("contradiction_applicability") == "not_applicable"
        ):
            gates[metric_name] = {
                "value": value,
                "threshold": threshold,
                "passed": True,
                "status": "not_applicable",
            }
            continue
        gates[metric_name] = {
            "value": value,
            "threshold": threshold,
            "passed": isinstance(value, (int, float)) and value >= threshold,
            "status": "measured",
        }
    return gates


def build_oracle_component_eval_artifact(
    *,
    family: str,
    scenario_count: int,
    template_mix: str,
) -> Dict[str, object]:
    return build_component_eval_artifact(
        family=family,
        scenario_count=scenario_count,
        template_mix=template_mix,
        predictions_by_scenario=None,
        mode="oracle_component_upper_bound",
    )


def build_component_eval_artifact(
    *,
    family: str,
    scenario_count: int,
    template_mix: str,
    predictions_by_scenario: Optional[Dict[str, List[CandidateComponentPrediction]]] = None,
    scenario_errors: Optional[Dict[str, object]] = None,
    mode: Optional[str] = None,
) -> Dict[str, object]:
    if family not in COMPONENT_EVAL_FAMILIES:
        raise ValueError(
            "Family '{}' is not component-eval eligible. Allowed: {}".format(
                family,
                ", ".join(sorted(COMPONENT_EVAL_FAMILIES)),
            )
        )
    scenarios = generate_scenarios(family, scenario_count, template_mix)
    scenario_errors = scenario_errors or {}
    if predictions_by_scenario is None:
        predictions_by_scenario = oracle_predictions_by_scenario(scenarios)
        artifact_mode = mode or "oracle_component_upper_bound"
    else:
        artifact_mode = mode or "component_predictions"
    evaluation = evaluate_component_predictions(
        scenarios,
        predictions_by_scenario,
        scenario_errors=scenario_errors,
    )
    return {
        "mode": artifact_mode,
        "family": family,
        "template_mix": template_mix,
        "requested_scenario_count": scenario_count,
        "scenario_count": len(scenarios),
        "scenario_error_count": len(scenario_errors),
        "scenario_errors": jsonable(scenario_errors),
        "quality_gate_thresholds": QUALITY_GATES,
        "metrics": evaluation["metrics"],
        "quality_gates": evaluation["quality_gates"],
        "failure_examples": evaluation["failure_examples"],
        "failure_example_count": evaluation["failure_example_count"],
        "failure_example_limits": evaluation["failure_example_limits"],
        "failure_example_overflow": evaluation["failure_example_overflow"],
    }


def load_predictions_by_scenario(
    predictions_path: Path,
) -> Dict[str, List[CandidateComponentPrediction]]:
    payload = json.loads(predictions_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "scenario_predictions" not in payload:
        raise ValueError("Prediction JSON must contain a top-level scenario_predictions object")
    scenario_predictions = payload["scenario_predictions"]
    if not isinstance(scenario_predictions, dict):
        raise ValueError("scenario_predictions must be an object keyed by scenario_id")
    for scenario_id, predictions in scenario_predictions.items():
        if not isinstance(predictions, list):
            raise ValueError("Predictions for scenario '{}' must be a list".format(scenario_id))
    return {
        scenario_id: [_prediction_from_mapping(prediction) for prediction in predictions]
        for scenario_id, predictions in scenario_predictions.items()
    }


def load_scenario_errors(predictions_path: Path) -> Dict[str, object]:
    payload = json.loads(predictions_path.read_text(encoding="utf-8"))
    scenario_errors = payload.get("scenario_errors", {}) if isinstance(payload, dict) else {}
    if not isinstance(scenario_errors, dict):
        raise ValueError("scenario_errors must be an object keyed by scenario_id")
    return scenario_errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate component predictions against scenario oracle labels."
    )
    parser.add_argument("--family", default=FORCED_CONTRADICTION, choices=sorted(COMPONENT_EVAL_FAMILIES))
    parser.add_argument("--scenarios", type=int, default=25)
    parser.add_argument("--template-mix", default="mixed")
    parser.add_argument("--predictions-json", default="")
    parser.add_argument("--output-json", default="")
    args = parser.parse_args(argv)

    predictions_by_scenario = (
        load_predictions_by_scenario(Path(args.predictions_json))
        if args.predictions_json
        else None
    )
    scenario_errors = (
        load_scenario_errors(Path(args.predictions_json))
        if args.predictions_json
        else None
    )
    artifact = build_component_eval_artifact(
        family=args.family,
        scenario_count=args.scenarios,
        template_mix=args.template_mix,
        predictions_by_scenario=predictions_by_scenario,
        scenario_errors=scenario_errors,
    )
    metrics = artifact["metrics"]
    print(
        "component_eval: candidate_f1={candidate} claim_type={claim} "
        "scope_level={scope_level} scope_key={scope_key} "
        "canonicalization_f1={canonicalization} contradiction_f1={contradiction}".format(
            candidate=_format_metric(metrics["candidate_detection_f1"]),
            claim=_format_metric(metrics["claim_type_accuracy"]),
            scope_level=_format_metric(metrics["scope_level_accuracy"]),
            scope_key=_format_metric(metrics["scope_key_accuracy"]),
            canonicalization=_format_metric(metrics["canonicalization_b_cubed_f1"]),
            contradiction=_format_metric(metrics["contradiction_f1"]),
        )
    )
    print("failure_examples={}".format(artifact["failure_example_count"]))
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(jsonable(artifact), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("Wrote {}".format(output_path))
    return 0


def _scenario_metadata(scenario: Scenario) -> Dict[str, object]:
    return {
        "scenario_id": scenario.scenario_id,
        "template_id": scenario.template_id,
        "template_kind": scenario.template_kind,
        "template_split": scenario.template_split,
    }


def _event_text_by_id(scenario: Scenario) -> Dict[str, str]:
    return {event.event_id: event.text for event in scenario.sorted_events()}


def _candidate_claim_payload(
    event_id: str,
    candidate: CandidateUpdate,
) -> Dict[str, object]:
    return {
        "event_id": event_id,
        "raw_claim": candidate.raw_claim,
        "claim_type": candidate.claim_type.value,
        "scope_level": candidate.scope_level.value,
        "scope_key": candidate.scope_key,
        "canonical_id": candidate.canonical_id or "",
    }


def _prediction_claim_payload(
    prediction: CandidateComponentPrediction,
) -> Dict[str, object]:
    return {
        "event_id": prediction.event_id,
        "raw_claim": prediction.raw_claim,
        "claim_type": prediction.claim_type,
        "scope_level": prediction.scope_level,
        "scope_key": prediction.scope_key,
        "canonical_id": prediction.canonical_id,
    }


def _event_only_claim_payload(event_id: str, event_text_by_id: Dict[str, str]) -> Dict[str, object]:
    return {
        "event_id": event_id,
        "raw_claim": event_text_by_id.get(event_id, ""),
        "claim_type": "",
        "scope_level": "",
        "scope_key": "",
        "canonical_id": "",
    }


def _failure_example(
    *,
    component: str,
    failure_type: str,
    metadata: Dict[str, object],
    event_text_by_id: Dict[str, str],
    event_id: str = "",
    other_event_id: str = "",
    gold: object = None,
    predicted: object = None,
    error: object = None,
) -> Dict[str, object]:
    example = {
        "component": component,
        "failure_type": failure_type,
        "event_id": event_id,
        "other_event_id": other_event_id,
        "events": _involved_events(event_text_by_id, event_id, other_event_id),
    }
    example.update(metadata)
    if gold is not None:
        example["gold"] = gold
    if predicted is not None:
        example["predicted"] = predicted
    if error is not None:
        example["error"] = error
    return example


def _involved_events(
    event_text_by_id: Dict[str, str],
    event_id: str,
    other_event_id: str = "",
) -> Dict[str, str]:
    events = {}
    for current_event_id in (event_id, other_event_id):
        if current_event_id and current_event_id not in events:
            events[current_event_id] = event_text_by_id.get(current_event_id, "")
    return events


def _add_canonicalization_failure_examples(
    failure_examples: List[Dict[str, object]],
    *,
    metadata: Dict[str, object],
    event_text_by_id: Dict[str, str],
    canonical_gold: Dict[str, str],
    canonical_predicted: Dict[str, str],
    gold_claim_payloads_by_item: Dict[str, Dict[str, object]],
    predicted_claim_payloads_by_item: Dict[str, Dict[str, object]],
) -> None:
    evaluable_item_ids = sorted(
        set(canonical_gold).intersection(canonical_predicted)
    )
    for index, first_item_id in enumerate(evaluable_item_ids):
        for second_item_id in evaluable_item_ids[index + 1:]:
            first_event_id = _event_id_from_component_item_id(first_item_id)
            second_event_id = _event_id_from_component_item_id(second_item_id)
            same_gold = canonical_gold[first_item_id] == canonical_gold[second_item_id]
            same_predicted = (
                canonical_predicted[first_item_id]
                == canonical_predicted[second_item_id]
            )
            if same_gold and not same_predicted:
                failure_examples.append(
                    _failure_example(
                        component="canonicalization",
                        failure_type="canonicalization_split",
                        metadata=metadata,
                        event_text_by_id=event_text_by_id,
                        event_id=first_event_id,
                        other_event_id=second_event_id,
                        gold=[
                            gold_claim_payloads_by_item[first_item_id],
                            gold_claim_payloads_by_item[second_item_id],
                        ],
                        predicted=[
                            predicted_claim_payloads_by_item[first_item_id],
                            predicted_claim_payloads_by_item[second_item_id],
                        ],
                    )
                )
            if not same_gold and same_predicted:
                failure_examples.append(
                    _failure_example(
                        component="canonicalization",
                        failure_type="canonicalization_merge",
                        metadata=metadata,
                        event_text_by_id=event_text_by_id,
                        event_id=first_event_id,
                        other_event_id=second_event_id,
                        gold=[
                            gold_claim_payloads_by_item[first_item_id],
                            gold_claim_payloads_by_item[second_item_id],
                        ],
                        predicted=[
                            predicted_claim_payloads_by_item[first_item_id],
                            predicted_claim_payloads_by_item[second_item_id],
                        ],
                    )
                )


def _event_id_from_component_item_id(item_id: str) -> str:
    return item_id.split("::", 1)[1]


def _contradiction_payload(
    metadata: Dict[str, object],
    event_id: str,
    other_event_id: str,
    first_claim: Dict[str, object],
    second_claim: Dict[str, object],
    event_text_by_id: Dict[str, str],
) -> Dict[str, object]:
    return {
        "metadata": dict(metadata),
        "event_id": event_id,
        "other_event_id": other_event_id,
        "events": _involved_events(event_text_by_id, event_id, other_event_id),
        "endpoints": [first_claim, second_claim],
    }


def _failure_example_from_contradiction(
    *,
    failure_type: str,
    component: str,
    payload: Dict[str, object],
) -> Dict[str, object]:
    metadata = payload.get("metadata", {})
    events = payload.get("events", {})
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(events, dict):
        events = {}
    example = _failure_example(
        component=component,
        failure_type=failure_type,
        metadata=metadata,
        event_text_by_id=events,
        event_id=str(payload["event_id"]),
        other_event_id=str(payload["other_event_id"]),
    )
    example["endpoints"] = payload["endpoints"]
    return example


def _prediction_from_candidate(
    event_id: str,
    candidate: CandidateUpdate,
) -> CandidateComponentPrediction:
    return CandidateComponentPrediction(
        event_id=event_id,
        candidate_id=candidate.candidate_id,
        canonical_id=candidate.canonical_id or "",
        claim_type=candidate.claim_type.value,
        scope_level=candidate.scope_level.value,
        scope_key=candidate.scope_key,
        contradicts=list(candidate.contradicts),
        raw_claim=candidate.raw_claim,
        confidence=candidate.strength,
    )


def _prediction_from_mapping(mapping: Dict[str, object]) -> CandidateComponentPrediction:
    if not isinstance(mapping, dict):
        raise ValueError("Each component prediction must be an object")
    return CandidateComponentPrediction(
        event_id=str(mapping.get("event_id") or ""),
        candidate_id=str(mapping.get("candidate_id") or ""),
        canonical_id=str(mapping.get("canonical_id") or ""),
        claim_type=str(mapping.get("claim_type") or ""),
        scope_level=str(mapping.get("scope_level") or ""),
        scope_key=str(mapping.get("scope_key") or ""),
        contradicts=[
            str(value)
            for value in (mapping.get("contradicts") or [])
            if value is not None
        ],
        contradicts_event_ids=[
            str(value)
            for value in (mapping.get("contradicts_event_ids") or [])
            if value is not None
        ],
        raw_claim=str(mapping.get("raw_claim") or ""),
        confidence=_optional_float(mapping.get("confidence")),
    )


def _optional_float(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        raise ValueError("confidence must be numeric or null")


def _gold_candidates_by_event(scenario: Scenario) -> Dict[str, CandidateUpdate]:
    return {
        event.event_id: event.candidate
        for event in scenario.sorted_events()
        if event.kind == EventKind.OBSERVATION and event.candidate is not None
    }


def _candidate_id_to_event_id(scenario: Scenario) -> Dict[str, str]:
    candidate_id_to_event_id: Dict[str, str] = {}
    for event in scenario.sorted_events():
        if event.kind != EventKind.OBSERVATION or event.candidate is None:
            continue
        candidate_id = event.candidate.candidate_id
        if candidate_id in candidate_id_to_event_id:
            raise ValueError(
                "Candidate '{}' appears in multiple observation events in scenario '{}'".format(
                    candidate_id,
                    scenario.scenario_id,
                )
            )
        candidate_id_to_event_id[candidate_id] = event.event_id
    for event in scenario.sorted_events():
        if event.kind != EventKind.OBSERVATION or event.candidate is None:
            continue
        for target_candidate_id in event.candidate.contradicts:
            if target_candidate_id not in candidate_id_to_event_id:
                raise ValueError(
                    "Contradiction target '{}' in scenario '{}' does not resolve to an observation event".format(
                        target_candidate_id,
                        scenario.scenario_id,
                    )
                )
    return candidate_id_to_event_id


def _best_predictions_by_event(
    predictions: List[CandidateComponentPrediction],
    gold_by_event: Dict[str, CandidateUpdate],
) -> _BestPredictionSelection:
    grouped_predictions: Dict[str, List[CandidateComponentPrediction]] = {}
    for prediction in predictions:
        grouped_predictions.setdefault(prediction.event_id, []).append(prediction)

    prediction_by_event: Dict[str, CandidateComponentPrediction] = {}
    duplicate_predictions: List[Tuple[str, CandidateComponentPrediction]] = []
    for event_id, event_predictions in grouped_predictions.items():
        gold = gold_by_event.get(event_id)
        if gold is None:
            selected_index = 0
        else:
            selected_index = max(
                range(len(event_predictions)),
                key=lambda index: _prediction_match_score(event_predictions[index], gold),
            )
        prediction_by_event[event_id] = event_predictions[selected_index]
        for index, prediction in enumerate(event_predictions):
            if index != selected_index:
                duplicate_predictions.append((event_id, prediction))
    return _BestPredictionSelection(
        prediction_by_event=prediction_by_event,
        duplicate_predictions=duplicate_predictions,
        event_prediction_counts=[
            len(event_predictions)
            for event_predictions in grouped_predictions.values()
        ],
    )


def _prediction_match_score(
    prediction: CandidateComponentPrediction,
    gold: CandidateUpdate,
) -> int:
    return sum(
        (
            prediction.canonical_id == gold.canonical_id,
            prediction.claim_type == gold.claim_type.value,
            prediction.scope_level == gold.scope_level.value,
            prediction.scope_key == gold.scope_key,
        )
    )


def _new_counters() -> Dict[str, int]:
    return {
        "candidate_detection_tp": 0,
        "candidate_detection_fp": 0,
        "candidate_detection_fn": 0,
        "extra_same_event_prediction_count": 0,
        "claim_type_correct": 0,
        "claim_type_count": 0,
        "scope_level_correct": 0,
        "scope_level_count": 0,
        "scope_key_correct": 0,
        "scope_key_count": 0,
    }


def _component_item_id(scenario_id: str, event_id: str) -> str:
    return "{}::{}".format(scenario_id, event_id)


def _scoped_canonical_label(scenario_id: str, canonical_id: Optional[str]) -> str:
    return "{}::{}".format(scenario_id, canonical_id or "")


def _contradiction_edge(
    scenario_id: str,
    source_event_id: str,
    target_event_id: str,
) -> Tuple[str, Tuple[str, str]]:
    return (scenario_id, tuple(sorted((source_event_id, target_event_id))))


def _predicted_contradiction_edges_with_payloads(
    scenario_id: str,
    predicted: CandidateComponentPrediction,
    candidate_id_to_event_id: Dict[str, str],
    event_text_by_id: Dict[str, str],
    metadata: Dict[str, object],
) -> Dict[Tuple[str, Tuple[str, str]], Dict[str, object]]:
    if predicted.contradicts_event_ids:
        return {
            _contradiction_edge(scenario_id, predicted.event_id, target_event_id): _contradiction_payload(
                metadata,
                predicted.event_id,
                target_event_id,
                _prediction_claim_payload(predicted),
                _event_only_claim_payload(target_event_id, event_text_by_id),
                event_text_by_id,
            )
            for target_event_id in predicted.contradicts_event_ids
        }

    source_event_id = candidate_id_to_event_id.get(
        predicted.candidate_id,
        "candidate:{}".format(predicted.candidate_id),
    )
    source_payload = _prediction_claim_payload(predicted)
    source_payload["event_id"] = source_event_id
    payloads = {}
    for target_candidate_id in predicted.contradicts:
        # Legacy candidate-id predictions that do not resolve to observation
        # events use a private sentinel namespace, so they cannot match gold
        # event-id edges and are counted as false positives.
        target_event_id = candidate_id_to_event_id.get(
            target_candidate_id,
            "candidate:{}".format(target_candidate_id),
        )
        payloads[
            _contradiction_edge(scenario_id, source_event_id, target_event_id)
        ] = _contradiction_payload(
            metadata,
            source_event_id,
            target_event_id,
            source_payload,
            _event_only_claim_payload(target_event_id, event_text_by_id),
            event_text_by_id,
        )
    return payloads


def _contradiction_applicability(
    gold_contradictions: Set[Tuple[str, Tuple[str, str]]],
    predicted_contradictions: Set[Tuple[str, Tuple[str, str]]],
) -> str:
    if not gold_contradictions and not predicted_contradictions:
        return "not_applicable"
    return "measured"


def _b_cubed(gold_labels: Dict[str, str], predicted_labels: Dict[str, str]) -> Dict[str, Optional[float]]:
    if not gold_labels:
        return {"precision": None, "recall": None, "f1": None, "coverage": None}
    evaluable_item_ids = sorted(set(gold_labels).intersection(predicted_labels))
    coverage = len(evaluable_item_ids) / len(gold_labels)
    if coverage < CANONICALIZATION_COVERAGE_THRESHOLD:
        return {
            "precision": None,
            "recall": None,
            "f1": None,
            "coverage": coverage,
        }
    gold_clusters = _clusters_by_label(gold_labels, evaluable_item_ids)
    predicted_clusters = _clusters_by_label(predicted_labels, evaluable_item_ids)
    precisions = []
    recalls = []
    for item_id in evaluable_item_ids:
        gold_cluster = gold_clusters[gold_labels[item_id]]
        predicted_cluster = predicted_clusters[predicted_labels[item_id]]
        overlap_count = len(gold_cluster.intersection(predicted_cluster))
        precisions.append(overlap_count / len(predicted_cluster))
        recalls.append(overlap_count / len(gold_cluster))
    precision = sum(precisions) / len(precisions)
    recall = sum(recalls) / len(recalls)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
        "coverage": coverage,
    }


def _clusters_by_label(labels: Dict[str, str], item_ids: List[str]) -> Dict[str, Set[str]]:
    clusters = {}
    for item_id in item_ids:
        clusters.setdefault(labels[item_id], set()).add(item_id)
    return clusters


def _limited_failure_examples(
    examples: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], Dict[str, Dict[str, object]]]:
    # TODO: Consider stratifying this cap by scenario before broad noisy sweeps;
    # deterministic sort can overrepresent early scenario ids when failures are abundant.
    sorted_examples = sorted(examples, key=_failure_example_sort_key)
    per_type_limit = int(FAILURE_EXAMPLE_LIMITS["per_type"])
    emitted_counts: Dict[str, int] = {}
    omitted_counts: Dict[str, int] = {}
    limited = []
    for example in sorted_examples:
        failure_type = str(example.get("failure_type", ""))
        emitted_count = emitted_counts.get(failure_type, 0)
        if emitted_count < per_type_limit:
            limited.append(example)
            emitted_counts[failure_type] = emitted_count + 1
        else:
            omitted_counts[failure_type] = omitted_counts.get(failure_type, 0) + 1
    return limited, {
        failure_type: {
            "emitted": emitted_counts.get(failure_type, 0),
            "omitted": omitted,
            "truncated": True,
        }
        for failure_type, omitted in sorted(omitted_counts.items())
    }


def _failure_example_sort_key(example: Dict[str, object]) -> Tuple[str, str, str, str]:
    return (
        str(example.get("failure_type", "")),
        str(example.get("scenario_id", "")),
        str(example.get("event_id", "")),
        str(example.get("other_event_id", "")),
    )


def _accuracy(correct: int, total: int) -> Optional[float]:
    if total == 0:
        return None
    return correct / total


def _safe_divide(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def _percentile(values: List[int], quantile: float) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, math.ceil(quantile * len(sorted_values)) - 1))
    return float(sorted_values[index])


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision == 0.0 or recall == 0.0:
        return 0.0
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _format_metric(value: object) -> str:
    if isinstance(value, (int, float)):
        return "{:.2f}".format(value)
    return "NA"


if __name__ == "__main__":
    raise SystemExit(main())
