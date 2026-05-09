#!/usr/bin/env python3
"""Diagnostic-only noisy component matrix runner.

This script broadens saved local-model component artifacts while keeping Phase A
separate from gate decisions and policy comparisons. It refuses to treat small
matrix rows as statistical verdicts, blocks prompt/determinism regressions, and
only reuses cached artifacts when their provenance matches the current run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cq.eval.component_eval import (  # noqa: E402
    QUALITY_GATES,
    build_component_eval_artifact,
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


DEFAULT_DECODING_JSON = '{"temperature": 0, "seed": 7, "top_p": 1}'
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_MODEL_COMMAND = "{} {}".format(
    shlex.quote(sys.executable),
    shlex.quote(str(REPO_ROOT / "scripts" / "ollama_component_extractor.py")),
)
GENERAL_PROMPT_PATH = REPO_ROOT / "prompts" / "component_extractor_general_v1.txt"
DEFAULT_GENERAL_PROMPT_LABEL = "general_v1"
FORCED_PROMPT_PATH = REPO_ROOT / "prompts" / "forced_contradiction_component_extractor_v1.txt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "results"
STOP_REPORT_PREFIX = "component_scoring_matrix_phase_a_stop"
ROW_SET_FULL = "full"
ROW_SET_PROMPT_SCHEMA_DIAGNOSTIC = "prompt_schema_diagnostic"
ROW_SETS = (ROW_SET_FULL, ROW_SET_PROMPT_SCHEMA_DIAGNOSTIC)
SUMMARY_PREFIX = "component_scoring_matrix"
EPSILON = 1e-12

GATE_METRICS: Tuple[str, ...] = tuple(QUALITY_GATES.keys())
FAILURE_BUCKETS: Tuple[str, ...] = (
    "scenario_error",
    "candidate_miss_or_extra",
    "contradiction_edge_drift",
    "scope_key_or_level_drift",
    "canonical_split_or_merge",
    "claim_type_drift",
    "unmapped",
)
BOUNDARY_SCOPE_EXCLUSIONS = frozenset(
    (
        ("preference_drift_002", "preference_drift_002-event-4", "scope_key"),
        ("preference_drift_002", "preference_drift_002-event-4", "scope_level"),
        ("preference_drift_004", "preference_drift_004-event-4", "scope_key"),
        ("preference_drift_004", "preference_drift_004-event-4", "scope_level"),
    )
)
ACCEPTANCE_SCOPE_DRIFT_MAX_EXCLUSIVE = 4
ACCEPTANCE_CANONICAL_DRIFT_MAX_EXCLUSIVE = 3


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    artifact_label: str
    role: str


QWEN_7B_Q4KM = ModelSpec(
    model_id="qwen2.5:7b-instruct-q4_K_M",
    artifact_label="qwen2_5_7b_q4km",
    role="floor",
)
QWEN_32B_Q4KM = ModelSpec(
    model_id="qwen2.5:32b-instruct-q4_K_M",
    artifact_label="qwen2_5_32b_q4km",
    role="headroom",
)


@dataclass(frozen=True)
class MatrixRow:
    family: str
    template_mix: str
    scenarios: int
    model: ModelSpec
    prompt_label: str
    prompt_path: Path

    @property
    def artifact_stem(self) -> str:
        return "{}_local_extractor_{}_{}_{}_{}".format(
            self.family,
            self.model.artifact_label,
            self.prompt_label,
            self.template_mix,
            self.model.role,
        )


@dataclass(frozen=True)
class ArtifactPaths:
    predictions: Path
    component_eval: Path


@dataclass(frozen=True)
class RowResult:
    row: MatrixRow
    paths: ArtifactPaths
    component_artifact: Dict[str, object]
    reused: bool


class StopConditionError(RuntimeError):
    def __init__(self, reason: str, details: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details


def floor_diagnostic_rows(
    prompt_path: Path = GENERAL_PROMPT_PATH,
    prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[MatrixRow]:
    return [
        MatrixRow(family, mix, scenarios, QWEN_7B_Q4KM, prompt_label, prompt_path)
        for family, mix, scenarios in _diagnostic_family_rows()
    ]


def headroom_diagnostic_rows(
    prompt_path: Path = GENERAL_PROMPT_PATH,
    prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[MatrixRow]:
    return [
        MatrixRow(family, mix, scenarios, QWEN_32B_Q4KM, prompt_label, prompt_path)
        for family, mix, scenarios in _headroom_family_rows()
    ]


def prompt_schema_diagnostic_floor_rows(
    prompt_path: Path = GENERAL_PROMPT_PATH,
    prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[MatrixRow]:
    return [
        MatrixRow(family, mix, scenarios, QWEN_7B_Q4KM, prompt_label, prompt_path)
        for family, mix, scenarios in _prompt_schema_diagnostic_floor_family_rows()
    ]


def prompt_schema_diagnostic_headroom_rows(
    prompt_path: Path = GENERAL_PROMPT_PATH,
    prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[MatrixRow]:
    return [
        MatrixRow(family, mix, scenarios, QWEN_32B_Q4KM, prompt_label, prompt_path)
        for family, mix, scenarios in _prompt_schema_diagnostic_headroom_family_rows()
    ]


def regression_rows(
    model: ModelSpec,
    *,
    forced_prompt_path: Path = FORCED_PROMPT_PATH,
    general_prompt_path: Path = GENERAL_PROMPT_PATH,
    general_prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> Tuple[MatrixRow, MatrixRow]:
    return (
        MatrixRow(
            FORCED_CONTRADICTION,
            "mixed",
            6,
            model,
            "forced_v1",
            forced_prompt_path,
        ),
        MatrixRow(
            FORCED_CONTRADICTION,
            "mixed",
            6,
            model,
            general_prompt_label,
            general_prompt_path,
        ),
    )


def artifact_paths(row: MatrixRow, output_dir: Path) -> ArtifactPaths:
    return ArtifactPaths(
        predictions=output_dir / "{}_predictions.json".format(row.artifact_stem),
        component_eval=output_dir / "{}_component_eval.json".format(row.artifact_stem),
    )


def legacy_forced_prompt_paths(row: MatrixRow, output_dir: Path) -> Optional[ArtifactPaths]:
    # Back-compat shim for operator-local artifacts from the pre-matrix
    # forced-contradiction smoke run; fresh checkouts will not have these.
    if row.family != FORCED_CONTRADICTION or row.template_mix != "mixed" or row.scenarios != 6:
        return None
    if row.prompt_label != "forced_v1":
        return None
    if row.model == QWEN_7B_Q4KM:
        return ArtifactPaths(
            predictions=output_dir / "forced_contradiction_local_extractor_qwen7b_predictions.json",
            component_eval=output_dir / "forced_contradiction_local_extractor_qwen7b_component_eval.json",
        )
    if row.model == QWEN_32B_Q4KM:
        return ArtifactPaths(
            predictions=output_dir / "forced_contradiction_local_extractor_qwen32b_headroom_predictions.json",
            component_eval=output_dir / "forced_contradiction_local_extractor_qwen32b_headroom_component_eval.json",
        )
    return None


def run_or_reuse_row(
    row: MatrixRow,
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    force: bool = False,
    legacy_paths: Optional[ArtifactPaths] = None,
) -> RowResult:
    paths = legacy_paths if legacy_paths and not force and _paths_exist(legacy_paths) else artifact_paths(row, output_dir)
    if not force and _paths_exist(paths) and cached_artifacts_match_row(
        row,
        paths,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
    ):
        return RowResult(row=row, paths=paths, component_artifact=_read_json(paths.component_eval), reused=True)
    return run_row(
        row,
        output_dir=output_dir,
        model_command=model_command,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
    )


def cached_artifacts_match_row(
    row: MatrixRow,
    paths: ArtifactPaths,
    *,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> bool:
    if not _paths_exist(paths):
        return False
    try:
        mismatches = cached_artifact_provenance_mismatches(
            row,
            paths,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return not mismatches


def cached_artifact_provenance_mismatches(
    row: MatrixRow,
    paths: ArtifactPaths,
    *,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> List[Dict[str, object]]:
    predictions_payload = _read_json(paths.predictions)
    component_payload = _read_json(paths.component_eval)
    expected_decoding = _parse_decoding_json(decoding_json)
    expected_prompt_sha = prompt_template_sha256(row.prompt_path)
    checks = [
        ("predictions.family", predictions_payload.get("family"), row.family),
        ("predictions.template_mix", predictions_payload.get("template_mix"), row.template_mix),
        ("predictions.requested_scenario_count", predictions_payload.get("requested_scenario_count"), row.scenarios),
        ("predictions.scenario_count", predictions_payload.get("scenario_count"), row.scenarios),
        ("predictions.mode", predictions_payload.get("mode"), MODEL_MODE),
        ("predictions.input_contract", predictions_payload.get("input_contract"), "transcript_only"),
        ("predictions.model_id", predictions_payload.get("model_id"), row.model.model_id),
        ("predictions.prompt_template_sha256", predictions_payload.get("prompt_template_sha256"), expected_prompt_sha),
        ("predictions.decoding_params", predictions_payload.get("decoding_params"), expected_decoding),
        (
            "predictions.per_scenario_timeout_seconds",
            predictions_payload.get("per_scenario_timeout_seconds"),
            per_scenario_timeout_seconds,
        ),
        ("component.family", component_payload.get("family"), row.family),
        ("component.template_mix", component_payload.get("template_mix"), row.template_mix),
        ("component.requested_scenario_count", component_payload.get("requested_scenario_count"), row.scenarios),
        ("component.scenario_count", component_payload.get("scenario_count"), row.scenarios),
    ]
    mismatches = []
    for field, observed, expected in checks:
        if not _values_match(observed, expected):
            mismatches.append(
                {
                    "field": field,
                    "observed": observed,
                    "expected": expected,
                    "predictions_path": str(paths.predictions),
                    "component_eval_path": str(paths.component_eval),
                }
            )
    return mismatches


def prompt_template_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def run_row(
    row: MatrixRow,
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> RowResult:
    paths = artifact_paths(row, output_dir)
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
    component_artifact = build_component_eval_artifact(
        family=row.family,
        scenario_count=row.scenarios,
        template_mix=row.template_mix,
        predictions_by_scenario=predictions,
        scenario_errors=scenario_errors,
    )
    _write_json(paths.component_eval, component_artifact)
    return RowResult(row=row, paths=paths, component_artifact=component_artifact, reused=False)


def run_prompt_regression(
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    general_prompt_path: Path = GENERAL_PROMPT_PATH,
    general_prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
    force: bool = False,
) -> None:
    all_violations: List[Dict[str, object]] = []
    for model in (QWEN_7B_Q4KM, QWEN_32B_Q4KM):
        baseline_row, general_row = regression_rows(
            model,
            general_prompt_path=general_prompt_path,
            general_prompt_label=general_prompt_label,
        )
        baseline = run_or_reuse_row(
            baseline_row,
            output_dir=output_dir,
            model_command=model_command,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
            force=force,
            legacy_paths=legacy_forced_prompt_paths(baseline_row, output_dir),
        )
        general = run_or_reuse_row(
            general_row,
            output_dir=output_dir,
            model_command=model_command,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
            force=force,
        )
        baseline_correct = scenario_correctness_by_id(
            baseline_row.family,
            baseline_row.scenarios,
            baseline_row.template_mix,
            baseline.paths.predictions,
        )
        general_correct = scenario_correctness_by_id(
            general_row.family,
            general_row.scenarios,
            general_row.template_mix,
            general.paths.predictions,
        )
        violations = regression_violations(
            model=model,
            baseline_artifact=baseline.component_artifact,
            general_artifact=general.component_artifact,
            baseline_correctness=baseline_correct,
            general_correctness=general_correct,
        )
        all_violations.extend(violations)
    if all_violations:
        raise StopConditionError("prompt_regression_failed", all_violations)


def regression_violations(
    *,
    model: ModelSpec,
    baseline_artifact: Dict[str, object],
    general_artifact: Dict[str, object],
    baseline_correctness: Dict[str, bool],
    general_correctness: Dict[str, bool],
) -> List[Dict[str, object]]:
    violations: List[Dict[str, object]] = []
    baseline_metrics = _mapping(baseline_artifact.get("metrics"))
    general_metrics = _mapping(general_artifact.get("metrics"))
    for metric_name in GATE_METRICS:
        baseline_value = baseline_metrics.get(metric_name)
        general_value = general_metrics.get(metric_name)
        if not _is_number(baseline_value):
            continue
        if not _is_number(general_value):
            violations.append(
                {
                    "model_id": model.model_id,
                    "type": "metric_became_undefined",
                    "metric": metric_name,
                    "baseline": baseline_value,
                    "general": general_value,
                }
            )
            continue
        if float(general_value) + EPSILON < float(baseline_value):
            violations.append(
                {
                    "model_id": model.model_id,
                    "type": "metric_regression",
                    "metric": metric_name,
                    "baseline": baseline_value,
                    "general": general_value,
                }
            )
    if int(general_artifact.get("scenario_error_count") or 0) > 0:
        violations.append(
            {
                "model_id": model.model_id,
                "type": "scenario_errors_introduced",
                "scenario_error_count": general_artifact.get("scenario_error_count"),
            }
        )
    violations.extend(
        scenario_regression_violations(
            model=model,
            baseline_correctness=baseline_correctness,
            general_correctness=general_correctness,
        )
    )
    return violations


def scenario_regression_violations(
    *,
    model: ModelSpec,
    baseline_correctness: Dict[str, bool],
    general_correctness: Dict[str, bool],
) -> List[Dict[str, object]]:
    violations = []
    for scenario_id, was_correct in sorted(baseline_correctness.items()):
        if was_correct and not general_correctness.get(scenario_id, False):
            violations.append(
                {
                    "model_id": model.model_id,
                    "type": "scenario_correctness_regression",
                    "scenario_id": scenario_id,
                }
            )
    return violations


def scenario_correctness_by_id(
    family: str,
    scenario_count: int,
    template_mix: str,
    predictions_path: Path,
) -> Dict[str, bool]:
    predictions_by_scenario = load_predictions_by_scenario(predictions_path)
    scenario_errors = load_scenario_errors(predictions_path)
    scenarios = generate_scenarios(family, scenario_count, template_mix)
    correctness = {}
    for scenario in scenarios:
        scenario_error = scenario_errors.get(scenario.scenario_id)
        one_scenario_errors = (
            {scenario.scenario_id: scenario_error}
            if scenario_error is not None
            else {}
        )
        evaluation = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions_by_scenario.get(scenario.scenario_id, [])},
            scenario_errors=one_scenario_errors,
        )
        correctness[scenario.scenario_id] = scenario_evaluation_is_correct(
            evaluation,
            has_scenario_error=scenario_error is not None,
        )
    return correctness


def scenario_evaluation_is_correct(
    evaluation: Dict[str, object],
    *,
    has_scenario_error: bool,
) -> bool:
    if has_scenario_error:
        return False
    if int(evaluation.get("failure_example_count") or 0) != 0:
        return False
    metrics = _mapping(evaluation.get("metrics"))
    quality_gates = _mapping(evaluation.get("quality_gates"))
    for metric_name in GATE_METRICS:
        gate = _mapping(quality_gates.get(metric_name))
        if gate.get("status") == "not_applicable":
            continue
        value = metrics.get(metric_name)
        if not _is_number(value) or float(value) != 1.0:
            return False
    return True


def run_determinism_check(
    *,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    general_prompt_path: Path = GENERAL_PROMPT_PATH,
    general_prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> None:
    row = MatrixRow(
        FORCED_CONTRADICTION,
        "mixed",
        6,
        QWEN_7B_Q4KM,
        general_prompt_label,
        general_prompt_path,
    )
    with tempfile.TemporaryDirectory(prefix="cq_component_matrix_determinism_a_") as first_dir:
        with tempfile.TemporaryDirectory(prefix="cq_component_matrix_determinism_b_") as second_dir:
            first = run_row(
                row,
                output_dir=Path(first_dir),
                model_command=model_command,
                decoding_json=decoding_json,
                per_scenario_timeout_seconds=per_scenario_timeout_seconds,
            )
            second = run_row(
                row,
                output_dir=Path(second_dir),
                model_command=model_command,
                decoding_json=decoding_json,
                per_scenario_timeout_seconds=per_scenario_timeout_seconds,
            )
            first_payload = _read_json(first.paths.predictions)
            second_payload = _read_json(second.paths.predictions)
            if normalized_json_bytes(first_payload) != normalized_json_bytes(second_payload):
                raise StopConditionError(
                    "determinism_check_failed",
                    {
                        "family": row.family,
                        "template_mix": row.template_mix,
                        "scenarios": row.scenarios,
                        "model_id": row.model.model_id,
                        "prompt_label": row.prompt_label,
                        "comparison": 'json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")',
                        "array_order": "preserved",
                    },
                )


def normalized_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def run_diagnostic_matrix(
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    row_set: str = ROW_SET_FULL,
    general_prompt_path: Path = GENERAL_PROMPT_PATH,
    general_prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
    force: bool = False,
) -> List[RowResult]:
    results = []
    for row in _diagnostic_rows_for_row_set(
        row_set,
        prompt_path=general_prompt_path,
        prompt_label=general_prompt_label,
    ):
        results.append(
            run_or_reuse_row(
                row,
                output_dir=output_dir,
                model_command=model_command,
                decoding_json=decoding_json,
                per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                force=force,
            )
        )
    return results


def dry_run_plan(
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    row_set: str = ROW_SET_FULL,
    general_prompt_path: Path = GENERAL_PROMPT_PATH,
    general_prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> Dict[str, object]:
    rows = []
    for row in _all_planned_rows(
        row_set,
        general_prompt_path=general_prompt_path,
        general_prompt_label=general_prompt_label,
    ):
        rows.append(
            {
                "family": row.family,
                "template_mix": row.template_mix,
                "scenarios": row.scenarios,
                "model_id": row.model.model_id,
                "model_role": row.model.role,
                "prompt_label": row.prompt_label,
                "paths": {
                    "predictions": str(artifact_paths(row, output_dir).predictions),
                    "component_eval": str(artifact_paths(row, output_dir).component_eval),
                },
                "commands": equivalent_commands(
                    row,
                    output_dir=output_dir,
                    model_command=model_command,
                    decoding_json=decoding_json,
                    per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                ),
            }
        )
    return {
        "mode": "dry_run",
        "phase": "diagnostic_noisy_component_matrix",
        "row_set": row_set,
        "general_prompt_path": str(general_prompt_path),
        "general_prompt_label": general_prompt_label,
        "statistical_gate_verdicts": "not_issued",
        "rows": rows,
    }


def equivalent_commands(
    row: MatrixRow,
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> Dict[str, str]:
    paths = artifact_paths(row, output_dir)
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
    return {
        "extract": shlex.join(extract),
        "score": shlex.join(score),
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
            "mode": "diagnostic_noisy_component_matrix_stop",
            "reason": error.reason,
            "details": error.details,
            "phase_b_policy_comparison_unlocked": False,
        },
    )
    return path


def write_diagnostic_summary(
    *,
    output_dir: Path,
    row_set: str,
    general_prompt_path: Path,
    general_prompt_label: str,
    results: Sequence[RowResult],
) -> Path:
    path = diagnostic_summary_path(
        output_dir,
        row_set=row_set,
        general_prompt_label=general_prompt_label,
    )
    _write_json(
        path,
        diagnostic_summary_payload(
            row_set=row_set,
            general_prompt_path=general_prompt_path,
            general_prompt_label=general_prompt_label,
            results=results,
        ),
    )
    return path


def diagnostic_summary_path(
    output_dir: Path,
    *,
    row_set: str,
    general_prompt_label: str,
) -> Path:
    return output_dir / "{}_{}_{}_summary.json".format(
        SUMMARY_PREFIX,
        _slug_for_filename(row_set),
        _slug_for_filename(general_prompt_label),
    )


def diagnostic_summary_payload(
    *,
    row_set: str,
    general_prompt_path: Path,
    general_prompt_label: str,
    results: Sequence[RowResult],
) -> Dict[str, object]:
    rows = []
    raw_by_role: Dict[str, Dict[str, int]] = {}
    exclusions_by_role: Dict[str, Dict[str, int]] = {}
    adjusted_by_role: Dict[str, Dict[str, int]] = {}
    scenario_error_count_by_role: Dict[str, int] = {}
    boundary_exclusion_records = []

    for result in results:
        raw_counts = _empty_bucket_counts()
        exclusion_counts = _empty_bucket_counts()
        row_exclusions = []
        for example in _failure_examples(result.component_artifact):
            bucket = failure_bucket(example)
            raw_counts[bucket] = raw_counts.get(bucket, 0) + 1
            if is_boundary_scope_exclusion(result.row, example):
                exclusion_counts[bucket] = exclusion_counts.get(bucket, 0) + 1
                exclusion_record = _boundary_exclusion_record(result.row, example, bucket)
                row_exclusions.append(exclusion_record)
                boundary_exclusion_records.append(exclusion_record)

        adjusted_counts = {
            bucket: raw_counts.get(bucket, 0) - exclusion_counts.get(bucket, 0)
            for bucket in FAILURE_BUCKETS
        }
        role = result.row.model.role
        _add_bucket_counts(raw_by_role, role, raw_counts)
        _add_bucket_counts(exclusions_by_role, role, exclusion_counts)
        _add_bucket_counts(adjusted_by_role, role, adjusted_counts)
        scenario_error_count = int(result.component_artifact.get("scenario_error_count") or 0)
        scenario_error_count_by_role[role] = (
            scenario_error_count_by_role.get(role, 0) + scenario_error_count
        )
        rows.append(
            {
                "family": result.row.family,
                "template_mix": result.row.template_mix,
                "scenarios": result.row.scenarios,
                "model_id": result.row.model.model_id,
                "model_role": role,
                "prompt_label": result.row.prompt_label,
                "reused": result.reused,
                "paths": {
                    "predictions": str(result.paths.predictions),
                    "component_eval": str(result.paths.component_eval),
                },
                "scenario_error_count": scenario_error_count,
                "failure_example_count": int(
                    result.component_artifact.get("failure_example_count") or 0
                ),
                "raw_bucket_counts": raw_counts,
                "boundary_exclusions": row_exclusions,
                "boundary_exclusion_bucket_counts": exclusion_counts,
                "adjusted_bucket_counts": adjusted_counts,
            }
        )

    headroom_adjusted = _bucket_counts_for_role(adjusted_by_role, QWEN_32B_Q4KM.role)
    headroom_scenario_errors = scenario_error_count_by_role.get(QWEN_32B_Q4KM.role, 0)
    total_scenario_errors = sum(scenario_error_count_by_role.values())
    scope_drift_count = headroom_adjusted["scope_key_or_level_drift"]
    canonical_count = headroom_adjusted["canonical_split_or_merge"]
    acceptance = {
        "phase_a_regression_required_before_rows": True,
        "policy_comparison_unlocked": False,
        "scenario_errors_absent": total_scenario_errors == 0,
        "scenario_error_count": total_scenario_errors,
        "headroom_scenario_error_count": headroom_scenario_errors,
        "adjusted_32b_scope_key_or_level_drift": scope_drift_count,
        "adjusted_32b_canonical_split_or_merge": canonical_count,
        "scope_key_or_level_drift_threshold_exclusive": ACCEPTANCE_SCOPE_DRIFT_MAX_EXCLUSIVE,
        "canonical_split_or_merge_threshold_exclusive": ACCEPTANCE_CANONICAL_DRIFT_MAX_EXCLUSIVE,
        "scope_key_or_level_drift_passed": (
            scope_drift_count < ACCEPTANCE_SCOPE_DRIFT_MAX_EXCLUSIVE
        ),
        "canonical_split_or_merge_passed": (
            canonical_count < ACCEPTANCE_CANONICAL_DRIFT_MAX_EXCLUSIVE
        ),
    }
    acceptance["branch_resolved"] = (
        acceptance["scenario_errors_absent"]
        and acceptance["scope_key_or_level_drift_passed"]
        and acceptance["canonical_split_or_merge_passed"]
    )
    return {
        "mode": "diagnostic_noisy_component_matrix_summary",
        "row_set": row_set,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "general_prompt_path": str(general_prompt_path),
        "general_prompt_label": general_prompt_label,
        "general_prompt_sha256": prompt_template_sha256(general_prompt_path),
        "statistical_gate_verdicts": "not_issued",
        "policy_comparison_unlocked": False,
        "boundary_exclusion_rule": {
            "applies_to_model_role": QWEN_32B_Q4KM.role,
            "bucket": "scope_key_or_level_drift",
            "excluded_examples": [
                {
                    "scenario_id": scenario_id,
                    "event_id": event_id,
                    "component": component,
                }
                for scenario_id, event_id, component in sorted(BOUNDARY_SCOPE_EXCLUSIONS)
            ],
        },
        "raw_bucket_counts_by_model_role": raw_by_role,
        "boundary_exclusion_bucket_counts_by_model_role": exclusions_by_role,
        "adjusted_bucket_counts_by_model_role": adjusted_by_role,
        "scenario_error_count_by_model_role": scenario_error_count_by_role,
        "boundary_exclusions": boundary_exclusion_records,
        "acceptance": acceptance,
        "rows": rows,
    }


def failure_bucket(example: Dict[str, object]) -> str:
    component = example.get("component")
    failure_type = example.get("failure_type")
    if component == "scenario" or failure_type == "scenario_error":
        return "scenario_error"
    if component == "candidate_detection":
        return "candidate_miss_or_extra"
    if component == "contradiction":
        return "contradiction_edge_drift"
    if component in ("scope_key", "scope_level"):
        return "scope_key_or_level_drift"
    if component == "canonicalization":
        return "canonical_split_or_merge"
    if component == "claim_type":
        return "claim_type_drift"
    return "unmapped"


def is_boundary_scope_exclusion(row: MatrixRow, example: Dict[str, object]) -> bool:
    if row.model != QWEN_32B_Q4KM:
        return False
    if row.family != PREFERENCE_DRIFT or row.template_mix != "heldout":
        return False
    return (
        str(example.get("scenario_id") or ""),
        str(example.get("event_id") or ""),
        str(example.get("component") or ""),
    ) in BOUNDARY_SCOPE_EXCLUSIONS


def _boundary_exclusion_record(
    row: MatrixRow,
    example: Dict[str, object],
    bucket: str,
) -> Dict[str, object]:
    return {
        "family": row.family,
        "template_mix": row.template_mix,
        "model_id": row.model.model_id,
        "model_role": row.model.role,
        "scenario_id": example.get("scenario_id"),
        "template_id": example.get("template_id"),
        "event_id": example.get("event_id"),
        "component": example.get("component"),
        "failure_type": example.get("failure_type"),
        "bucket": bucket,
        "reason": "pre_enumerated_preference_drift_one_off_scope_boundary",
    }


def _failure_examples(component_artifact: Dict[str, object]) -> List[Dict[str, object]]:
    examples = component_artifact.get("failure_examples") or []
    return [example for example in examples if isinstance(example, dict)]


def _empty_bucket_counts() -> Dict[str, int]:
    return {bucket: 0 for bucket in FAILURE_BUCKETS}


def _add_bucket_counts(
    grouped_counts: Dict[str, Dict[str, int]],
    role: str,
    counts: Dict[str, int],
) -> None:
    if role not in grouped_counts:
        grouped_counts[role] = _empty_bucket_counts()
    for bucket in FAILURE_BUCKETS:
        grouped_counts[role][bucket] = grouped_counts[role].get(bucket, 0) + counts.get(bucket, 0)


def _bucket_counts_for_role(
    grouped_counts: Dict[str, Dict[str, int]],
    role: str,
) -> Dict[str, int]:
    return grouped_counts.get(role, _empty_bucket_counts())


def _diagnostic_family_rows() -> Tuple[Tuple[str, str, int], ...]:
    return (
        (FORCED_CONTRADICTION, "mixed", 6),
        (FORCED_CONTRADICTION, "heldout", 4),
        (SCOPE_CONTAMINATION, "mixed", 8),
        (SCOPE_CONTAMINATION, "heldout", 4),
        (PREFERENCE_DRIFT, "mixed", 6),
        (PREFERENCE_DRIFT, "heldout", 4),
        (USEFUL_PENDING_MEMORY, "mixed", 4),
        (USEFUL_PENDING_MEMORY, "heldout", 4),
        (FALSE_CORROBORATION, "mixed", 4),
        (FALSE_CORROBORATION, "heldout", 4),
        (MEMORY_POISONING, "mixed", 10),
        (MEMORY_POISONING, "heldout", 10),
        (MECHANISM_DIVERSE_HELDOUT, "frozen", 3),
    )


def _headroom_family_rows() -> Tuple[Tuple[str, str, int], ...]:
    return (
        (FORCED_CONTRADICTION, "heldout", 4),
        (SCOPE_CONTAMINATION, "heldout", 4),
        (PREFERENCE_DRIFT, "heldout", 4),
        (USEFUL_PENDING_MEMORY, "heldout", 4),
        (FALSE_CORROBORATION, "heldout", 4),
        (MEMORY_POISONING, "heldout", 10),
        (MECHANISM_DIVERSE_HELDOUT, "frozen", 3),
    )


def _prompt_schema_diagnostic_floor_family_rows() -> Tuple[Tuple[str, str, int], ...]:
    return (
        (PREFERENCE_DRIFT, "mixed", 6),
        (PREFERENCE_DRIFT, "heldout", 4),
        (SCOPE_CONTAMINATION, "mixed", 8),
        (SCOPE_CONTAMINATION, "heldout", 4),
        (MEMORY_POISONING, "mixed", 10),
        (MEMORY_POISONING, "heldout", 10),
        (FALSE_CORROBORATION, "heldout", 4),
        (MECHANISM_DIVERSE_HELDOUT, "frozen", 3),
    )


def _prompt_schema_diagnostic_headroom_family_rows() -> Tuple[Tuple[str, str, int], ...]:
    return (
        (PREFERENCE_DRIFT, "heldout", 4),
        (SCOPE_CONTAMINATION, "heldout", 4),
        (MECHANISM_DIVERSE_HELDOUT, "frozen", 3),
    )


def _diagnostic_rows_for_row_set(
    row_set: str,
    *,
    prompt_path: Path,
    prompt_label: str,
) -> List[MatrixRow]:
    if row_set == ROW_SET_FULL:
        return floor_diagnostic_rows(prompt_path, prompt_label) + headroom_diagnostic_rows(
            prompt_path,
            prompt_label,
        )
    if row_set == ROW_SET_PROMPT_SCHEMA_DIAGNOSTIC:
        return prompt_schema_diagnostic_floor_rows(
            prompt_path,
            prompt_label,
        ) + prompt_schema_diagnostic_headroom_rows(prompt_path, prompt_label)
    raise ValueError("Unsupported row set: {}".format(row_set))


def _all_planned_rows(
    row_set: str = ROW_SET_FULL,
    *,
    general_prompt_path: Path = GENERAL_PROMPT_PATH,
    general_prompt_label: str = DEFAULT_GENERAL_PROMPT_LABEL,
) -> List[MatrixRow]:
    rows: List[MatrixRow] = []
    for model in (QWEN_7B_Q4KM, QWEN_32B_Q4KM):
        rows.extend(
            regression_rows(
                model,
                general_prompt_path=general_prompt_path,
                general_prompt_label=general_prompt_label,
            )
        )
    rows.extend(
        _diagnostic_rows_for_row_set(
            row_set,
            prompt_path=general_prompt_path,
            prompt_label=general_prompt_label,
        )
    )
    return rows


def _paths_exist(paths: ArtifactPaths) -> bool:
    return paths.predictions.exists() and paths.component_eval.exists()


def _parse_decoding_json(decoding_json: str) -> Dict[str, object]:
    payload = json.loads(decoding_json or "{}")
    if not isinstance(payload, dict):
        raise ValueError("decoding JSON must be an object")
    return payload


def _values_match(observed: object, expected: object) -> bool:
    if _is_number(observed) and _is_number(expected):
        return abs(float(observed) - float(expected)) <= EPSILON
    return observed == expected


def _read_json(path: Path) -> Dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("{} did not contain a JSON object".format(path))
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mapping(value: object) -> Dict[str, object]:
    return value if isinstance(value, dict) else {}


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _slug_for_filename(value: str) -> str:
    slug = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    return slug.strip("_") or "default"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the diagnostic-only noisy component scoring matrix."
    )
    parser.add_argument("--model-command", default=DEFAULT_MODEL_COMMAND)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--decoding-json", default=DEFAULT_DECODING_JSON)
    parser.add_argument("--per-scenario-timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--row-set", choices=ROW_SETS, default=ROW_SET_FULL)
    parser.add_argument("--general-prompt-path", default=str(GENERAL_PROMPT_PATH))
    parser.add_argument("--general-prompt-label", default=DEFAULT_GENERAL_PROMPT_LABEL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    general_prompt_path = Path(args.general_prompt_path)
    if args.dry_run:
        print(
            json.dumps(
                dry_run_plan(
                    output_dir=output_dir,
                    model_command=args.model_command,
                    decoding_json=args.decoding_json,
                    per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
                    row_set=args.row_set,
                    general_prompt_path=general_prompt_path,
                    general_prompt_label=args.general_prompt_label,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    try:
        run_prompt_regression(
            output_dir=output_dir,
            model_command=args.model_command,
            decoding_json=args.decoding_json,
            per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
            general_prompt_path=general_prompt_path,
            general_prompt_label=args.general_prompt_label,
            force=args.force,
        )
        run_determinism_check(
            model_command=args.model_command,
            decoding_json=args.decoding_json,
            per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
            general_prompt_path=general_prompt_path,
            general_prompt_label=args.general_prompt_label,
        )
        results = run_diagnostic_matrix(
            output_dir=output_dir,
            model_command=args.model_command,
            decoding_json=args.decoding_json,
            per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
            row_set=args.row_set,
            general_prompt_path=general_prompt_path,
            general_prompt_label=args.general_prompt_label,
            force=args.force,
        )
    except StopConditionError as error:
        report_path = write_stop_report(output_dir, error)
        print(
            "Stopped diagnostic matrix: {}. Wrote {}".format(error.reason, report_path),
            file=sys.stderr,
        )
        return 2

    summary_path = write_diagnostic_summary(
        output_dir=output_dir,
        row_set=args.row_set,
        general_prompt_path=general_prompt_path,
        general_prompt_label=args.general_prompt_label,
        results=results,
    )
    print("Wrote or reused {} diagnostic rows in {}".format(len(results), output_dir))
    print("Wrote diagnostic summary {}".format(summary_path))
    print("No statistical gate verdicts were issued.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
