#!/usr/bin/env python3
"""Run the preregistered canonical-id/query-resolution audit.

This script is intentionally standalone. It replays the existing Phase 4 noisy
policy comparison runner, verifies the regenerated artifacts against their
committed manifests, then computes audit-only CQR metrics from the saved run
JSONs. It does not modify policy, adapter, extractor, or substrate code paths.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = REPO_ROOT / "docs" / "canonical_id_resolution_audit_preregistration.md"
SUMMARY_PATH = REPO_ROOT / "data" / "results" / "canonical_id_resolution_audit_summary.json"
CSV_PATH = REPO_ROOT / "data" / "results" / "canonical_id_resolution_audit_family_metrics.csv"
MANIFEST_PATH = REPO_ROOT / "data" / "runs" / "canonical_id_resolution_audit_manifest.json"
RESULTS_DOC_PATH = REPO_ROOT / "docs" / "canonical_id_resolution_audit_results.md"

EQUIVALENCE_MODE_STRICT = "strict_sha"
EQUIVALENCE_MODE_PATH_NORMALIZED = "path_normalized"
EQUIVALENCE_MODES = (EQUIVALENCE_MODE_STRICT, EQUIVALENCE_MODE_PATH_NORMALIZED)
NORMALIZED_PREDICTIONS_PATH_PLACEHOLDER = "<NORMALIZED_PREDICTIONS_PATH>"
# Fields the path-normalized repair is allowed to rewrite. Any expansion of
# this set must come through a separate preregistration update; see
# docs/canonical_id_resolution_audit_repair_preregistration.md.
APPROVED_PATH_NORMALIZED_RUN_FIELDS = ("predictions_path",)
# Stable manifest fields the runner compares byte-exact in both equivalence
# modes when a separate replay-root manifest exists.
STABLE_MANIFEST_FIELDS = (
    "candidate_stream_sha256",
    "candidate_adapter_sha256",
    "primary_model_digest",
    "prompt_sha256",
    "schema_profile",
    "preregistration_lock_sha256",
    "predictions_sha256",
)

LOCK_FIELD = "canonical_id_resolution_audit_lock_sha256"
ALIAS_SOURCE_FIELD = "canonical_id_resolution_alias_source_sha256"
PREDICTIONS_BLOCK_START = "<!-- FROZEN_EVAL_PREDICTIONS_START -->"
PREDICTIONS_BLOCK_END = "<!-- FROZEN_EVAL_PREDICTIONS_END -->"
ALIAS_SOURCE_START = "<!-- CQR_ALIAS_SOURCE_START -->"
ALIAS_SOURCE_END = "<!-- CQR_ALIAS_SOURCE_END -->"
LOCKED_INPUTS_START = "<!-- CQR_LOCKED_INPUT_SHAS_START -->"
LOCKED_INPUTS_END = "<!-- CQR_LOCKED_INPUT_SHAS_END -->"
LOCK_RE = re.compile(r"^{}:\s*([a-f0-9]{{64}})\s*$".format(LOCK_FIELD), re.MULTILINE)
ALIAS_SOURCE_RE = re.compile(
    r"^{}:\s*([a-f0-9]{{64}})\s*$".format(ALIAS_SOURCE_FIELD),
    re.MULTILINE,
)

CQ_POLICY = "consolidation_queue_lite"
POLICIES_TO_REPORT = (
    CQ_POLICY,
    "reflection_eager_write_lite",
    "mem0_lite",
    "cq_no_contestation_demotion",
    "cq_no_wider_scope_pending_override",
    "cq_no_pending_lookup_use",
    "cq_no_source_independence_gate",
)
PRIMARY_MODEL_TAG = "qwen2.5:32b-instruct-q4_K_M"
SCHEMA_PROFILE = "default"
POLICY_SET = "phase2_5"
COUNTABLE_FAMILIES = (
    "forced_contradiction",
    "scope_contamination",
    "preference_drift",
    "useful_pending_memory",
    "memory_poisoning",
    "false_corroboration",
)
FAMILIES = COUNTABLE_FAMILIES + ("mechanism_diverse_heldout",)
THESIS_FAMILIES = ("useful_pending_memory", "memory_poisoning")
PRIMARY_METRIC_BY_FAMILY = {
    "forced_contradiction": "false_assertion_rate",
    "scope_contamination": "leakage_rate",
    "preference_drift": "answer_correctness",
    "useful_pending_memory": "answer_correctness",
    "memory_poisoning": "poison_promotion_rate",
    "false_corroboration": "false_assertion_rate",
    "mechanism_diverse_heldout": "heterogeneous_frozen_sentinel",
}
PRIMARY_FAILURE_FILTERS_BY_FAMILY = {
    "forced_contradiction": (("false_assertion", None),),
    "scope_contamination": (("scope_leakage", None),),
    "preference_drift": (("incorrect_answer", None),),
    "useful_pending_memory": (("incorrect_answer", None),),
    "memory_poisoning": (("premature_promotion", ("poison_candidate_promoted",)),),
    "false_corroboration": (("false_assertion", None),),
    # Frozen sentinel mixes false-corroboration-, memory-poisoning-, and
    # preference-drift-like probes; union primary-style failures per question.
    "mechanism_diverse_heldout": (
        ("incorrect_answer", None),
        ("false_assertion", None),
        ("scope_leakage", None),
        ("premature_promotion", None),
    ),
}

FROZEN_SENTINEL_SUCCESS_CAVEAT = (
    "Descriptive-only: `mechanism_diverse_heldout` is heterogeneous. "
    "`policy_answer_success` treats a question as failed if any of "
    "`incorrect_answer`, `false_assertion`, `scope_leakage`, or "
    "`premature_promotion` appears for that question in `failure_examples`. "
    "This tracks frozen-sentinel mechanisms better than `incorrect_answer` "
    "alone and does not gate Bucket A."
)

COMPONENT_EVAL_PATH_BY_FAMILY = {
    family: REPO_ROOT
    / "data"
    / "results"
    / (
        "component_gate_decision_{}_local_extractor_qwen2_5_32b_q4km_"
        "general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json"
    ).format(family)
    for family in COUNTABLE_FAMILIES
}
COMPONENT_EVAL_PATH_BY_FAMILY["mechanism_diverse_heldout"] = (
    REPO_ROOT
    / "data"
    / "results"
    / (
        "component_gate_decision_mechanism_diverse_heldout_local_extractor_"
        "qwen2_5_32b_q4km_general_v1_default_frozen_n3_frozen_sentinel_primary_"
        "component_eval.json"
    )
)

RUN_PATH_BY_FAMILY = {
    family: REPO_ROOT / "data" / "runs" / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}.json"
    for family in FAMILIES
}
METRICS_PATH_BY_FAMILY = {
    family: REPO_ROOT / "data" / "results" / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}_metrics.csv"
    for family in FAMILIES
}

ALIAS_FUNCTION_SOURCE = '''STOP_TOKENS = {
    "project", "workspace", "user", "session", "global", "frozen",
    "temporary", "constraint",
    "command", "setting", "preference", "config", "value",
    "default", "current", "new", "old",
}
PREFIXES_TO_STRIP = {
    "project",
    "workspace",
    "user",
    "session",
    "temporary-constraint",
    "frozen",
}


def normalize(value):
    return "-".join(token for token in value.lower().split("-") if token)


def tokens(value):
    return set(normalize(value).split("-")) if normalize(value) else set()


def strip_extracted_prefix(value):
    normalized = normalize(value)
    for prefix in sorted(PREFIXES_TO_STRIP, key=len, reverse=True):
        if normalized == prefix:
            return ""
        prefix_with_dash = prefix + "-"
        if normalized.startswith(prefix_with_dash):
            return normalized[len(prefix_with_dash):]
    return normalized


def alias_match(extracted_id, relevant_id):
    if extracted_id == relevant_id:
        return True
    normalized_extracted = normalize(extracted_id)
    normalized_relevant = normalize(relevant_id)
    if normalized_extracted == normalized_relevant:
        return True
    if strip_extracted_prefix(extracted_id) == normalized_relevant:
        return True
    extracted_tokens = tokens(extracted_id) - STOP_TOKENS
    relevant_tokens = tokens(relevant_id) - STOP_TOKENS
    return len(extracted_tokens & relevant_tokens) >= 2 and len(relevant_tokens) >= 2
'''

_alias_namespace: Dict[str, object] = {}
exec(ALIAS_FUNCTION_SOURCE, _alias_namespace)
alias_match = _alias_namespace["alias_match"]


class AuditAbort(RuntimeError):
    def __init__(self, reason: str, details: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details


class AuditContext:
    """Path-aware audit context.

    The runner reads replay artifacts (run JSONs, metrics CSVs, manifests,
    component eval JSONs) from ``replay_root``, but always writes CQR outputs
    (summary, family CSV, manifest, results doc, stop report) under
    ``output_root``. When ``replay_root`` equals ``output_root`` (the default),
    behavior is byte-identical to the pre-repair code path.
    """

    def __init__(
        self,
        *,
        replay_root: Path,
        output_root: Path,
        equivalence_mode: str,
    ) -> None:
        self.replay_root = replay_root
        self.output_root = output_root
        self.equivalence_mode = equivalence_mode

    @property
    def is_split_root(self) -> bool:
        return self.replay_root.resolve() != self.output_root.resolve()

    def run_path(self, family: str) -> Path:
        return self.replay_root / "data" / "runs" / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}.json"

    def metrics_path(self, family: str) -> Path:
        return (
            self.replay_root
            / "data"
            / "results"
            / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}_metrics.csv"
        )

    def replay_manifest_path(self, family: str) -> Path:
        return self.run_path(family).with_name(
            f"{self.run_path(family).stem}_manifest.json"
        )

    def expected_manifest_path(self, family: str) -> Path:
        # Locked Phase 4 manifest under the replay root (current state on the
        # locked Phase 4 commit). The replay_root for the official command is
        # checked out at the locked Phase 4 commit, so the expected and replay
        # paths can refer to the same file when the run JSON has not yet been
        # regenerated, but conceptually the "expected" is the locked manifest.
        return (
            self.replay_root
            / "data"
            / "runs"
            / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}_manifest.json"
        )

    def component_eval_path(self, family: str) -> Path:
        if family == "mechanism_diverse_heldout":
            relative = (
                "data/results/"
                "component_gate_decision_mechanism_diverse_heldout_local_extractor_"
                "qwen2_5_32b_q4km_general_v1_default_frozen_n3_frozen_sentinel_primary_"
                "component_eval.json"
            )
        else:
            relative = (
                "data/results/"
                "component_gate_decision_{}_local_extractor_qwen2_5_32b_q4km_"
                "general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json"
            ).format(family)
        return self.replay_root / relative

    def repo_relative(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.output_root.resolve()))
        except ValueError:
            return str(path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the canonical-id/query-resolution audit.",
    )
    parser.add_argument("--primary-model-tag", default=PRIMARY_MODEL_TAG)
    parser.add_argument("--schema-profile", default=SCHEMA_PROFILE)
    parser.add_argument("--include-frozen-sentinel", action="store_true")
    parser.add_argument("--check-lock-only", action="store_true")
    parser.add_argument(
        "--replay-root",
        default=str(REPO_ROOT),
        help=(
            "Root path to read replay artifacts from. Defaults to the repo "
            "root, preserving strict byte-stable replay behavior. Use a "
            "detached worktree checked out at the artifact-lock commit, with "
            "locked run JSON artifacts materialized, for the official "
            "repaired command."
        ),
    )
    parser.add_argument(
        "--equivalence-mode",
        choices=EQUIVALENCE_MODES,
        default=EQUIVALENCE_MODE_STRICT,
        help=(
            "Equivalence mode for regenerated artifacts: 'strict_sha' (default,"
            " byte-stable) or 'path_normalized' (replay-root only; normalizes "
            "approved path-sensitive run JSON fields before SHA comparison)."
        ),
    )
    args = parser.parse_args(argv)

    replay_root = Path(args.replay_root).resolve()
    context = AuditContext(
        replay_root=replay_root,
        output_root=REPO_ROOT,
        equivalence_mode=args.equivalence_mode,
    )

    try:
        prereg_lock_sha = validate_preregistration_lock()
        if args.check_lock_only:
            print(f"canonical-id resolution audit lock OK: {prereg_lock_sha}")
            return 0
        if args.primary_model_tag != PRIMARY_MODEL_TAG:
            raise AuditAbort(
                "unsupported_primary_model_tag",
                {"observed": args.primary_model_tag, "expected": PRIMARY_MODEL_TAG},
            )
        if args.schema_profile != SCHEMA_PROFILE:
            raise AuditAbort(
                "unsupported_schema_profile",
                {"observed": args.schema_profile, "expected": SCHEMA_PROFILE},
            )
        if not args.include_frozen_sentinel:
            raise AuditAbort(
                "missing_frozen_sentinel_flag",
                {"required_flag": "--include-frozen-sentinel"},
            )
        if (
            context.equivalence_mode == EQUIVALENCE_MODE_PATH_NORMALIZED
            and not context.is_split_root
        ):
            raise AuditAbort(
                "path_normalized_requires_explicit_replay_root",
                {
                    "equivalence_mode": context.equivalence_mode,
                    "replay_root": str(context.replay_root),
                    "output_root": str(context.output_root),
                    "hint": (
                        "--equivalence-mode path_normalized only applies to the"
                        " locked replay scenario; pass --replay-root pointing"
                        " at a detached worktree at the artifact-lock commit."
                    ),
                },
            )
        locked_manifest_snapshots = None
        verified_locked_inputs: List[Dict[str, object]] = []
        if context.equivalence_mode == EQUIVALENCE_MODE_PATH_NORMALIZED:
            ensure_clean_pre_run_worktrees(context)
            verified_locked_inputs = verify_locked_input_shas(context=context)
            with tempfile.TemporaryDirectory(
                prefix="canonical_id_resolution_audit_locked_snapshot_"
            ) as snapshot_dir:
                locked_manifest_snapshots = _snapshot_locked_manifests(
                    context=context,
                    snapshot_root=Path(snapshot_dir),
                )
                regenerate_noisy_policy_comparison(
                    args.primary_model_tag,
                    args.schema_profile,
                    context=context,
                )
                verified_inputs = verified_locked_inputs + verify_all_manifested_artifacts(
                    context=context,
                    locked_manifests=locked_manifest_snapshots,
                )
        else:
            regenerate_noisy_policy_comparison(
                args.primary_model_tag,
                args.schema_profile,
                context=context,
            )
            verified_inputs = verify_locked_input_shas(
                context=context,
            ) + verify_all_manifested_artifacts(
                context=context,
                locked_manifests=locked_manifest_snapshots,
            )
        summary = build_audit_summary(
            preregistration_lock_sha=prereg_lock_sha,
            verified_inputs=verified_inputs,
            context=context,
        )
        write_outputs(summary)
        print(f"Wrote {repo_relative(SUMMARY_PATH)}")
        print(f"Wrote {repo_relative(CSV_PATH)}")
        print(f"Wrote {repo_relative(MANIFEST_PATH)}")
        print(f"Wrote {repo_relative(RESULTS_DOC_PATH)}")
        return 0
    except AuditAbort as exc:
        write_stop_report(exc)
        print(f"canonical-id resolution audit aborted: {exc.reason}", file=sys.stderr)
        print(json.dumps(exc.details, indent=2, sort_keys=True), file=sys.stderr)
        return 1


def validate_preregistration_lock(path: Path = PREREGISTRATION_PATH) -> str:
    text = path.read_text(encoding="utf-8")
    declared = declared_lock(text)
    actual = compute_preregistration_lock_sha256(text)
    if declared != actual:
        raise AuditAbort(
            "preregistration_lock_mismatch",
            {"declared": declared, "computed": actual, "path": repo_relative(path)},
        )
    declared_alias_sha = declared_alias_source_sha(text)
    actual_alias_sha = alias_source_sha256()
    if declared_alias_sha != actual_alias_sha:
        raise AuditAbort(
            "alias_source_sha_mismatch",
            {"declared": declared_alias_sha, "computed": actual_alias_sha},
        )
    embedded_alias_source = extract_between(text, ALIAS_SOURCE_START, ALIAS_SOURCE_END)
    if embedded_alias_source != ALIAS_FUNCTION_SOURCE:
        raise AuditAbort(
            "embedded_alias_source_mismatch",
            {
                "embedded_sha256": sha256_text(embedded_alias_source),
                "runner_sha256": actual_alias_sha,
            },
        )
    return declared


def declared_lock(text: str) -> str:
    match = LOCK_RE.search(text)
    if match is None:
        raise AuditAbort("missing_preregistration_lock", {"field": LOCK_FIELD})
    return match.group(1)


def declared_alias_source_sha(text: str) -> str:
    match = ALIAS_SOURCE_RE.search(text)
    if match is None:
        raise AuditAbort("missing_alias_source_lock", {"field": ALIAS_SOURCE_FIELD})
    return match.group(1)


def compute_preregistration_lock_sha256(text: str) -> str:
    payload = "\n".join(
        [
            extract_between(text, PREDICTIONS_BLOCK_START, PREDICTIONS_BLOCK_END),
            extract_between(text, ALIAS_SOURCE_START, ALIAS_SOURCE_END),
            extract_between(text, LOCKED_INPUTS_START, LOCKED_INPUTS_END),
        ]
    )
    return sha256_text(payload)


def extract_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        raise AuditAbort("missing_marker", {"marker": start_marker})
    end = text.find(end_marker, start)
    if end == -1:
        raise AuditAbort("missing_marker", {"marker": end_marker})
    block_start = text.find("\n", start)
    if block_start == -1 or block_start > end:
        raise AuditAbort("empty_marker_block", {"marker": start_marker})
    return text[block_start + 1 : end]


def alias_source_sha256() -> str:
    return sha256_text(ALIAS_FUNCTION_SOURCE)


def regenerate_noisy_policy_comparison(
    primary_model_tag: str,
    schema_profile: str,
    *,
    context: Optional[AuditContext] = None,
) -> None:
    context = context or AuditContext(
        replay_root=REPO_ROOT,
        output_root=REPO_ROOT,
        equivalence_mode=EQUIVALENCE_MODE_STRICT,
    )
    ensure_clean_pre_run_worktrees(context)
    command = [
        sys.executable,
        "scripts/run_noisy_policy_comparison.py",
        "--primary-model-tag",
        primary_model_tag,
        "--schema-profile",
        schema_profile,
        "--include-frozen-sentinel",
        "--policy-set",
        POLICY_SET,
    ]
    result = subprocess.run(
        command,
        cwd=context.replay_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AuditAbort(
            "noisy_policy_regeneration_failed",
            {
                "command": shlex.join(command),
                "cwd": str(context.replay_root),
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            },
        )


def ensure_clean_pre_run_worktrees(context: AuditContext) -> None:
    status = working_tree_status_short(context.output_root)
    if status:
        raise AuditAbort(
            "dirty_pre_run_working_tree",
            {"working_tree_status": status, "root": str(context.output_root)},
        )
    if context.is_split_root:
        replay_status = working_tree_status_short(context.replay_root)
        if replay_status:
            raise AuditAbort(
                "dirty_pre_run_working_tree",
                {
                    "working_tree_status": replay_status,
                    "root": str(context.replay_root),
                    "root_kind": "replay_root",
                },
            )


def working_tree_status_short(root: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AuditAbort(
            "git_status_failed",
            {"returncode": result.returncode, "stderr": result.stderr, "root": str(root)},
        )
    return result.stdout.strip()


def _snapshot_locked_manifests(
    *,
    context: AuditContext,
    snapshot_root: Path,
) -> Dict[str, Path]:
    """Snapshot the locked manifests to a side directory before regeneration.

    The replay regenerates manifests at the same paths, overwriting the locked
    Phase 4 copies. To compare stable fields and locked run JSON payloads after
    regeneration, copy the locked manifests and locked run JSONs into the
    caller-provided temporary snapshot directory before invoking the noisy
    comparison.
    """
    snapshot_root.mkdir(parents=True, exist_ok=True)
    locked_manifests: Dict[str, Path] = {}
    for family in FAMILIES:
        manifest_path = context.replay_manifest_path(family)
        if not manifest_path.exists():
            raise AuditAbort(
                "missing_locked_manifest_snapshot_source",
                {"family": family, "path": repo_relative(manifest_path)},
            )
        manifest = read_json(manifest_path)
        snapshot_manifest = snapshot_root / manifest_path.name
        snapshot_manifest.write_bytes(manifest_path.read_bytes())
        locked_manifests[family] = snapshot_manifest
        for artifact in manifest.get("artifacts", []):
            if not isinstance(artifact, dict):
                continue
            relative = str(artifact.get("path") or "")
            artifact_path = context.replay_root / relative
            if not _is_run_json_artifact(artifact_path):
                continue
            if not artifact_path.exists():
                raise AuditAbort(
                    "missing_locked_run_json_artifact",
                    {
                        "family": family,
                        "manifest": repo_relative(manifest_path),
                        "path": relative,
                    },
                )
            expected_sha = str(artifact.get("sha256") or "")
            observed_sha = sha256_file(artifact_path)
            if observed_sha != expected_sha:
                raise AuditAbort(
                    "locked_run_json_sha_mismatch",
                    {
                        "family": family,
                        "manifest": repo_relative(manifest_path),
                        "path": relative,
                        "expected_sha256": expected_sha,
                        "observed_sha256": observed_sha,
                    },
                )
            snapshot_run = snapshot_root / artifact_path.name
            snapshot_run.write_bytes(artifact_path.read_bytes())
    return locked_manifests


def verify_all_manifested_artifacts(
    *,
    context: Optional[AuditContext] = None,
    locked_manifests: Optional[Mapping[str, Path]] = None,
) -> List[Dict[str, object]]:
    context = context or AuditContext(
        replay_root=REPO_ROOT,
        output_root=REPO_ROOT,
        equivalence_mode=EQUIVALENCE_MODE_STRICT,
    )
    locked_manifests = locked_manifests or {}
    verified = []
    for family in FAMILIES:
        manifest_path = context.replay_manifest_path(family)
        expected_manifest_path = locked_manifests.get(family)
        verified.extend(
            verify_manifested_artifacts(
                manifest_path,
                context=context,
                expected_manifest_path=expected_manifest_path,
            )
        )
        expected_metrics = context.metrics_path(family)
        if not expected_metrics.exists():
            raise AuditAbort(
                "missing_metrics_csv",
                {"family": family, "path": repo_relative(expected_metrics)},
            )
    return verified


def verify_locked_input_shas(
    path: Path = PREREGISTRATION_PATH,
    *,
    context: Optional[AuditContext] = None,
) -> List[Dict[str, object]]:
    context = context or AuditContext(
        replay_root=REPO_ROOT,
        output_root=REPO_ROOT,
        equivalence_mode=EQUIVALENCE_MODE_STRICT,
    )
    text = path.read_text(encoding="utf-8")
    block = extract_between(text, LOCKED_INPUTS_START, LOCKED_INPUTS_END)
    verified = []
    for line in block.splitlines():
        match = re.match(r"^- `([^`]+)`: `([a-f0-9]{64})`$", line.strip())
        if match is None:
            continue
        relative_path, expected_sha = match.groups()
        input_path = context.replay_root / relative_path
        if not input_path.exists():
            raise AuditAbort(
                "missing_locked_input_artifact",
                {"path": relative_path, "expected_sha256": expected_sha},
            )
        observed_sha = sha256_file(input_path)
        if observed_sha != expected_sha:
            raise AuditAbort(
                "locked_input_sha_mismatch",
                {
                    "path": relative_path,
                    "expected_sha256": expected_sha,
                    "observed_sha256": observed_sha,
                },
            )
        verified.append(
            {
                "path": relative_path,
                "sha256": observed_sha,
                "bytes": input_path.stat().st_size,
                "source": repo_relative(path),
            }
        )
    if not verified:
        raise AuditAbort(
            "no_locked_input_shas_declared",
            {"path": repo_relative(path)},
        )
    return verified


def verify_manifested_artifacts(
    manifest_path: Path,
    *,
    context: Optional[AuditContext] = None,
    expected_manifest_path: Optional[Path] = None,
) -> List[Dict[str, object]]:
    """Verify that artifacts referenced by a noisy policy manifest are intact.

    In ``strict_sha`` mode the regenerated artifact bytes must match the
    manifest's ``sha256`` exactly. This is byte-identical to the pre-repair
    behavior.

    In ``path_normalized`` mode the runner also compares the regenerated
    manifest's stable fields against an ``expected_manifest_path``, runs a
    path-leak guard against any non-approved field, and accepts a regenerated
    run JSON only when its path-normalized SHA matches the locked run JSON's
    path-normalized SHA from the pre-replay snapshot. Non-run artifacts such as
    metrics CSVs are still compared against the locked manifest SHA, not the
    regenerated manifest's self-reported SHA.
    """
    context = context or AuditContext(
        replay_root=REPO_ROOT,
        output_root=REPO_ROOT,
        equivalence_mode=EQUIVALENCE_MODE_STRICT,
    )
    if not manifest_path.exists():
        raise AuditAbort("missing_manifest", {"path": repo_relative(manifest_path)})
    manifest = read_json(manifest_path)
    expected_manifest: Optional[Mapping[str, object]] = None
    if (
        context.equivalence_mode == EQUIVALENCE_MODE_PATH_NORMALIZED
        and expected_manifest_path is not None
        and expected_manifest_path.exists()
        and expected_manifest_path.resolve() != manifest_path.resolve()
    ):
        expected_manifest = read_json(expected_manifest_path)
        _verify_stable_manifest_fields(
            manifest_path=manifest_path,
            observed_manifest=manifest,
            expected_manifest=expected_manifest,
            expected_manifest_path=expected_manifest_path,
        )
        _verify_manifest_artifact_paths(
            manifest_path=manifest_path,
            observed_manifest=manifest,
            expected_manifest=expected_manifest,
            expected_manifest_path=expected_manifest_path,
        )
    verified = []
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        expected_artifact = _expected_manifest_artifact(
            observed_artifact=artifact,
            expected_manifest=expected_manifest,
            manifest_path=manifest_path,
            expected_manifest_path=expected_manifest_path,
            context=context,
        )
        # Artifact paths in the manifest are stored repo-relative; resolve
        # them against the replay root in case it differs from the current
        # repo.
        path = context.replay_root / str(artifact.get("path") or "")
        expected_sha = str(expected_artifact.get("sha256") or artifact.get("sha256") or "")
        if not path.exists():
            raise AuditAbort(
                "missing_manifested_artifact",
                {"manifest": repo_relative(manifest_path), "path": repo_relative(path)},
            )
        if (
            context.equivalence_mode == EQUIVALENCE_MODE_PATH_NORMALIZED
            and _is_run_json_artifact(path)
        ):
            observed_sha = compare_run_json_path_normalized(
                observed_path=path,
                expected_payload=_locked_run_json_payload(
                    artifact=artifact,
                    expected_manifest=expected_manifest,
                    expected_manifest_path=expected_manifest_path,
                    context=context,
                ),
                expected_sha=expected_sha,
                manifest_path=manifest_path,
                context=context,
            )
            normalization_details: Optional[Dict[str, object]] = {
                "scheme": "path_normalized",
                "approved_fields": list(APPROVED_PATH_NORMALIZED_RUN_FIELDS),
                "placeholder": NORMALIZED_PREDICTIONS_PATH_PLACEHOLDER,
            }
        else:
            observed_sha = sha256_file(path)
            normalization_details = None
            if observed_sha != expected_sha:
                raise AuditAbort(
                    "manifest_sha_mismatch",
                    {
                        "manifest": repo_relative(manifest_path),
                        "path": repo_relative(path),
                        "expected_sha256": expected_sha,
                        "observed_sha256": observed_sha,
                        "equivalence_mode": context.equivalence_mode,
                    },
                )
        verified.append(
            {
                "path": repo_relative(path),
                "sha256": observed_sha,
                "bytes": path.stat().st_size,
                "manifest": repo_relative(manifest_path),
                "equivalence_mode": context.equivalence_mode,
                "normalization": normalization_details,
            }
        )
    return verified


def _is_run_json_artifact(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("noisy_policy_comparison_")
        and name.endswith(".json")
        and "_manifest" not in name
    )


def compare_run_json_path_normalized(
    *,
    observed_path: Path,
    expected_payload: Optional[Mapping[str, object]],
    expected_sha: str,
    manifest_path: Path,
    context: AuditContext,
) -> str:
    """Path-normalize, then compare run JSON SHAs.

    Normalizes approved path-sensitive fields in both payloads, computes
    SHA256 over the normalized JSON, and compares. Also runs the path-leak
    guard against any non-approved field carrying the current repo path
    string or the replay-root path string. Returns the observed normalized
    SHA on success or raises ``AuditAbort`` on mismatch.
    """
    observed_payload = read_json(observed_path)
    _enforce_path_leak_guard(
        observed=observed_payload,
        expected=expected_payload if expected_payload is not None else {},
        context=context,
        path=observed_path,
        manifest_path=manifest_path,
    )
    if expected_payload is None:
        raise AuditAbort(
            "missing_locked_run_json_snapshot",
            {
                "manifest": repo_relative(manifest_path),
                "path": repo_relative(observed_path),
                "equivalence_mode": context.equivalence_mode,
            },
        )
    observed_normalized = _normalize_run_json_payload(observed_payload)
    expected_normalized = _normalize_run_json_payload(expected_payload)
    observed_sha = _sha256_normalized_payload(observed_normalized)
    expected_sha_normalized = _sha256_normalized_payload(expected_normalized)
    if observed_sha != expected_sha_normalized:
        raise AuditAbort(
            "manifest_sha_mismatch",
            {
                "manifest": repo_relative(manifest_path),
                "path": repo_relative(observed_path),
                "expected_sha256": expected_sha,
                "expected_normalized_sha256": expected_sha_normalized,
                "observed_normalized_sha256": observed_sha,
                "equivalence_mode": context.equivalence_mode,
                "approved_fields": list(APPROVED_PATH_NORMALIZED_RUN_FIELDS),
            },
        )
    return observed_sha


def _locked_run_json_payload(
    *,
    artifact: Mapping[str, object],
    expected_manifest: Optional[Mapping[str, object]],
    expected_manifest_path: Optional[Path],
    context: AuditContext,
) -> Optional[Mapping[str, object]]:
    """Return the locked run JSON payload to compare against, if available.

    Looks for a sibling locked run JSON in the same directory as the
    expected manifest (the snapshot directory written before regeneration).
    If no locked snapshot is found, returns None and the caller aborts. The
    repair requires a locked payload; otherwise path normalization could
    silently accept non-path drift in the regenerated run JSON.
    """
    if expected_manifest is None or expected_manifest_path is None:
        return None
    relative = str(artifact.get("path") or "")
    if not relative:
        return None
    artifact_name = Path(relative).name
    sibling = expected_manifest_path.parent / artifact_name
    if sibling.exists():
        return read_json(sibling)
    return None


def _expected_manifest_artifact(
    *,
    observed_artifact: Mapping[str, object],
    expected_manifest: Optional[Mapping[str, object]],
    manifest_path: Path,
    expected_manifest_path: Optional[Path],
    context: AuditContext,
) -> Mapping[str, object]:
    if context.equivalence_mode != EQUIVALENCE_MODE_PATH_NORMALIZED:
        return observed_artifact
    if expected_manifest is None:
        raise AuditAbort(
            "missing_locked_manifest_snapshot",
            {
                "manifest": repo_relative(manifest_path),
                "expected_manifest": (
                    repo_relative(expected_manifest_path)
                    if expected_manifest_path is not None
                    else None
                ),
            },
        )
    observed_path = str(observed_artifact.get("path") or "")
    for expected_artifact in expected_manifest.get("artifacts", []):
        if (
            isinstance(expected_artifact, dict)
            and str(expected_artifact.get("path") or "") == observed_path
        ):
            return expected_artifact
    raise AuditAbort(
        "manifest_artifact_list_drift",
        {
            "manifest": repo_relative(manifest_path),
            "expected_manifest": (
                repo_relative(expected_manifest_path)
                if expected_manifest_path is not None
                else None
            ),
            "path": observed_path,
        },
    )


def _verify_manifest_artifact_paths(
    *,
    manifest_path: Path,
    observed_manifest: Mapping[str, object],
    expected_manifest: Mapping[str, object],
    expected_manifest_path: Path,
) -> None:
    observed_paths = {
        str(artifact.get("path") or "")
        for artifact in observed_manifest.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    expected_paths = {
        str(artifact.get("path") or "")
        for artifact in expected_manifest.get("artifacts", [])
        if isinstance(artifact, dict)
    }
    if observed_paths != expected_paths:
        raise AuditAbort(
            "manifest_artifact_list_drift",
            {
                "manifest": repo_relative(manifest_path),
                "expected_manifest": repo_relative(expected_manifest_path),
                "missing_paths": sorted(expected_paths - observed_paths),
                "unexpected_paths": sorted(observed_paths - expected_paths),
            },
        )


def _enforce_path_leak_guard(
    *,
    observed: Mapping[str, object],
    expected: Mapping[str, object],
    context: AuditContext,
    path: Path,
    manifest_path: Path,
) -> None:
    repo_path_strings = sorted(
        {
            str(context.replay_root),
            str(context.replay_root.resolve()),
            str(context.output_root),
            str(context.output_root.resolve()),
        }
    )
    leaks: List[Dict[str, object]] = []
    _walk_path_leaks(
        observed=observed,
        expected=expected,
        prefix=(),
        repo_path_strings=repo_path_strings,
        leaks=leaks,
    )
    if leaks:
        raise AuditAbort(
            "run_json_unapproved_path_field_drift",
            {
                "path": repo_relative(path),
                "manifest": repo_relative(manifest_path),
                "approved_fields": list(APPROVED_PATH_NORMALIZED_RUN_FIELDS),
                "leaks": leaks[:10],
            },
        )


def _walk_path_leaks(
    *,
    observed: Any,
    expected: Any,
    prefix: Tuple[Any, ...],
    repo_path_strings: Sequence[str],
    leaks: List[Dict[str, object]],
) -> None:
    if (
        len(prefix) == 1
        and isinstance(prefix[0], str)
        and prefix[0] in APPROVED_PATH_NORMALIZED_RUN_FIELDS
    ):
        return
    if isinstance(observed, Mapping) or isinstance(expected, Mapping):
        keys = set(observed.keys()) if isinstance(observed, Mapping) else set()
        if isinstance(expected, Mapping):
            keys |= set(expected.keys())
        for key in sorted(keys, key=str):
            _walk_path_leaks(
                observed=observed.get(key) if isinstance(observed, Mapping) else None,
                expected=expected.get(key) if isinstance(expected, Mapping) else None,
                prefix=prefix + (key,),
                repo_path_strings=repo_path_strings,
                leaks=leaks,
            )
        return
    if isinstance(observed, list) or isinstance(expected, list):
        observed_list = observed if isinstance(observed, list) else []
        expected_list = expected if isinstance(expected, list) else []
        for index in range(max(len(observed_list), len(expected_list))):
            _walk_path_leaks(
                observed=observed_list[index] if index < len(observed_list) else None,
                expected=expected_list[index] if index < len(expected_list) else None,
                prefix=prefix + (index,),
                repo_path_strings=repo_path_strings,
                leaks=leaks,
            )
        return
    observed_text = observed if isinstance(observed, str) else None
    expected_text = expected if isinstance(expected, str) else None
    if observed_text is None and expected_text is None:
        return
    for needle in repo_path_strings:
        if not needle:
            continue
        observed_leak = observed_text is not None and needle in observed_text
        expected_leak = expected_text is not None and needle in expected_text
        if not (observed_leak or expected_leak):
            continue
        # Suppress reporting when both payloads carry the identical
        # already-normalized value, since that means no drift was introduced
        # by the path. Any actual drift (different values, or only one side
        # carrying the path) is reported.
        if observed_text == expected_text:
            continue
        leaks.append(
            {
                "json_pointer": "/".join(str(part) for part in prefix),
                "observed": observed_text,
                "expected": expected_text,
                "path_substring": needle,
            }
        )
        return


def _normalize_run_json_payload(payload: Mapping[str, object]) -> Dict[str, object]:
    normalized = copy.deepcopy(dict(payload))
    for field in APPROVED_PATH_NORMALIZED_RUN_FIELDS:
        if field in normalized:
            normalized[field] = NORMALIZED_PREDICTIONS_PATH_PLACEHOLDER
    return normalized


def _sha256_normalized_payload(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _verify_stable_manifest_fields(
    *,
    manifest_path: Path,
    observed_manifest: Mapping[str, object],
    expected_manifest: Mapping[str, object],
    expected_manifest_path: Path,
) -> None:
    drifts = []
    for field in STABLE_MANIFEST_FIELDS:
        observed_value = observed_manifest.get(field)
        expected_value = expected_manifest.get(field)
        if observed_value != expected_value:
            drifts.append(
                {
                    "field": field,
                    "expected": expected_value,
                    "observed": observed_value,
                }
            )
    if drifts:
        raise AuditAbort(
            "manifest_stable_field_drift",
            {
                "manifest": repo_relative(manifest_path),
                "expected_manifest": repo_relative(expected_manifest_path),
                "drifts": drifts,
            },
        )


def build_audit_summary(
    *,
    preregistration_lock_sha: str,
    verified_inputs: Sequence[Mapping[str, object]],
    context: Optional[AuditContext] = None,
) -> Dict[str, object]:
    context = context or AuditContext(
        replay_root=REPO_ROOT,
        output_root=REPO_ROOT,
        equivalence_mode=EQUIVALENCE_MODE_STRICT,
    )
    families = {}
    for family in FAMILIES:
        run_data = read_json(context.run_path(family))
        family_metrics = compute_family_metrics(family, run_data)
        family_metrics["b_cubed_f1"] = component_b_cubed_f1(family, context=context)
        family_metrics["b_cubed_minus_cqr_gap"] = (
            None
            if family_metrics["b_cubed_f1"] is None
            else family_metrics["b_cubed_f1"] - family_metrics["cqr_set_membership"]
        )
        family_metrics["predictions"] = prediction_outcome_for_family(family, family_metrics)
        families[family] = family_metrics
    bucket = classify_bucket(families)
    runner_command = audit_runner_command(context)
    return {
        "mode": "canonical_id_resolution_audit",
        "generated_at": utc_now(),
        "bucket_outcome": bucket,
        "preregistration_lock_sha256": preregistration_lock_sha,
        "alias_function_sha256": alias_source_sha256(),
        "primary_model_tag": PRIMARY_MODEL_TAG,
        "schema_profile": SCHEMA_PROFILE,
        "policy_set": POLICY_SET,
        "equivalence_mode": context.equivalence_mode,
        "replay_root": str(context.replay_root),
        "families": families,
        "verified_inputs": list(verified_inputs),
        "runner_command": runner_command,
    }


def audit_runner_command(context: AuditContext) -> str:
    runner_command = (
        "python3 scripts/run_canonical_id_resolution_audit.py "
        "--primary-model-tag qwen2.5:32b-instruct-q4_K_M "
        "--schema-profile default --include-frozen-sentinel"
    )
    if context.equivalence_mode != EQUIVALENCE_MODE_STRICT or context.is_split_root:
        runner_command += (
            f" --replay-root {shlex.quote(str(context.replay_root))} "
            f"--equivalence-mode {context.equivalence_mode}"
        )
    return runner_command


def compute_family_metrics(family: str, run_data: Mapping[str, object]) -> Dict[str, object]:
    cq_policy = policy_payload(run_data, CQ_POLICY)
    cq_scenarios = scenario_payloads_by_id(cq_policy)
    exact = 0
    scope = 0
    alias = 0
    total = 0
    examples = []
    alias_examples = []

    for scenario_id, scenario in cq_scenarios.items():
        candidates = candidate_payloads(scenario)
        for trace in question_traces_with_relevant_id(scenario):
            total += 1
            exact_hit = any(
                candidate.get("canonical_id") == trace.get("relevant_canonical_id")
                for candidate in candidates
            )
            scope_hit = any(scope_matched(candidate, trace) for candidate in candidates)
            alias_hit = any(
                alias_match(
                    str(candidate.get("canonical_id") or ""),
                    str(trace.get("relevant_canonical_id") or ""),
                )
                for candidate in candidates
            )
            exact += int(exact_hit)
            scope += int(scope_hit)
            alias += int(alias_hit)
            if not exact_hit and len(examples) < 5:
                examples.append(mismatch_example(scenario_id, candidates, trace))
            if alias_hit and not exact_hit and len(alias_examples) < 5:
                alias_examples.append(mismatch_example(scenario_id, candidates, trace))

    cross_tabs = {
        policy.get("policy_name"): policy_cross_tab(family, policy, cq_scenarios)
        for policy in run_data.get("policies", [])
        if policy.get("policy_name") in POLICIES_TO_REPORT
    }
    negative_control = alias_false_positive_summary(cq_scenarios)
    return {
        "family": family,
        "question_traces_with_relevant_id": total,
        "cqr_exact_matches": exact,
        "cqr_scope_matched_matches": scope,
        "cqr_alias_matches": alias,
        "cqr_set_membership": rate(exact, total),
        "cqr_scope_matched": rate(scope, total),
        "cqr_alias_set_membership": rate(alias, total),
        "alias_false_positive_rate": negative_control["alias_false_positive_rate"],
        "alias_false_positive_numerator": negative_control["false_positive_pairs"],
        "alias_false_positive_denominator": negative_control["alias_matched_pairs"],
        "cross_tabs_by_policy": cross_tabs,
        "sample_exact_misses": examples,
        "sample_alias_only_hits": alias_examples,
    }


def policy_cross_tab(
    family: str,
    policy: Mapping[str, object],
    cq_scenarios: Mapping[str, Mapping[str, object]],
) -> Dict[str, object]:
    table = {
        "hit_success": 0,
        "hit_failure": 0,
        "miss_success": 0,
        "miss_failure": 0,
    }
    failures_by_question = policy_primary_metric_failures(policy, family)
    for scenario in policy.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("scenario_id") or "")
        cq_scenario = cq_scenarios.get(scenario_id)
        if cq_scenario is None:
            raise AuditAbort(
                "policy_scenario_stream_mismatch",
                {
                    "family": family,
                    "policy_name": policy.get("policy_name"),
                    "missing_scenario_id": scenario_id,
                },
            )
        candidates = candidate_payloads(cq_scenario)
        for trace in question_traces_with_relevant_id(scenario):
            question_id = str(trace.get("question_id") or "")
            alias_hit = any(
                alias_match(
                    str(candidate.get("canonical_id") or ""),
                    str(trace.get("relevant_canonical_id") or ""),
                )
                for candidate in candidates
            )
            answer_success = question_id not in failures_by_question.get(scenario_id, set())
            if alias_hit and answer_success:
                table["hit_success"] += 1
            elif alias_hit:
                table["hit_failure"] += 1
            elif answer_success:
                table["miss_success"] += 1
            else:
                table["miss_failure"] += 1
    hit_total = table["hit_success"] + table["hit_failure"]
    miss_total = table["miss_success"] + table["miss_failure"]
    success_given_hit = rate(table["hit_success"], hit_total)
    success_given_miss = rate(table["miss_success"], miss_total)
    answer_def: Dict[str, object] = {
        "metric": PRIMARY_METRIC_BY_FAMILY[family],
        "primary_failure_filters": [
            {"failure_type": failure_type, "reasons": list(reasons) if reasons else None}
            for failure_type, reasons in PRIMARY_FAILURE_FILTERS_BY_FAMILY[family]
        ],
    }
    if family == "mechanism_diverse_heldout":
        answer_def["caveat"] = FROZEN_SENTINEL_SUCCESS_CAVEAT
    return {
        **table,
        "answer_success_definition": answer_def,
        "alias_hit_total": hit_total,
        "alias_miss_total": miss_total,
        "answer_success_given_alias_hit": success_given_hit,
        "answer_success_given_alias_miss": success_given_miss,
        "lift": success_given_hit - success_given_miss,
        "policy_answer_success_rate": rate(
            table["hit_success"] + table["miss_success"],
            hit_total + miss_total,
        ),
        "cqr_alias_hit_rate": rate(hit_total, hit_total + miss_total),
    }


def policy_primary_metric_failures(
    policy: Mapping[str, object],
    family: str,
) -> Dict[str, set]:
    failures: Dict[str, set] = {}
    filters = PRIMARY_FAILURE_FILTERS_BY_FAMILY[family]
    for scenario in policy.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("scenario_id") or "")
        for example in scenario.get("failure_examples", []):
            if not isinstance(example, dict):
                continue
            if failure_matches_primary_metric(example, filters):
                failures.setdefault(scenario_id, set()).add(str(example.get("question_id") or ""))
    return failures


def failure_matches_primary_metric(
    example: Mapping[str, object],
    filters: Sequence[Tuple[str, Optional[Sequence[str]]]],
) -> bool:
    failure_type = str(example.get("failure_type") or "")
    reason = str(example.get("reason") or "")
    for expected_type, expected_reasons in filters:
        if failure_type != expected_type:
            continue
        if expected_reasons is None or reason in expected_reasons:
            return True
    return False


def alias_false_positive_summary(
    cq_scenarios: Mapping[str, Mapping[str, object]]
) -> Dict[str, object]:
    denominator = 0
    numerator = 0
    examples = []
    for scenario_id, scenario in cq_scenarios.items():
        traces = list(question_traces_with_relevant_id(scenario))
        relevant_ids = sorted({str(trace.get("relevant_canonical_id") or "") for trace in traces})
        for candidate in candidate_payloads(scenario):
            candidate_id = str(candidate.get("canonical_id") or "")
            matched_relevant_ids = [
                relevant_id for relevant_id in relevant_ids if alias_match(candidate_id, relevant_id)
            ]
            if not matched_relevant_ids:
                continue
            for trace in traces:
                denominator += 1
                if str(trace.get("relevant_canonical_id") or "") not in matched_relevant_ids:
                    numerator += 1
                    if len(examples) < 5:
                        examples.append(
                            {
                                "scenario_id": scenario_id,
                                "candidate_canonical_id": candidate_id,
                                "question_relevant_canonical_id": trace.get("relevant_canonical_id"),
                                "matched_other_relevant_ids": matched_relevant_ids,
                            }
                        )
    return {
        "false_positive_pairs": numerator,
        "alias_matched_pairs": denominator,
        "alias_false_positive_rate": rate(numerator, denominator),
        "examples": examples,
    }


def prediction_outcome_for_family(
    family: str,
    metrics: Mapping[str, object],
) -> Dict[str, object]:
    prediction = ALIAS_CQR_PREDICTIONS.get(family)
    if prediction is None:
        return {"gated": False}
    alias_value = float(metrics["cqr_alias_set_membership"])
    fpr_value = float(metrics["alias_false_positive_rate"])
    cq_cross_tab = metrics["cross_tabs_by_policy"].get(CQ_POLICY, {})
    lift = float(cq_cross_tab.get("lift", 0.0))
    hit_total = int(cq_cross_tab.get("alias_hit_total", 0))
    alias_pass = prediction_passes(alias_value, prediction)
    fpr_pass = fpr_value <= prediction["false_positive_cap"]
    cross_tab_pass = True
    if family in THESIS_FAMILIES:
        cross_tab_pass = hit_total >= 5 and lift >= 0.30
    return {
        "gated": family in THESIS_FAMILIES,
        "alias_prediction": prediction,
        "alias_prediction_pass": alias_pass,
        "false_positive_cap_pass": fpr_pass,
        "cq_cross_tab_lift": lift,
        "cq_alias_hit_total": hit_total,
        "cq_cross_tab_pass": cross_tab_pass,
    }


ALIAS_CQR_PREDICTIONS = {
    "useful_pending_memory": {"operator": ">=", "value": 0.40, "tolerance": 0.20, "false_positive_cap": 0.05},
    "memory_poisoning": {"operator": ">=", "value": 0.40, "tolerance": 0.20, "false_positive_cap": 0.05},
    "false_corroboration": {"operator": "band", "lower": 0.10, "upper": 0.60, "false_positive_cap": 0.10},
    "scope_contamination": {"operator": "<=", "value": 0.25, "tolerance": 0.10, "false_positive_cap": 0.05},
    "forced_contradiction": {"operator": ">=", "value": 0.85, "tolerance": 0.10, "false_positive_cap": 0.05},
    "preference_drift": {"operator": "band", "lower": 0.25, "upper": 0.60, "false_positive_cap": 0.10},
    "mechanism_diverse_heldout": {"operator": "<=", "value": 0.40, "tolerance": 0.20, "false_positive_cap": 0.10},
}


def prediction_passes(observed: float, prediction: Mapping[str, object]) -> bool:
    operator = prediction["operator"]
    if operator == ">=":
        return observed >= float(prediction["value"]) - float(prediction["tolerance"])
    if operator == "<=":
        return observed <= float(prediction["value"]) + float(prediction["tolerance"])
    if operator == "band":
        return float(prediction["lower"]) <= observed <= float(prediction["upper"])
    raise ValueError(f"Unknown prediction operator: {operator}")


def classify_bucket(families: Mapping[str, Mapping[str, object]]) -> Dict[str, object]:
    thesis_outcomes = {
        family: families[family]["predictions"]
        for family in THESIS_FAMILIES
    }
    failures_by_family = {}
    for family, outcome in thesis_outcomes.items():
        failures = []
        if not outcome["alias_prediction_pass"]:
            failures.append(f"{family}: alias-CQR outside locked band")
        if not outcome["false_positive_cap_pass"]:
            failures.append(f"{family}: alias false-positive cap exceeded")
        if not outcome["cq_cross_tab_pass"]:
            failures.append(f"{family}: CQ cross-tab lift failed or underpowered")
        failures_by_family[family] = failures
    if all(not failures for failures in failures_by_family.values()):
        return {
            "bucket": "A",
            "label": "thesis confirmed",
            "reasons": [
                "Both thesis families cleared alias-CQR bands, false-positive caps, and CQ cross-tab lift."
            ],
        }
    if partial_bucket_b(thesis_outcomes):
        return {
            "bucket": "B",
            "label": "partial / descriptive",
            "reasons": [
                reason
                for family in THESIS_FAMILIES
                for reason in failures_by_family[family]
            ],
        }
    return {
        "bucket": "C",
        "label": "thesis falsified or contaminated",
        "reasons": [
            reason
            for family in THESIS_FAMILIES
            for reason in failures_by_family[family]
        ],
    }


def partial_bucket_b(thesis_outcomes: Mapping[str, Mapping[str, object]]) -> bool:
    if any(not thesis_outcomes[family]["false_positive_cap_pass"] for family in THESIS_FAMILIES):
        return False

    def non_contaminant_fail_count(outcome: Mapping[str, object]) -> int:
        return int(not outcome["alias_prediction_pass"]) + int(not outcome["cq_cross_tab_pass"])

    counts = {family: non_contaminant_fail_count(thesis_outcomes[family]) for family in THESIS_FAMILIES}
    if all(count == 0 for count in counts.values()):
        return False
    passing = [family for family in THESIS_FAMILIES if counts[family] == 0]
    failing = [family for family in THESIS_FAMILIES if counts[family] > 0]
    if len(passing) != 1 or len(failing) != 1:
        return False
    return counts[failing[0]] == 1


def policy_payload(run_data: Mapping[str, object], policy_name: str) -> Mapping[str, object]:
    for policy in run_data.get("policies", []):
        if isinstance(policy, dict) and policy.get("policy_name") == policy_name:
            return policy
    raise AuditAbort(
        "missing_policy_payload",
        {"policy_name": policy_name, "family": run_data.get("family")},
    )


def scenario_payloads_by_id(policy: Mapping[str, object]) -> Dict[str, Mapping[str, object]]:
    return {
        str(scenario.get("scenario_id")): scenario
        for scenario in policy.get("scenarios", [])
        if isinstance(scenario, dict)
    }


def candidate_payloads(scenario: Mapping[str, object]) -> List[Mapping[str, object]]:
    return [
        candidate
        for candidate in scenario.get("extracted_candidate_stream", [])
        if isinstance(candidate, dict)
    ]


def question_traces_with_relevant_id(
    scenario: Mapping[str, object]
) -> Iterable[Mapping[str, object]]:
    for trace in scenario.get("question_traces", []):
        if isinstance(trace, dict) and trace.get("relevant_canonical_id"):
            yield trace


def scope_matched(candidate: Mapping[str, object], trace: Mapping[str, object]) -> bool:
    return (
        candidate.get("canonical_id") == trace.get("relevant_canonical_id")
        and candidate.get("scope_level") == trace.get("scope_level")
        and candidate.get("scope_key") == trace.get("scope_key")
    )


def mismatch_example(
    scenario_id: str,
    candidates: Sequence[Mapping[str, object]],
    trace: Mapping[str, object],
) -> Dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "question_id": trace.get("question_id"),
        "relevant_canonical_id": trace.get("relevant_canonical_id"),
        "scope_level": trace.get("scope_level"),
        "scope_key": trace.get("scope_key"),
        "candidate_canonical_ids": sorted(
            str(candidate.get("canonical_id") or "") for candidate in candidates
        ),
        "answer_text": trace.get("answer_text"),
    }


def component_b_cubed_f1(
    family: str,
    *,
    context: Optional[AuditContext] = None,
) -> Optional[float]:
    context = context or AuditContext(
        replay_root=REPO_ROOT,
        output_root=REPO_ROOT,
        equivalence_mode=EQUIVALENCE_MODE_STRICT,
    )
    path = context.component_eval_path(family)
    if not path.exists():
        raise AuditAbort("missing_component_eval", {"family": family, "path": repo_relative(path)})
    data = read_json(path)
    metrics = data.get("metrics", {})
    value = metrics.get("canonicalization_b_cubed_f1")
    return None if value is None else float(value)


def write_outputs(summary: Mapping[str, object]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY_PATH, summary)
    write_family_csv(CSV_PATH, summary["families"])
    RESULTS_DOC_PATH.write_text(render_results_doc(summary), encoding="utf-8")
    manifest = {
        "mode": "canonical_id_resolution_audit_manifest",
        "generated_at": utc_now(),
        "archive_status": "tracked",
        "preregistration_lock_sha256": summary["preregistration_lock_sha256"],
        "alias_function_sha256": summary["alias_function_sha256"],
        "input_artifacts": summary["verified_inputs"],
        "output_artifacts": [
            artifact_payload(SUMMARY_PATH),
            artifact_payload(CSV_PATH),
            artifact_payload(RESULTS_DOC_PATH),
        ],
        "runner_command": summary["runner_command"],
        "git_status_after_outputs": working_tree_status_short(),
    }
    write_json(MANIFEST_PATH, manifest)


def write_family_csv(path: Path, families: Mapping[str, Mapping[str, object]]) -> None:
    fieldnames = [
        "family",
        "bucket_gate_role",
        "question_traces_with_relevant_id",
        "b_cubed_f1",
        "cqr_set_membership",
        "cqr_scope_matched",
        "cqr_alias_set_membership",
        "b_cubed_minus_cqr_gap",
        "alias_false_positive_rate",
        "cq_cross_tab_lift",
        "cq_alias_hit_total",
        "alias_prediction_pass",
        "false_positive_cap_pass",
        "cq_cross_tab_pass",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for family, metrics in families.items():
            predictions = metrics.get("predictions", {})
            writer.writerow(
                {
                    "family": family,
                    "bucket_gate_role": "thesis" if family in THESIS_FAMILIES else "descriptive",
                    "question_traces_with_relevant_id": metrics["question_traces_with_relevant_id"],
                    "b_cubed_f1": format_optional_float(metrics["b_cubed_f1"]),
                    "cqr_set_membership": format_float(metrics["cqr_set_membership"]),
                    "cqr_scope_matched": format_float(metrics["cqr_scope_matched"]),
                    "cqr_alias_set_membership": format_float(metrics["cqr_alias_set_membership"]),
                    "b_cubed_minus_cqr_gap": format_optional_float(metrics["b_cubed_minus_cqr_gap"]),
                    "alias_false_positive_rate": format_float(metrics["alias_false_positive_rate"]),
                    "cq_cross_tab_lift": format_float(predictions.get("cq_cross_tab_lift", 0.0)),
                    "cq_alias_hit_total": predictions.get("cq_alias_hit_total", ""),
                    "alias_prediction_pass": predictions.get("alias_prediction_pass", ""),
                    "false_positive_cap_pass": predictions.get("false_positive_cap_pass", ""),
                    "cq_cross_tab_pass": predictions.get("cq_cross_tab_pass", ""),
                }
            )


def render_results_doc(summary: Mapping[str, object]) -> str:
    bucket = summary["bucket_outcome"]
    lines = [
        "# Canonical-Id Resolution Audit Results",
        "",
        f"Date: {utc_now()[:10]}",
        "",
        f"Bucket outcome: Bucket {bucket['bucket']} - {bucket['label']}.",
        "",
        "This audit is replay-only and audit-time only. It does not change the Phase 4 policy comparison, the candidate adapter, or memory-substrate lookup semantics.",
        "",
        "This file is emitted automatically as a replay stub. Before treating it as the final published readout, add an interpretive pass that ties the bucket verdict to the mechanism audit and the Phase 4 artifacts.",
        "",
        "For `mechanism_diverse_heldout`, descriptive cross-tabs use a union of primary-style failure types per question (see `answer_success_definition` in the summary JSON). Thesis gates still use only `useful_pending_memory` and `memory_poisoning`.",
        "",
        "## Verdict",
        "",
    ]
    lines.extend(f"- {reason}" for reason in bucket["reasons"])
    lines.extend(
        [
            "",
            "## Observed Family Metrics",
            "",
            "| Family | Role | B-cubed F1 | exact CQR | scope CQR | alias CQR | alias FPR | CQ lift |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for family, metrics in summary["families"].items():
        predictions = metrics["predictions"]
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                family,
                "thesis" if family in THESIS_FAMILIES else "descriptive",
                format_optional_float(metrics["b_cubed_f1"]),
                format_float(metrics["cqr_set_membership"]),
                format_float(metrics["cqr_scope_matched"]),
                format_float(metrics["cqr_alias_set_membership"]),
                format_float(metrics["alias_false_positive_rate"]),
                format_float(predictions.get("cq_cross_tab_lift", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "## Locked Inputs",
            "",
            f"- preregistration lock: `{summary['preregistration_lock_sha256']}`",
            f"- alias source SHA256: `{summary['alias_function_sha256']}`",
            "",
            "Any production aliasing would require a separate preregistration ensuring symmetric application to all policies on the same upstream candidate stream.",
            "",
        ]
    )
    return "\n".join(lines)


def write_stop_report(exc: AuditAbort) -> None:
    path = REPO_ROOT / "data" / "results" / "canonical_id_resolution_audit_stop.json"
    payload = {
        "mode": "canonical_id_resolution_audit_stop",
        "generated_at": utc_now(),
        "bucket": "D",
        "reason": exc.reason,
        "details": exc.details,
    }
    write_json(path, payload)


def artifact_payload(path: Path) -> Dict[str, object]:
    return {
        "path": repo_relative(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def format_float(value: object) -> str:
    return f"{float(value):.3f}"


def format_optional_float(value: object) -> str:
    return "" if value is None else format_float(value)


def repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
