#!/usr/bin/env python3
"""CI-aware noisy component gate-decision runner.

This script is intentionally separate from run_component_scoring_matrix.py. The
matrix runner broadens diagnostic artifacts and refuses statistical verdicts;
this runner consumes the same extractor/scorer plumbing and emits the explicit
gate artifact that decides whether extracted-candidate policy comparisons stay
locked.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cq.eval.component_eval import (  # noqa: E402
    QUALITY_GATES,
    CandidateComponentPrediction,
    canonical_component_maps,
    evaluate_component_predictions,
    load_predictions_by_scenario,
    load_scenario_errors,
)
from cq.eval.runner import (  # noqa: E402
    FALSE_CORROBORATION,
    FORCED_CONTRADICTION,
    MECHANISM_DIVERSE_HELDOUT,
    MEMORY_POISONING,
    PREFERENCE_DRIFT,
    SCOPE_CONTAMINATION,
    USEFUL_PENDING_MEMORY,
    generate_scenarios,
)
from cq.pipeline.local_extractor import MODEL_MODE, build_extractor_output  # noqa: E402
from cq.schemas.memory import jsonable  # noqa: E402
from cq.schemas.scenario import EventKind, Scenario  # noqa: E402


def _load_matrix_module():
    module_path = REPO_ROOT / "scripts" / "run_component_scoring_matrix.py"
    spec = importlib.util.spec_from_file_location("run_component_scoring_matrix", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


matrix = _load_matrix_module()

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "results"
SUMMARY_PREFIX = "component_gate_decision"
STOP_REPORT_PREFIX = "component_gate_decision_phase_a_stop"
PRIMARY_SCENARIO_COUNT = 60
FROZEN_SENTINEL_SCENARIO_COUNT = 3
TEMPLATE_MIX_HELDOUT = "heldout"
TEMPLATE_MIX_FROZEN = "frozen"
CONFIDENCE_LEVEL = 0.95
WILSON_Z = 1.959963984540054
PRIMARY_GATE_FAMILIES: Tuple[str, ...] = (
    FORCED_CONTRADICTION,
    SCOPE_CONTAMINATION,
    PREFERENCE_DRIFT,
    USEFUL_PENDING_MEMORY,
    FALSE_CORROBORATION,
    MEMORY_POISONING,
)


@dataclass(frozen=True)
class GateRow:
    family: str
    template_mix: str
    scenarios: int
    model: matrix.ModelSpec
    prompt_label: str
    prompt_path: Path
    gate_role: str

    @property
    def artifact_stem(self) -> str:
        return "{}_{}_local_extractor_{}_{}_{}_n{}_{}".format(
            SUMMARY_PREFIX,
            self.family,
            self.model.artifact_label,
            self.prompt_label,
            self.template_mix,
            self.scenarios,
            self.gate_role,
        )

    def as_matrix_row(self) -> matrix.MatrixRow:
        return matrix.MatrixRow(
            self.family,
            self.template_mix,
            self.scenarios,
            self.model,
            self.prompt_label,
            self.prompt_path,
        )


@dataclass(frozen=True)
class GateArtifactPaths:
    predictions: Path
    component_eval: Path


@dataclass(frozen=True)
class GateRowResult:
    row: GateRow
    paths: GateArtifactPaths
    component_artifact: Dict[str, object]
    predictions_by_scenario: Dict[str, List[CandidateComponentPrediction]]
    scenario_errors: Dict[str, object]
    reused: bool


def primary_gate_rows(
    prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[GateRow]:
    return [
        GateRow(
            family=family,
            template_mix=TEMPLATE_MIX_HELDOUT,
            scenarios=PRIMARY_SCENARIO_COUNT,
            model=matrix.QWEN_7B_Q4KM,
            prompt_label=prompt_label,
            prompt_path=prompt_path,
            gate_role="primary_floor",
        )
        for family in PRIMARY_GATE_FAMILIES
    ]


def headroom_gate_rows(
    prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[GateRow]:
    return [
        GateRow(
            family=family,
            template_mix=TEMPLATE_MIX_HELDOUT,
            scenarios=PRIMARY_SCENARIO_COUNT,
            model=matrix.QWEN_32B_Q4KM,
            prompt_label=prompt_label,
            prompt_path=prompt_path,
            gate_role="descriptive_headroom",
        )
        for family in PRIMARY_GATE_FAMILIES
    ]


def frozen_sentinel_rows(
    prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[GateRow]:
    return [
        GateRow(
            family=MECHANISM_DIVERSE_HELDOUT,
            template_mix=TEMPLATE_MIX_FROZEN,
            scenarios=FROZEN_SENTINEL_SCENARIO_COUNT,
            model=matrix.QWEN_7B_Q4KM,
            prompt_label=prompt_label,
            prompt_path=prompt_path,
            gate_role="frozen_sentinel_floor",
        )
    ]


def gate_artifact_paths(row: GateRow, output_dir: Path) -> GateArtifactPaths:
    return GateArtifactPaths(
        predictions=output_dir / "{}_predictions.json".format(row.artifact_stem),
        component_eval=output_dir / "{}_component_eval.json".format(row.artifact_stem),
    )


def run_or_reuse_gate_row(
    row: GateRow,
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    force: bool = False,
) -> GateRowResult:
    paths = gate_artifact_paths(row, output_dir)
    if not force and _paths_exist(paths) and cached_gate_artifacts_match_row(
        row,
        paths,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
    ):
        return _gate_result_from_paths(row, paths, reused=True)
    return run_gate_row(
        row,
        output_dir=output_dir,
        model_command=model_command,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
    )


def run_gate_row(
    row: GateRow,
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> GateRowResult:
    paths = gate_artifact_paths(row, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    extractor_output = build_extractor_output(
        family=row.family,
        scenario_count=row.scenarios,
        template_mix=row.template_mix,
        mode=MODEL_MODE,
        model_command=model_command,
        model_id=row.model.model_id,
        prompt_template_path=str(row.prompt_path),
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
    )
    _write_json(paths.predictions, extractor_output)
    predictions = load_predictions_by_scenario(paths.predictions)
    scenario_errors = load_scenario_errors(paths.predictions)
    component_artifact = _build_row_component_artifact(row, predictions, scenario_errors)
    _write_json(paths.component_eval, component_artifact)
    return GateRowResult(
        row=row,
        paths=paths,
        component_artifact=component_artifact,
        predictions_by_scenario=predictions,
        scenario_errors=scenario_errors,
        reused=False,
    )


def _gate_result_from_paths(
    row: GateRow,
    paths: GateArtifactPaths,
    *,
    reused: bool,
) -> GateRowResult:
    predictions = load_predictions_by_scenario(paths.predictions)
    scenario_errors = load_scenario_errors(paths.predictions)
    return GateRowResult(
        row=row,
        paths=paths,
        component_artifact=_read_json(paths.component_eval),
        predictions_by_scenario=predictions,
        scenario_errors=scenario_errors,
        reused=reused,
    )


def cached_gate_artifacts_match_row(
    row: GateRow,
    paths: GateArtifactPaths,
    *,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> bool:
    if not _paths_exist(paths):
        return False
    matrix_paths = matrix.ArtifactPaths(
        predictions=paths.predictions,
        component_eval=paths.component_eval,
    )
    try:
        mismatches = matrix.cached_artifact_provenance_mismatches(
            row.as_matrix_row(),
            matrix_paths,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return not mismatches


def _build_row_component_artifact(
    row: GateRow,
    predictions_by_scenario: Dict[str, List[CandidateComponentPrediction]],
    scenario_errors: Dict[str, object],
) -> Dict[str, object]:
    scenarios = generate_scenarios(row.family, row.scenarios, row.template_mix)
    evaluation = evaluate_component_predictions(
        scenarios,
        predictions_by_scenario,
        scenario_errors=scenario_errors,
    )
    return {
        "mode": "component_gate_decision_row",
        "family": row.family,
        "template_mix": row.template_mix,
        "requested_scenario_count": row.scenarios,
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


def run_gate_decision(
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    general_prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    general_prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
    include_headroom: bool = False,
    include_frozen_sentinel: bool = False,
    force: bool = False,
) -> Path:
    matrix.run_prompt_regression(
        output_dir=output_dir,
        model_command=model_command,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        general_prompt_path=general_prompt_path,
        general_prompt_label=general_prompt_label,
        force=force,
    )
    matrix.run_determinism_check(
        model_command=model_command,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        general_prompt_path=general_prompt_path,
        general_prompt_label=general_prompt_label,
    )
    primary_results = [
        run_or_reuse_gate_row(
            row,
            output_dir=output_dir,
            model_command=model_command,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
            force=force,
        )
        for row in primary_gate_rows(general_prompt_path, general_prompt_label)
    ]
    headroom_results = (
        [
            run_or_reuse_gate_row(
                row,
                output_dir=output_dir,
                model_command=model_command,
                decoding_json=decoding_json,
                per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                force=force,
            )
            for row in headroom_gate_rows(general_prompt_path, general_prompt_label)
        ]
        if include_headroom
        else []
    )
    frozen_results = (
        [
            run_or_reuse_gate_row(
                row,
                output_dir=output_dir,
                model_command=model_command,
                decoding_json=decoding_json,
                per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                force=force,
            )
            for row in frozen_sentinel_rows(general_prompt_path, general_prompt_label)
        ]
        if include_frozen_sentinel
        else []
    )
    path = gate_summary_path(output_dir, general_prompt_label=general_prompt_label)
    # These helpers raise StopConditionError on failure; reaching the summary write means both guards passed.
    _write_json(
        path,
        gate_summary_payload(
            primary_results=primary_results,
            headroom_results=headroom_results,
            frozen_sentinel_results=frozen_results,
            general_prompt_path=general_prompt_path,
            general_prompt_label=general_prompt_label,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
            phase_a_passed=True,
            determinism_passed=True,
        ),
    )
    return path


def gate_summary_path(output_dir: Path, *, general_prompt_label: str) -> Path:
    return output_dir / "{}_{}_summary.json".format(
        SUMMARY_PREFIX,
        matrix._slug_for_filename(general_prompt_label),
    )


def gate_summary_payload(
    *,
    primary_results: Sequence[GateRowResult],
    headroom_results: Sequence[GateRowResult],
    frozen_sentinel_results: Sequence[GateRowResult],
    general_prompt_path: Path,
    general_prompt_label: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    phase_a_passed: bool,
    determinism_passed: bool,
) -> Dict[str, object]:
    aggregate = aggregate_gate_evaluation(primary_results)
    row_summaries = [row_summary(result) for result in primary_results]
    headroom_summaries = [row_summary(result) for result in headroom_results]
    frozen_summaries = [row_summary(result) for result in frozen_sentinel_results]
    primary_observed_failures = _observed_gate_failures(primary_results)
    frozen_failures = _observed_gate_failures(frozen_sentinel_results)
    aggregate_observed_failures = _aggregate_observed_gate_failures(aggregate)
    aggregate_ci_failures = [
        {"metric": metric_name, "gate": gate}
        for metric_name, gate in aggregate["ci_supported_gates"].items()
        if gate.get("status") == "measured" and not gate.get("passed")
    ]
    scenario_error_count = sum(
        int(result.component_artifact.get("scenario_error_count") or 0)
        for result in primary_results
    )
    blockers = []
    if not phase_a_passed:
        blockers.append({"type": "phase_a_failed"})
    if not determinism_passed:
        blockers.append({"type": "determinism_failed"})
    if scenario_error_count:
        blockers.append(
            {
                "type": "primary_scenario_errors",
                "scenario_error_count": scenario_error_count,
            }
        )
    for failure in primary_observed_failures:
        blockers.append({"type": "per_family_observed_gate_failed", **failure})
    for failure in aggregate_observed_failures:
        blockers.append({"type": "aggregate_observed_gate_failed", **failure})
    for failure in aggregate_ci_failures:
        gate = failure["gate"]
        blockers.append(
            {
                "type": "aggregate_ci_gate_failed",
                "metric": failure["metric"],
                "threshold": gate.get("threshold"),
                "value": gate.get("value"),
            }
        )
    for failure in frozen_failures:
        blockers.append({"type": "frozen_sentinel_observed_gate_failed", **failure})
    policy_unlocked = not blockers

    return {
        "mode": "ci_aware_component_gate_decision",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "phase": "phase3_component_gate_decision",
        "general_prompt_path": str(general_prompt_path),
        "general_prompt_label": general_prompt_label,
        "general_prompt_sha256": matrix.prompt_template_sha256(general_prompt_path),
        "decoding_params": _parse_decoding_json(decoding_json),
        "per_scenario_timeout_seconds": per_scenario_timeout_seconds,
        "policy_comparison_unlocked": policy_unlocked,
        "component_risk_notes": [
            "The targeted general_v2 prompt/schema diagnostic branch failed acceptance and is not the gate default.",
            "Remaining 7B empty-scope-key validation errors from that branch are treated as component-quality risk.",
        ],
        "phase_a_contract": phase_a_contract_payload(
            phase_a_passed,
            general_prompt_label=general_prompt_label,
        ),
        "determinism_contract": determinism_contract_payload(determinism_passed),
        "generation_contract": generation_contract_payload(),
        "statistical_contract": statistical_contract_payload(),
        "unlock_rule": {
            "primary_model_role": "primary_floor",
            "primary_model_id": matrix.QWEN_7B_Q4KM.model_id,
            "requires_phase_a_pass": True,
            "requires_determinism_pass": True,
            "requires_primary_zero_scenario_errors": True,
            "requires_all_aggregate_ci_supported_gates": True,
            "requires_all_per_family_observed_gates": True,
            "requires_frozen_sentinel_observed_gates_if_included": True,
            "headroom_can_unlock_policy_comparison": False,
        },
        "unlock_checks": {
            "phase_a_passed": phase_a_passed,
            "determinism_passed": determinism_passed,
            "primary_scenario_error_count": scenario_error_count,
            "primary_observed_gate_failure_count": len(primary_observed_failures),
            "aggregate_observed_gate_failure_count": len(aggregate_observed_failures),
            "aggregate_ci_gate_failure_count": len(
                [
                    blocker
                    for blocker in blockers
                    if blocker["type"] == "aggregate_ci_gate_failed"
                ]
            ),
            "frozen_sentinel_included": bool(frozen_sentinel_results),
            "frozen_sentinel_observed_gate_failure_count": len(frozen_failures),
            "policy_comparison_unlocked": policy_unlocked,
        },
        "blockers": blockers,
        "aggregate_primary": aggregate,
        "rows": row_summaries,
        "headroom_rows": headroom_summaries,
        "frozen_sentinel_rows": frozen_summaries,
    }


def aggregate_gate_evaluation(results: Sequence[GateRowResult]) -> Dict[str, object]:
    scenarios, predictions, scenario_errors = _combined_inputs(results)
    evaluation = evaluate_component_predictions(
        scenarios,
        predictions,
        scenario_errors=scenario_errors,
    )
    metrics = evaluation["metrics"]
    canonical_pairwise = pairwise_canonicalization_counts(
        scenarios,
        predictions,
        scenario_errors,
    )
    ci_supported_gates = ci_supported_gates_payload(metrics, canonical_pairwise)
    return {
        "scenario_count": len(scenarios),
        "scenario_error_count": len(scenario_errors),
        "metrics_observed": metrics,
        "canonicalization_b_cubed_f1_interval_policy": {
            "value": metrics.get("canonicalization_b_cubed_f1"),
            "threshold": QUALITY_GATES["canonicalization_b_cubed_f1"],
            "passed": _metric_passed(
                metrics.get("canonicalization_b_cubed_f1"),
                QUALITY_GATES["canonicalization_b_cubed_f1"],
            ),
            "status": "observed_only",
            "reason": (
                "Wilson intervals are not applied to B-cubed F1; both observed aggregate "
                "B-cubed F1 and the pairwise CI-supported proxy must pass."
            ),
        },
        "denominators": denominator_summary(metrics, canonical_pairwise),
        "expected_denominators_current_generator": expected_denominators_payload(
            primary_gate_rows()
        ),
        "ci_supported_gates": ci_supported_gates,
        "failure_examples": evaluation["failure_examples"],
        "failure_example_count": evaluation["failure_example_count"],
    }


def ci_supported_gates_payload(
    metrics: Mapping[str, object],
    canonical_pairwise: Mapping[str, int],
) -> Dict[str, object]:
    candidate = f1_composite_gate(
        metric_name="candidate_detection_f1",
        threshold=QUALITY_GATES["candidate_detection_f1"],
        precision_successes=_int_metric(metrics, "candidate_detection_tp"),
        precision_total=_int_metric(metrics, "candidate_detection_tp")
        + _int_metric(metrics, "candidate_detection_fp"),
        recall_successes=_int_metric(metrics, "candidate_detection_tp"),
        recall_total=_int_metric(metrics, "candidate_detection_tp")
        + _int_metric(metrics, "candidate_detection_fn"),
    )
    claim_type = ratio_gate(
        metric_name="claim_type_accuracy",
        successes=_int_metric(metrics, "claim_type_correct"),
        total=_int_metric(metrics, "claim_type_count"),
        threshold=QUALITY_GATES["claim_type_accuracy"],
    )
    scope_level = ratio_gate(
        metric_name="scope_level_accuracy",
        successes=_int_metric(metrics, "scope_level_correct"),
        total=_int_metric(metrics, "scope_level_count"),
        threshold=QUALITY_GATES["scope_level_accuracy"],
    )
    scope_key = ratio_gate(
        metric_name="scope_key_accuracy",
        successes=_int_metric(metrics, "scope_key_correct"),
        total=_int_metric(metrics, "scope_key_count"),
        threshold=QUALITY_GATES["scope_key_accuracy"],
    )
    canonical = f1_composite_gate(
        metric_name="canonicalization_pairwise_f1",
        threshold=QUALITY_GATES["canonicalization_b_cubed_f1"],
        precision_successes=int(canonical_pairwise["true_positive_pair_count"]),
        precision_total=int(canonical_pairwise["predicted_positive_pair_count"]),
        recall_successes=int(canonical_pairwise["true_positive_pair_count"]),
        recall_total=int(canonical_pairwise["gold_positive_pair_count"]),
        supports_quality_gate="canonicalization_b_cubed_f1",
        threshold_note=(
            "Proxy threshold: this reuses canonicalization_b_cubed_f1's threshold without a "
            "separate pairwise calibration artifact."
        ),
    )
    contradiction_precision = ratio_gate(
        metric_name="contradiction_precision",
        successes=_int_metric(metrics, "contradiction_tp"),
        total=_int_metric(metrics, "contradiction_tp") + _int_metric(metrics, "contradiction_fp"),
        threshold=QUALITY_GATES["contradiction_precision"],
    )
    contradiction_recall = ratio_gate(
        metric_name="contradiction_recall",
        successes=_int_metric(metrics, "contradiction_tp"),
        total=_int_metric(metrics, "contradiction_tp") + _int_metric(metrics, "contradiction_fn"),
        threshold=QUALITY_GATES["contradiction_recall"],
    )
    contradiction_f1 = f1_composite_gate(
        metric_name="contradiction_f1",
        threshold=QUALITY_GATES["contradiction_f1"],
        precision_successes=_int_metric(metrics, "contradiction_tp"),
        precision_total=_int_metric(metrics, "contradiction_tp") + _int_metric(metrics, "contradiction_fp"),
        recall_successes=_int_metric(metrics, "contradiction_tp"),
        recall_total=_int_metric(metrics, "contradiction_tp") + _int_metric(metrics, "contradiction_fn"),
    )
    if metrics.get("contradiction_applicability") == "not_applicable":
        for gate in (contradiction_precision, contradiction_recall, contradiction_f1):
            gate.update({"status": "not_applicable", "passed": True})
    return {
        "candidate_detection_f1": candidate,
        "claim_type_accuracy": claim_type,
        "scope_level_accuracy": scope_level,
        "scope_key_accuracy": scope_key,
        "canonicalization_pairwise_f1": canonical,
        "contradiction_f1": contradiction_f1,
        "contradiction_precision": contradiction_precision,
        "contradiction_recall": contradiction_recall,
    }


def ratio_gate(
    *,
    metric_name: str,
    successes: int,
    total: int,
    threshold: float,
) -> Dict[str, object]:
    observed = _safe_divide(successes, total)
    needed = minimum_successes_for_wilson_threshold(total, threshold)
    if total <= 0:
        return {
            "metric": metric_name,
            "status": "no_data",
            "passed": False,
            "value": None,
            "threshold": threshold,
            "successes": successes,
            "total": total,
            "interval_method": "wilson_lower_bound_event_assumption",
            "minimum_successes_for_threshold": None,
            "minimum_observed_rate_for_threshold": None,
        }
    lower_bound = wilson_lower_bound(successes, total)
    return {
        "metric": metric_name,
        "status": "measured",
        "passed": lower_bound >= threshold,
        "value": observed,
        "threshold": threshold,
        "successes": successes,
        "total": total,
        "wilson_lower_bound_event_assumption": lower_bound,
        "interval_method": "wilson_lower_bound_event_assumption",
        "minimum_successes_for_threshold": needed,
        "minimum_observed_rate_for_threshold": _safe_divide(needed, total)
        if needed is not None
        else None,
    }


def f1_composite_gate(
    *,
    metric_name: str,
    threshold: float,
    precision_successes: int,
    precision_total: int,
    recall_successes: int,
    recall_total: int,
    supports_quality_gate: Optional[str] = None,
    threshold_note: Optional[str] = None,
) -> Dict[str, object]:
    precision_gate = ratio_gate(
        metric_name="{}_precision_support".format(metric_name),
        successes=precision_successes,
        total=precision_total,
        threshold=threshold,
    )
    recall_gate = ratio_gate(
        metric_name="{}_recall_support".format(metric_name),
        successes=recall_successes,
        total=recall_total,
        threshold=threshold,
    )
    observed_precision = precision_gate["value"]
    observed_recall = recall_gate["value"]
    observed = _f1(observed_precision, observed_recall)
    precision_lb = precision_gate.get("wilson_lower_bound_event_assumption")
    recall_lb = recall_gate.get("wilson_lower_bound_event_assumption")
    composite = _f1(precision_lb, recall_lb)
    status = "measured" if composite is not None else "no_data"
    payload = {
        "metric": metric_name,
        "status": status,
        "passed": bool(composite is not None and composite >= threshold),
        "value": observed,
        "threshold": threshold,
        "f1_conservative_composite_from_wilson_pr": composite,
        "interval_method": "conservative_composite_from_wilson_precision_recall",
        "coverage_note": "This is not a 95% lower bound on F1; it is a conservative composite from separate Wilson precision and recall lower bounds.",
        "precision_support": precision_gate,
        "recall_support": recall_gate,
        "supports_quality_gate": supports_quality_gate,
    }
    if threshold_note is not None:
        payload["threshold_note"] = threshold_note
    return payload


def pairwise_canonicalization_counts(
    scenarios: Sequence[Scenario],
    predictions_by_scenario: Dict[str, List[CandidateComponentPrediction]],
    scenario_errors: Dict[str, object],
) -> Dict[str, int]:
    gold, predicted = canonical_component_maps(
        scenarios,
        predictions_by_scenario,
        scenario_errors=scenario_errors,
    )
    item_ids_by_scenario: Dict[str, List[str]] = {}
    for item_id in gold:
        scenario_id = item_id.split("::", 1)[0]
        item_ids_by_scenario.setdefault(scenario_id, []).append(item_id)

    true_positive = 0
    false_positive = 0
    false_negative = 0
    gold_positive = 0
    predicted_positive = 0
    total_pairs = 0
    for item_ids in item_ids_by_scenario.values():
        sorted_item_ids = sorted(item_ids)
        for index, left in enumerate(sorted_item_ids):
            for right in sorted_item_ids[index + 1 :]:
                total_pairs += 1
                gold_same = gold[left] == gold[right]
                predicted_same = (
                    left in predicted
                    and right in predicted
                    and predicted[left] == predicted[right]
                )
                gold_positive += int(gold_same)
                predicted_positive += int(predicted_same)
                true_positive += int(gold_same and predicted_same)
                false_positive += int((not gold_same) and predicted_same)
                false_negative += int(gold_same and not predicted_same)
    return {
        "total_pair_count": total_pairs,
        "gold_positive_pair_count": gold_positive,
        "predicted_positive_pair_count": predicted_positive,
        "true_positive_pair_count": true_positive,
        "false_positive_pair_count": false_positive,
        "false_negative_pair_count": false_negative,
    }


def denominator_summary(
    metrics: Mapping[str, object],
    canonical_pairwise: Mapping[str, int],
) -> Dict[str, object]:
    return {
        "candidate_event_count": _int_metric(metrics, "candidate_detection_tp")
        + _int_metric(metrics, "candidate_detection_fn"),
        "candidate_precision_denominator": _int_metric(metrics, "candidate_detection_tp")
        + _int_metric(metrics, "candidate_detection_fp"),
        "claim_type_count": _int_metric(metrics, "claim_type_count"),
        "scope_level_count": _int_metric(metrics, "scope_level_count"),
        "scope_key_count": _int_metric(metrics, "scope_key_count"),
        "contradiction_gold_edge_count": _int_metric(metrics, "contradiction_tp")
        + _int_metric(metrics, "contradiction_fn"),
        "contradiction_predicted_edge_count": _int_metric(metrics, "contradiction_tp")
        + _int_metric(metrics, "contradiction_fp"),
        "canonicalization_pairwise": dict(canonical_pairwise),
    }


def expected_denominators_payload(rows: Sequence[GateRow]) -> Dict[str, object]:
    by_family = []
    total_candidate = 0
    total_contradictions = 0
    total_positive_pairs = 0
    for row in rows:
        denominators = expected_denominators_for_row(row)
        total_candidate += denominators["candidate_event_count"]
        total_contradictions += denominators["undirected_contradiction_edge_count"]
        total_positive_pairs += denominators["positive_canonical_pair_count"]
        by_family.append(
            {
                "family": row.family,
                "template_mix": row.template_mix,
                "scenarios": row.scenarios,
                **denominators,
            }
        )
    return {
        "generation_contract": 'generate_scenarios(family, 60, "heldout")',
        "by_family": by_family,
        "aggregate": {
            "candidate_event_count": total_candidate,
            "undirected_contradiction_edge_count": total_contradictions,
            "positive_canonical_pair_count": total_positive_pairs,
        },
    }


def expected_denominators_for_row(row: GateRow) -> Dict[str, int]:
    scenarios = generate_scenarios(row.family, row.scenarios, row.template_mix)
    candidate_events = 0
    contradiction_edges = set()
    positive_pairs = 0
    total_pairs = 0
    for scenario in scenarios:
        events = [
            event
            for event in scenario.sorted_events()
            if event.kind == EventKind.OBSERVATION and event.candidate is not None
        ]
        candidate_events += len(events)
        event_id_by_candidate_id = {
            event.candidate.candidate_id: event.event_id
            for event in events
            if event.candidate is not None
        }
        for event in events:
            for target_candidate_id in event.candidate.contradicts:
                target_event_id = event_id_by_candidate_id.get(target_candidate_id)
                if target_event_id:
                    contradiction_edges.add(
                        (
                            scenario.scenario_id,
                            tuple(sorted((event.event_id, target_event_id))),
                        )
                    )
        for index, left in enumerate(events):
            for right in events[index + 1 :]:
                total_pairs += 1
                if left.candidate.canonical_id == right.candidate.canonical_id:
                    positive_pairs += 1
    return {
        "candidate_event_count": candidate_events,
        "undirected_contradiction_edge_count": len(contradiction_edges),
        "positive_canonical_pair_count": positive_pairs,
        "total_canonical_pair_count": total_pairs,
    }


def row_summary(result: GateRowResult) -> Dict[str, object]:
    failures = []
    for metric_name, gate in _quality_gates(result.component_artifact).items():
        if not gate.get("passed"):
            failures.append(
                {
                    "metric": metric_name,
                    "status": gate.get("status"),
                    "value": gate.get("value"),
                    "threshold": gate.get("threshold"),
                }
            )
    return {
        "family": result.row.family,
        "template_mix": result.row.template_mix,
        "scenarios": result.row.scenarios,
        "model_id": result.row.model.model_id,
        "model_role": result.row.model.role,
        "gate_role": result.row.gate_role,
        "prompt_label": result.row.prompt_label,
        "reused": result.reused,
        "paths": {
            "predictions": str(result.paths.predictions),
            "component_eval": str(result.paths.component_eval),
        },
        "expected_denominators_current_generator": expected_denominators_for_row(result.row),
        "scenario_error_count": int(result.component_artifact.get("scenario_error_count") or 0),
        "observed_quality_gate_failures": failures,
        "metrics": result.component_artifact.get("metrics", {}),
        "quality_gates": result.component_artifact.get("quality_gates", {}),
        "failure_examples": result.component_artifact.get("failure_examples", []),
        "failure_example_count": int(result.component_artifact.get("failure_example_count") or 0),
    }


def dry_run_plan(
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    general_prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    general_prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
    include_headroom: bool = False,
    include_frozen_sentinel: bool = False,
) -> Dict[str, object]:
    rows = primary_gate_rows(general_prompt_path, general_prompt_label)
    if include_headroom:
        rows.extend(headroom_gate_rows(general_prompt_path, general_prompt_label))
    if include_frozen_sentinel:
        rows.extend(frozen_sentinel_rows(general_prompt_path, general_prompt_label))
    return {
        "mode": "dry_run",
        "phase": "ci_aware_component_gate_decision",
        "general_prompt_path": str(general_prompt_path),
        "general_prompt_label": general_prompt_label,
        "policy_comparison_unlocked": "not_evaluated",
        "phase_a_contract": phase_a_contract_payload(
            False,
            general_prompt_label=general_prompt_label,
        )["contract"],
        "determinism_contract": determinism_contract_payload(False)["contract"],
        "generation_contract": generation_contract_payload(),
        "statistical_contract": statistical_contract_payload(),
        "expected_denominators_current_generator": expected_denominators_payload(
            primary_gate_rows(general_prompt_path, general_prompt_label)
        ),
        "rows": [
            {
                "family": row.family,
                "template_mix": row.template_mix,
                "scenarios": row.scenarios,
                "model_id": row.model.model_id,
                "model_role": row.model.role,
                "gate_role": row.gate_role,
                "prompt_label": row.prompt_label,
                "paths": {
                    "predictions": str(gate_artifact_paths(row, output_dir).predictions),
                    "component_eval": str(gate_artifact_paths(row, output_dir).component_eval),
                },
                "expected_denominators_current_generator": expected_denominators_for_row(row),
                "commands": equivalent_commands(
                    row,
                    output_dir=output_dir,
                    model_command=model_command,
                    decoding_json=decoding_json,
                    per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                ),
            }
            for row in rows
        ],
    }


def equivalent_commands(
    row: GateRow,
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> Dict[str, str]:
    paths = gate_artifact_paths(row, output_dir)
    extract = [
        sys.executable,
        "-m",
        "cq.pipeline.local_extractor",
        "--family",
        row.family,
        "--scenarios",
        str(row.scenarios),
        "--template-mix",
        row.template_mix,
        "--mode",
        MODEL_MODE,
        "--model-command",
        model_command,
        "--model-id",
        row.model.model_id,
        "--prompt-template-path",
        str(row.prompt_path),
        "--decoding-json",
        decoding_json,
        "--per-scenario-timeout-seconds",
        str(per_scenario_timeout_seconds),
        "--output-json",
        str(paths.predictions),
    ]
    score = [
        sys.executable,
        "-m",
        "cq.eval.component_eval",
        "--family",
        row.family,
        "--scenarios",
        str(row.scenarios),
        "--template-mix",
        row.template_mix,
        "--predictions-json",
        str(paths.predictions),
        "--output-json",
        str(paths.component_eval),
    ]
    return {"extract": shlex.join(extract), "score": shlex.join(score)}


def phase_a_contract_payload(
    passed: bool,
    *,
    general_prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
) -> Dict[str, object]:
    return {
        "passed": passed,
        "contract": {
            "source": "scripts/run_component_scoring_matrix.py::run_prompt_regression",
            "models": [
                matrix.QWEN_7B_Q4KM.model_id,
                matrix.QWEN_32B_Q4KM.model_id,
            ],
            "family": FORCED_CONTRADICTION,
            "template_mix": "mixed",
            "scenarios": 6,
            "baseline_prompt_label": "forced_v1",
            "general_prompt_label": general_prompt_label,
            "blocks": [
                "measured metric regression versus forced_v1",
                "metric becoming undefined when baseline was numeric",
                "new scenario errors",
                "correct-to-incorrect per-scenario flip",
            ],
        },
    }


def determinism_contract_payload(passed: bool) -> Dict[str, object]:
    return {
        "passed": passed,
        "contract": {
            "source": "scripts/run_component_scoring_matrix.py::run_determinism_check",
            "model_id": matrix.QWEN_7B_Q4KM.model_id,
            "family": FORCED_CONTRADICTION,
            "template_mix": "mixed",
            "scenarios": 6,
            "comparison": 'json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")',
            "array_order": "preserved",
            "same_seed_and_decoding_required": True,
            "scope_note": (
                "This sentinel checks the fixed 6-scenario forced-contradiction prompt-regression row; "
                "primary held-out gate rows are not rerun for determinism."
            ),
        },
    }


def generation_contract_payload() -> Dict[str, object]:
    return {
        "primary_rows": 'generate_scenarios(family, 60, "heldout")',
        "frozen_sentinel": 'generate_scenarios("mechanism_diverse_heldout", 3, "frozen") when included',
        "dependence_warning": (
            "The 60-per-family rows are deterministic template-rotation variants over existing "
            "held-out templates and entity/value pools, not independent new mechanisms. Wilson "
            "intervals are decision aids under an event-level assumption and may be optimistic "
            "under template-correlated errors."
        ),
    }


def statistical_contract_payload() -> Dict[str, object]:
    return {
        "confidence_level": CONFIDENCE_LEVEL,
        "binomial_interval_field": "wilson_lower_bound_event_assumption",
        "f1_field": "f1_conservative_composite_from_wilson_pr",
        "f1_warning": "The F1 field is not a 95% lower bound on F1.",
        "canonicalization_b_cubed_f1": {
            "status": "observed_only",
            "unlock_rule": "Aggregate observed B-cubed F1 must clear its threshold.",
            "reason": "Wilson intervals do not apply to B-cubed F1.",
        },
        "canonicalization_ci_gate": "canonicalization_pairwise_f1",
        "canonicalization_pairwise_threshold_note": (
            "Pairwise F1 is a CI-supported proxy for canonicalization_b_cubed_f1 and currently "
            "uses the same 0.65 threshold without separate oracle-artifact calibration; it cannot "
            "unlock canonicalization unless observed aggregate B-cubed F1 also clears 0.65."
        ),
        "per_family_contradiction_ci_policy": (
            "Reported for diagnostics only; per-family edge counts are small, so per-family "
            "contradiction CIs do not unlock policy comparisons. Per-family observed gate "
            "failures still block unlock."
        ),
    }


def _observed_gate_failures(results: Sequence[GateRowResult]) -> List[Dict[str, object]]:
    failures = []
    for result in results:
        for metric_name, gate in _quality_gates(result.component_artifact).items():
            if not gate.get("passed"):
                failures.append(
                    {
                        "family": result.row.family,
                        "template_mix": result.row.template_mix,
                        "model_id": result.row.model.model_id,
                        "metric": metric_name,
                        "status": gate.get("status"),
                        "value": gate.get("value"),
                        "threshold": gate.get("threshold"),
                    }
                )
    return failures


def _aggregate_observed_gate_failures(aggregate: Mapping[str, object]) -> List[Dict[str, object]]:
    policy = aggregate.get("canonicalization_b_cubed_f1_interval_policy")
    if not isinstance(policy, dict) or policy.get("passed"):
        return []
    return [
        {
            "metric": "canonicalization_b_cubed_f1",
            "status": policy.get("status"),
            "value": policy.get("value"),
            "threshold": policy.get("threshold"),
        }
    ]


def _combined_inputs(
    results: Sequence[GateRowResult],
) -> Tuple[List[Scenario], Dict[str, List[CandidateComponentPrediction]], Dict[str, object]]:
    scenarios: List[Scenario] = []
    predictions: Dict[str, List[CandidateComponentPrediction]] = {}
    scenario_errors: Dict[str, object] = {}
    for result in results:
        scenarios.extend(
            generate_scenarios(result.row.family, result.row.scenarios, result.row.template_mix)
        )
        predictions.update(result.predictions_by_scenario)
        scenario_errors.update(result.scenario_errors)
    return scenarios, predictions, scenario_errors


def wilson_lower_bound(successes: int, total: int, z: float = WILSON_Z) -> Optional[float]:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = proportion + z * z / (2 * total)
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return (center - margin) / denominator


def minimum_successes_for_wilson_threshold(total: int, threshold: float) -> Optional[int]:
    if total <= 0:
        return None
    for successes in range(total + 1):
        lower_bound = wilson_lower_bound(successes, total)
        if lower_bound is not None and lower_bound >= threshold:
            return successes
    return None


def _f1(precision: Optional[float], recall: Optional[float]) -> Optional[float]:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _safe_divide(numerator: Optional[int], denominator: Optional[int]) -> Optional[float]:
    if denominator is None or denominator == 0 or numerator is None:
        return None
    return numerator / denominator


def _metric_passed(value: object, threshold: float) -> bool:
    return isinstance(value, (int, float)) and value >= threshold


def _int_metric(metrics: Mapping[str, object], key: str) -> int:
    value = metrics.get(key)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def _quality_gates(component_artifact: Mapping[str, object]) -> Dict[str, Dict[str, object]]:
    gates = component_artifact.get("quality_gates")
    if not isinstance(gates, dict):
        return {}
    return {
        str(name): gate
        for name, gate in gates.items()
        if isinstance(gate, dict)
    }


def _paths_exist(paths: GateArtifactPaths) -> bool:
    return paths.predictions.exists() and paths.component_eval.exists()


def _read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_decoding_json(decoding_json: str) -> Dict[str, object]:
    payload = json.loads(decoding_json)
    if not isinstance(payload, dict):
        raise ValueError("decoding JSON must be an object")
    return payload


def write_stop_report(output_dir: Path, error: matrix.StopConditionError) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "{}_{}.json".format(
        STOP_REPORT_PREFIX,
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
    )
    _write_json(
        path,
        {
            "mode": "ci_aware_component_gate_decision_stop",
            "reason": error.reason,
            "details": error.details,
            "policy_comparison_unlocked": False,
        },
    )
    return path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-command", default=matrix.DEFAULT_MODEL_COMMAND)
    parser.add_argument("--decoding-json", default=matrix.DEFAULT_DECODING_JSON)
    parser.add_argument(
        "--per-scenario-timeout-seconds",
        type=float,
        default=matrix.DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--general-prompt-path", type=Path, default=matrix.GENERAL_PROMPT_PATH)
    parser.add_argument("--general-prompt-label", default=matrix.DEFAULT_GENERAL_PROMPT_LABEL)
    parser.add_argument("--include-headroom", action="store_true")
    parser.add_argument("--include-frozen-sentinel", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        print(
            json.dumps(
                dry_run_plan(
                    output_dir=args.output_dir,
                    model_command=args.model_command,
                    decoding_json=args.decoding_json,
                    per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
                    general_prompt_path=args.general_prompt_path,
                    general_prompt_label=args.general_prompt_label,
                    include_headroom=args.include_headroom,
                    include_frozen_sentinel=args.include_frozen_sentinel,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    try:
        summary_path = run_gate_decision(
            output_dir=args.output_dir,
            model_command=args.model_command,
            decoding_json=args.decoding_json,
            per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
            general_prompt_path=args.general_prompt_path,
            general_prompt_label=args.general_prompt_label,
            include_headroom=args.include_headroom,
            include_frozen_sentinel=args.include_frozen_sentinel,
            force=args.force,
        )
    except matrix.StopConditionError as error:
        report_path = write_stop_report(args.output_dir, error)
        print("Gate decision stopped: {}. Report: {}".format(error.reason, report_path))
        return 1
    print("Wrote component gate decision summary to {}".format(summary_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
