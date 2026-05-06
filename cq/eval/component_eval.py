from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from cq.eval.runner import (
    FORCED_CONTRADICTION,
    TEMPLATE_MIXES_BY_FAMILY,
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


@dataclass
class CandidateComponentPrediction:
    event_id: str
    candidate_id: str
    canonical_id: str
    claim_type: str
    scope_level: str
    scope_key: str
    contradicts: List[str] = field(default_factory=list)


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
) -> Dict[str, object]:
    counters = _new_counters()
    canonical_gold: Dict[str, str] = {}
    canonical_predicted: Dict[str, str] = {}
    gold_contradictions = set()
    predicted_contradictions = set()
    scenario_count = 0

    for scenario in scenarios:
        scenario_count += 1
        predictions = predictions_by_scenario.get(scenario.scenario_id, [])
        gold_by_event = _gold_candidates_by_event(scenario)
        prediction_by_event, duplicate_count = _first_predictions_by_event(predictions)
        gold_event_ids = set(gold_by_event)
        predicted_event_ids = set(prediction_by_event)
        true_positive_events = gold_event_ids.intersection(predicted_event_ids)

        counters["candidate_detection_tp"] += len(true_positive_events)
        counters["candidate_detection_fp"] += len(predicted_event_ids - gold_event_ids) + duplicate_count
        counters["candidate_detection_fn"] += len(gold_event_ids - predicted_event_ids)
        counters["claim_type_count"] += len(true_positive_events)
        counters["scope_level_count"] += len(true_positive_events)
        counters["scope_key_count"] += len(true_positive_events)

        for event_id in sorted(true_positive_events):
            gold = gold_by_event[event_id]
            predicted = prediction_by_event[event_id]
            counters["claim_type_correct"] += int(predicted.claim_type == gold.claim_type.value)
            counters["scope_level_correct"] += int(predicted.scope_level == gold.scope_level.value)
            counters["scope_key_correct"] += int(predicted.scope_key == gold.scope_key)

        for event_id, gold in gold_by_event.items():
            item_id = _component_item_id(scenario.scenario_id, event_id)
            canonical_gold[item_id] = _scoped_canonical_label(scenario.scenario_id, gold.canonical_id)
            predicted = prediction_by_event.get(event_id)
            if predicted is not None:
                canonical_predicted[item_id] = _scoped_canonical_label(
                    scenario.scenario_id,
                    predicted.canonical_id,
                )
            for target_id in gold.contradicts:
                gold_contradictions.add(
                    _contradiction_edge(scenario.scenario_id, gold.candidate_id, target_id)
                )

        for predicted in predictions:
            for target_id in predicted.contradicts:
                # Phase 4 extractors must emit candidate ids aligned to scenario gold ids;
                # otherwise contradiction metrics should be replaced with a mapped-id scorer.
                predicted_contradictions.add(
                    _contradiction_edge(scenario.scenario_id, predicted.candidate_id, target_id)
                )

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
    b_cubed = _b_cubed(canonical_gold, canonical_predicted)

    metrics = {
        "scenario_count": scenario_count,
        "candidate_detection_tp": counters["candidate_detection_tp"],
        "candidate_detection_fp": counters["candidate_detection_fp"],
        "candidate_detection_fn": counters["candidate_detection_fn"],
        "candidate_detection_precision": candidate_precision,
        "candidate_detection_recall": candidate_recall,
        "candidate_detection_f1": _f1(candidate_precision, candidate_recall),
        "claim_type_accuracy": _accuracy(
            counters["claim_type_correct"],
            counters["claim_type_count"],
        ),
        "scope_level_accuracy": _accuracy(
            counters["scope_level_correct"],
            counters["scope_level_count"],
        ),
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
        "contradiction_precision": contradiction_precision,
        "contradiction_recall": contradiction_recall,
        "contradiction_f1": _f1(contradiction_precision, contradiction_recall),
    }
    return {
        "metrics": metrics,
        "quality_gates": evaluate_quality_gates(metrics),
    }


def evaluate_quality_gates(metrics: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    gates = {}
    for metric_name, threshold in QUALITY_GATES.items():
        value = metrics.get(metric_name)
        gates[metric_name] = {
            "value": value,
            "threshold": threshold,
            "passed": isinstance(value, (int, float)) and value >= threshold,
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
    mode: Optional[str] = None,
) -> Dict[str, object]:
    scenarios = generate_scenarios(family, scenario_count, template_mix)
    if predictions_by_scenario is None:
        predictions_by_scenario = oracle_predictions_by_scenario(scenarios)
        artifact_mode = mode or "oracle_component_upper_bound"
    else:
        artifact_mode = mode or "component_predictions"
    evaluation = evaluate_component_predictions(scenarios, predictions_by_scenario)
    return {
        "mode": artifact_mode,
        "family": family,
        "template_mix": template_mix,
        "requested_scenario_count": scenario_count,
        "scenario_count": len(scenarios),
        "quality_gate_thresholds": QUALITY_GATES,
        "metrics": evaluation["metrics"],
        "quality_gates": evaluation["quality_gates"],
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate component predictions against scenario oracle labels."
    )
    parser.add_argument("--family", default=FORCED_CONTRADICTION, choices=sorted(TEMPLATE_MIXES_BY_FAMILY))
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
    artifact = build_component_eval_artifact(
        family=args.family,
        scenario_count=args.scenarios,
        template_mix=args.template_mix,
        predictions_by_scenario=predictions_by_scenario,
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
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(jsonable(artifact), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("Wrote {}".format(output_path))
    return 0


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
    )


def _gold_candidates_by_event(scenario: Scenario) -> Dict[str, CandidateUpdate]:
    return {
        event.event_id: event.candidate
        for event in scenario.sorted_events()
        if event.kind == EventKind.OBSERVATION and event.candidate is not None
    }


def _first_predictions_by_event(
    predictions: List[CandidateComponentPrediction],
) -> Tuple[Dict[str, CandidateComponentPrediction], int]:
    prediction_by_event: Dict[str, CandidateComponentPrediction] = {}
    duplicate_count = 0
    for prediction in predictions:
        if prediction.event_id in prediction_by_event:
            duplicate_count += 1
            continue
        prediction_by_event[prediction.event_id] = prediction
    return prediction_by_event, duplicate_count


def _new_counters() -> Dict[str, int]:
    return {
        "candidate_detection_tp": 0,
        "candidate_detection_fp": 0,
        "candidate_detection_fn": 0,
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
    source_candidate_id: str,
    target_candidate_id: str,
) -> Tuple[str, Tuple[str, str]]:
    return (scenario_id, tuple(sorted((source_candidate_id, target_candidate_id))))


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
    precisions = []
    recalls = []
    for item_id in evaluable_item_ids:
        gold_cluster = {
            other_id
            for other_id in evaluable_item_ids
            if gold_labels[other_id] == gold_labels[item_id]
        }
        predicted_cluster = {
            other_id
            for other_id in evaluable_item_ids
            if predicted_labels[other_id] == predicted_labels[item_id]
        }
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


def _accuracy(correct: int, total: int) -> Optional[float]:
    if total == 0:
        return None
    return correct / total


def _safe_divide(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


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
