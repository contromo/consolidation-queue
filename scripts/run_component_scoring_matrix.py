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
FORCED_PROMPT_PATH = REPO_ROOT / "prompts" / "forced_contradiction_component_extractor_v1.txt"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "results"
STOP_REPORT_PREFIX = "component_scoring_matrix_phase_a_stop"
EPSILON = 1e-12

GATE_METRICS: Tuple[str, ...] = tuple(QUALITY_GATES.keys())


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


def floor_diagnostic_rows(prompt_path: Path = GENERAL_PROMPT_PATH) -> List[MatrixRow]:
    return [
        MatrixRow(family, mix, scenarios, QWEN_7B_Q4KM, "general_v1", prompt_path)
        for family, mix, scenarios in _diagnostic_family_rows()
    ]


def headroom_diagnostic_rows(prompt_path: Path = GENERAL_PROMPT_PATH) -> List[MatrixRow]:
    return [
        MatrixRow(family, mix, scenarios, QWEN_32B_Q4KM, "general_v1", prompt_path)
        for family, mix, scenarios in _headroom_family_rows()
    ]


def regression_rows(
    model: ModelSpec,
    *,
    forced_prompt_path: Path = FORCED_PROMPT_PATH,
    general_prompt_path: Path = GENERAL_PROMPT_PATH,
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
            "general_v1",
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
    force: bool = False,
) -> None:
    all_violations: List[Dict[str, object]] = []
    for model in (QWEN_7B_Q4KM, QWEN_32B_Q4KM):
        baseline_row, general_row = regression_rows(model)
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
) -> None:
    row = MatrixRow(
        FORCED_CONTRADICTION,
        "mixed",
        6,
        QWEN_7B_Q4KM,
        "general_v1",
        GENERAL_PROMPT_PATH,
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
    force: bool = False,
) -> List[RowResult]:
    results = []
    for row in floor_diagnostic_rows() + headroom_diagnostic_rows():
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
) -> Dict[str, object]:
    rows = []
    for row in _all_planned_rows():
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


def _all_planned_rows() -> List[MatrixRow]:
    rows: List[MatrixRow] = []
    for model in (QWEN_7B_Q4KM, QWEN_32B_Q4KM):
        rows.extend(regression_rows(model))
    rows.extend(floor_diagnostic_rows())
    rows.extend(headroom_diagnostic_rows())
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the diagnostic-only noisy component scoring matrix."
    )
    parser.add_argument("--model-command", default=DEFAULT_MODEL_COMMAND)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--decoding-json", default=DEFAULT_DECODING_JSON)
    parser.add_argument("--per-scenario-timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    if args.dry_run:
        print(
            json.dumps(
                dry_run_plan(
                    output_dir=output_dir,
                    model_command=args.model_command,
                    decoding_json=args.decoding_json,
                    per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
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
            force=args.force,
        )
        run_determinism_check(
            model_command=args.model_command,
            decoding_json=args.decoding_json,
            per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
        )
        results = run_diagnostic_matrix(
            output_dir=output_dir,
            model_command=args.model_command,
            decoding_json=args.decoding_json,
            per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
            force=args.force,
        )
    except StopConditionError as error:
        report_path = write_stop_report(output_dir, error)
        print(
            "Stopped diagnostic matrix: {}. Wrote {}".format(error.reason, report_path),
            file=sys.stderr,
        )
        return 2

    print("Wrote or reused {} diagnostic rows in {}".format(len(results), output_dir))
    print("No statistical gate verdicts were issued.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
