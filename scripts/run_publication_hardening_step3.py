#!/usr/bin/env python3
"""Run publication-hardening Step 3 fresh archived CQR cross-tab replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cq.eval.extracted_candidate_runner import (  # noqa: E402
    NoisyPolicyComparisonError,
    prediction_cell_paths,
    validate_noisy_preregistration_lock,
)
from cq.eval.publication_hardening_lock import (  # noqa: E402
    PublicationHardeningLockError,
    validate_publication_hardening_lock,
)
from scripts.run_canonical_id_resolution_audit import (  # noqa: E402
    CQ_POLICY,
    PRIMARY_METRIC_BY_FAMILY,
    alias_false_positive_summary,
    alias_source_sha256,
    policy_cross_tab,
    policy_payload,
    scenario_payloads_by_id,
    validate_preregistration_lock,
)


THESIS_FAMILIES = ("useful_pending_memory", "memory_poisoning")
DESCRIPTIVE_FAMILIES = ("false_corroboration", "mechanism_diverse_heldout")
ALL_FAMILIES = THESIS_FAMILIES + DESCRIPTIVE_FAMILIES
REGENERATION_FAMILIES = (
    "forced_contradiction",
    "scope_contamination",
    "preference_drift",
    "useful_pending_memory",
    "false_corroboration",
    "memory_poisoning",
    "mechanism_diverse_heldout",
)
MIN_ALIAS_HITS_PER_THESIS_FAMILY = 5
EXPECTED_ALIAS_SOURCE_SHA = (
    "8176c5a93ffbdbfd99d48f73836b954aa27aee4ab08de567ca47ec63d7896de0"
)
EXPECTED_PUBLICATION_HARDENING_LOCK_SHA = (
    "05671290ae8ebcc665c915521128c18c48b13be075ace55472b5931874672590"
)
SCHEMA_PROFILE = "default"
PRIMARY_MODEL_TAG = "qwen2.5:32b-instruct-q4_K_M"
POLICY_SET = "phase2_5"
CANONICAL_OUTPUT_DIR = REPO_ROOT / "data" / "results"
CANONICAL_RUN_DIR = REPO_ROOT / "data" / "runs"
CANONICAL_MANIFEST_PATH = CANONICAL_RUN_DIR / "publication_hardening_step3_manifest.json"
CANONICAL_RESULTS_DOC = REPO_ROOT / "docs" / "publication_hardening_step3_results.md"
CANONICAL_SKIP_DOC = REPO_ROOT / "docs" / "publication_hardening_step3_precondition_skip.md"
FAMILY_ROWS_FILENAME = "publication_hardening_step3_family_rows.csv"
SUMMARY_FILENAME = "publication_hardening_step3_summary.json"

CSV_COLUMNS = [
    "family",
    "role",
    "primary_metric",
    "alias_hit_total",
    "alias_miss_total",
    "hit_success",
    "hit_failure",
    "miss_success",
    "miss_failure",
    "answer_success_given_alias_hit",
    "answer_success_given_alias_miss",
    "lift",
    "alias_false_positive_rate",
    "min_n_passed",
    "miss_partition_evaluable",
]


class Step3PreconditionFail(RuntimeError):
    def __init__(self, reason: str, details: Mapping[str, Any]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = dict(details)


class Step3RegenerationFail(RuntimeError):
    def __init__(
        self,
        *,
        returncode: int,
        stop_report: Optional[str],
        stderr_tail: str,
        stdout_tail: str,
    ) -> None:
        super().__init__("noisy comparison regeneration failed")
        self.returncode = returncode
        self.stop_report = stop_report
        self.stderr_tail = stderr_tail
        self.stdout_tail = stdout_tail


@dataclass(frozen=True)
class Step3Paths:
    output_dir: Path
    manifest_path: Path
    results_doc: Path
    skip_doc: Path

    @property
    def summary_json(self) -> Path:
        return self.output_dir / SUMMARY_FILENAME

    @property
    def family_rows_csv(self) -> Path:
        return self.output_dir / FAMILY_ROWS_FILENAME


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the publication-hardening Step 3 fresh archived CQR replay."
    )
    regen = parser.add_mutually_exclusive_group()
    regen.add_argument(
        "--regenerate-noisy-comparison",
        dest="regenerate_noisy_comparison",
        action="store_true",
        default=True,
        help="Refresh the canonical noisy comparison artifacts before computing Step 3.",
    )
    regen.add_argument(
        "--no-regenerate-noisy-comparison",
        dest="regenerate_noisy_comparison",
        action="store_false",
        help="Development-only mode for non-canonical output paths.",
    )
    parser.add_argument("--output-dir", type=Path, default=CANONICAL_OUTPUT_DIR)
    parser.add_argument("--manifest-path", type=Path, default=CANONICAL_MANIFEST_PATH)
    parser.add_argument("--results-doc", type=Path, default=CANONICAL_RESULTS_DOC)
    parser.add_argument("--skip-doc", type=Path, default=CANONICAL_SKIP_DOC)
    args = parser.parse_args(argv)

    args.output_dir = _resolve_path(args.output_dir)
    args.manifest_path = _resolve_path(args.manifest_path)
    args.results_doc = _resolve_path(args.results_doc)
    args.skip_doc = _resolve_path(args.skip_doc)

    if not args.regenerate_noisy_comparison:
        canonical_paths = (
            args.output_dir == CANONICAL_OUTPUT_DIR.resolve(),
            args.manifest_path == CANONICAL_MANIFEST_PATH.resolve(),
            args.results_doc == CANONICAL_RESULTS_DOC.resolve(),
        )
        if any(canonical_paths):
            parser.error(
                "--no-regenerate-noisy-comparison requires non-canonical "
                "--output-dir, --manifest-path, and --results-doc paths"
            )
    return args


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def capture_worktree_status() -> str:
    return subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.strip()


def validate_preconditions(
    *,
    skip_doc_path: Path = CANONICAL_SKIP_DOC,
    predictions_dir: Path = CANONICAL_OUTPUT_DIR,
    schema_profile: str = SCHEMA_PROFILE,
) -> Dict[str, Any]:
    pre_run_worktree = capture_worktree_status()
    if pre_run_worktree:
        raise Step3PreconditionFail(
            "C_preconditions_fail",
            {
                "precondition": "clean_worktree",
                "pre_run_worktree_status": pre_run_worktree,
            },
        )

    try:
        publication_lock_sha = validate_publication_hardening_lock()
    except PublicationHardeningLockError as exc:
        raise Step3PreconditionFail(
            "C_preconditions_fail",
            {"precondition": "publication_hardening_lock", "error": str(exc)},
        ) from exc
    if publication_lock_sha != EXPECTED_PUBLICATION_HARDENING_LOCK_SHA:
        raise Step3PreconditionFail(
            "C_preconditions_fail",
            {
                "precondition": "publication_hardening_lock_sha256",
                "observed": publication_lock_sha,
                "expected": EXPECTED_PUBLICATION_HARDENING_LOCK_SHA,
            },
        )

    observed_alias_sha = alias_source_sha256()
    if observed_alias_sha != EXPECTED_ALIAS_SOURCE_SHA:
        raise Step3PreconditionFail(
            "C_preconditions_fail",
            {
                "precondition": "alias_function_sha256",
                "observed": observed_alias_sha,
                "expected": EXPECTED_ALIAS_SOURCE_SHA,
            },
        )

    skip_doc_path = _resolve_path(skip_doc_path)
    if not skip_doc_path.exists():
        raise Step3PreconditionFail(
            "C_preconditions_fail",
            {
                "precondition": "skip_doc_exists",
                "skip_doc_path": repo_relative(skip_doc_path),
            },
        )
    skip_doc_sha = sha256_file(skip_doc_path)

    try:
        cqr_lock_sha = validate_preregistration_lock()
    except Exception as exc:
        raise Step3PreconditionFail(
            "C_preconditions_fail",
            {"precondition": "cqr_audit_preregistration_lock", "error": str(exc)},
        ) from exc

    try:
        noisy_lock_sha = validate_noisy_preregistration_lock()
    except NoisyPolicyComparisonError as exc:
        raise Step3PreconditionFail(
            "C_preconditions_fail",
            {"precondition": "noisy_comparison_preregistration_lock", "error": str(exc)},
        ) from exc

    missing_prediction_families: List[Dict[str, str]] = []
    for family in REGENERATION_FAMILIES:
        try:
            prediction_cell_paths(
                predictions_dir=predictions_dir,
                family=family,
                schema_profile=schema_profile,
            )
        except NoisyPolicyComparisonError as exc:
            missing_prediction_families.append({"family": family, "error": str(exc)})
    if missing_prediction_families:
        raise Step3PreconditionFail(
            "C_missing_predictions",
            {
                "precondition": "prediction_artifacts_exist",
                "missing_families": missing_prediction_families,
            },
        )

    return {
        "publication_hardening_lock_sha256": publication_lock_sha,
        "alias_function_sha256": observed_alias_sha,
        "cqr_audit_preregistration_lock_sha256": cqr_lock_sha,
        "noisy_comparison_preregistration_lock_sha256": noisy_lock_sha,
        "skip_doc_path": repo_relative(skip_doc_path),
        "skip_doc_sha256": skip_doc_sha,
        "git_commit": git_commit(),
        "pre_run_worktree_status": pre_run_worktree,
    }


def regenerate_noisy_comparison() -> None:
    stop_dir = CANONICAL_OUTPUT_DIR
    pre_existing_stop_reports = set(stop_dir.glob("noisy_policy_comparison_stop_*.json"))
    command = [
        sys.executable,
        "scripts/run_noisy_policy_comparison.py",
        "--primary-model-tag",
        PRIMARY_MODEL_TAG,
        "--schema-profile",
        SCHEMA_PROFILE,
        "--include-frozen-sentinel",
        "--policy-set",
        POLICY_SET,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0:
        return

    stop_report_path: Optional[str] = None
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("Noisy policy comparison stopped:") and "Report:" in stripped:
            parsed = stripped.split("Report:", 1)[1].strip()
            parsed_path = Path(parsed)
            if not parsed_path.is_absolute():
                parsed_path = (REPO_ROOT / parsed_path).resolve()
            else:
                parsed_path = parsed_path.resolve()
            stop_report_path = str(parsed_path)
            break
    if stop_report_path is None:
        new_reports = sorted(set(stop_dir.glob("noisy_policy_comparison_stop_*.json")) - pre_existing_stop_reports)
        if new_reports:
            stop_report_path = str(new_reports[-1].resolve())
    raise Step3RegenerationFail(
        returncode=result.returncode,
        stop_report=stop_report_path,
        stderr_tail=(result.stderr or "")[-4000:],
        stdout_tail=(result.stdout or "")[-4000:],
    )


def load_fresh_run(family: str) -> Dict[str, Any]:
    path = CANONICAL_RUN_DIR / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def collect_regeneration_metadata(
    *,
    regeneration_skipped: bool = False,
    family: str = "useful_pending_memory",
) -> Dict[str, Any]:
    path = CANONICAL_RUN_DIR / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "regeneration_skipped": regeneration_skipped,
        "source_manifest_path": repo_relative(path),
        "primary_model_digest": payload.get("primary_model_digest"),
        "ollama_server_version": payload.get("ollama_server_version"),
        "expected_primary_model_digest": payload.get("expected_primary_model_digest"),
        "prompt_sha256": payload.get("prompt_sha256"),
        "candidate_adapter_sha256": payload.get("candidate_adapter_sha256"),
    }


def collect_source_artifact_hashes(
    family: str,
    *,
    predictions_dir: Path = CANONICAL_OUTPUT_DIR,
    schema_profile: str = SCHEMA_PROFILE,
) -> Dict[str, Any]:
    run_json = CANONICAL_RUN_DIR / f"noisy_policy_comparison_{family}_{schema_profile}.json"
    run_manifest = CANONICAL_RUN_DIR / f"noisy_policy_comparison_{family}_{schema_profile}_manifest.json"
    metrics_csv = CANONICAL_OUTPUT_DIR / f"noisy_policy_comparison_{family}_{schema_profile}_metrics.csv"
    paths = prediction_cell_paths(
        predictions_dir=predictions_dir,
        family=family,
        schema_profile=schema_profile,
    )
    artifacts = {
        "run_json": run_json,
        "run_manifest": run_manifest,
        "metrics_csv": metrics_csv,
        "predictions": paths.predictions,
        "component_eval": paths.component_eval,
        "component_gate_summary": paths.summary,
        "component_gate_manifest": paths.manifest,
    }
    return {
        f"{name}_path": repo_relative(path)
        for name, path in artifacts.items()
    } | {
        f"{name}_sha256": sha256_file(path)
        for name, path in artifacts.items()
    }


def compute_family_step3(family: str, run_data: Mapping[str, Any]) -> Dict[str, Any]:
    cq_policy = policy_payload(run_data, CQ_POLICY)
    cq_scenarios = scenario_payloads_by_id(cq_policy)
    cross_tab = policy_cross_tab(family, cq_policy, cq_scenarios)
    fp_summary = alias_false_positive_summary(cq_scenarios)
    alias_hit_total = int(cross_tab["alias_hit_total"])
    alias_miss_total = int(cross_tab["alias_miss_total"])
    return {
        "family": family,
        "role": "thesis" if family in THESIS_FAMILIES else "descriptive",
        "primary_metric": PRIMARY_METRIC_BY_FAMILY.get(family, "answer_correctness"),
        "cross_tab": cross_tab,
        "alias_false_positive": fp_summary,
        "min_n_passed": alias_hit_total >= MIN_ALIAS_HITS_PER_THESIS_FAMILY,
        "miss_partition_evaluable": alias_miss_total > 0,
        "alias_hit_total": alias_hit_total,
        "alias_miss_total": alias_miss_total,
    }


def classify_outcome(per_family: Mapping[str, Mapping[str, Any]]) -> str:
    for family in THESIS_FAMILIES:
        cross_tab = per_family[family]["cross_tab"]
        if cross_tab["alias_hit_total"] == 0 and cross_tab["alias_miss_total"] == 0:
            return "B_inconclusive_empty_partition"
        if not per_family[family]["miss_partition_evaluable"]:
            return "B_inconclusive_unevaluable_miss"
        if not per_family[family]["min_n_passed"]:
            return "B_inconclusive_min_n"
    return "A_cross_tab_populated"


def build_limitation_text(
    bucket: str,
    per_family: Mapping[str, Mapping[str, Any]],
    *,
    failure_details: Optional[Mapping[str, Any]] = None,
) -> str:
    if bucket == "A_cross_tab_populated":
        non_positive = [
            family
            for family in THESIS_FAMILIES
            if float(per_family[family]["cross_tab"]["lift"]) <= 0.0
        ]
        if non_positive:
            return (
                "Step 3 emitted populated and evaluable cross-tabs, but "
                "non-positive lift in {} means the result is diagnostic rather "
                "than supporting evidence for Claim 2.".format(", ".join(non_positive))
            )
        return (
            "Step 3 emitted populated and evaluable cross-tabs with positive "
            "lift on both thesis families; Claim 2 may cite the cross-tab as "
            "supporting evidence within the preregistered scope."
        )
    if bucket.startswith("C_"):
        detail = failure_details or {}
        if bucket == "C_regeneration_fail":
            return (
                "Step 3 preconditions passed but noisy-comparison regeneration "
                "failed (returncode={returncode}, stop_report={stop_report}). "
                "Claim 2 is unchanged.".format(
                    returncode=detail.get("returncode"),
                    stop_report=detail.get("stop_report"),
                )
            )
        return (
            "Step 3 did not emit a cross-tab verdict because a precondition "
            "failed ({precondition}). Claim 2 is unchanged.".format(
                precondition=detail.get("precondition", detail.get("reason", "unknown"))
            )
        )

    messages = []
    for family in THESIS_FAMILIES:
        cross_tab = per_family[family]["cross_tab"]
        hits = int(cross_tab["alias_hit_total"])
        misses = int(cross_tab["alias_miss_total"])
        if bucket == "B_inconclusive_empty_partition" and hits == 0 and misses == 0:
            messages.append(
                "Step 3 did not emit a cross-tab verdict on {family} because "
                "both alias-CQR partitions were empty (alias_hit_total=0, "
                "alias_miss_total=0). The fresh replay did not surface any "
                "alias-relevant scenarios in this family. Prior PFLC null rows "
                "for {family} are preserved as unattributed.".format(family=family)
            )
        elif bucket == "B_inconclusive_unevaluable_miss" and misses == 0:
            messages.append(
                "Step 3 did not emit a cross-tab verdict on {family} because "
                "the alias-CQR miss denominator was zero (observed: "
                "alias_hit_total={hits}, alias_miss_total=0). "
                "P(answer_success | alias_CQR_miss) is undefined; lift is "
                "non-evaluable. Prior PFLC null rows for {family} are "
                "preserved as unattributed.".format(family=family, hits=hits)
            )
        elif bucket == "B_inconclusive_min_n" and hits < MIN_ALIAS_HITS_PER_THESIS_FAMILY:
            messages.append(
                "Step 3 did not emit a cross-tab verdict on {family} because "
                "the alias-CQR hit denominator was below the preregistered "
                "minimum of {threshold} (observed: {hits}). Prior PFLC null "
                "rows for {family} are preserved as unattributed.".format(
                    family=family,
                    threshold=MIN_ALIAS_HITS_PER_THESIS_FAMILY,
                    hits=hits,
                )
            )
    return "\n\n".join(messages) if messages else "Step 3 remains inconclusive."


def runner_command(argv: Optional[Sequence[str]]) -> str:
    args = sys.argv[1:] if argv is None else list(argv)
    return shlex.join(["python3", repo_relative(Path(__file__)), *map(str, args)])


def write_summary_json(
    per_family: Mapping[str, Mapping[str, Any]],
    bucket: str,
    preconditions: Mapping[str, Any],
    regeneration_metadata: Mapping[str, Any],
    path: Path,
    *,
    command: str,
    limitation_text: str,
    failure_details: Optional[Mapping[str, Any]] = None,
) -> None:
    payload = {
        "mode": "publication_hardening_step3_summary",
        "generated_at": utc_now(),
        "bucket": bucket,
        "min_n_threshold": MIN_ALIAS_HITS_PER_THESIS_FAMILY,
        "runner_command": command,
        "preconditions": dict(preconditions),
        "regeneration_metadata": dict(regeneration_metadata),
        "per_family": per_family,
        "limitation_text": limitation_text,
    }
    if failure_details is not None:
        payload["failure_details"] = dict(failure_details)
    write_json(path, payload)


def write_family_rows_csv(per_family: Mapping[str, Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for family in ALL_FAMILIES:
            if family not in per_family:
                continue
            row = per_family[family]
            cross_tab = row["cross_tab"]
            writer.writerow(
                {
                    "family": family,
                    "role": row["role"],
                    "primary_metric": row["primary_metric"],
                    "alias_hit_total": row["alias_hit_total"],
                    "alias_miss_total": row["alias_miss_total"],
                    "hit_success": cross_tab["hit_success"],
                    "hit_failure": cross_tab["hit_failure"],
                    "miss_success": cross_tab["miss_success"],
                    "miss_failure": cross_tab["miss_failure"],
                    "answer_success_given_alias_hit": _format_float(
                        cross_tab["answer_success_given_alias_hit"]
                    ),
                    "answer_success_given_alias_miss": _format_float(
                        cross_tab["answer_success_given_alias_miss"]
                    ),
                    "lift": _format_float(cross_tab["lift"]),
                    "alias_false_positive_rate": _format_float(
                        row["alias_false_positive"]["alias_false_positive_rate"]
                    ),
                    "min_n_passed": row["min_n_passed"],
                    "miss_partition_evaluable": row["miss_partition_evaluable"],
                }
            )


def _format_float(value: Any) -> str:
    return f"{float(value):.6f}"


def write_results_doc(
    per_family: Mapping[str, Mapping[str, Any]],
    bucket: str,
    limitation: str,
    path: Path,
    *,
    preconditions: Mapping[str, Any],
    regeneration_metadata: Mapping[str, Any],
    source_hashes: Optional[Mapping[str, Mapping[str, Any]]] = None,
    failure_details: Optional[Mapping[str, Any]] = None,
) -> None:
    source_hashes = source_hashes or {}
    lines = [
        "# Publication-Hardening Step 3 Results",
        "",
        f"Date: {utc_now()[:10]}",
        "",
        "## Verdict",
        "",
        f"Bucket: `{bucket}`.",
        "",
        "## Scope",
        "",
        "Publication-hardening preregistration Section 5 scopes this fresh archived CQR replay to four families.",
        "",
        "| Family | Role |",
        "| --- | --- |",
    ]
    for family in ALL_FAMILIES:
        role = "thesis" if family in THESIS_FAMILIES else "descriptive"
        lines.append(f"| `{family}` | {role} |")
    lines.extend(
        [
            "",
            "## Preconditions",
            "",
            f"- publication-hardening lock: `{preconditions.get('publication_hardening_lock_sha256', '')}`",
            f"- CQR audit preregistration lock: `{preconditions.get('cqr_audit_preregistration_lock_sha256', '')}`",
            f"- noisy comparison preregistration lock: `{preconditions.get('noisy_comparison_preregistration_lock_sha256', '')}`",
            f"- alias function SHA256: `{preconditions.get('alias_function_sha256', '')}`",
            f"- Ollama backend version: `{regeneration_metadata.get('ollama_server_version', '')}`",
            f"- pre-run worktree status: `{preconditions.get('pre_run_worktree_status', '')}`",
            f"- git commit: `{preconditions.get('git_commit', '')}`",
            f"- skip document: `{preconditions.get('skip_doc_path', repo_relative(CANONICAL_SKIP_DOC))}`",
            "",
            "## Fresh Run Summary",
            "",
            "| Family | Scenario count | Run JSON | Run JSON SHA256 | Metrics CSV SHA256 |",
            "| --- | ---: | --- | --- | --- |",
        ]
    )
    for family in ALL_FAMILIES:
        scenario_count = ""
        if family in per_family:
            # Number of CQ scenarios with payloads, not question traces.
            run_data = load_fresh_run(family) if (CANONICAL_RUN_DIR / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}.json").exists() else {}
            scenario_count = str(run_data.get("scenario_count", ""))
        hashes = source_hashes.get(family, {})
        lines.append(
            "| `{}` | {} | `{}` | `{}` | `{}` |".format(
                family,
                scenario_count,
                hashes.get("run_json_path", ""),
                hashes.get("run_json_sha256", ""),
                hashes.get("metrics_csv_sha256", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Per-Family Cross-Tab",
            "",
            "| Family | Role | Hits | Misses | P(success | hit) | P(success | miss) | Lift | Alias FPR | Min N | Miss evaluable |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for family in ALL_FAMILIES:
        if family not in per_family:
            continue
        row = per_family[family]
        cross_tab = row["cross_tab"]
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                family,
                row["role"],
                row["alias_hit_total"],
                row["alias_miss_total"],
                _format_float(cross_tab["answer_success_given_alias_hit"]),
                _format_float(cross_tab["answer_success_given_alias_miss"]),
                _format_float(cross_tab["lift"]),
                _format_float(row["alias_false_positive"]["alias_false_positive_rate"]),
                row["min_n_passed"],
                row["miss_partition_evaluable"],
            )
        )
    lines.extend(["", "## False-Positive Negative Control", ""])
    for family in ALL_FAMILIES:
        if family not in per_family:
            continue
        fp = per_family[family]["alias_false_positive"]
        lines.append(
            "- `{}`: alias false-positive rate `{}` (`{}` / `{}` pairs).".format(
                family,
                _format_float(fp["alias_false_positive_rate"]),
                fp["false_positive_pairs"],
                fp["alias_matched_pairs"],
            )
        )
    lines.extend(["", "## Outcome", ""])
    if bucket == "A_cross_tab_populated":
        for family in THESIS_FAMILIES:
            lift = float(per_family[family]["cross_tab"]["lift"])
            sign = "positive" if lift > 0 else "zero" if lift == 0 else "negative"
            lines.append(f"- `{family}` is populated and evaluable with {sign} lift `{_format_float(lift)}`.")
    elif bucket.startswith("B_"):
        lines.append("- The cross-tab is not evaluable under the preregistered thesis-family gates.")
    else:
        lines.append("- Preconditions failed; no cross-tab verdict was emitted.")
        if failure_details:
            lines.append(f"- Failure details: `{json.dumps(failure_details, sort_keys=True)}`")
    lines.extend(
        [
            "",
            "## Limitation Text",
            "",
            limitation,
            "",
            "## What This Means For Claim 2",
            "",
            claim2_interpretation(bucket, per_family),
            "",
            "## References",
            "",
            "- preregistration: `docs/publication_hardening_preregistration.md`",
            "- skip document: `docs/publication_hardening_step3_precondition_skip.md`",
            "- manifest: `data/runs/publication_hardening_step3_manifest.json`",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def claim2_interpretation(bucket: str, per_family: Mapping[str, Mapping[str, Any]]) -> str:
    if bucket == "A_cross_tab_populated":
        lifts = {family: float(per_family[family]["cross_tab"]["lift"]) for family in THESIS_FAMILIES}
        if all(value > 0.0 for value in lifts.values()):
            return (
                "Claim 2 can absorb the cross-tab as supporting evidence within "
                "the locked Step 3 scope. Paper sections discussing PFLC and "
                "canonical-id lookup may cite it with the archived replay manifest."
            )
        if any(value < 0.0 for value in lifts.values()):
            return (
                "Claim 2 absorbs this as diagnostic limitation evidence only. "
                "At least one thesis family does worse on alias-hit rows than "
                "alias-miss rows, so this must be reported transparently and not "
                "used as a supporting rescue."
            )
        return (
            "Claim 2 absorbs this as diagnostic evidence only: the cross-tab is "
            "populated and evaluable but does not separate alias-hit from "
            "alias-miss success rates."
        )
    if bucket.startswith("B_"):
        return "Claim 2 null rows remain unchanged because the Step 3 cross-tab is not evaluable."
    return "Claim 2 is unchanged because Step 3 stopped at the precondition/regeneration layer."


def artifact_payload(path: Path) -> Dict[str, Any]:
    return {
        "path": repo_relative(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def write_manifest(
    per_family: Mapping[str, Mapping[str, Any]],
    preconditions: Mapping[str, Any],
    regeneration_metadata: Mapping[str, Any],
    bucket: str,
    post_output_worktree: str,
    source_hashes: Mapping[str, Mapping[str, Any]],
    step3_output_paths: Sequence[Path],
    path: Path,
    *,
    command: str,
    failure_details: Optional[Mapping[str, Any]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "mode": "publication_hardening_step3_manifest",
        "manifest_version": 1,
        "generated_at": utc_now(),
        "archive_status": "tracked",
        "bucket": bucket,
        "runner_command": command,
        "pre_run_worktree_status": preconditions.get("pre_run_worktree_status", ""),
        "working_tree_status": post_output_worktree,
        "working_tree_status_context": "step3_after_outputs",
        "publication_hardening_lock_sha256": preconditions.get(
            "publication_hardening_lock_sha256"
        ),
        "alias_function_sha256": preconditions.get("alias_function_sha256"),
        "cqr_audit_preregistration_lock_sha256": preconditions.get(
            "cqr_audit_preregistration_lock_sha256"
        ),
        "noisy_comparison_preregistration_lock_sha256": preconditions.get(
            "noisy_comparison_preregistration_lock_sha256"
        ),
        "skip_doc_path": preconditions.get("skip_doc_path"),
        "skip_doc_sha256": preconditions.get("skip_doc_sha256"),
        "git_commit": preconditions.get("git_commit"),
        "source_run_artifacts": source_hashes,
        "artifacts": [artifact_payload(output_path) for output_path in step3_output_paths if output_path.exists()],
        "regeneration_metadata": dict(regeneration_metadata),
        "per_family": per_family,
    }
    if failure_details is not None:
        payload["failure_details"] = dict(failure_details)
        if "stop_report" in failure_details:
            payload["stop_report"] = failure_details["stop_report"]
    write_json(path, payload)


def write_bucket_c_outputs(
    *,
    paths: Step3Paths,
    bucket: str,
    preconditions: Mapping[str, Any],
    regeneration_metadata: Mapping[str, Any],
    command: str,
    failure_details: Mapping[str, Any],
) -> None:
    limitation = build_limitation_text(bucket, {}, failure_details=failure_details)
    write_summary_json(
        {},
        bucket,
        preconditions,
        regeneration_metadata,
        paths.summary_json,
        command=command,
        limitation_text=limitation,
        failure_details=failure_details,
    )
    write_family_rows_csv({}, paths.family_rows_csv)
    write_results_doc(
        {},
        bucket,
        limitation,
        paths.results_doc,
        preconditions=preconditions,
        regeneration_metadata=regeneration_metadata,
        failure_details=failure_details,
    )
    post_output_worktree = capture_worktree_status()
    write_manifest(
        {},
        preconditions,
        regeneration_metadata,
        bucket,
        post_output_worktree,
        {},
        [paths.summary_json, paths.family_rows_csv, paths.results_doc],
        paths.manifest_path,
        command=command,
        failure_details=failure_details,
    )


def stop_report_reason(stop_report: Optional[str]) -> Optional[str]:
    if not stop_report:
        return None
    path = Path(stop_report)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    reason = payload.get("reason")
    return str(reason) if reason is not None else None


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    paths = Step3Paths(
        output_dir=args.output_dir,
        manifest_path=args.manifest_path,
        results_doc=args.results_doc,
        skip_doc=args.skip_doc,
    )
    command = runner_command(argv)
    try:
        preconditions = validate_preconditions(skip_doc_path=paths.skip_doc)
    except Step3PreconditionFail as exc:
        preconditions = {
            "pre_run_worktree_status": exc.details.get("pre_run_worktree_status", ""),
        }
        failure_details = {"reason": exc.reason, **exc.details}
        write_bucket_c_outputs(
            paths=paths,
            bucket=exc.reason,
            preconditions=preconditions,
            regeneration_metadata={"regeneration_skipped": True},
            command=command,
            failure_details=failure_details,
        )
        return 1

    if args.regenerate_noisy_comparison:
        try:
            regenerate_noisy_comparison()
        except Step3RegenerationFail as exc:
            failure_details = {
                "reason": "C_regeneration_fail",
                "returncode": exc.returncode,
                "stop_report": exc.stop_report,
                "stop_report_reason": stop_report_reason(exc.stop_report),
                "stderr_tail": exc.stderr_tail,
                "stdout_tail": exc.stdout_tail,
            }
            write_bucket_c_outputs(
                paths=paths,
                bucket="C_regeneration_fail",
                preconditions=preconditions,
                regeneration_metadata={"regeneration_skipped": False},
                command=command,
                failure_details=failure_details,
            )
            return 1

    regeneration_metadata = collect_regeneration_metadata(
        regeneration_skipped=not args.regenerate_noisy_comparison
    )
    per_family = {
        family: compute_family_step3(family, load_fresh_run(family))
        for family in ALL_FAMILIES
    }
    source_hashes = {family: collect_source_artifact_hashes(family) for family in ALL_FAMILIES}
    bucket = classify_outcome(per_family)
    limitation = build_limitation_text(bucket, per_family)

    write_summary_json(
        per_family,
        bucket,
        preconditions,
        regeneration_metadata,
        paths.summary_json,
        command=command,
        limitation_text=limitation,
    )
    write_family_rows_csv(per_family, paths.family_rows_csv)
    write_results_doc(
        per_family,
        bucket,
        limitation,
        paths.results_doc,
        preconditions=preconditions,
        regeneration_metadata=regeneration_metadata,
        source_hashes=source_hashes,
    )
    post_output_worktree = capture_worktree_status()
    write_manifest(
        per_family,
        preconditions,
        regeneration_metadata,
        bucket,
        post_output_worktree,
        source_hashes,
        [paths.summary_json, paths.family_rows_csv, paths.results_doc],
        paths.manifest_path,
        command=command,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
