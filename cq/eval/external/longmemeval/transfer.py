"""Phase X.4 LongMemEval fair-stream policy transfer runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from cq.eval.bootstrap import (
    mean,
    one_sided_lower_confidence_bound,
    one_sided_upper_confidence_bound,
    paired_bootstrap_sample_means,
)
from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.extracted_candidate_runner import candidate_stream_sha256 as candidate_updates_sha256
from cq.eval.external.longmemeval.adapter import (
    ADAPTER_PIN_PATH,
    DEFAULT_ANNOTATIONS_PATH,
    adapt_annotations,
    candidate_stream_hash_report,
    load_agreed_annotations,
    validate_adapter_pin,
)
from cq.eval.external.longmemeval.dirty_worktree_check import (
    assert_clean_worktree,
    current_commit_sha,
    detect_repo_root,
    worktree_status_porcelain,
)
from cq.eval.external.longmemeval.gold_loader import load_gold_cases
from cq.eval.external.longmemeval.judge_stability import (
    DEFAULT_PRIMARY_JUDGE,
    CALIBRATION_SET_SIZE,
    CalibrationCase,
    run_judge,
)
from cq.eval.external.longmemeval.scorer import (
    DEFAULT_K,
    PolicyPrediction,
    score_predictions,
)
from cq.eval.runner import (
    POLICY_SET_CHOICES,
    POLICY_SET_DEFAULT,
    POLICY_SET_PHASE_2_5,
    POLICY_SET_PHASE_2_5_FOLLOWUP,
    _policies_for_family,
)
from cq.schemas.memory import jsonable
from cq.schemas.scenario import TaskFamily


REPO_ROOT = detect_repo_root(Path(__file__))
DEFAULT_ORACLE_JSON = Path("/tmp/longmemeval_oracle.json")
PATH_A_ANNOTATIONS = REPO_ROOT / "data" / "external" / "longmemeval" / "annotations_path_a.json"
PATH_B_ANNOTATIONS = REPO_ROOT / "data" / "external" / "longmemeval" / "annotations_path_b.json"
DEFAULT_JUDGE_REPORT = (
    REPO_ROOT / "data" / "external" / "longmemeval" / "judge_stability_report.json"
)
DEFAULT_SUMMARY = REPO_ROOT / "data" / "external" / "longmemeval" / "transfer_summary.json"
DEFAULT_ROWS = REPO_ROOT / "data" / "external" / "longmemeval" / "transfer_per_case_rows.csv"
DEFAULT_MANIFEST = REPO_ROOT / "data" / "external" / "longmemeval" / "transfer_manifest.json"
DEFAULT_SENSITIVITY_DIR = REPO_ROOT / "data" / "external" / "longmemeval" / "sensitivity"
DEV_OVERRIDE_ENV = "LONGMEMEVAL_DEV_OVERRIDE"
HEADLINE_POLICY = "consolidation_queue_lite"
REFLECTION_POLICY = "reflection_eager_write_lite"
MEM0_POLICY = "mem0_lite"
FOLLOWUP_CQ_POLICY = "cq_pending_multi_evidence"
REFLECTION_CAPPED_POLICY = "reflection_eager_write_cardinality_capped"
HEADLINE_METRIC = "all_hit_at_50"


class LongMemEvalTransferError(RuntimeError):
    pass


def validate_judge_report(path: str | Path = DEFAULT_JUDGE_REPORT) -> dict[str, Any]:
    report = _load_json_object(path)
    if bool(report.get("kill_criterion_10_triggered", True)):
        raise LongMemEvalTransferError(
            "Judge stability report triggers kill criterion 10: {}".format(path)
        )
    support_count = int(report.get("support_count") or 0)
    if support_count < CALIBRATION_SET_SIZE:
        raise LongMemEvalTransferError(
            "Judge stability support_count {} is below {}".format(
                support_count,
                CALIBRATION_SET_SIZE,
            )
        )
    floor = report.get("synthetic_correctness_floor")
    if not isinstance(floor, Mapping) or not floor.get("applicable"):
        raise LongMemEvalTransferError(
            "Judge stability report is missing an applicable synthetic correctness floor"
        )
    if not floor.get("passed"):
        raise LongMemEvalTransferError("Synthetic correctness floor did not pass")
    return report


def build_sensitivity_cells(
    *,
    include_sensitivity_cells: bool,
    primary_annotations_path: str | Path = DEFAULT_ANNOTATIONS_PATH,
) -> list[dict[str, Any]]:
    primary = load_agreed_annotations(primary_annotations_path)
    cells = [
        {
            "cell_id": "primary_contract",
            "description": "primary canonicalizer plus primary scope mapping",
            "annotations_path": _repo_relative(Path(primary_annotations_path)),
            "annotations": primary,
        }
    ]
    if not include_sensitivity_cells:
        return cells
    cells.extend(
        [
            {
                "cell_id": "path_a_only_denominator",
                "description": "primary contract on Path A-only denominator",
                "annotations_path": _repo_relative(PATH_A_ANNOTATIONS),
                "annotations": load_agreed_annotations(PATH_A_ANNOTATIONS),
            },
            {
                "cell_id": "path_b_only_denominator",
                "description": "primary contract on Path B-only denominator",
                "annotations_path": _repo_relative(PATH_B_ANNOTATIONS),
                "annotations": load_agreed_annotations(PATH_B_ANNOTATIONS),
            },
        ]
    )
    return cells


def build_transfer_artifacts(
    *,
    oracle_json: str | Path = DEFAULT_ORACLE_JSON,
    judge_report_path: str | Path = DEFAULT_JUDGE_REPORT,
    include_ablations: bool = True,
    include_sensitivity_cells: bool = True,
    run_local_judge: bool = False,
    judge_model: str = DEFAULT_PRIMARY_JUDGE,
    allow_dirty_worktree: bool = False,
    skip_judge_validation: bool = False,
    adapter_pin_path: str | Path = ADAPTER_PIN_PATH,
    policy_set: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if allow_dirty_worktree:
        _require_dev_override("--allow-dirty-worktree")
    if skip_judge_validation:
        _require_dev_override("--skip-judge-validation")

    provenance = _source_provenance(allow_dirty_worktree=allow_dirty_worktree)
    adapter_pin = validate_adapter_pin(pin_path=adapter_pin_path)
    judge_report = (
        {"validation_skipped": True}
        if skip_judge_validation
        else validate_judge_report(judge_report_path)
    )
    if policy_set is None:
        policy_set = POLICY_SET_PHASE_2_5 if include_ablations else POLICY_SET_DEFAULT
    if policy_set not in POLICY_SET_CHOICES:
        raise LongMemEvalTransferError(
            "Unsupported policy set '{}'. Allowed: {}".format(
                policy_set,
                ", ".join(POLICY_SET_CHOICES),
            )
        )
    policy_classes = _policies_for_family(
        TaskFamily.LONGMEMEVAL_EXTERNAL.value,
        policy_set=policy_set,
    )
    policy_names = [policy.policy_name for policy in policy_classes]
    gold_cases = _load_gold_cases_for_transfer(oracle_json)
    gold_by_case = {case.case_id: case for case in gold_cases}

    cell_summaries = []
    all_rows = []
    sensitivity_payloads = {}
    for cell in build_sensitivity_cells(include_sensitivity_cells=include_sensitivity_cells):
        cell_payload, cell_rows = _run_cell(
            cell=cell,
            policy_classes=policy_classes,
            policy_names=policy_names,
            gold_cases=gold_cases,
            gold_by_case=gold_by_case,
            run_local_judge=run_local_judge,
            judge_model=judge_model,
        )
        cell_summaries.append(_cell_summary_for_top_level(cell_payload))
        all_rows.extend(cell_rows)
        sensitivity_payloads[cell["cell_id"]] = cell_payload

    pairwise = _pairwise_comparisons_by_cell(sensitivity_payloads)
    followup_outcome = _followup_outcome(sensitivity_payloads)
    bucket = _bucket_verdict(pairwise, judge_report=judge_report, run_local_judge=run_local_judge)
    summary = {
        "mode": "longmemeval_transfer_policy_comparison",
        "policy_set": policy_set,
        "policy_names": policy_names,
        "include_ablations": include_ablations,
        "include_sensitivity_cells": include_sensitivity_cells,
        "judge_mode": "local_judge" if run_local_judge else "dry_run_unjudged",
        "judge_model": judge_model,
        "headline_metric": HEADLINE_METRIC,
        "policy_set_warning": _policy_set_warning(policy_set),
        "judge_report_path": _repo_relative(Path(judge_report_path)),
        "judge_report": _judge_report_summary(judge_report),
        "adapter_pin": adapter_pin,
        "cell_summaries": cell_summaries,
        "pairwise_comparisons": pairwise,
        "followup_outcome": followup_outcome,
        "bucket_verdict": bucket,
    }
    manifest = {
        "artifact": "longmemeval_transfer_policy_comparison",
        "artifact_class": "phase_x4_transfer",
        "source_provenance": provenance,
        "inputs": {
            "oracle_json_path": str(oracle_json),
            "oracle_json_sha256": sha256_file(oracle_json),
            "adapter_pin_path": _repo_relative(Path(adapter_pin_path)),
            "adapter_pin_sha256": sha256_file(adapter_pin_path),
            "judge_report_path": _repo_relative(Path(judge_report_path)),
            "judge_report_sha256": (
                sha256_file(judge_report_path) if Path(judge_report_path).exists() else ""
            ),
            "policy_set": policy_set,
        },
        "policy_names": policy_names,
        "cell_ids": [cell["cell_id"] for cell in cell_summaries],
        "judge_mode": summary["judge_mode"],
        "bucket": bucket,
    }
    return summary, all_rows, manifest, sensitivity_payloads


def write_transfer_artifacts(
    *,
    summary_path: str | Path,
    rows_path: str | Path,
    manifest_path: str | Path,
    sensitivity_dir: str | Path,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    sensitivity_payloads: Mapping[str, Mapping[str, Any]],
) -> None:
    summary_path = Path(summary_path)
    rows_path = Path(rows_path)
    manifest_path = Path(manifest_path)
    sensitivity_dir = Path(sensitivity_dir)
    _write_json(summary_path, summary)
    _write_csv(rows_path, rows)
    sensitivity_dir.mkdir(parents=True, exist_ok=True)
    sensitivity_outputs = {}
    for cell_id, payload in sensitivity_payloads.items():
        path = sensitivity_dir / "{}.json".format(cell_id)
        _write_json(path, payload)
        sensitivity_outputs[cell_id] = {
            "path": _repo_relative(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    manifest_with_outputs = dict(manifest)
    manifest_with_outputs["outputs"] = {
        "summary_path": _repo_relative(summary_path),
        "summary_sha256": sha256_file(summary_path),
        "summary_bytes": summary_path.stat().st_size,
        "per_case_rows_path": _repo_relative(rows_path),
        "per_case_rows_sha256": sha256_file(rows_path),
        "per_case_rows_bytes": rows_path.stat().st_size,
        "sensitivity": sensitivity_outputs,
    }
    _write_json(manifest_path, manifest_with_outputs)


def _run_cell(
    *,
    cell: Mapping[str, Any],
    policy_classes: Sequence[type],
    policy_names: Sequence[str],
    gold_cases: Sequence[Any],
    gold_by_case: Mapping[str, Any],
    run_local_judge: bool,
    judge_model: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scenarios, streams = adapt_annotations(cell["annotations"])
    expected_stream_hashes = _expected_scenario_stream_hashes(
        scenarios=scenarios,
        streams=streams,
        cell_id=str(cell["cell_id"]),
    )
    expected_case_ids = [
        str(scenario.latent_truth_graph["case_id"]) for scenario in scenarios
    ]
    missing_gold = sorted(set(expected_case_ids) - set(gold_by_case))
    if missing_gold:
        raise LongMemEvalTransferError(
            "Gold oracle missing cell {} case ids: {}".format(
                cell["cell_id"],
                ", ".join(missing_gold[:10]),
            )
        )
    hash_report = candidate_stream_hash_report(streams, policy_names)
    if hash_report["candidate_stream_hash_mismatches"]:
        raise LongMemEvalTransferError(
            "Candidate-stream hash mismatch in cell {}".format(cell["cell_id"])
        )

    predictions = []
    trace_rows = []
    for policy_cls in policy_classes:
        for scenario in scenarios:
            record = execute_scenario(policy_cls, scenario)
            _assert_candidate_stream_unchanged(
                scenario,
                expected_stream_hashes[scenario.scenario_id],
                policy_name=policy_cls.policy_name,
                cell_id=str(cell["cell_id"]),
            )
            trace = (record.get("question_traces") or [{}])[0]
            case_id = str(scenario.latent_truth_graph["case_id"])
            predicted_session_ids = _predicted_session_ids(
                trace.get("resolved_candidate_ids", []),
                streams[scenario.scenario_id].source_session_id_by_candidate_id,
            )
            candidate_answer = str(trace.get("answer_text") or "")
            predictions.append(
                PolicyPrediction(
                    case_id=case_id,
                    policy_name=policy_cls.policy_name,
                    predicted_session_ids_ranked=predicted_session_ids,
                    candidate_answer=candidate_answer,
                    answer_correct=False,
                )
            )
            trace_rows.append(
                {
                    "cell_id": cell["cell_id"],
                    "case_id": case_id,
                    "scenario_id": scenario.scenario_id,
                    "policy_name": policy_cls.policy_name,
                    "candidate_answer": candidate_answer,
                    "predicted_session_ids_ranked": predicted_session_ids,
                    "resolved_candidate_ids": list(trace.get("resolved_candidate_ids", [])),
                    "used_memory_ids": list(trace.get("used_memory_ids", [])),
                    "used_pending": bool(trace.get("used_pending", False)),
                }
            )

    if run_local_judge:
        predictions = _judge_predictions(
            predictions,
            gold_by_case=gold_by_case,
            cell_id=str(cell["cell_id"]),
            judge_model=judge_model,
        )
    scored = score_predictions(
        predictions,
        gold_cases,
        expected_case_ids=expected_case_ids,
        ks=DEFAULT_K,
    )
    scored_rows = []
    trace_by_key = {
        (row["policy_name"], row["case_id"]): row for row in trace_rows
    }
    for row in scored["rows"]:
        trace_row = trace_by_key[(row["policy_name"], row["case_id"])]
        scored_row = {
            **trace_row,
            "answer_correct": bool(row["answer_correct"]),
            "gold_evidence_count": row["gold_evidence_count"],
            "predicted_session_count": row["predicted_session_count"],
            "any_hit_all_context": bool(row["any_hit_all_context"]),
            "all_hit_all_context": bool(row["all_hit_all_context"]),
            "first_gold_rank": row["first_gold_rank"],
        }
        for k in DEFAULT_K:
            scored_row["any_hit_at_{}".format(k)] = bool(row["any_hit_at_{}".format(k)])
            scored_row["all_hit_at_{}".format(k)] = bool(row["all_hit_at_{}".format(k)])
        scored_rows.append(scored_row)
    return (
        {
            "cell_id": cell["cell_id"],
            "description": cell["description"],
            "annotations_path": cell["annotations_path"],
            "scenario_count": len(scenarios),
            "candidate_stream_hash_report": hash_report,
            "runtime_candidate_stream_mutation_check": {
                "passed": True,
                "description": "scenario candidate stream unchanged after each policy execution",
            },
            "score_summary": scored["summary"],
            "rows": scored_rows,
        },
        scored_rows,
    )


def _load_gold_cases_for_transfer(oracle_json: str | Path) -> list[Any]:
    path = Path(oracle_json)
    if not path.exists():
        raise LongMemEvalTransferError(
            "LongMemEval oracle JSON is missing: {}. Provide --oracle-json or "
            "materialize the scoring-only oracle at the default path {}.".format(
                path,
                DEFAULT_ORACLE_JSON,
            )
        )
    return load_gold_cases(path)


def _require_dev_override(flag_name: str) -> None:
    if os.environ.get(DEV_OVERRIDE_ENV) != "1":
        raise LongMemEvalTransferError(
            "{} requires {}=1 because it bypasses a preregistered runtime gate.".format(
                flag_name,
                DEV_OVERRIDE_ENV,
            )
        )


def _policy_set_warning(policy_set: str) -> str:
    if policy_set != POLICY_SET_PHASE_2_5_FOLLOWUP:
        return ""
    return (
        "phase2_5_followup is a diagnostic follow-up policy set for the "
        "preregistered pending multi-evidence repair; do not treat it as the "
        "original X.4 phase2_5 headline comparison."
    )


def _expected_scenario_stream_hashes(
    *,
    scenarios: Sequence[Any],
    streams: Mapping[str, Any],
    cell_id: str,
) -> dict[str, str]:
    expected = {}
    for scenario in scenarios:
        scenario_hash = _scenario_candidate_stream_sha256(scenario)
        adapter_hash = streams[scenario.scenario_id].candidate_stream_sha256
        if scenario_hash != adapter_hash:
            raise LongMemEvalTransferError(
                "Adapted scenario stream hash mismatch in cell {} scenario {}: "
                "scenario={}, adapter={}".format(
                    cell_id,
                    scenario.scenario_id,
                    scenario_hash,
                    adapter_hash,
                )
            )
        expected[scenario.scenario_id] = scenario_hash
    return expected


def _scenario_candidate_stream_sha256(scenario: Any) -> str:
    candidates = [
        event.candidate
        for event in scenario.sorted_events()
        if event.candidate is not None
    ]
    return candidate_updates_sha256(candidates)


def _assert_candidate_stream_unchanged(
    scenario: Any,
    expected_hash: str,
    *,
    policy_name: str,
    cell_id: str,
) -> None:
    observed_hash = _scenario_candidate_stream_sha256(scenario)
    if observed_hash != expected_hash:
        raise LongMemEvalTransferError(
            "Policy {} mutated the LongMemEval candidate stream in cell {} "
            "scenario {}: before={}, after={}".format(
                policy_name,
                cell_id,
                scenario.scenario_id,
                expected_hash,
                observed_hash,
            )
        )


def _judge_predictions(
    predictions: Sequence[PolicyPrediction],
    *,
    gold_by_case: Mapping[str, Any],
    cell_id: str,
    judge_model: str,
) -> list[PolicyPrediction]:
    judge_cases = [
        CalibrationCase(
            case_id="{}::{}::{}".format(cell_id, prediction.policy_name, prediction.case_id),
            question=gold_by_case[prediction.case_id].question,
            gold_answer=gold_by_case[prediction.case_id].answer,
            candidate_answer=prediction.candidate_answer,
            source_case_id=prediction.case_id,
            source_policy=prediction.policy_name,
        )
        for prediction in predictions
    ]
    verdicts = run_judge(judge_cases, model_id=judge_model)
    verdict_by_id = {verdict.case_id: verdict.verdict for verdict in verdicts}
    judged = []
    for prediction, judge_case in zip(predictions, judge_cases):
        judged.append(
            PolicyPrediction(
                case_id=prediction.case_id,
                policy_name=prediction.policy_name,
                predicted_session_ids_ranked=prediction.predicted_session_ids_ranked,
                candidate_answer=prediction.candidate_answer,
                answer_correct=verdict_by_id.get(judge_case.case_id) == "correct",
            )
        )
    return judged


def _predicted_session_ids(
    resolved_candidate_ids: Sequence[str],
    source_session_id_by_candidate_id: Mapping[str, str],
) -> list[str]:
    result = []
    seen = set()
    for candidate_id in resolved_candidate_ids:
        source_id = source_session_id_by_candidate_id.get(str(candidate_id))
        if source_id and source_id not in seen:
            result.append(source_id)
            seen.add(source_id)
    return result


def _pairwise_comparisons_by_cell(
    sensitivity_payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    comparisons = {}
    for cell_id, payload in sorted(sensitivity_payloads.items()):
        rows = payload["rows"]
        comparisons[cell_id] = {
            "cq_vs_reflection": _pairwise_for_rows(
                rows,
                reference_policy=HEADLINE_POLICY,
                comparator_policy=REFLECTION_POLICY,
                metric_name=HEADLINE_METRIC,
            ),
            "cq_vs_mem0": _pairwise_for_rows(
                rows,
                reference_policy=HEADLINE_POLICY,
                comparator_policy=MEM0_POLICY,
                metric_name=HEADLINE_METRIC,
            ),
        }
        policy_names = {str(row["policy_name"]) for row in rows}
        if FOLLOWUP_CQ_POLICY in policy_names:
            comparisons[cell_id]["followup_cq_vs_base_cq"] = _pairwise_for_rows(
                rows,
                reference_policy=FOLLOWUP_CQ_POLICY,
                comparator_policy=HEADLINE_POLICY,
                metric_name=HEADLINE_METRIC,
            )
            comparisons[cell_id]["followup_cq_vs_reflection"] = _pairwise_for_rows(
                rows,
                reference_policy=FOLLOWUP_CQ_POLICY,
                comparator_policy=REFLECTION_POLICY,
                metric_name=HEADLINE_METRIC,
            )
        if REFLECTION_CAPPED_POLICY in policy_names:
            comparisons[cell_id]["reflection_capped_vs_reflection"] = _pairwise_for_rows(
                rows,
                reference_policy=REFLECTION_CAPPED_POLICY,
                comparator_policy=REFLECTION_POLICY,
                metric_name=HEADLINE_METRIC,
            )
        if FOLLOWUP_CQ_POLICY in policy_names and REFLECTION_CAPPED_POLICY in policy_names:
            comparisons[cell_id]["followup_cq_vs_reflection_capped"] = _pairwise_for_rows(
                rows,
                reference_policy=FOLLOWUP_CQ_POLICY,
                comparator_policy=REFLECTION_CAPPED_POLICY,
                metric_name=HEADLINE_METRIC,
            )
    return comparisons


def _followup_outcome(
    sensitivity_payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if not sensitivity_payloads:
        return {"applicable": False, "reason": "no sensitivity payloads"}
    primary = sensitivity_payloads.get("primary_contract")
    if primary is None:
        return {"applicable": False, "reason": "no primary_contract cell"}
    policy_names = {str(row["policy_name"]) for row in primary["rows"]}
    if FOLLOWUP_CQ_POLICY not in policy_names or REFLECTION_CAPPED_POLICY not in policy_names:
        return {"applicable": False, "reason": "follow-up policies absent"}

    counts_by_cell = {
        cell_id: _policy_metric_counts(payload["rows"], metric_name=HEADLINE_METRIC)
        for cell_id, payload in sorted(sensitivity_payloads.items())
    }
    primary_counts = counts_by_cell["primary_contract"]
    base_cq = primary_counts.get(HEADLINE_POLICY, {})
    followup_cq = primary_counts.get(FOLLOWUP_CQ_POLICY, {})
    capped = primary_counts.get(REFLECTION_CAPPED_POLICY, {})
    reflection = primary_counts.get(REFLECTION_POLICY, {})
    denominator = int(followup_cq.get("count", 0))
    followup_hits = int(followup_cq.get("hits", 0))
    base_hits = int(base_cq.get("hits", 0))
    capped_hits = int(capped.get("hits", 0))
    reflection_hits = int(reflection.get("hits", 0))
    improvement_points = (
        (followup_hits / denominator) - (base_hits / denominator)
        if denominator
        else 0.0
    )
    capped_reflection_active = _reflection_capped_is_strict_subset(primary["rows"])
    stable_followup_success = all(
        counts.get(FOLLOWUP_CQ_POLICY, {}).get("hits") == counts.get(FOLLOWUP_CQ_POLICY, {}).get("count")
        for counts in counts_by_cell.values()
    )

    if not capped_reflection_active:
        bucket = "D"
        reason = "reflection cardinality-capped control did not form a strict subset"
    elif denominator and followup_hits >= min(70, denominator) and capped_hits <= base_hits + 1:
        bucket = "A"
        reason = "pending multi-evidence repair succeeds and capped Reflection reproduces readout loss"
    elif denominator and followup_hits >= min(70, denominator) and capped_hits == reflection_hits:
        bucket = "A-weak"
        reason = "pending multi-evidence succeeds but capped Reflection still passes"
    elif improvement_points >= 0.50:
        bucket = "B"
        reason = "pending multi-evidence partially improves evidence completeness"
    elif improvement_points < 0.10:
        bucket = "C"
        reason = "pending multi-evidence does not materially improve evidence completeness"
    else:
        bucket = "B"
        reason = "pending multi-evidence improves without clearing the preregistered threshold"

    return {
        "applicable": True,
        "bucket": bucket,
        "reason": reason,
        "headline_metric": HEADLINE_METRIC,
        "primary_contract_counts": primary_counts,
        "counts_by_cell": counts_by_cell,
        "primary_improvement_points": improvement_points,
        "reflection_capped_strict_subset_on_primary": capped_reflection_active,
        "followup_success_all_cells": stable_followup_success,
    }


def _policy_metric_counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    metric_name: str,
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        policy_name = str(row["policy_name"])
        counts.setdefault(policy_name, {"hits": 0, "count": 0})
        counts[policy_name]["count"] += 1
        if bool(row[metric_name]):
            counts[policy_name]["hits"] += 1
    return counts


def _reflection_capped_is_strict_subset(rows: Sequence[Mapping[str, Any]]) -> bool:
    base_by_case = {
        str(row["case_id"]): set(row.get("resolved_candidate_ids") or [])
        for row in rows
        if row["policy_name"] == REFLECTION_POLICY
    }
    capped_by_case = {
        str(row["case_id"]): set(row.get("resolved_candidate_ids") or [])
        for row in rows
        if row["policy_name"] == REFLECTION_CAPPED_POLICY
    }
    compared = sorted(set(base_by_case) & set(capped_by_case))
    if not compared:
        return False
    strict_count = 0
    for case_id in compared:
        base = base_by_case[case_id]
        capped = capped_by_case[case_id]
        if not capped.issubset(base):
            return False
        if len(capped) < len(base):
            strict_count += 1
    return strict_count > 0


def _pairwise_for_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    reference_policy: str,
    comparator_policy: str,
    metric_name: str,
) -> dict[str, Any]:
    reference = {
        str(row["case_id"]): float(bool(row[metric_name]))
        for row in rows
        if row["policy_name"] == reference_policy
    }
    comparator = {
        str(row["case_id"]): float(bool(row[metric_name]))
        for row in rows
        if row["policy_name"] == comparator_policy
    }
    case_ids = sorted(set(reference) & set(comparator))
    if not case_ids:
        return {
            "metric_name": metric_name,
            "reference_policy_name": reference_policy,
            "comparator_policy_name": comparator_policy,
            "case_count": 0,
            "point_estimate_delta": None,
            "two_sided_95_lcb": None,
            "two_sided_95_ucb": None,
            "sign": "missing",
        }
    deltas = [reference[case_id] - comparator[case_id] for case_id in case_ids]
    samples = paired_bootstrap_sample_means(deltas, resamples=5000, seed=1729)
    point = mean(deltas)
    return {
        "metric_name": metric_name,
        "reference_policy_name": reference_policy,
        "comparator_policy_name": comparator_policy,
        "case_count": len(case_ids),
        "point_estimate_delta": point,
        "two_sided_95_lcb": one_sided_lower_confidence_bound(samples, confidence_level=0.975),
        "two_sided_95_ucb": one_sided_upper_confidence_bound(samples, confidence_level=0.975),
        "sign": _sign(point),
    }


def _bucket_verdict(
    pairwise: Mapping[str, Any],
    *,
    judge_report: Mapping[str, Any],
    run_local_judge: bool,
) -> dict[str, Any]:
    if judge_report.get("validation_skipped"):
        return {
            "bucket": "not_evaluated",
            "reason": "judge validation skipped",
        }
    if not run_local_judge:
        return {
            "bucket": "not_evaluated",
            "reason": "dry-run transfer did not judge answers",
        }
    signs = [
        row["cq_vs_reflection"]["sign"]
        for row in pairwise.values()
        if row["cq_vs_reflection"]["sign"] != "missing"
    ]
    if not signs:
        return {"bucket": "D", "reason": "no CQ-vs-Reflection comparisons"}
    if len(set(signs)) > 1:
        return {"bucket": "C", "reason": "contract sensitivity sign flip", "signs": signs}
    if signs[0] == "zero":
        return {"bucket": "B", "reason": "transfer-null CQ-vs-Reflection result", "signs": signs}
    return {"bucket": "A", "reason": "contract sensitivity sign stable", "signs": signs}


def _sign(value: Optional[float]) -> str:
    if value is None:
        return "missing"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _cell_summary_for_top_level(payload: Mapping[str, Any]) -> dict[str, Any]:
    score_summary = payload["score_summary"]
    return {
        "cell_id": payload["cell_id"],
        "description": payload["description"],
        "annotations_path": payload["annotations_path"],
        "scenario_count": payload["scenario_count"],
        "candidate_stream_hash_invariant_passed": not payload[
            "candidate_stream_hash_report"
        ]["candidate_stream_hash_mismatches"],
        "score_summary": score_summary,
    }


def _source_provenance(*, allow_dirty_worktree: bool) -> dict[str, Any]:
    status = worktree_status_porcelain(REPO_ROOT)
    if not allow_dirty_worktree:
        assert_clean_worktree(REPO_ROOT)
    return {
        "git_commit_sha": current_commit_sha(REPO_ROOT),
        "worktree_clean": not status,
        "dirty_worktree_check_passed": not status,
        "dirty_worktree_allowed": allow_dirty_worktree,
        "git_status_porcelain": status.splitlines() if status else [],
    }


def _judge_report_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "calibration_path",
        "support_count",
        "primary_agreement",
        "kill_criterion_10_triggered",
        "synthetic_correctness_floor",
    )
    return {field: report.get(field) for field in fields if field in report}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LongMemEvalTransferError("Expected JSON object in {}".format(path))
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "cell_id",
        "policy_name",
        "case_id",
        "scenario_id",
        "answer_correct",
        "candidate_answer",
        "predicted_session_ids_ranked",
        "resolved_candidate_ids",
        "used_memory_ids",
        "used_pending",
        "gold_evidence_count",
        "predicted_session_count",
        "any_hit_all_context",
        "all_hit_all_context",
        "first_gold_rank",
    ]
    for k in DEFAULT_K:
        fieldnames.extend(["any_hit_at_{}".format(k), "all_hit_at_{}".format(k)])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            for key in ("predicted_session_ids_ranked", "resolved_candidate_ids", "used_memory_ids"):
                rendered[key] = json.dumps(rendered.get(key, []), sort_keys=True)
            writer.writerow({field: rendered.get(field, "") for field in fieldnames})


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run LongMemEval Phase X.4 transfer.")
    parser.add_argument("--oracle-json", default=str(DEFAULT_ORACLE_JSON))
    parser.add_argument("--judge-report", default=str(DEFAULT_JUDGE_REPORT))
    parser.add_argument("--adapter-pin", default=str(ADAPTER_PIN_PATH))
    parser.add_argument("--out-summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--out-rows", default=str(DEFAULT_ROWS))
    parser.add_argument("--out-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--sensitivity-dir", default=str(DEFAULT_SENSITIVITY_DIR))
    parser.add_argument("--include-ablations", action="store_true")
    parser.add_argument("--include-sensitivity-cells", action="store_true")
    parser.add_argument("--policy-set", choices=POLICY_SET_CHOICES, default=None)
    parser.add_argument("--run-local-judge", action="store_true")
    parser.add_argument("--judge-model", default=DEFAULT_PRIMARY_JUDGE)
    parser.add_argument("--allow-dirty-worktree", action="store_true")
    parser.add_argument("--skip-judge-validation", action="store_true")
    args = parser.parse_args(argv)

    summary, rows, manifest, sensitivity_payloads = build_transfer_artifacts(
        oracle_json=args.oracle_json,
        judge_report_path=args.judge_report,
        include_ablations=args.include_ablations,
        include_sensitivity_cells=args.include_sensitivity_cells,
        run_local_judge=args.run_local_judge,
        judge_model=args.judge_model,
        allow_dirty_worktree=args.allow_dirty_worktree,
        skip_judge_validation=args.skip_judge_validation,
        adapter_pin_path=args.adapter_pin,
        policy_set=args.policy_set,
    )
    write_transfer_artifacts(
        summary_path=args.out_summary,
        rows_path=args.out_rows,
        manifest_path=args.out_manifest,
        sensitivity_dir=args.sensitivity_dir,
        summary=summary,
        rows=rows,
        manifest=manifest,
        sensitivity_payloads=sensitivity_payloads,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
