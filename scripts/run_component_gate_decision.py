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
import hashlib
import importlib.util
import json
import math
import shlex
import subprocess
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
from cq.pipeline.ollama_component_extractor import (  # noqa: E402
    OllamaCommandError,
    OllamaHttpClient,
    SCHEMA_PROFILE_DEFAULT,
    SCHEMA_PROFILES,
)
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
STOP_REPORT_PREFIX = "component_gate_decision_stop"
PRIMARY_SCENARIO_COUNT = 60
FROZEN_SENTINEL_SCENARIO_COUNT = 3
TEMPLATE_MIX_HELDOUT = "heldout"
TEMPLATE_MIX_FROZEN = "frozen"
CONFIDENCE_LEVEL = 0.95
WILSON_Z = 1.959963984540054
VACUOUS_STRING_VALUES = frozenset(("", "unknown", "n/a", "na", "none", "null", "todo"))
PRIMARY_GATE_FAMILIES: Tuple[str, ...] = (
    FORCED_CONTRADICTION,
    SCOPE_CONTAMINATION,
    PREFERENCE_DRIFT,
    USEFUL_PENDING_MEMORY,
    FALSE_CORROBORATION,
    MEMORY_POISONING,
)
PRIMARY_MODEL_SPECS: Dict[str, matrix.ModelSpec] = {
    matrix.QWEN_7B_Q4KM.model_id: matrix.QWEN_7B_Q4KM,
    matrix.QWEN_32B_Q4KM.model_id: matrix.QWEN_32B_Q4KM,
}
PREREGISTERED_MODEL_DIGESTS: Dict[str, str] = {
    matrix.QWEN_7B_Q4KM.model_id: "sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
    matrix.QWEN_32B_Q4KM.model_id: "sha256:9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368",
}
LOCKED_BASELINE_SUMMARY_PATH = (
    DEFAULT_OUTPUT_DIR / "component_gate_decision_general_v1_summary.json"
)
LOCKED_BASELINE_UNLOCK_CHECKS = {
    "phase_a_passed": True,
    "determinism_passed": True,
    "primary_scenario_error_count": 45,
    "primary_observed_gate_failure_count": 8,
    "aggregate_observed_gate_failure_count": 0,
    "aggregate_ci_gate_failure_count": 0,
    "frozen_sentinel_included": True,
    "frozen_sentinel_observed_gate_failure_count": 3,
    "policy_comparison_unlocked": False,
}


@dataclass(frozen=True)
class GateRow:
    family: str
    template_mix: str
    scenarios: int
    model: matrix.ModelSpec
    prompt_label: str
    prompt_path: Path
    gate_role: str
    schema_profile: str = SCHEMA_PROFILE_DEFAULT

    @property
    def artifact_stem(self) -> str:
        return "{}_{}_local_extractor_{}_{}_{}_{}_n{}_{}".format(
            SUMMARY_PREFIX,
            self.family,
            self.model.artifact_label,
            self.prompt_label,
            self.schema_profile,
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


@dataclass(frozen=True)
class PrimaryModelBackend:
    model_tag: str
    expected_digest: str
    resolved_digest: str
    ollama_server_version: str


def primary_gate_rows(
    prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
    *,
    primary_model: matrix.ModelSpec = matrix.QWEN_7B_Q4KM,
    schema_profile: str = SCHEMA_PROFILE_DEFAULT,
) -> List[GateRow]:
    return [
        GateRow(
            family=family,
            template_mix=TEMPLATE_MIX_HELDOUT,
            scenarios=PRIMARY_SCENARIO_COUNT,
            model=primary_model,
            prompt_label=prompt_label,
            prompt_path=prompt_path,
            gate_role=primary_gate_role(primary_model),
            schema_profile=schema_profile,
        )
        for family in PRIMARY_GATE_FAMILIES
    ]


def headroom_gate_rows(
    prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
    families: Sequence[str] = PRIMARY_GATE_FAMILIES,
    schema_profile: str = SCHEMA_PROFILE_DEFAULT,
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
            schema_profile=schema_profile,
        )
        for family in families
    ]


