#!/usr/bin/env python3
"""Phase X.3 smoke artifact generator.

Runs the LongMemEval adapter dry-run on the first N agreed cases, validates
the adapter pin and preregistration lock, and commits a byte-stable smoke
summary plus manifest under ``data/external/longmemeval/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cq.eval.external.longmemeval.adapter import (
    ADAPTER_PIN_PATH,
    DEFAULT_ANNOTATIONS_PATH,
    build_dry_run_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SUMMARY_PATH = Path("data/external/longmemeval/smoke_summary.json")
SMOKE_MANIFEST_PATH = Path("data/external/longmemeval/smoke_manifest.json")
DEFAULT_CASE_LIMIT = 6


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--annotations-json",
        default=str(DEFAULT_ANNOTATIONS_PATH),
        type=str,
        help="Agreed annotations input.",
    )
    parser.add_argument(
        "--adapter-pin",
        default=str(ADAPTER_PIN_PATH),
        type=str,
        help="Adapter pin JSON path.",
    )
    parser.add_argument(
        "--case-limit",
        type=int,
        default=DEFAULT_CASE_LIMIT,
        help="Number of agreed cases to include in the smoke run (default 6).",
    )
    parser.add_argument(
        "--out-summary",
        type=Path,
        default=SMOKE_SUMMARY_PATH,
    )
    parser.add_argument(
        "--out-manifest",
        type=Path,
        default=SMOKE_MANIFEST_PATH,
    )
    parser.add_argument(
        "--no-pin-validation",
        action="store_true",
        help="Skip adapter pin validation. Use only when generating a fresh pin.",
    )
    args = parser.parse_args()

    annotations_path = Path(args.annotations_json)
    adapter_pin_path = Path(args.adapter_pin)
    summary = build_dry_run_summary(
        annotations_path=annotations_path,
        case_limit=args.case_limit,
        validate_pin=not args.no_pin_validation,
        adapter_pin_path=adapter_pin_path,
    )
    _write_json(args.out_summary, summary)

    manifest = {
        "artifact": "longmemeval_externalization_smoke",
        "artifact_class": "phase_x3_smoke",
        "case_limit": args.case_limit,
        "adapter_sha256": summary["adapter_sha256"],
        "preregistration_lock_sha256": summary["preregistration_lock_sha256"],
        "inputs": {
            "annotations_json_repo_path": _repo_relative(annotations_path),
            "annotations_json_sha256": _sha256(annotations_path),
            "annotations_json_bytes": annotations_path.stat().st_size,
            "adapter_pin_repo_path": _repo_relative(adapter_pin_path),
            "adapter_pin_sha256": _sha256(adapter_pin_path),
            "adapter_pin_bytes": adapter_pin_path.stat().st_size,
        },
        "outputs": {
            "smoke_summary_repo_path": _repo_relative(args.out_summary),
            "smoke_summary_sha256": _sha256(args.out_summary),
            "smoke_summary_bytes": args.out_summary.stat().st_size,
        },
        "candidate_stream_hash_invariant_passed": summary[
            "candidate_stream_hash_invariant_passed"
        ],
        "scenario_count": summary["scenario_count"],
        "candidate_count": summary["candidate_count"],
    }
    _write_json(args.out_manifest, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
