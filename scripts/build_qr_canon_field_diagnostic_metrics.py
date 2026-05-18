"""Build the PFLC / QR-canon field-diagnostic synthetic-counterexample
metrics CSV and manifest.

Workstream A.6 outcome: all four anchor benchmarks landed at
``descriptive-only`` (LongMemEval, Mem0/LoCoMo, MemoryAgentBench,
MemBench). No anchor benchmark released artifacts that support empirical
PFLC scoring, so the workstream lands at outcome bucket B-3 per
``docs/policy_facing_lookup_contract_registration.md`` §4.

This script ships the four per-benchmark synthetic counterexamples as
fixture rows in ``data/results/qr_canon_field_diagnostic_metrics.csv``.
Each row instantiates either Proposition 1 (cluster-partition gap),
Lemma 1 (retrieval-content / retrieval-id gap), or Lemma 2
(answer-accuracy / lookup-handle gap) from
``docs/policy_facing_lookup_contract_proposition.md``.

The script reads **no** external inputs; the fixtures are constructed
verbatim from the per-benchmark feasibility memos. Output bytes are
byte-stable across reruns.

The script does **not**:

- read any gitignored Phase 4 run JSONs;
- read any external benchmark dataset;
- run any policy on any external benchmark;
- modify the byte-locked CQR alias function.

See ``docs/policy_facing_lookup_contract_registration.md`` for the
locked posture.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_METRICS = Path("data/results/qr_canon_field_diagnostic_metrics.csv")
OUTPUT_MANIFEST = Path("data/results/qr_canon_field_diagnostic_metrics_manifest.json")

ALIAS_SOURCE_SCRIPT = Path("scripts/run_canonical_id_resolution_audit.py")
ALIAS_SOURCE_SHA_DOC = Path("docs/canonical_id_resolution_audit_preregistration.md")
ALIAS_SOURCE_SHA_EXPECTED = (
    "8176c5a93ffbdbfd99d48f73836b954aa27aee4ab08de567ca47ec63d7896de0"
)

BENCHMARK_ORDER = [
    "longmemeval",
    "mem0_locomo",
    "memoryagentbench",
    "membench",
]

CSV_FIELDNAMES = [
    "row_id",
    "benchmark",
    "pflc_instance",
    "denominator",
    "pflc_exact_hits",
    "pflc_exact_rate",
    "pflc_exact_wilson_lcb",
    "pflc_exact_wilson_ucb",
    "paired_headline_metric_name",
    "paired_headline_metric_value",
    "joint_passes_headline_but_not_lookup",
    "proposition_or_lemma_ref",
    "row_kind",
]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the PFLC field-diagnostic synthetic-counterexample "
            "metrics CSV and manifest. No external inputs; no policy run."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root for relative-path outputs.",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    rows = _build_synthetic_rows()

    metrics_path = (repo_root / OUTPUT_METRICS).resolve()
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(metrics_path, rows)

    manifest = _build_manifest(repo_root=repo_root, metrics_path=metrics_path, rows=rows)
    manifest_path = (repo_root / OUTPUT_MANIFEST).resolve()
    _write_json(manifest_path, manifest)

    print(f"Wrote {metrics_path.relative_to(repo_root)}")
    print(f"Wrote {manifest_path.relative_to(repo_root)}")
    return 0


def _build_synthetic_rows() -> List[Dict[str, object]]:
    """Construct the four anchor-benchmark synthetic counterexample rows.

    Each row is a fixture per the corresponding feasibility memo's §7.
    Values are by construction, not observation; the row_kind makes that
    explicit.
    """
    audit = _load_audit_module()
    wilson_ucb_zero_over_one = audit._wilson_interval(0, 1)[1]

    rows: List[Dict[str, object]] = []
    for benchmark in BENCHMARK_ORDER:
        spec = _FIXTURE_SPECS[benchmark]
        rows.append(
            {
                "row_id": f"synthetic_{benchmark}_counterexample",
                "benchmark": benchmark,
                "pflc_instance": spec["pflc_instance"],
                "denominator": 1,
                "pflc_exact_hits": 0,
                "pflc_exact_rate": _fmt(0.0),
                "pflc_exact_wilson_lcb": _fmt(0.0),
                "pflc_exact_wilson_ucb": _fmt(wilson_ucb_zero_over_one),
                "paired_headline_metric_name": spec["paired_headline_metric_name"],
                "paired_headline_metric_value": _fmt(1.0),
                "joint_passes_headline_but_not_lookup": True,
                "proposition_or_lemma_ref": spec["proposition_or_lemma_ref"],
                "row_kind": f"synthetic_{benchmark}_counterexample",
            }
        )
    return rows


_FIXTURE_SPECS: Dict[str, Dict[str, str]] = {
    "longmemeval": {
        "pflc_instance": "answer-handle",
        "paired_headline_metric_name": "overall_accuracy",
        "proposition_or_lemma_ref": "Lemma 2",
    },
    "mem0_locomo": {
        "pflc_instance": "dialog-evidence-id",
        "paired_headline_metric_name": "recall_at_k",
        "proposition_or_lemma_ref": "Lemma 1",
    },
    "memoryagentbench": {
        "pflc_instance": "conflict-resolution-id",
        "paired_headline_metric_name": "task_accuracy",
        "proposition_or_lemma_ref": "Lemma 2",
    },
    "membench": {
        "pflc_instance": "fact-id",
        "paired_headline_metric_name": "factual_recall",
        "proposition_or_lemma_ref": "Lemma 1",
    },
}


def proposition_one_construction() -> Dict[str, object]:
    """Return the canonical Proposition 1 construction for a label-renaming
    bijection with rho(g*) != g* AND g* not in image(rho).

    Gold partition: a single two-item cluster ``{e1, e2}`` labeled
    ``gold-X``. Predicted partition: the same one cluster labeled
    ``pred-Y`` via the renaming rho: gold-X -> pred-Y. Set-membership
    PFLC for the queried target g* = ``gold-X`` checks
    ``gold-X in image(rho) = {pred-Y}``, which is False. B-cubed F1 over
    identical partitions equals 1.00 regardless of labels.
    """
    return {
        "items": ("e1", "e2"),
        "gold_partition": ({"e1", "e2"},),
        "pred_partition": ({"e1", "e2"},),
        "label_gold_for_cluster": {frozenset({"e1", "e2"}): "gold-X"},
        "label_pred_for_cluster": {frozenset({"e1", "e2"}): "pred-Y"},
        "query_target_g_star": "gold-X",
        "renaming_rho": {"gold-X": "pred-Y"},
        "renaming_image": {"pred-Y"},
        "predicted_label_set": {"pred-Y"},
        "m_cluster_b_cubed_f1_by_construction": 1.0,
        "m_lookup_set_membership_by_construction": 0,
        "rho_g_star_not_equal_g_star": True,
        "g_star_not_in_image_rho": True,
    }


def _wilson_interval(successes: int, trials: int) -> Tuple[float, float]:
    """Thin wrapper that reuses the audit module's Wilson implementation
    so this script does not duplicate the formula.
    """
    return _load_audit_module()._wilson_interval(successes, trials)


def _fmt(value: float) -> str:
    return f"{value:.6f}"


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
    repo_root: Path,
    metrics_path: Path,
    rows: List[Dict[str, object]],
) -> Dict[str, object]:
    metrics_sha, metrics_size = _hash_file(metrics_path)
    per_benchmark_summary: Dict[str, Dict[str, object]] = {}
    for row in rows:
        per_benchmark_summary[row["benchmark"]] = {
            "pflc_instance": row["pflc_instance"],
            "pflc_exact_rate": row["pflc_exact_rate"],
            "paired_headline_metric_name": row["paired_headline_metric_name"],
            "paired_headline_metric_value": row["paired_headline_metric_value"],
            "joint_passes_headline_but_not_lookup": row[
                "joint_passes_headline_but_not_lookup"
            ],
            "proposition_or_lemma_ref": row["proposition_or_lemma_ref"],
            "row_kind": row["row_kind"],
        }
    construction = proposition_one_construction()
    return {
        "command": "python3 scripts/build_qr_canon_field_diagnostic_metrics.py",
        "date": "2026-05-18",
        "inputs": {},
        "outputs": {
            "field_diagnostic_metrics_csv": {
                "path": str(OUTPUT_METRICS),
                "sha256": metrics_sha,
                "byte_size": metrics_size,
            },
        },
        "per_benchmark_synthetic_summary": per_benchmark_summary,
        "proposition_one_reproducibility": {
            "m_cluster_b_cubed_f1_by_construction": (
                construction["m_cluster_b_cubed_f1_by_construction"]
            ),
            "m_lookup_set_membership_by_construction": (
                construction["m_lookup_set_membership_by_construction"]
            ),
            "rho_g_star_not_equal_g_star": construction["rho_g_star_not_equal_g_star"],
            "g_star_not_in_image_rho": construction["g_star_not_in_image_rho"],
        },
        "alias_function_sha256_pin": {
            "expected_sha256": ALIAS_SOURCE_SHA_EXPECTED,
            "source_doc": str(ALIAS_SOURCE_SHA_DOC),
            "source_script": str(ALIAS_SOURCE_SCRIPT),
            "note": (
                "PFLC canonical-id instance inherits the byte-locked CQR "
                "alias function. Other PFLC instances (retrieval-id, "
                "slot-id, fact-id, answer-handle) do not inherit it. The "
                "pin is documentary; the audit logic does not modify the "
                "function."
            ),
        },
        "registration_doc": "docs/policy_facing_lookup_contract_registration.md",
        "proposition_doc": "docs/policy_facing_lookup_contract_proposition.md",
        "workstream_outcome_bucket": "B-3",
        "workstream_outcome_rationale": (
            "All four anchor benchmark feasibility memos landed at "
            "descriptive-only. No anchor released artifacts sufficient "
            "for empirical PFLC scoring. B-3 (artifact-blocked) per "
            "registration section 4."
        ),
    }


def _load_audit_module():
    audit_path = REPO_ROOT / "scripts" / "run_qr_canon_audit.py"
    spec = importlib.util.spec_from_file_location(
        "run_qr_canon_audit_for_field_diagnostic", audit_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load audit module at {audit_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())