def frozen_sentinel_rows(
    prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
    *,
    model: matrix.ModelSpec = matrix.QWEN_7B_Q4KM,
    gate_role: str = "frozen_sentinel_floor",
    schema_profile: str = SCHEMA_PROFILE_DEFAULT,
) -> List[GateRow]:
    return [
        GateRow(
            family=MECHANISM_DIVERSE_HELDOUT,
            template_mix=TEMPLATE_MIX_FROZEN,
            scenarios=FROZEN_SENTINEL_SCENARIO_COUNT,
            model=model,
            prompt_label=prompt_label,
            prompt_path=prompt_path,
            gate_role=gate_role,
            schema_profile=schema_profile,
        )
    ]


def primary_gate_role(model: matrix.ModelSpec) -> str:
    if model == matrix.QWEN_7B_Q4KM:
        return "primary_floor"
    return "primary_unlock_probe"


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
        model_command=model_command,
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
    _flag_vacuous_predictions(extractor_output)
    _write_json(paths.predictions, extractor_output)
    predictions = load_predictions_by_scenario(paths.predictions)
    scenario_errors = load_scenario_errors(paths.predictions)
    component_artifact = _build_row_component_artifact(
        row,
        predictions,
        scenario_errors,
        model_digest=_model_digest_from_prediction_payload(extractor_output),
        ollama_server_version=_ollama_version_from_prediction_payload(extractor_output),
    )
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
    payload = _read_json(paths.predictions)
    changed = _flag_vacuous_predictions(payload)
    if changed:
        _write_json(paths.predictions, payload)
    predictions = load_predictions_by_scenario(paths.predictions)
    scenario_errors = load_scenario_errors(paths.predictions)
    component_artifact = (
        _build_row_component_artifact(
            row,
            predictions,
            scenario_errors,
            model_digest=_model_digest_from_prediction_payload(payload),
            ollama_server_version=_ollama_version_from_prediction_payload(payload),
        )
        if changed
        else _read_json(paths.component_eval)
    )
    if changed:
        _write_json(paths.component_eval, component_artifact)
    return GateRowResult(
        row=row,
        paths=paths,
        component_artifact=component_artifact,
        predictions_by_scenario=predictions,
        scenario_errors=scenario_errors,
        reused=reused,
    )


