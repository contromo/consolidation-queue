from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

from cq.pipeline.ollama_component_extractor import (
    OllamaCommandError,
    OllamaHttpClient,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "results"
LOCKED_BASELINE_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "component_gate_decision_general_v1_summary.json"

QWEN_7B_Q4KM = "qwen2.5:7b-instruct-q4_K_M"
QWEN_32B_Q4KM = "qwen2.5:32b-instruct-q4_K_M"
SCHEMA_PROFILE_DEFAULT = "default"

PREREGISTERED_MODEL_DIGESTS: Dict[str, str] = {
    QWEN_7B_Q4KM: "sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
    QWEN_32B_Q4KM: "sha256:9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368",
}
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
class PrimaryModelBackend:
    model_tag: str
    expected_digest: str
    resolved_digest: str
    ollama_server_version: str


class GateRuntimeError(RuntimeError):
    def __init__(self, reason: str, details: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details


def verify_primary_model_backend(
    primary_model_tag: str,
    *,
    runner_command: Optional[str],
    client: Optional[OllamaHttpClient] = None,
) -> PrimaryModelBackend:
    expected_digest = PREREGISTERED_MODEL_DIGESTS.get(primary_model_tag)
    if expected_digest is None:
        raise GateRuntimeError(
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
        raise GateRuntimeError(
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
        raise GateRuntimeError(
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


def default_anchor_summary_path(output_dir: Path) -> Path:
    label = "_".join(
        [
            "component_gate_decision",
            _slug_for_filename(QWEN_7B_Q4KM),
            SCHEMA_PROFILE_DEFAULT,
            "summary",
        ]
    )
    return output_dir / "{}.json".format(label)


def verify_required_anchor_before_probe(
    output_dir: Path,
    *,
    live_ollama_server_version: str = "",
) -> Optional[GateRuntimeError]:
    anchor_path = default_anchor_summary_path(output_dir)
    if not anchor_path.exists():
        return GateRuntimeError(
            "anchor_summary_missing",
            {
                "required_anchor_summary_path": str(anchor_path),
                "locked_baseline_summary_path": str(LOCKED_BASELINE_SUMMARY_PATH),
                "message": "Run the preregistered 7B default-schema anchor before 32B scoring.",
            },
        )
    anchor_error = verify_anchor_against_locked_baseline(anchor_path)
    if anchor_error is not None:
        return anchor_error
    return verify_anchor_ollama_server_version(
        anchor_path,
        live_ollama_server_version=live_ollama_server_version,
    )


def verify_anchor_against_locked_baseline(
    new_summary_path: Path,
    *,
    locked_summary_path: Path = LOCKED_BASELINE_SUMMARY_PATH,
) -> Optional[GateRuntimeError]:
    try:
        new_payload = _read_json(new_summary_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return GateRuntimeError(
            "anchor_summary_unreadable",
            {
                "new_summary_path": str(new_summary_path),
                "message": str(error),
            },
        )
    locked_checks: Optional[Dict[str, object]] = None
    if locked_summary_path.exists():
        try:
            locked_payload = _read_json(locked_summary_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return GateRuntimeError(
                "locked_baseline_summary_unreadable",
                {
                    "locked_summary_path": str(locked_summary_path),
                    "message": str(error),
                },
            )
        locked_checks = _mapping(locked_payload.get("unlock_checks"))
    new_checks = _mapping(new_payload.get("unlock_checks"))
    mismatches = []
    for key, expected in LOCKED_BASELINE_UNLOCK_CHECKS.items():
        observed = new_checks.get(key)
        locked_observed = locked_checks.get(key) if locked_checks is not None else expected
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
    return GateRuntimeError(
        "anchor_reproduction_mismatch",
        {
            "new_summary_path": str(new_summary_path),
            "locked_summary_path": str(locked_summary_path),
            "locked_summary_present": locked_checks is not None,
            "mismatches": mismatches,
        },
    )


def verify_anchor_ollama_server_version(
    anchor_summary_path: Path,
    *,
    live_ollama_server_version: str,
) -> Optional[GateRuntimeError]:
    try:
        anchor_payload = _read_json(anchor_summary_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return GateRuntimeError(
            "anchor_summary_unreadable",
            {
                "new_summary_path": str(anchor_summary_path),
                "message": str(error),
            },
        )
    anchor_version = anchor_payload.get("ollama_server_version")
    if not isinstance(anchor_version, str) or not anchor_version:
        return GateRuntimeError(
            "anchor_ollama_server_version_missing",
            {
                "anchor_summary_path": str(anchor_summary_path),
                "live_ollama_server_version": live_ollama_server_version,
            },
        )
    if not live_ollama_server_version:
        return GateRuntimeError(
            "live_ollama_server_version_missing",
            {
                "anchor_summary_path": str(anchor_summary_path),
                "anchor_ollama_server_version": anchor_version,
            },
        )
    if anchor_version == live_ollama_server_version:
        return None
    return GateRuntimeError(
        "anchor_ollama_server_version_mismatch",
        {
            "anchor_summary_path": str(anchor_summary_path),
            "anchor_ollama_server_version": anchor_version,
            "live_ollama_server_version": live_ollama_server_version,
        },
    )


def git_commit() -> str:
    return _git_output(["rev-parse", "HEAD"])


def working_tree_status() -> str:
    return "clean" if not _git_output(["status", "--short"]) else "dirty"


def _git_output(args: Sequence[str]) -> str:
    return subprocess.check_output(["git", *args], text=True, cwd=REPO_ROOT).strip()


def _read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _slug_for_filename(value: str) -> str:
    slug = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in value.strip()
    )
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "default"
