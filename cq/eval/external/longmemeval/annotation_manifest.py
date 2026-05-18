from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional

from cq.eval.external.longmemeval.preregistration_lock import (
    validate_fair_stream_externalization_lock,
)


MANIFEST_DATE = "2026-05-18"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    *,
    oracle_json: Path,
    feasibility_csv: Path,
    path_a_json: Path,
    path_b_json: Path,
    agreed_json: Path,
    divergence_json: Path,
    verifier_json: Path,
    preregistration_lock_sha256: str,
) -> dict[str, Any]:
    divergence = _read_json(divergence_json)
    verifier = _read_json(verifier_json)
    return {
        "manifest_date": MANIFEST_DATE,
        "workstream": "longmemeval_fair_stream_externalization_phase_x1",
        "preregistration_lock_sha256": preregistration_lock_sha256,
        "inputs": {
            "oracle_json_sha256": sha256_file(oracle_json),
            "oracle_json_bytes": oracle_json.stat().st_size,
            "feasibility_csv_sha256": sha256_file(feasibility_csv),
            "feasibility_csv_bytes": feasibility_csv.stat().st_size,
        },
        "outputs": {
            "annotations_path_a_json_sha256": sha256_file(path_a_json),
            "annotations_path_b_json_sha256": sha256_file(path_b_json),
            "annotations_agreed_json_sha256": sha256_file(agreed_json),
            "dual_path_divergence_report_json_sha256": sha256_file(divergence_json),
            "verifier_report_json_sha256": sha256_file(verifier_json),
        },
        "audit_summary": divergence.get("summary", {}),
        "verifier_summary": {
            "verifier_passed": verifier.get("verifier_passed"),
            "audit_summary_present": verifier.get("audit_summary_present"),
            "hidden_answer_check_passed": verifier.get("hidden_answer_check_passed"),
            "agreement_rate_check_passed": verifier.get("agreement_rate_check_passed"),
            "binomial_check_passed": verifier.get("binomial_check_passed"),
        },
    }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected object JSON in {}".format(path))
    return payload


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Write LongMemEval Phase X.1 manifest.")
    parser.add_argument("--oracle-json", required=True)
    parser.add_argument("--feasibility-csv", required=True)
    parser.add_argument("--path-a-json", required=True)
    parser.add_argument("--path-b-json", required=True)
    parser.add_argument("--agreed-json", required=True)
    parser.add_argument("--divergence-json", required=True)
    parser.add_argument("--verifier-json", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)
    manifest = build_manifest(
        oracle_json=Path(args.oracle_json),
        feasibility_csv=Path(args.feasibility_csv),
        path_a_json=Path(args.path_a_json),
        path_b_json=Path(args.path_b_json),
        agreed_json=Path(args.agreed_json),
        divergence_json=Path(args.divergence_json),
        verifier_json=Path(args.verifier_json),
        preregistration_lock_sha256=validate_fair_stream_externalization_lock(),
    )
    write_json(args.output_json, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
