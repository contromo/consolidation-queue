"""Build the committed source table for the QR-canon audit.

This is a one-time generator. It reads the gitignored Phase 4 noisy
policy-comparison run JSONs (full per-question records) and emits a small
committed CSV plus a manifest. The audit script `run_qr_canon_audit.py`
reads only the committed CSV; it does not depend on the gitignored run
JSONs at audit time.

See `docs/qr_canon_audit_registration.md` for the registration. The audit
reuses the locked CQR alias function from
`docs/canonical_id_resolution_audit_preregistration.md` via
`scripts/run_canonical_id_resolution_audit.py`.

The regression check ties this generator's per-family `qr_canon_exact_hit`
sums and row counts to the already-committed
`data/results/noisy_policy_mechanism_audit_evidence.json` exact-match and
denominator counts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


COUNTABLE_FAMILIES = [
    "forced_contradiction",
    "scope_contamination",
    "preference_drift",
    "useful_pending_memory",
    "memory_poisoning",
    "false_corroboration",
]
ALL_FAMILIES = COUNTABLE_FAMILIES + ["mechanism_diverse_heldout"]

POLICY_NAME = "consolidation_queue_lite"
SCHEMA_PROFILE = "default"

OUTPUT_CSV = Path("data/results/qr_canon_source_table.csv")
OUTPUT_MANIFEST = Path("data/results/qr_canon_source_table_manifest.json")
EVIDENCE_PATH = Path("data/results/noisy_policy_mechanism_audit_evidence.json")

CSV_FIELDNAMES = [
    "family",
    "scenario_id",
    "question_id",
    "relevant_canonical_id",
    "extracted_canonical_ids",
    "qr_canon_exact_hit",
    "qr_canon_normalized_hit",
    "row_canonicalization_b_cubed_f1",
]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the QR-canon audit source table from Phase 4 noisy "
            "run JSONs and the committed mechanism audit evidence."
        )
    )
    parser.add_argument(
        "--replay-root",
        type=Path,
        default=REPO_ROOT,
        help=(
            "Repository root that contains the gitignored data/runs/ "
            "Phase 4 noisy run JSONs. Defaults to the worktree root; pass the "
            "main repository path when the worktree has no run JSONs."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to write outputs into. Defaults to the worktree root.",
    )
    args = parser.parse_args(argv)
    replay_root = args.replay_root.resolve()
    output_root = args.output_root.resolve()

    alias_match = _load_alias_match()
    evidence = _load_evidence(output_root)
    rows: List[Dict[str, object]] = []
    per_family_counts: Dict[str, Dict[str, int]] = {}
    input_files: List[Dict[str, object]] = []

    for family in ALL_FAMILIES:
        run_path = _run_path(replay_root, family)
        if not run_path.exists():
            print(
                f"Missing Phase 4 run JSON: {run_path}",
                file=sys.stderr,
            )
            print(
                "Pass --replay-root pointing to a repository root that has "
                "the gitignored Phase 4 run JSONs materialized in data/runs/.",
                file=sys.stderr,
            )
            return 2

        sha256, size = _hash_file(run_path)
        input_files.append(
            {
                "path": str(run_path),
                "sha256": sha256,
                "byte_size": size,
                "family": family,
            }
        )

        family_rows, family_b_cubed = _build_family_rows(
            family=family,
            run_path=run_path,
            evidence=evidence,
            alias_match=alias_match,
        )
        rows.extend(family_rows)
        per_family_counts[family] = {
            "row_count": len(family_rows),
            "exact_hits": sum(int(r["qr_canon_exact_hit"]) for r in family_rows),
            "normalized_hits": sum(
                int(r["qr_canon_normalized_hit"]) for r in family_rows
            ),
            "row_canonicalization_b_cubed_f1": family_b_cubed,
        }

    regression = _check_regression(per_family_counts, evidence)
    if not regression["all_passed"]:
        print("Regression check failed:", file=sys.stderr)
        print(json.dumps(regression, indent=2), file=sys.stderr)
        return 3

    csv_path = (output_root / OUTPUT_CSV).resolve()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(csv_path, rows)

    manifest_path = (output_root / OUTPUT_MANIFEST).resolve()
    manifest = _build_manifest(
        input_files=[_relativize_input(entry) for entry in input_files],
        evidence_path=(output_root / EVIDENCE_PATH).resolve(),
        csv_path=csv_path,
        regression=regression,
        per_family_counts=per_family_counts,
    )
    _write_json(manifest_path, manifest)

    print(f"Wrote {csv_path.relative_to(output_root)}")
    print(f"Wrote {manifest_path.relative_to(output_root)}")
    print(f"Regression check passed for {len(per_family_counts)} families.")
    return 0


def _load_alias_match():
    """Import the locked CQR alias function verbatim."""
    cqr_path = REPO_ROOT / "scripts" / "run_canonical_id_resolution_audit.py"
    spec = importlib.util.spec_from_file_location(
        "run_canonical_id_resolution_audit", cqr_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.alias_match


def _load_evidence(output_root: Path) -> Dict[str, object]:
    return json.loads((output_root / EVIDENCE_PATH).read_text(encoding="utf-8"))


def _run_path(replay_root: Path, family: str) -> Path:
    return (
        replay_root
        / "data"
        / "runs"
        / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}.json"
    )


def _build_family_rows(
    *,
    family: str,
    run_path: Path,
    evidence: Dict[str, object],
    alias_match,
) -> Tuple[List[Dict[str, object]], Optional[float]]:
    run_data = json.loads(run_path.read_text(encoding="utf-8"))
    policy_scenarios = _policy_scenarios(run_data, POLICY_NAME)
    row_b_cubed = _row_b_cubed_f1(evidence, family)
    rows: List[Dict[str, object]] = []
    for scenario in policy_scenarios:
        scenario_id = scenario["scenario_id"]
        candidate_ids = sorted(
            {
                candidate.get("canonical_id", "")
                for candidate in scenario.get("extracted_candidate_stream", [])
                if candidate.get("canonical_id")
            }
        )
        for trace in scenario.get("question_traces", []):
            relevant = trace.get("relevant_canonical_id")
            if not relevant:
                continue
            exact_hit = 1 if relevant in candidate_ids else 0
            normalized_hit = 1 if _any_alias_match(
                candidate_ids, relevant, alias_match
            ) else 0
            rows.append(
                {
                    "family": family,
                    "scenario_id": scenario_id,
                    "question_id": trace.get("question_id", ""),
                    "relevant_canonical_id": relevant,
                    "extracted_canonical_ids": ";".join(candidate_ids),
                    "qr_canon_exact_hit": exact_hit,
                    "qr_canon_normalized_hit": normalized_hit,
                    "row_canonicalization_b_cubed_f1": (
                        f"{row_b_cubed:.10f}" if row_b_cubed is not None else ""
                    ),
                }
            )
    return rows, row_b_cubed


def _policy_scenarios(
    run_data: Dict[str, object], policy_name: str
) -> List[Dict[str, object]]:
    for policy in run_data["policies"]:
        if policy["policy_name"] == policy_name:
            return policy["scenarios"]
    raise KeyError(f"policy {policy_name!r} not in run JSON")


def _any_alias_match(
    candidate_ids: Iterable[str], relevant: str, alias_match
) -> bool:
    for candidate in candidate_ids:
        if alias_match(candidate, relevant):
            return True
    return False


def _row_b_cubed_f1(evidence: Dict[str, object], family: str) -> Optional[float]:
    row = evidence["rows"].get(family)
    if not row:
        return None
    metrics = row.get("component_32b_default", {}).get("metrics", {})
    return metrics.get("canonicalization_b_cubed_f1")


def _check_regression(
    per_family_counts: Dict[str, Dict[str, int]],
    evidence: Dict[str, object],
) -> Dict[str, object]:
    per_family: Dict[str, Dict[str, object]] = {}
    all_passed = True
    for family, counts in per_family_counts.items():
        evidence_alignment = evidence["rows"][family]["canonical_alignment"]
        expected_exact = evidence_alignment["exact_matches"]
        expected_denominator = evidence_alignment["question_traces_with_relevant_id"]
        passed = (
            counts["row_count"] == expected_denominator
            and counts["exact_hits"] == expected_exact
        )
        all_passed = all_passed and passed
        per_family[family] = {
            "expected_exact_matches": expected_exact,
            "computed_exact_hits": counts["exact_hits"],
            "expected_denominator": expected_denominator,
            "computed_row_count": counts["row_count"],
            "passed": passed,
        }
    return {"all_passed": all_passed, "per_family": per_family}


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDNAMES})


def _write_json(path: Path, value: Dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _hash_file(path: Path) -> Tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _build_manifest(
    *,
    input_files: List[Dict[str, object]],
    evidence_path: Path,
    csv_path: Path,
    regression: Dict[str, object],
    per_family_counts: Dict[str, Dict[str, int]],
) -> Dict[str, object]:
    evidence_sha, evidence_size = _hash_file(evidence_path)
    csv_sha, csv_size = _hash_file(csv_path)
    return {
        "command": "python3 scripts/build_qr_canon_source_table.py",
        "date": "2026-05-17",
        "git_commit": _git_commit(),
        "python_version": _python_version(),
        "working_tree_status": _working_tree_status(),
        "regression": regression,
        "per_family_counts": per_family_counts,
        "inputs": {
            "phase_4_run_jsons": input_files,
            "noisy_policy_mechanism_audit_evidence": {
                "path": str(EVIDENCE_PATH),
                "sha256": evidence_sha,
                "byte_size": evidence_size,
            },
        },
        "outputs": {
            "source_table_csv": {
                "path": str(OUTPUT_CSV),
                "sha256": csv_sha,
                "byte_size": csv_size,
            },
        },
        "schema_profile": SCHEMA_PROFILE,
        "policy_name": POLICY_NAME,
        "families": ALL_FAMILIES,
        "alias_function_source": (
            "scripts/run_canonical_id_resolution_audit.py imports "
            "ALIAS_FUNCTION_SOURCE verbatim from "
            "docs/canonical_id_resolution_audit_preregistration.md "
            "section 6"
        ),
    }


def _relativize_input(entry: Dict[str, object]) -> Dict[str, object]:
    """Replace absolute path with a replay-root-relative one for manifest stability."""
    relative = Path(
        "data", "runs",
        f"noisy_policy_comparison_{entry['family']}_{SCHEMA_PROFILE}.json",
    )
    return {
        "path": str(relative),
        "sha256": entry["sha256"],
        "byte_size": entry["byte_size"],
        "family": entry["family"],
    }


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _working_tree_status() -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            return "git_unavailable"
        return "clean" if not result.stdout.strip() else "dirty"
    except FileNotFoundError:
        return "git_unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
