#!/usr/bin/env python3
"""CLI for LongMemEval dialog-evidence-id PFLC scoring.

Reads a policy-predictions JSON and a LongMemEval oracle JSON, computes PFLC
metrics per the preregistration §6 contract, and writes per-row CSV + summary
JSON.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cq.eval.external.longmemeval.scorer import (
    DEFAULT_K,
    degeneracy_diagnostic,
    load_gold_cases,
    load_policy_predictions,
    score_predictions,
)
from cq.eval.external.longmemeval.adapter import load_agreed_annotations


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _expected_case_ids_from_annotations(path: Path, case_limit: int | None) -> list[str]:
    rows = sorted(load_agreed_annotations(path), key=lambda row: str(row.get("case_id") or ""))
    if case_limit is not None:
        rows = rows[:case_limit]
    return [str(row["case_id"]) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions-json", required=True, type=Path)
    parser.add_argument("--oracle-json", required=True, type=Path)
    parser.add_argument("--out-csv", required=True, type=Path)
    parser.add_argument("--out-summary", required=True, type=Path)
    parser.add_argument("--bootstrap-seed", type=int, default=1729)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--k", type=int, nargs="*", default=list(DEFAULT_K))
    parser.add_argument(
        "--expected-annotations-json",
        type=Path,
        help=(
            "Agreed annotation denominator. If omitted, every gold case in "
            "--oracle-json must have one prediction per policy."
        ),
    )
    parser.add_argument(
        "--case-limit",
        type=int,
        help="Apply the same sorted case limit to --expected-annotations-json.",
    )
    args = parser.parse_args()

    gold_cases = load_gold_cases(args.oracle_json)
    predictions = load_policy_predictions(args.predictions_json)
    expected_case_ids = (
        _expected_case_ids_from_annotations(args.expected_annotations_json, args.case_limit)
        if args.expected_annotations_json is not None
        else None
    )
    ks = tuple(args.k)
    result = score_predictions(
        predictions,
        gold_cases,
        expected_case_ids=expected_case_ids,
        ks=ks,
        bootstrap_seed=args.bootstrap_seed,
        bootstrap_samples=args.bootstrap_samples,
    )
    _write_csv(args.out_csv, result["rows"])
    summary = {
        "artifact": "longmemeval_pflc",
        "artifact_class": "external_transfer_phase_x3_to_x4",
        "created_utc_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "predictions_json_path": str(args.predictions_json),
        "predictions_json_sha256": _sha256(args.predictions_json),
        "oracle_json_path": str(args.oracle_json),
        "oracle_json_sha256": _sha256(args.oracle_json),
        "expected_annotations_json_path": (
            str(args.expected_annotations_json) if args.expected_annotations_json else None
        ),
        "expected_annotations_json_sha256": (
            _sha256(args.expected_annotations_json) if args.expected_annotations_json else None
        ),
        "expected_case_count": result["summary"]["expected_case_count"],
        "out_csv_path": str(args.out_csv),
        "out_csv_sha256": _sha256(args.out_csv),
        "bootstrap_seed": args.bootstrap_seed,
        "bootstrap_samples": args.bootstrap_samples,
        "ks": list(ks),
        "summary": result["summary"],
        "degeneracy_diagnostic": degeneracy_diagnostic(gold_cases),
    }
    _write_json(args.out_summary, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