def cached_gate_artifacts_match_row(
    row: GateRow,
    paths: GateArtifactPaths,
    *,
    model_command: str,
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
        mismatches.extend(
            gate_cached_artifact_provenance_mismatches(
                row,
                paths,
                model_command=model_command,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return not mismatches


def gate_cached_artifact_provenance_mismatches(
    row: GateRow,
    paths: GateArtifactPaths,
    *,
    model_command: str,
) -> List[Dict[str, object]]:
    predictions_payload = _read_json(paths.predictions)
    component_payload = _read_json(paths.component_eval)
    diagnostics = predictions_payload.get("model_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    expected_digest = PREREGISTERED_MODEL_DIGESTS.get(row.model.model_id, "")
    checks = [
        ("predictions.model_command", predictions_payload.get("model_command"), model_command),
        (
            "predictions.model_diagnostics.schema_profile",
            diagnostics.get("schema_profile"),
            row.schema_profile,
        ),
        ("predictions.model_digest", predictions_payload.get("model_digest"), expected_digest),
        (
            "predictions.model_diagnostics.model_digest",
            diagnostics.get("model_digest"),
            expected_digest,
        ),
        ("component.schema_profile", component_payload.get("schema_profile"), row.schema_profile),
        ("component.model_id", component_payload.get("model_id"), row.model.model_id),
        ("component.model_digest", component_payload.get("model_digest"), expected_digest),
    ]
    mismatches = []
    for field, observed, expected in checks:
        if not matrix._values_match(observed, expected):
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


def _build_row_component_artifact(
    row: GateRow,
    predictions_by_scenario: Dict[str, List[CandidateComponentPrediction]],
    scenario_errors: Dict[str, object],
    *,
    model_digest: str = "",
    ollama_server_version: str = "",
) -> Dict[str, object]:
    scenarios = generate_scenarios(row.family, row.scenarios, row.template_mix)
    evaluation = evaluate_component_predictions(
        scenarios,
        predictions_by_scenario,
        scenario_errors=scenario_errors,
    )
    artifact = {
        "mode": "component_gate_decision_row",
        "family": row.family,
        "template_mix": row.template_mix,
        "requested_scenario_count": row.scenarios,
        "scenario_count": len(scenarios),
        "model_id": row.model.model_id,
        "schema_profile": row.schema_profile,
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
    if model_digest:
        artifact["model_digest"] = model_digest
    if ollama_server_version:
        artifact["ollama_server_version"] = ollama_server_version
    return artifact


def run_gate_decision(
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    general_prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    general_prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
    summary_label: Optional[str] = None,
    primary_model_tag: str = matrix.QWEN_7B_Q4KM.model_id,
    schema_profile: str = SCHEMA_PROFILE_DEFAULT,
    include_headroom: bool = False,
    include_frozen_sentinel: bool = False,
    headroom_families: Sequence[str] = PRIMARY_GATE_FAMILIES,
    include_headroom_frozen_sentinel: bool = False,
    force: bool = False,
    runner_command: Optional[str] = None,
) -> Path:
    primary_model = model_spec_for_tag(primary_model_tag)
    if primary_model != matrix.QWEN_7B_Q4KM:
        anchor_error = verify_required_anchor_before_probe(output_dir)
        if anchor_error is not None:
            raise anchor_error
    backend = verify_primary_model_backend(
        primary_model_tag,
        runner_command=runner_command,
    )
    pre_run_working_tree_status = working_tree_status()
    effective_model_command = model_command_for_schema_profile(
        model_command,
        schema_profile,
    )
    phase_a_force = force or schema_profile != SCHEMA_PROFILE_DEFAULT
    matrix.run_prompt_regression(
        output_dir=output_dir,
        model_command=effective_model_command,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        general_prompt_path=general_prompt_path,
        general_prompt_label=general_prompt_label,
        force=phase_a_force,
    )
    matrix.run_determinism_check(
        model_command=effective_model_command,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        general_prompt_path=general_prompt_path,
        general_prompt_label=general_prompt_label,
        model=primary_model,
    )
    primary_results = [
        run_or_reuse_gate_row(
            row,
            output_dir=output_dir,
            model_command=effective_model_command,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
            force=force,
        )
        for row in primary_gate_rows(
            general_prompt_path,
            general_prompt_label,
            primary_model=primary_model,
            schema_profile=schema_profile,
        )
    ]
    headroom_results = (
        [
            run_or_reuse_gate_row(
                row,
                output_dir=output_dir,
                model_command=effective_model_command,
                decoding_json=decoding_json,
                per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                force=force,
            )
            for row in headroom_gate_rows(
                general_prompt_path,
                general_prompt_label,
                families=headroom_families,
                schema_profile=schema_profile,
            )
        ]
        if include_headroom
        else []
    )
    if include_headroom_frozen_sentinel:
        headroom_results.extend(
            [
                run_or_reuse_gate_row(
                    row,
                    output_dir=output_dir,
                    model_command=effective_model_command,
                    decoding_json=decoding_json,
                    per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                    force=force,
                )
                for row in frozen_sentinel_rows(
                    general_prompt_path,
                    general_prompt_label,
                    model=matrix.QWEN_32B_Q4KM,
                    gate_role="descriptive_headroom_frozen_sentinel",
                    schema_profile=schema_profile,
                )
            ]
        )
    frozen_results = (
        [
            run_or_reuse_gate_row(
                row,
                output_dir=output_dir,
                model_command=effective_model_command,
                decoding_json=decoding_json,
                per_scenario_timeout_seconds=per_scenario_timeout_seconds,
                force=force,
            )
            for row in frozen_sentinel_rows(
                general_prompt_path,
                general_prompt_label,
                model=primary_model,
                gate_role="frozen_sentinel_primary",
                schema_profile=schema_profile,
            )
        ]
        if include_frozen_sentinel
        else []
    )
    path = gate_summary_path(
        output_dir,
        general_prompt_label=summary_label or general_prompt_label,
        primary_model_tag=primary_model_tag,
        schema_profile=schema_profile,
        summary_label=summary_label,
    )
    # These helpers raise StopConditionError on failure; reaching the summary write means both guards passed.
    summary_payload = gate_summary_payload(
        primary_results=primary_results,
        headroom_results=headroom_results,
        frozen_sentinel_results=frozen_results,
        general_prompt_path=general_prompt_path,
        general_prompt_label=general_prompt_label,
        summary_label=summary_label,
        decoding_json=decoding_json,
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        phase_a_passed=True,
        determinism_passed=True,
        primary_model_backend=backend,
        schema_profile=schema_profile,
        runner_command=runner_command,
        pre_run_working_tree_status=pre_run_working_tree_status,
    )
    _write_json(
        path,
        summary_payload,
    )
    if is_locked_7b_anchor_run(
        primary_model_tag=primary_model_tag,
        schema_profile=schema_profile,
        include_frozen_sentinel=include_frozen_sentinel,
        summary_label=summary_label,
    ):
        anchor_error = verify_anchor_against_locked_baseline(path)
        if anchor_error is not None:
            raise anchor_error
    write_gate_manifest(
        summary_path=path,
        summary_payload=summary_payload,
        runner_command=runner_command,
        pre_run_working_tree_status=pre_run_working_tree_status,
    )
    return path


def gate_summary_path(
    output_dir: Path,
    *,
    general_prompt_label: str,
    primary_model_tag: Optional[str] = None,
    schema_profile: Optional[str] = None,
    summary_label: Optional[str] = None,
) -> Path:
    """Return the summary path.

    A custom summary_label is an explicit operator override and takes
    precedence over cell-derived primary-model/schema labels.
    """
    if summary_label:
        label = summary_label
    elif primary_model_tag and schema_profile:
        label = "{}_{}".format(primary_model_tag, schema_profile)
    else:
        label = general_prompt_label
    return output_dir / "{}_{}_summary.json".format(
        SUMMARY_PREFIX,
        matrix._slug_for_filename(label),
    )


def default_anchor_summary_path(output_dir: Path) -> Path:
    return gate_summary_path(
        output_dir,
        general_prompt_label=matrix.DEFAULT_GENERAL_PROMPT_LABEL,
        primary_model_tag=matrix.QWEN_7B_Q4KM.model_id,
        schema_profile=SCHEMA_PROFILE_DEFAULT,
    )


def model_spec_for_tag(model_tag: str) -> matrix.ModelSpec:
    try:
        return PRIMARY_MODEL_SPECS[model_tag]
    except KeyError:
        raise ValueError(
            "Unsupported primary model tag '{}'. Allowed: {}".format(
                model_tag,
                ", ".join(sorted(PRIMARY_MODEL_SPECS)),
            )
        )


def verify_primary_model_backend(
    primary_model_tag: str,
    *,
    runner_command: Optional[str],
    client: Optional[OllamaHttpClient] = None,
) -> PrimaryModelBackend:
    expected_digest = PREREGISTERED_MODEL_DIGESTS.get(primary_model_tag)
    if expected_digest is None:
        raise matrix.StopConditionError(
            "unsupported_primary_model_tag",
            {
                "primary_model_tag": primary_model_tag,
                "allowed_primary_model_tags": sorted(PREREGISTERED_MODEL_DIGESTS),
                "runner_command": runner_command,
            },
        )
    client = client or OllamaHttpClient()
    try:
        ollama_server_version = client.get_version()
        resolved_digest = client.get_model_digest(primary_model_tag)
    except OllamaCommandError as error:
        raise matrix.StopConditionError(
            "model_digest_verification_failed",
            {
                "primary_model_tag": primary_model_tag,
                "expected_digest": expected_digest,
                "observed_digest": None,
                "ollama_server_version": None,
                "message": str(error),
                "runner_command": runner_command,
            },
        )
    if resolved_digest != expected_digest:
        raise matrix.StopConditionError(
            "model_digest_mismatch",
            {
                "primary_model_tag": primary_model_tag,
                "expected_digest": expected_digest,
                "observed_digest": resolved_digest,
                "ollama_server_version": ollama_server_version,
                "runner_command": runner_command,
            },
        )
    return PrimaryModelBackend(
        model_tag=primary_model_tag,
        expected_digest=expected_digest,
        resolved_digest=resolved_digest,
        ollama_server_version=ollama_server_version,
    )


def model_command_for_schema_profile(model_command: str, schema_profile: str) -> str:
    if schema_profile not in SCHEMA_PROFILES:
        raise ValueError(
            "Unsupported schema profile '{}'. Allowed: {}".format(
                schema_profile,
                ", ".join(SCHEMA_PROFILES),
            )
        )
    try:
        argv = shlex.split(model_command)
    except ValueError as error:
        raise ValueError("--model-command could not be parsed: {}".format(error))
    if not argv:
        raise ValueError("--model-command is required")
    for item in argv:
        if item == "--schema-profile" or item.startswith("--schema-profile="):
            raise ValueError(
                "Pass schema profile with the runner-level --schema-profile argument, "
                "not inside --model-command"
            )
    return shlex.join([*argv, "--schema-profile", schema_profile])


def write_gate_manifest(
    *,
    summary_path: Path,
    summary_payload: Mapping[str, object],
    runner_command: Optional[str],
    pre_run_working_tree_status: Optional[str],
) -> Path:
    summary_sha = sha256_file(summary_path)
    manifest_path = summary_path.with_name(
        "{}_manifest.json".format(summary_path.stem.removesuffix("_summary"))
    )
    artifact = {
        "path": _repo_relative_path(summary_path),
        "bytes": summary_path.stat().st_size,
        "sha256": summary_sha,
        "summary_json_sha256": summary_sha,
        "git_commit": git_commit(),
        "python_version": sys.version.split()[0],
        "runner_command": runner_command,
        "working_tree_status": pre_run_working_tree_status,
        "working_tree_status_context": "pre_run_before_scored_rows",
        "primary_model_tag": summary_payload.get("primary_model_tag"),
        "primary_model_digest": summary_payload.get("primary_model_digest"),
        "expected_primary_model_digest": summary_payload.get("expected_primary_model_digest"),
        "ollama_server_version": summary_payload.get("ollama_server_version"),
        "prompt_sha256": summary_payload.get("general_prompt_sha256"),
        "schema_profile": summary_payload.get("schema_profile"),
    }
    manifest = {
        "manifest_version": 1,
        "run_name": summary_path.stem.removesuffix("_summary"),
        "artifact_count": 1,
        "artifacts": [artifact],
    }
    _write_json(manifest_path, manifest)
    return manifest_path


def locked_baseline_anchor_matches(summary_path: Path = LOCKED_BASELINE_SUMMARY_PATH) -> bool:
    try:
        payload = _read_json(summary_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    checks = payload.get("unlock_checks")
    return isinstance(checks, dict) and all(
        checks.get(key) == expected
        for key, expected in LOCKED_BASELINE_UNLOCK_CHECKS.items()
    )


def verify_required_anchor_before_probe(output_dir: Path) -> Optional[matrix.StopConditionError]:
    anchor_path = default_anchor_summary_path(output_dir)
    if not anchor_path.exists():
        return matrix.StopConditionError(
            "anchor_summary_missing",
            {
                "required_anchor_summary_path": str(anchor_path),
                "locked_baseline_summary_path": str(LOCKED_BASELINE_SUMMARY_PATH),
                "message": "Run the preregistered 7B default-schema anchor before 32B scoring.",
            },
        )
    return verify_anchor_against_locked_baseline(anchor_path)


def verify_anchor_against_locked_baseline(
    new_summary_path: Path,
    *,
    locked_summary_path: Path = LOCKED_BASELINE_SUMMARY_PATH,
) -> Optional[matrix.StopConditionError]:
    try:
        new_payload = _read_json(new_summary_path)
        locked_payload = _read_json(locked_summary_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return matrix.StopConditionError(
            "anchor_summary_unreadable",
            {
                "new_summary_path": str(new_summary_path),
                "locked_summary_path": str(locked_summary_path),
                "message": str(error),
            },
        )
    new_checks = _mapping(new_payload.get("unlock_checks"))
    locked_checks = _mapping(locked_payload.get("unlock_checks"))
    mismatches = []
    for key, expected in LOCKED_BASELINE_UNLOCK_CHECKS.items():
        observed = new_checks.get(key)
        locked_observed = locked_checks.get(key)
        if observed != expected or locked_observed != expected:
            mismatches.append(
                {
                    "field": "unlock_checks.{}".format(key),
                    "observed": observed,
                    "expected": expected,
                    "locked_summary_observed": locked_observed,
                }
            )
    if not mismatches:
        return None
    return matrix.StopConditionError(
        "anchor_reproduction_mismatch",
        {
            "new_summary_path": str(new_summary_path),
            "locked_summary_path": str(locked_summary_path),
            "mismatches": mismatches,
        },
    )


def is_locked_7b_anchor_run(
    *,
    primary_model_tag: str,
    schema_profile: str,
    include_frozen_sentinel: bool,
    summary_label: Optional[str],
) -> bool:
    return (
        primary_model_tag == matrix.QWEN_7B_Q4KM.model_id
        and schema_profile == SCHEMA_PROFILE_DEFAULT
        and include_frozen_sentinel
        and summary_label is None
    )


def gate_summary_payload(
    *,
    primary_results: Sequence[GateRowResult],
    headroom_results: Sequence[GateRowResult],
    frozen_sentinel_results: Sequence[GateRowResult],
    general_prompt_path: Path,
    general_prompt_label: str,
    summary_label: Optional[str],
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    phase_a_passed: bool,
    determinism_passed: bool,
    primary_model_backend: Optional[PrimaryModelBackend] = None,
    schema_profile: str = SCHEMA_PROFILE_DEFAULT,
    runner_command: Optional[str] = None,
    pre_run_working_tree_status: Optional[str] = None,
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
    primary_model_tag = (
        primary_model_backend.model_tag
        if primary_model_backend is not None
        else _primary_model_tag_from_results(primary_results)
    )
    primary_model_digest = (
        primary_model_backend.resolved_digest
        if primary_model_backend is not None
        else _model_digest_from_results(primary_results)
    )
    ollama_server_version = (
        primary_model_backend.ollama_server_version
        if primary_model_backend is not None
        else _ollama_server_version_from_results(primary_results)
    )

    return {
        "mode": "ci_aware_component_gate_decision",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "phase": "phase3_component_gate_decision",
        "general_prompt_path": str(general_prompt_path),
        "general_prompt_label": general_prompt_label,
        "summary_label": summary_label,
        "general_prompt_sha256": matrix.prompt_template_sha256(general_prompt_path),
        "primary_model_tag": primary_model_tag,
        "primary_model_digest": primary_model_digest,
        "expected_primary_model_digest": (
            primary_model_backend.expected_digest
            if primary_model_backend is not None
            else PREREGISTERED_MODEL_DIGESTS.get(primary_model_tag, "")
        ),
        "ollama_server_version": ollama_server_version,
        "schema_profile": schema_profile,
        "runner_command": runner_command,
        "pre_run_working_tree_status": pre_run_working_tree_status,
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
        "determinism_contract": determinism_contract_payload(
            determinism_passed,
            model_tag=primary_model_tag,
        ),
        "generation_contract": generation_contract_payload(),
        "statistical_contract": statistical_contract_payload(),
        "unlock_rule": {
            "primary_model_role": (
                model_spec_for_tag(primary_model_tag).role
                if primary_model_tag in PRIMARY_MODEL_SPECS
                else "unknown"
            ),
            "primary_model_id": primary_model_tag,
            "primary_model_tag": primary_model_tag,
            "primary_model_digest": primary_model_digest,
            "schema_profile": schema_profile,
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
        "schema_profile": result.row.schema_profile,
        "model_digest": _model_digest_from_prediction_artifact(result.paths.predictions),
        "ollama_server_version": _ollama_version_from_prediction_artifact(
            result.paths.predictions
        ),
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


def _primary_model_tag_from_results(results: Sequence[GateRowResult]) -> str:
    if not results:
        return ""
    return results[0].row.model.model_id


def _model_digest_from_results(results: Sequence[GateRowResult]) -> str:
    for result in results:
        digest = _model_digest_from_prediction_artifact(result.paths.predictions)
        if digest:
            return digest
    return ""


def _ollama_server_version_from_results(results: Sequence[GateRowResult]) -> str:
    for result in results:
        version = _ollama_version_from_prediction_artifact(result.paths.predictions)
        if version:
            return version
    return ""


def _model_digest_from_prediction_artifact(path: Path) -> str:
    try:
        payload = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return ""
    return _model_digest_from_prediction_payload(payload)


def _model_digest_from_prediction_payload(payload: Mapping[str, object]) -> str:
    top_level = payload.get("model_digest")
    if isinstance(top_level, str) and top_level:
        return top_level
    diagnostics = _prediction_payload_model_diagnostics(payload)
    digest = diagnostics.get("model_digest")
    return digest if isinstance(digest, str) else ""


def _ollama_version_from_prediction_artifact(path: Path) -> str:
    try:
        payload = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return ""
    return _ollama_version_from_prediction_payload(payload)


def _ollama_version_from_prediction_payload(payload: Mapping[str, object]) -> str:
    diagnostics = _prediction_payload_model_diagnostics(payload)
    version = diagnostics.get("ollama_server_version")
    return version if isinstance(version, str) else ""


def _prediction_payload_model_diagnostics(payload: Mapping[str, object]) -> Dict[str, object]:
    diagnostics = payload.get("model_diagnostics")
    return diagnostics if isinstance(diagnostics, dict) else {}


def dry_run_plan(
    *,
    output_dir: Path,
    model_command: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
    general_prompt_path: Path = matrix.GENERAL_PROMPT_PATH,
    general_prompt_label: str = matrix.DEFAULT_GENERAL_PROMPT_LABEL,
    primary_model_tag: str = matrix.QWEN_7B_Q4KM.model_id,
    schema_profile: str = SCHEMA_PROFILE_DEFAULT,
    include_headroom: bool = False,
    include_frozen_sentinel: bool = False,
    headroom_families: Sequence[str] = PRIMARY_GATE_FAMILIES,
    include_headroom_frozen_sentinel: bool = False,
) -> Dict[str, object]:
    primary_model = model_spec_for_tag(primary_model_tag)
    effective_model_command = model_command_for_schema_profile(
        model_command,
        schema_profile,
    )
    rows = primary_gate_rows(
        general_prompt_path,
        general_prompt_label,
        primary_model=primary_model,
        schema_profile=schema_profile,
    )
    if include_headroom:
        rows.extend(
            headroom_gate_rows(
                general_prompt_path,
                general_prompt_label,
                families=headroom_families,
                schema_profile=schema_profile,
            )
        )
    if include_headroom_frozen_sentinel:
        rows.extend(
            frozen_sentinel_rows(
                general_prompt_path,
                general_prompt_label,
                model=matrix.QWEN_32B_Q4KM,
                gate_role="descriptive_headroom_frozen_sentinel",
                schema_profile=schema_profile,
            )
        )
    if include_frozen_sentinel:
        rows.extend(
            frozen_sentinel_rows(
                general_prompt_path,
                general_prompt_label,
                model=primary_model,
                gate_role="frozen_sentinel_primary",
                schema_profile=schema_profile,
            )
        )
    return {
        "mode": "dry_run",
        "phase": "ci_aware_component_gate_decision",
        "general_prompt_path": str(general_prompt_path),
        "general_prompt_label": general_prompt_label,
        "primary_model_tag": primary_model_tag,
        "expected_primary_model_digest": PREREGISTERED_MODEL_DIGESTS[primary_model_tag],
        "schema_profile": schema_profile,
        "effective_model_command": effective_model_command,
        "policy_comparison_unlocked": "not_evaluated",
        "phase_a_contract": phase_a_contract_payload(
            False,
            general_prompt_label=general_prompt_label,
        )["contract"],
        "determinism_contract": determinism_contract_payload(
            False,
            model_tag=primary_model_tag,
        )["contract"],
        "generation_contract": generation_contract_payload(),
        "statistical_contract": statistical_contract_payload(),
        "expected_denominators_current_generator": expected_denominators_payload(
            primary_gate_rows(
                general_prompt_path,
                general_prompt_label,
                primary_model=primary_model,
                schema_profile=schema_profile,
            )
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
                "schema_profile": row.schema_profile,
                "paths": {
                    "predictions": str(gate_artifact_paths(row, output_dir).predictions),
                    "component_eval": str(gate_artifact_paths(row, output_dir).component_eval),
                },
                "expected_denominators_current_generator": expected_denominators_for_row(row),
                "commands": equivalent_commands(
                    row,
                    output_dir=output_dir,
                    model_command=effective_model_command,
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


def determinism_contract_payload(
    passed: bool,
    *,
    model_tag: str = matrix.QWEN_7B_Q4KM.model_id,
) -> Dict[str, object]:
    return {
        "passed": passed,
        "contract": {
            "source": "scripts/run_component_scoring_matrix.py::run_determinism_check",
            "model_id": model_tag,
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


def _flag_vacuous_predictions(payload: Dict[str, object]) -> bool:
    scenario_predictions = payload.get("scenario_predictions")
    scenario_errors = payload.setdefault("scenario_errors", {})
    if not isinstance(scenario_predictions, dict) or not isinstance(scenario_errors, dict):
        return False
    changed = False
    for scenario_id, predictions in scenario_predictions.items():
        if scenario_id in scenario_errors or not isinstance(predictions, list):
            continue
        for index, prediction in enumerate(predictions):
            if not isinstance(prediction, dict):
                continue
            vacuous_field = _first_vacuous_prediction_field(prediction)
            if vacuous_field is None:
                continue
            scenario_errors[scenario_id] = {
                "error_type": "validation_error",
                "message": "Prediction {} must include non-vacuous string {}".format(
                    index,
                    vacuous_field,
                ),
            }
            scenario_predictions[scenario_id] = []
            changed = True
            break
    scenario_count = payload.get("scenario_count")
    if isinstance(scenario_count, int):
        payload["successful_scenario_count"] = max(0, scenario_count - len(scenario_errors))
    return changed


def _first_vacuous_prediction_field(prediction: Mapping[str, object]) -> Optional[str]:
    for field in ("canonical_id", "scope_key"):
        if _is_vacuous_string(prediction.get(field)):
            return field
    return None


def _is_vacuous_string(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() in VACUOUS_STRING_VALUES


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
        raise ValueError("{} must be an integer count, not a boolean".format(key))
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError("{} must be an integer count, not a rate: {}".format(key, value))
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


def _mapping(value: object) -> Dict[str, object]:
    return value if isinstance(value, dict) else {}


def _paths_exist(paths: GateArtifactPaths) -> bool:
    return paths.predictions.exists() and paths.component_eval.exists()


def _repo_relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def git_commit() -> str:
    return _git_output(["rev-parse", "HEAD"])


def working_tree_status() -> str:
    return "clean" if not _git_output(["status", "--short"]) else "dirty"


def _git_output(args: Sequence[str]) -> str:
    return subprocess.check_output(["git", *args], text=True, cwd=REPO_ROOT).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def runner_command_for_invocation(argv: Optional[Sequence[str]]) -> str:
    if argv is None:
        return shlex.join([sys.executable, str(Path(__file__)), *sys.argv[1:]])
    return shlex.join([sys.executable, str(Path(__file__)), *argv])


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
    parser.add_argument("--summary-label", default=None)
    parser.add_argument(
        "--primary-model-tag",
        required=True,
        choices=sorted(PRIMARY_MODEL_SPECS),
        help="Primary unlocking model tag. Exact resolved digest is checked before scoring.",
    )
    parser.add_argument(
        "--schema-profile",
        required=True,
        choices=SCHEMA_PROFILES,
        help="Ollama extractor schema profile. This is passed to the wrapper by the runner.",
    )
    parser.add_argument("--include-headroom", action="store_true")
    parser.add_argument(
        "--headroom-family",
        action="append",
        dest="headroom_families",
        choices=sorted(PRIMARY_GATE_FAMILIES),
        default=None,
    )
    parser.add_argument("--include-headroom-frozen-sentinel", action="store_true")
    parser.add_argument("--include-frozen-sentinel", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.headroom_families and not args.include_headroom:
        parser.error("--headroom-family requires --include-headroom")
    try:
        model_command_for_schema_profile(args.model_command, args.schema_profile)
    except ValueError as error:
        parser.error(str(error))
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    runner_command = runner_command_for_invocation(argv)
    headroom_families = tuple(args.headroom_families or PRIMARY_GATE_FAMILIES)
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
                    primary_model_tag=args.primary_model_tag,
                    schema_profile=args.schema_profile,
                    include_headroom=args.include_headroom,
                    include_frozen_sentinel=args.include_frozen_sentinel,
                    headroom_families=headroom_families,
                    include_headroom_frozen_sentinel=args.include_headroom_frozen_sentinel,
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
            summary_label=args.summary_label,
            primary_model_tag=args.primary_model_tag,
            schema_profile=args.schema_profile,
            include_headroom=args.include_headroom,
            include_frozen_sentinel=args.include_frozen_sentinel,
            headroom_families=headroom_families,
            include_headroom_frozen_sentinel=args.include_headroom_frozen_sentinel,
            force=args.force,
            runner_command=runner_command,
        )
    except matrix.StopConditionError as error:
        report_path = write_stop_report(args.output_dir, error)
        print("Gate decision stopped: {}. Report: {}".format(error.reason, report_path))
        return 1
    print("Wrote component gate decision summary to {}".format(summary_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
