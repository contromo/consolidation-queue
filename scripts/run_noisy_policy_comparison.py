#!/usr/bin/env python3
"""Run the preregistered Phase 4 extracted-candidate policy comparison."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cq.eval.bootstrap import (  # noqa: E402
    one_sided_lower_confidence_bound,
    one_sided_upper_confidence_bound,
    paired_bootstrap_sample_means,
    paired_delta_point_estimate,
)
from cq.eval.component_eval import evaluate_component_predictions  # noqa: E402
from cq.eval.component_gate_runtime import (  # noqa: E402
    GateRuntimeError,
    git_commit,
    verify_primary_model_backend,
    verify_required_anchor_before_probe,
    working_tree_status,
)
from cq.eval.extracted_candidate_runner import (  # noqa: E402
    ADAPTER_PIN_PATH,
    FROZEN_SENTINEL_SCENARIO_COUNT,
    LOCKED_MODEL_DIGEST,
    LOCKED_MODEL_TAG,
    LOCKED_PROMPT_SHA256,
    PRIMARY_SCENARIO_COUNT,
    NoisyPolicyComparisonError,
    adapt_predictions_for_scenarios,
    candidate_stream_audit_for_adapted_scenarios,
    load_extracted_predictions,
    prediction_cell_paths,
    sha256_file,
    validate_adapter_pin,
    validate_noisy_preregistration_lock,
)
from cq.eval.runner import (  # noqa: E402
    FALSE_CORROBORATION,
    FORCED_CONTRADICTION,
    MECHANISM_DIVERSE_HELDOUT,
    MEMORY_POISONING,
    POLICY_SET_CHOICES,
    POLICY_SET_PHASE_2_5,
    PREFERENCE_DRIFT,
    SCOPE_CONTAMINATION,
    USEFUL_PENDING_MEMORY,
    build_extracted_candidate_run_artifact,
    generate_scenarios,
    write_outputs,
)
from cq.schemas.memory import jsonable  # noqa: E402


DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "results"
DEFAULT_RUN_DIR = REPO_ROOT / "data" / "runs"
STOP_REPORT_PREFIX = "noisy_policy_comparison_stop"
SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "noisy_policy_comparison_summary.json"
MAX_ADAPTER_DROP_RATE = 0.05
BUCKET_C_DIRECTIONAL_LOSS_NOTE = (
    "Bucket C intentionally uses directional CQ-vs-Reflection losses before "
    "statistical loss gating; Bucket A still requires preregistered win size "
    "and LCB conditions."
)
COMPONENT_FAMILIES = (
    FORCED_CONTRADICTION,
    SCOPE_CONTAMINATION,
    PREFERENCE_DRIFT,
    USEFUL_PENDING_MEMORY,
    FALSE_CORROBORATION,
    MEMORY_POISONING,
)
COUNTABLE_FAMILIES = (
    FORCED_CONTRADICTION,
    SCOPE_CONTAMINATION,
    PREFERENCE_DRIFT,
    USEFUL_PENDING_MEMORY,
    MEMORY_POISONING,
)
PRIMARY_METRIC_BY_FAMILY = {
    FORCED_CONTRADICTION: "false_assertion_rate",
    SCOPE_CONTAMINATION: "leakage_rate",
    PREFERENCE_DRIFT: "answer_correctness",
    USEFUL_PENDING_MEMORY: "answer_correctness",
    FALSE_CORROBORATION: "false_assertion_rate",
    MEMORY_POISONING: "poison_promotion_rate",
}
FROZEN_PRIMARY_METRICS = (
    "false_assertion_rate",
    "poison_promotion_rate",
    "premature_promotion_rate",
)
DESCRIPTIVE_METRICS = (
    "answer_correctness",
    "false_assertion_rate",
    "leakage_rate",
    "premature_promotion_rate",
    "poison_promotion_rate",
    "clean_durable_displacement_rate",
)
HIGHER_IS_BETTER = {"answer_correctness"}
LOWER_IS_BETTER = {
    "false_assertion_rate",
    "poison_promotion_rate",
    "premature_promotion_rate",
    "clean_durable_displacement_rate",
    "leakage_rate",
}
CQ_POLICY = "consolidation_queue_lite"
REFLECTION_POLICY = "reflection_eager_write_lite"
MEM0_POLICY = "mem0_lite"
COMPARATORS = (
    REFLECTION_POLICY,
    MEM0_POLICY,
    "cq_no_contestation_demotion",
    "cq_no_wider_scope_pending_override",
    "cq_no_pending_lookup_use",
    "cq_no_source_independence_gate",
)


class StopConditionError(RuntimeError):
    def __init__(self, reason: str, details: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details


def run_noisy_policy_comparison(
    *,
    output_dir: Path,
    run_dir: Path,
    predictions_dir: Path,
    primary_model_tag: str,
    schema_profile: str,
    include_frozen_sentinel: bool,
    policy_set: str,
    runner_command: str,
) -> Path:
    if primary_model_tag != LOCKED_MODEL_TAG:
        raise StopConditionError(
            "unsupported_primary_model_tag",
            {"observed": primary_model_tag, "expected": LOCKED_MODEL_TAG},
        )
    if working_tree_status() != "clean":
        raise StopConditionError(
            "dirty_pre_run_working_tree",
            {"working_tree_status": subprocess.check_output(["git", "status", "--short"], text=True, cwd=REPO_ROOT)},
        )
    backend = verify_primary_model_backend(
        primary_model_tag,
        runner_command=runner_command,
    )
    anchor_error = verify_required_anchor_before_probe(
        output_dir,
        live_ollama_server_version=backend.ollama_server_version,
    )
    if anchor_error is not None:
        raise StopConditionError(anchor_error.reason, anchor_error.details)
    preregistration_lock_sha = validate_noisy_preregistration_lock()
    adapter_pin = validate_adapter_pin()
    families = list(COMPONENT_FAMILIES)
    if include_frozen_sentinel:
        families.append(MECHANISM_DIVERSE_HELDOUT)

    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    written_runs = []
    for family in families:
        scenario_count = (
            FROZEN_SENTINEL_SCENARIO_COUNT
            if family == MECHANISM_DIVERSE_HELDOUT
            else PRIMARY_SCENARIO_COUNT
        )
        template_mix = "frozen" if family == MECHANISM_DIVERSE_HELDOUT else "heldout"
        paths = prediction_cell_paths(
            predictions_dir=predictions_dir,
            family=family,
            schema_profile=schema_profile,
        )
        _assert_component_gate_still_passes(
            family=family,
            scenario_count=scenario_count,
            template_mix=template_mix,
            predictions_path=paths.predictions,
        )
        _assert_adapter_drop_rate_before_policy_scoring(
            family=family,
            scenario_count=scenario_count,
            template_mix=template_mix,
            predictions_path=paths.predictions,
        )
        run_artifact = build_extracted_candidate_run_artifact(
            scenario_count,
            template_mix=template_mix,
            family=family,
            policy_set=policy_set,
            extracted_predictions_dir=predictions_dir,
            schema_profile=schema_profile,
        )
        output_json = run_dir / "noisy_policy_comparison_{}_{}.json".format(family, schema_profile)
        output_csv = output_dir / "noisy_policy_comparison_{}_{}_metrics.csv".format(
            family,
            schema_profile,
        )
        write_outputs(run_artifact, output_json, output_csv)
        manifest_path = write_run_manifest(
            run_artifact=run_artifact,
            output_json=output_json,
            output_csv=output_csv,
            runner_command=runner_command,
            schema_profile=schema_profile,
            model_backend=backend,
            preregistration_lock_sha=preregistration_lock_sha,
            adapter_sha=str(adapter_pin["candidate_adapter_sha256"]),
        )
        written_runs.append(
            {
                "family": family,
                "run_json": _repo_relative_path(output_json),
                "metrics_csv": _repo_relative_path(output_csv),
                "manifest": _repo_relative_path(manifest_path),
            }
        )

    summary = aggregate_summary(
        run_dir=run_dir,
        schema_profiles=("default", "scenario_conditioned"),
        include_frozen_sentinel=include_frozen_sentinel,
    )
    summary.update(
        {
            "mode": "noisy_policy_comparison_summary",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "primary_model_tag": primary_model_tag,
            "primary_model_digest": LOCKED_MODEL_DIGEST,
            "prompt_sha256": LOCKED_PROMPT_SHA256,
            "runner_command": runner_command,
            "last_schema_profile_run": schema_profile,
            "last_written_runs": written_runs,
            "preregistration_lock_sha256": preregistration_lock_sha,
            "candidate_adapter_sha256": str(adapter_pin["candidate_adapter_sha256"]),
            "adapter_pin_path": _repo_relative_path(ADAPTER_PIN_PATH),
        }
    )
    _write_json(SUMMARY_PATH, summary)
    return SUMMARY_PATH


def _assert_component_gate_still_passes(
    *,
    family: str,
    scenario_count: int,
    template_mix: str,
    predictions_path: Path,
) -> None:
    predictions_by_scenario, scenario_errors = load_extracted_predictions(predictions_path)
    scenarios = generate_scenarios(family, scenario_count, template_mix)
    evaluation = evaluate_component_predictions(
        scenarios,
        predictions_by_scenario,
        scenario_errors=scenario_errors,
    )
    if scenario_errors:
        raise StopConditionError(
            "component_quality_drift_scenario_errors",
            {
                "family": family,
                "predictions_path": _repo_relative_path(predictions_path),
                "scenario_error_count": len(scenario_errors),
                "scenario_errors": jsonable(scenario_errors),
            },
        )
    failures = [
        {"metric": metric_name, **gate_payload}
        for metric_name, gate_payload in evaluation["quality_gates"].items()
        if not gate_payload.get("passed")
    ]
    if failures:
        raise StopConditionError(
            "component_quality_drift_gate_failure",
            {
                "family": family,
                "predictions_path": _repo_relative_path(predictions_path),
                "failures": failures,
            },
        )


def assert_adapter_drop_rate_within_limit(
    run_artifact: Mapping[str, object],
    *,
    family: str,
    max_drop_rate: float = MAX_ADAPTER_DROP_RATE,
) -> None:
    summary = adapter_drop_summary(run_artifact)
    if summary["adapter_drop_rate"] <= max_drop_rate:
        return
    raise StopConditionError(
        "adapter_drop_rate_exceeded",
        {
            "family": family,
            "max_adapter_drop_rate": max_drop_rate,
            **summary,
        },
    )


def _assert_adapter_drop_rate_before_policy_scoring(
    *,
    family: str,
    scenario_count: int,
    template_mix: str,
    predictions_path: Path,
) -> None:
    predictions_by_scenario, scenario_errors = load_extracted_predictions(predictions_path)
    scenarios = generate_scenarios(family, scenario_count, template_mix)
    adapted_by_scenario = adapt_predictions_for_scenarios(
        scenarios,
        predictions_by_scenario,
        scenario_errors,
    )
    candidate_stream_audit = candidate_stream_audit_for_adapted_scenarios(
        scenarios,
        adapted_by_scenario,
    )
    assert_adapter_drop_rate_within_limit(
        {"candidate_stream_audit": candidate_stream_audit},
        family=family,
    )


def adapter_drop_summary(run_artifact: Mapping[str, object]) -> Dict[str, object]:
    rows = []
    total_predictions = 0
    total_drops = 0
    for audit_row in run_artifact.get("candidate_stream_audit", []):
        if not isinstance(audit_row, dict):
            continue
        drops = audit_row.get("drops")
        fallback_drop_count = len(drops) if isinstance(drops, list) else 0
        drop_count = int(audit_row.get("adapter_drop_count", fallback_drop_count))
        fallback_prediction_count = drop_count + int(audit_row.get("candidate_count", 0))
        prediction_count = int(audit_row.get("input_prediction_count", fallback_prediction_count))
        drop_rate = float(drop_count / prediction_count) if prediction_count else 0.0
        total_predictions += prediction_count
        total_drops += drop_count
        rows.append(
            {
                "scenario_id": audit_row.get("scenario_id"),
                "input_prediction_count": prediction_count,
                "adapter_drop_count": drop_count,
                "adapter_drop_rate": drop_rate,
                "drop_reasons": _drop_reason_counts(drops if isinstance(drops, list) else []),
            }
        )
    aggregate_rate = float(total_drops / total_predictions) if total_predictions else 0.0
    return {
        "input_prediction_count": total_predictions,
        "adapter_drop_count": total_drops,
        "adapter_drop_rate": aggregate_rate,
        "scenario_count": len(rows),
        "scenarios_with_drops": [row for row in rows if row["adapter_drop_count"]],
    }


def _drop_reason_counts(drops: Sequence[object]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for drop in drops:
        if not isinstance(drop, dict):
            continue
        reason = str(drop.get("reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def aggregate_summary(
    *,
    run_dir: Path,
    schema_profiles: Sequence[str],
    include_frozen_sentinel: bool,
) -> Dict[str, object]:
    artifacts_by_profile = {
        schema_profile: _load_profile_artifacts(
            run_dir,
            schema_profile=schema_profile,
            include_frozen_sentinel=include_frozen_sentinel,
        )
        for schema_profile in schema_profiles
    }
    comparisons_by_profile = {
        schema_profile: _profile_comparisons(artifacts)
        for schema_profile, artifacts in artifacts_by_profile.items()
        if _profile_complete(artifacts, include_frozen_sentinel=include_frozen_sentinel)
    }
    bucket = _bucket_decision(comparisons_by_profile)
    return {
        "schema_profiles": {
            schema_profile: {
                "complete": _profile_complete(artifacts, include_frozen_sentinel=include_frozen_sentinel),
                "artifacts": {
                    family: _repo_relative_path(path)
                    for family, path in artifacts.get("_paths", {}).items()
                },
                "primary_metric_comparisons": comparisons_by_profile.get(schema_profile, {}).get(
                    "primary_metric_comparisons",
                    {},
                ),
                "frozen_primary_comparisons": comparisons_by_profile.get(schema_profile, {}).get(
                    "frozen_primary_comparisons",
                    {},
                ),
                "descriptive_metric_comparisons": comparisons_by_profile.get(schema_profile, {}).get(
                    "descriptive_metric_comparisons",
                    {},
                ),
            }
            for schema_profile, artifacts in artifacts_by_profile.items()
        },
        "bucket_decision": bucket,
    }


def _load_profile_artifacts(
    run_dir: Path,
    *,
    schema_profile: str,
    include_frozen_sentinel: bool,
) -> Dict[str, object]:
    artifacts: Dict[str, object] = {"_paths": {}}
    families = list(COMPONENT_FAMILIES)
    if include_frozen_sentinel:
        families.append(MECHANISM_DIVERSE_HELDOUT)
    for family in families:
        path = run_dir / "noisy_policy_comparison_{}_{}.json".format(family, schema_profile)
        if path.exists():
            artifacts[family] = json.loads(path.read_text(encoding="utf-8"))
            artifacts["_paths"][family] = path
    return artifacts


def _profile_complete(
    artifacts: Mapping[str, object],
    *,
    include_frozen_sentinel: bool,
) -> bool:
    families = set(COMPONENT_FAMILIES)
    if include_frozen_sentinel:
        families.add(MECHANISM_DIVERSE_HELDOUT)
    return all(family in artifacts for family in families)


def _profile_comparisons(artifacts: Mapping[str, object]) -> Dict[str, object]:
    primary = {}
    descriptive = {}
    for family in COMPONENT_FAMILIES:
        artifact = artifacts.get(family)
        if not isinstance(artifact, dict):
            continue
        metric = PRIMARY_METRIC_BY_FAMILY[family]
        primary[family] = {
            comparator: comparison_payload(artifact, metric, comparator)
            for comparator in COMPARATORS
            if _policy_present(artifact, comparator)
        }
        descriptive[family] = {
            metric_name: {
                comparator: comparison_payload(artifact, metric_name, comparator)
                for comparator in COMPARATORS
                if _policy_present(artifact, comparator)
            }
            for metric_name in DESCRIPTIVE_METRICS
        }
    frozen = {}
    artifact = artifacts.get(MECHANISM_DIVERSE_HELDOUT)
    if isinstance(artifact, dict):
        for metric in FROZEN_PRIMARY_METRICS:
            frozen[metric] = {
                comparator: comparison_payload(artifact, metric, comparator)
                for comparator in COMPARATORS
                if _policy_present(artifact, comparator)
            }
    return {
        "primary_metric_comparisons": primary,
        "frozen_primary_comparisons": frozen,
        "descriptive_metric_comparisons": descriptive,
    }


def comparison_payload(
    artifact: Mapping[str, object],
    metric_name: str,
    comparator_policy_name: str,
) -> Dict[str, object]:
    cq_values = _metric_values_for_policy(artifact, CQ_POLICY, metric_name)
    comparator_values = _metric_values_for_policy(artifact, comparator_policy_name, metric_name)
    if len(cq_values) != len(comparator_values) or not cq_values:
        raise StopConditionError(
            "comparison_metric_unavailable",
            {
                "family": artifact.get("family"),
                "metric_name": metric_name,
                "comparator_policy_name": comparator_policy_name,
                "cq_count": len(cq_values),
                "comparator_count": len(comparator_values),
            },
        )
    if metric_name in HIGHER_IS_BETTER:
        deltas = [left - right for left, right in zip(cq_values, comparator_values)]
    elif metric_name in LOWER_IS_BETTER:
        deltas = [right - left for left, right in zip(cq_values, comparator_values)]
    else:
        raise StopConditionError("unknown_metric_direction", {"metric_name": metric_name})
    samples = paired_bootstrap_sample_means(deltas, resamples=10_000, seed=0)
    return {
        "metric_name": metric_name,
        "reference_policy_name": CQ_POLICY,
        "comparator_policy_name": comparator_policy_name,
        "scenario_count": len(deltas),
        "improvement_delta": paired_delta_point_estimate(deltas),
        "one_sided_95_lcb": one_sided_lower_confidence_bound(samples, confidence_level=0.95),
        "one_sided_95_ucb": one_sided_upper_confidence_bound(samples, confidence_level=0.95),
        "win": _is_win(paired_delta_point_estimate(deltas), one_sided_lower_confidence_bound(samples)),
        "loss": _is_loss(paired_delta_point_estimate(deltas), one_sided_upper_confidence_bound(samples)),
    }


def _bucket_decision(comparisons_by_profile: Mapping[str, Mapping[str, object]]) -> Dict[str, object]:
    primary = comparisons_by_profile.get("default")
    if primary is None:
        return {
            "bucket": "pending",
            "reason": "default primary cell artifacts are not complete",
        }
    primary_comparisons = primary["primary_metric_comparisons"]
    frozen = primary["frozen_primary_comparisons"]
    reflection_wins = [
        family
        for family in COUNTABLE_FAMILIES
        if primary_comparisons.get(family, {}).get(REFLECTION_POLICY, {}).get("win")
    ]
    reflection_directional_losses = [
        family
        for family in COUNTABLE_FAMILIES
        if primary_comparisons.get(family, {}).get(REFLECTION_POLICY, {}).get("improvement_delta", 0.0) < 0.0
    ]
    if len(reflection_directional_losses) >= 3:
        return {
            "bucket": "C",
            "reason": "CQ has at least three directional losses vs Reflection on countable primary metrics.",
            "directional_loss_note": BUCKET_C_DIRECTIONAL_LOSS_NOTE,
            "reflection_directional_losses": reflection_directional_losses,
        }
    frozen_mem0 = {
        metric: rows.get(MEM0_POLICY)
        for metric, rows in frozen.items()
        if isinstance(rows, dict)
    }
    if set(frozen_mem0) != set(FROZEN_PRIMARY_METRICS):
        return {
            "bucket": "pending",
            "reason": "frozen sentinel artifacts are not complete",
        }
    non_inferior = all(row["one_sided_95_lcb"] >= -0.05 for row in frozen_mem0.values())
    superior = any(
        row["improvement_delta"] >= 0.05 and row["one_sided_95_lcb"] > 0.0
        for row in frozen_mem0.values()
    )
    replicate = comparisons_by_profile.get("scenario_conditioned")
    contradictions = []
    if replicate is None:
        return {
            "bucket": "pending",
            "reason": "scenario_conditioned robustness replicate artifacts are not complete",
            "primary_reflection_wins": reflection_wins,
            "frozen_mem0_non_inferior": non_inferior,
            "frozen_mem0_superior": superior,
        }
    replicate_primary = replicate["primary_metric_comparisons"]
    for family in reflection_wins:
        row = replicate_primary.get(family, {}).get(REFLECTION_POLICY)
        if not row:
            continue
        if row["improvement_delta"] <= -0.05 or row["one_sided_95_ucb"] < 0.0:
            contradictions.append({"family": family, "replicate_row": row})
    if (
        len(reflection_wins) >= 4
        and non_inferior
        and superior
        and not contradictions
    ):
        return {
            "bucket": "A",
            "reason": "Primary cell clears the preregistered countable-family and frozen Mem0 gates without replicate contradiction.",
            "primary_reflection_wins": reflection_wins,
            "frozen_mem0_non_inferior": non_inferior,
            "frozen_mem0_superior": superior,
        }
    return {
        "bucket": "B",
        "reason": "Completed result survived D/C but failed at least one Bucket A condition.",
        "primary_reflection_wins": reflection_wins,
        "reflection_directional_losses": reflection_directional_losses,
        "directional_loss_note": BUCKET_C_DIRECTIONAL_LOSS_NOTE,
        "frozen_mem0_non_inferior": non_inferior,
        "frozen_mem0_superior": superior,
        "replicate_contradictions": contradictions,
    }


def _metric_values_for_policy(
    artifact: Mapping[str, object],
    policy_name: str,
    metric_name: str,
) -> List[float]:
    for policy in artifact.get("policies", []):
        if isinstance(policy, dict) and policy.get("policy_name") == policy_name:
            return [
                float(scenario["metrics"][metric_name])
                for scenario in policy.get("scenarios", [])
            ]
    return []


def _policy_present(artifact: Mapping[str, object], policy_name: str) -> bool:
    return any(
        isinstance(policy, dict) and policy.get("policy_name") == policy_name
        for policy in artifact.get("policies", [])
    )


def _is_win(point: float, lcb: float) -> bool:
    return point >= 0.10 and lcb > 0.0


def _is_loss(point: float, ucb: float) -> bool:
    return point <= -0.10 and ucb < 0.0


def write_run_manifest(
    *,
    run_artifact: Mapping[str, object],
    output_json: Path,
    output_csv: Path,
    runner_command: str,
    schema_profile: str,
    model_backend: object,
    preregistration_lock_sha: str,
    adapter_sha: str,
) -> Path:
    manifest_path = output_json.with_name("{}_manifest.json".format(output_json.stem))
    candidate_stream_hashes = [
        {
            "scenario_id": row["scenario_id"],
            "candidate_stream_sha256": row["candidate_stream_sha256"],
            "input_prediction_count": row.get("input_prediction_count", 0),
            "candidate_count": row["candidate_count"],
            "adapter_drop_count": row.get("adapter_drop_count", 0),
            "adapter_drop_rate": row.get("adapter_drop_rate", 0.0),
        }
        for row in run_artifact.get("candidate_stream_audit", [])
    ]
    manifest = {
        "manifest_version": 1,
        "run_name": output_json.stem,
        "archive_status": "regeneratable_only",
        "artifacts": [
            _artifact_manifest_row(output_json),
            _artifact_manifest_row(output_csv),
        ],
        "runner_command": runner_command,
        "git_commit": git_commit(),
        "working_tree_status": working_tree_status(),
        "working_tree_status_context": "manifest_write_after_outputs",
        "primary_model_tag": getattr(model_backend, "model_tag", LOCKED_MODEL_TAG),
        "primary_model_digest": getattr(model_backend, "resolved_digest", LOCKED_MODEL_DIGEST),
        "expected_primary_model_digest": getattr(model_backend, "expected_digest", LOCKED_MODEL_DIGEST),
        "ollama_server_version": getattr(model_backend, "ollama_server_version", ""),
        "prompt_sha256": LOCKED_PROMPT_SHA256,
        "schema_profile": schema_profile,
        "predictions_path": run_artifact.get("predictions_path"),
        "predictions_sha256": run_artifact.get("predictions_sha256"),
        "candidate_adapter_sha256": adapter_sha,
        "preregistration_lock_sha256": preregistration_lock_sha,
        "candidate_stream_sha256": candidate_stream_hashes,
    }
    _write_json(manifest_path, manifest)
    return manifest_path


def _artifact_manifest_row(path: Path) -> Dict[str, object]:
    return {
        "path": _repo_relative_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def dry_run_plan(
    *,
    predictions_dir: Path,
    schema_profile: str,
    include_frozen_sentinel: bool,
    policy_set: str,
) -> Dict[str, object]:
    families = list(COMPONENT_FAMILIES)
    if include_frozen_sentinel:
        families.append(MECHANISM_DIVERSE_HELDOUT)
    rows = []
    for family in families:
        scenario_count = FROZEN_SENTINEL_SCENARIO_COUNT if family == MECHANISM_DIVERSE_HELDOUT else PRIMARY_SCENARIO_COUNT
        template_mix = "frozen" if family == MECHANISM_DIVERSE_HELDOUT else "heldout"
        try:
            paths = prediction_cell_paths(
                predictions_dir=predictions_dir,
                family=family,
                schema_profile=schema_profile,
            )
            status = "ready"
            path_payload = {
                "summary": _repo_relative_path(paths.summary),
                "manifest": _repo_relative_path(paths.manifest),
                "predictions": _repo_relative_path(paths.predictions),
                "component_eval": _repo_relative_path(paths.component_eval),
            }
        except NoisyPolicyComparisonError as error:
            status = "blocked"
            path_payload = {"error": str(error)}
        rows.append(
            {
                "family": family,
                "scenario_count": scenario_count,
                "template_mix": template_mix,
                "schema_profile": schema_profile,
                "status": status,
                "paths": path_payload,
            }
        )
    pin_status = "ready" if ADAPTER_PIN_PATH.exists() else "missing"
    return {
        "mode": "dry_run",
        "policy_comparison_unlocked": "not_evaluated",
        "primary_model_tag": LOCKED_MODEL_TAG,
        "primary_model_digest": LOCKED_MODEL_DIGEST,
        "prompt_sha256": LOCKED_PROMPT_SHA256,
        "schema_profile": schema_profile,
        "policy_set": policy_set,
        "adapter_pin_status": pin_status,
        "rows": rows,
    }


def write_stop_report(output_dir: Path, error: StopConditionError) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "{}_{}.json".format(
        STOP_REPORT_PREFIX,
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
    )
    _write_json(
        path,
        {
            "mode": "noisy_policy_comparison_stop",
            "reason": error.reason,
            "details": error.details,
            "policy_comparison_unlocked": False,
        },
    )
    return path


def runner_command_for_invocation(argv: Optional[Sequence[str]]) -> str:
    args = sys.argv[1:] if argv is None else argv
    return shlex.join(
        [
            "python3",
            _repo_relative_path(Path(__file__)),
            *[str(arg) for arg in args],
        ]
    )


def _repo_relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--predictions-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--primary-model-tag",
        required=True,
        choices=[LOCKED_MODEL_TAG],
    )
    parser.add_argument(
        "--schema-profile",
        required=True,
        choices=["default", "scenario_conditioned"],
    )
    parser.add_argument("--include-frozen-sentinel", action="store_true")
    parser.add_argument(
        "--policy-set",
        choices=POLICY_SET_CHOICES,
        default=POLICY_SET_PHASE_2_5,
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    runner_command = runner_command_for_invocation(argv)
    if args.dry_run:
        print(
            json.dumps(
                dry_run_plan(
                    predictions_dir=args.predictions_dir,
                    schema_profile=args.schema_profile,
                    include_frozen_sentinel=args.include_frozen_sentinel,
                    policy_set=args.policy_set,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    try:
        summary_path = run_noisy_policy_comparison(
            output_dir=args.output_dir,
            run_dir=args.run_dir,
            predictions_dir=args.predictions_dir,
            primary_model_tag=args.primary_model_tag,
            schema_profile=args.schema_profile,
            include_frozen_sentinel=args.include_frozen_sentinel,
            policy_set=args.policy_set,
            runner_command=runner_command,
        )
    except (NoisyPolicyComparisonError, StopConditionError, GateRuntimeError, ValueError) as error:
        reason = getattr(error, "reason", error.__class__.__name__)
        details = getattr(error, "details", {"message": str(error)})
        report_path = write_stop_report(args.output_dir, StopConditionError(reason, details))
        print("Noisy policy comparison stopped: {}. Report: {}".format(reason, report_path))
        return 1
    print("Wrote noisy policy comparison summary to {}".format(summary_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
