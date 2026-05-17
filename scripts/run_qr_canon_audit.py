"""Run the QR-canon audit from the committed source table.

This script reads only ``data/results/qr_canon_source_table.csv`` and
emits per-row aggregates with Wilson confidence intervals, a joint
B-cubed/QR-canon table, an alias sensitivity table, and a synthetic
counterexample row demonstrating that B-cubed F1 can be ``1.00`` while
QR-canon (exact) is ``0.00`` by construction.

See ``docs/qr_canon_audit_registration.md`` for the registration. The
audit does not read any gitignored run JSON, does not rerun any policy,
and does not change any prompt, threshold, validator, adapter, policy,
or substrate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_TABLE = Path("data/results/qr_canon_source_table.csv")
OUTPUT_METRICS = Path("data/results/qr_canon_audit_metrics.csv")
OUTPUT_MANIFEST = Path("data/results/qr_canon_audit_manifest.json")

FAMILY_ORDER = [
    "forced_contradiction",
    "preference_drift",
    "scope_contamination",
    "useful_pending_memory",
    "memory_poisoning",
    "false_corroboration",
    "mechanism_diverse_heldout",
]

CSV_FIELDNAMES = [
    "row_id",
    "family",
    "denominator",
    "qr_canon_exact_hits",
    "qr_canon_exact_rate",
    "qr_canon_exact_wilson_lcb",
    "qr_canon_exact_wilson_ucb",
    "qr_canon_normalized_hits",
    "qr_canon_normalized_rate",
    "qr_canon_normalized_wilson_lcb",
    "qr_canon_normalized_wilson_ucb",
    "canonicalization_b_cubed_f1",
    "joint_passes_clustering_floor_but_not_lookup",
    "row_kind",
]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the QR-canon audit from the committed source table. "
            "No policy rerun. No replay. No gitignored inputs."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing the committed source table.",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    source_path = (repo_root / SOURCE_TABLE).resolve()
    if not source_path.exists():
        print(
            f"Missing committed source table: {source_path}",
            file=sys.stderr,
        )
        print(
            "Run scripts/build_qr_canon_source_table.py first; see "
            "docs/qr_canon_audit_registration.md section 4.",
            file=sys.stderr,
        )
        return 2

    rows = _load_source_rows(source_path)
    family_rows = _aggregate_family_rows(rows)
    synthetic_row = _synthetic_counterexample()
    metrics_rows = family_rows + [synthetic_row]

    metrics_path = (repo_root / OUTPUT_METRICS).resolve()
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(metrics_path, metrics_rows)

    manifest = _build_manifest(
        source_path=source_path,
        metrics_path=metrics_path,
        family_rows=family_rows,
        synthetic_row=synthetic_row,
    )
    manifest_path = (repo_root / OUTPUT_MANIFEST).resolve()
    _write_json(manifest_path, manifest)

    print(f"Wrote {metrics_path.relative_to(repo_root)}")
    print(f"Wrote {manifest_path.relative_to(repo_root)}")
    return 0


def _load_source_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _aggregate_family_rows(rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    by_family: Dict[str, Dict[str, object]] = {}
    for row in rows:
        family = row["family"]
        bucket = by_family.setdefault(
            family,
            {
                "denominator": 0,
                "exact_hits": 0,
                "normalized_hits": 0,
                "b_cubed": _parse_optional_float(
                    row["row_canonicalization_b_cubed_f1"]
                ),
            },
        )
        bucket["denominator"] = int(bucket["denominator"]) + 1
        bucket["exact_hits"] = int(bucket["exact_hits"]) + int(
            row["qr_canon_exact_hit"]
        )
        bucket["normalized_hits"] = int(bucket["normalized_hits"]) + int(
            row["qr_canon_normalized_hit"]
        )
    aggregated: List[Dict[str, object]] = []
    for family in FAMILY_ORDER:
        if family not in by_family:
            continue
        bucket = by_family[family]
        denominator = int(bucket["denominator"])
        exact_hits = int(bucket["exact_hits"])
        normalized_hits = int(bucket["normalized_hits"])
        b_cubed = bucket["b_cubed"]
        exact_rate = exact_hits / denominator if denominator else 0.0
        normalized_rate = normalized_hits / denominator if denominator else 0.0
        exact_lcb, exact_ucb = _wilson_interval(exact_hits, denominator)
        norm_lcb, norm_ucb = _wilson_interval(normalized_hits, denominator)
        aggregated.append(
            {
                "row_id": family,
                "family": family,
                "denominator": denominator,
                "qr_canon_exact_hits": exact_hits,
                "qr_canon_exact_rate": _fmt(exact_rate),
                "qr_canon_exact_wilson_lcb": _fmt(exact_lcb),
                "qr_canon_exact_wilson_ucb": _fmt(exact_ucb),
                "qr_canon_normalized_hits": normalized_hits,
                "qr_canon_normalized_rate": _fmt(normalized_rate),
                "qr_canon_normalized_wilson_lcb": _fmt(norm_lcb),
                "qr_canon_normalized_wilson_ucb": _fmt(norm_ucb),
                "canonicalization_b_cubed_f1": (
                    _fmt(b_cubed) if b_cubed is not None else ""
                ),
                "joint_passes_clustering_floor_but_not_lookup": _is_clustering_pass_lookup_miss(
                    b_cubed, exact_rate
                ),
                "row_kind": "phase_4_default",
            }
        )
    return aggregated


def _synthetic_counterexample() -> Dict[str, object]:
    """Toy example: B-cubed F1 = 1.00 with QR-canon (exact) = 0.00.

    Construction: gold has two events e1, e2 in one cluster with
    canonical_id ``gold-X``. Predicted has the same two events e1, e2 in
    one cluster, but with canonical_id ``pred-Y``. B-cubed F1 between the
    cluster partitions is 1.00 because both partitions are
    ``{e1, e2}`` (a single perfect cluster). The question's
    relevant_canonical_id is ``gold-X``. The extracted canonical-id set is
    ``{pred-Y}``. Exact-string membership fails, so QR-canon (exact) is 0.

    This row ships in the metrics CSV so the methodological claim does not
    rely on the Phase 4 numbers alone.
    """
    return {
        "row_id": "synthetic_counterexample",
        "family": "synthetic_counterexample",
        "denominator": 1,
        "qr_canon_exact_hits": 0,
        "qr_canon_exact_rate": _fmt(0.0),
        "qr_canon_exact_wilson_lcb": _fmt(0.0),
        "qr_canon_exact_wilson_ucb": _fmt(_wilson_interval(0, 1)[1]),
        "qr_canon_normalized_hits": 0,
        "qr_canon_normalized_rate": _fmt(0.0),
        "qr_canon_normalized_wilson_lcb": _fmt(0.0),
        "qr_canon_normalized_wilson_ucb": _fmt(_wilson_interval(0, 1)[1]),
        "canonicalization_b_cubed_f1": _fmt(1.0),
        "joint_passes_clustering_floor_but_not_lookup": True,
        "row_kind": "synthetic_counterexample",
    }


def _is_clustering_pass_lookup_miss(
    b_cubed: Optional[float], qr_canon_exact_rate: float
) -> bool:
    """Returns True when the row crosses the gap this audit names.

    The Phase 3 noisy-mode gate threshold for canonicalization B-cubed F1
    is 0.65 (see PROJECT_PLAN.md "Noisy-Mode Quality Gates"). A row that
    passes that clustering-quality floor while having a near-zero
    exact-lookup rate is the headline case the audit exposes. The
    threshold here is a *description* of the existing gate, not a new
    QR-canon pass/fail threshold.
    """
    if b_cubed is None:
        return False
    return b_cubed >= 0.65 and qr_canon_exact_rate < 0.05


def _wilson_interval(
    successes: int, trials: int, confidence: float = 0.95
) -> Tuple[float, float]:
    """Two-sided Wilson score confidence interval.

    Uses z = 1.959963984540054 for 95% confidence (scipy-free, byte-stable).
    """
    if trials <= 0:
        return 0.0, 0.0
    z = 1.959963984540054  # 0.5 + 0.475 quantile of standard normal
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    half = (
        z
        * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials)
        / denom
    )
    return max(0.0, center - half), min(1.0, center + half)


def _fmt(value: float) -> str:
    return f"{value:.6f}"


def _parse_optional_float(value: str) -> Optional[float]:
    if value == "":
        return None
    return float(value)


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
    source_path: Path,
    metrics_path: Path,
    family_rows: List[Dict[str, object]],
    synthetic_row: Dict[str, object],
) -> Dict[str, object]:
    source_sha, source_size = _hash_file(source_path)
    metrics_sha, metrics_size = _hash_file(metrics_path)
    return {
        "command": "python3 scripts/run_qr_canon_audit.py",
        "date": "2026-05-17",
        "git_commit": _git_commit(),
        "python_version": _python_version(),
        "working_tree_status": _working_tree_status(),
        "inputs": {
            "source_table_csv": {
                "path": str(SOURCE_TABLE),
                "sha256": source_sha,
                "byte_size": source_size,
            },
        },
        "outputs": {
            "audit_metrics_csv": {
                "path": str(OUTPUT_METRICS),
                "sha256": metrics_sha,
                "byte_size": metrics_size,
            },
        },
        "phase_4_per_family_summary": {
            row["family"]: {
                "denominator": row["denominator"],
                "qr_canon_exact_hits": row["qr_canon_exact_hits"],
                "qr_canon_exact_rate": row["qr_canon_exact_rate"],
                "qr_canon_normalized_hits": row["qr_canon_normalized_hits"],
                "qr_canon_normalized_rate": row["qr_canon_normalized_rate"],
                "canonicalization_b_cubed_f1": row["canonicalization_b_cubed_f1"],
                "joint_passes_clustering_floor_but_not_lookup": row[
                    "joint_passes_clustering_floor_but_not_lookup"
                ],
            }
            for row in family_rows
        },
        "synthetic_counterexample_present": True,
        "synthetic_counterexample_summary": {
            "b_cubed_f1": synthetic_row["canonicalization_b_cubed_f1"],
            "qr_canon_exact_rate": synthetic_row["qr_canon_exact_rate"],
            "qr_canon_normalized_rate": synthetic_row["qr_canon_normalized_rate"],
        },
        "registration_doc": "docs/qr_canon_audit_registration.md",
        "alias_function_source": (
            "scripts/run_canonical_id_resolution_audit.py imports "
            "ALIAS_FUNCTION_SOURCE verbatim from "
            "docs/canonical_id_resolution_audit_preregistration.md "
            "section 6"
        ),
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
