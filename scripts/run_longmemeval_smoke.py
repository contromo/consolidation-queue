#!/usr/bin/env python3
"""Phase X.3 smoke artifact generator.

Runs the LongMemEval adapter and actual memory policies on the first N agreed
cases, validates the adapter pin and preregistration lock, and writes a
byte-stable smoke summary plus manifest under ``data/external/longmemeval/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cq.eval.external.longmemeval.adapter import (
    ADAPTER_PIN_PATH,
    DEFAULT_ANNOTATIONS_PATH,
    adapt_annotations,
    build_dry_run_summary,
    load_agreed_annotations,
)
from cq.eval.end_to_end_eval import execute_scenario, summarize_runs
from cq.eval.external.longmemeval.dirty_worktree_check import (
    assert_clean_worktree,
    current_commit_sha,
    worktree_status_porcelain,
)
from cq.eval.runner import POLICY_SET_CHOICES, POLICY_SET_PHASE_2_5, _policies_for_family
from cq.schemas.memory import jsonable
from cq.schemas.scenario import TaskFamily


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


def _source_provenance(*, allow_dirty_worktree: bool) -> dict:
    status = worktree_status_porcelain(REPO_ROOT)
    if not allow_dirty_worktree:
        assert_clean_worktree(REPO_ROOT)
    return {
        "git_commit_sha": current_commit_sha(REPO_ROOT),
        "worktree_clean": not status,
        "dirty_worktree_check_passed": not status,
        "dirty_worktree_allowed": allow_dirty_worktree,
        "git_status_porcelain": status.splitlines() if status else [],
    }


def _smoke_policy_classes(policy_set: str):
    return _policies_for_family(
        TaskFamily.LONGMEMEVAL_EXTERNAL.value,
        policy_set=policy_set,
    )


def _policy_visible_candidate_hash(candidate_rows: list[dict]) -> str:
    visible_rows = []
    for candidate in candidate_rows:
        visible_rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "raw_text": candidate.get("raw_text"),
                "raw_claim": candidate.get("raw_claim"),
                "canonical_claim": candidate.get("canonical_claim"),
                "claim_type": candidate.get("claim_type"),
                "scope_level": candidate.get("scope_level"),
                "scope_key": candidate.get("scope_key"),
                "canonical_id": candidate.get("canonical_id"),
                "provenance": candidate.get("provenance", []),
                "verification_score": candidate.get("verification_score"),
                "contradicts": candidate.get("contradicts", []),
                "supports": candidate.get("supports", []),
            }
        )
    payload = json.dumps(visible_rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _policy_smoke_summary(
    *,
    annotations_path: Path,
    case_limit: int | None,
    policy_set: str,
    policy_classes,
) -> dict:
    scenarios, streams = adapt_annotations(
        load_agreed_annotations(annotations_path),
        case_limit=case_limit,
    )
    pre_policy_hash_by_scenario = {
        scenario_id: _policy_visible_candidate_hash(
            [jsonable(candidate) for candidate in stream.candidates]
        )
        for scenario_id, stream in streams.items()
    }
    policy_runs = []
    for policy_cls in policy_classes:
        run_records = [execute_scenario(policy_cls, scenario) for scenario in scenarios]
        per_scenario = []
        for record in run_records:
            traces = list(record["question_traces"])
            trace = traces[0] if traces else {}
            store_snapshot = record["store_snapshot"]
            metrics = record["metrics"]
            candidate_memory_count = len(store_snapshot.get("candidate_memories", []))
            input_candidate_count = len(streams[record["scenario_id"]].candidates)
            post_hash_applicable = candidate_memory_count == input_candidate_count
            post_hash = _policy_visible_candidate_hash(
                store_snapshot.get("candidate_memories", [])
            )
            pre_hash = pre_policy_hash_by_scenario[record["scenario_id"]]
            per_scenario.append(
                {
                    "scenario_id": record["scenario_id"],
                    "question_trace_count": len(traces),
                    "resolved_candidate_count": len(trace.get("resolved_candidate_ids", [])),
                    "used_memory_count": len(trace.get("used_memory_ids", [])),
                    "used_pending": bool(trace.get("used_pending", False)),
                    "candidate_memory_count": candidate_memory_count,
                    "durable_memory_count": len(store_snapshot.get("durable_memories", [])),
                    "lifecycle_event_count": len(store_snapshot.get("lifecycle_events", [])),
                    "failure_example_count": len(record.get("failure_examples", [])),
                    "pre_policy_visible_candidate_sha256": pre_hash,
                    "post_policy_visible_candidate_sha256": post_hash,
                    "post_execution_candidate_hash_check_applicable": post_hash_applicable,
                    "post_execution_candidate_hash_match": (
                        post_hash == pre_hash if post_hash_applicable else None
                    ),
                    "useful_recall": metrics["useful_recall"],
                    "durable_commit": metrics["durable_commit"],
                }
            )
        post_hash_rows = [
            row["post_execution_candidate_hash_match"]
            for row in per_scenario
            if row["post_execution_candidate_hash_check_applicable"]
        ]
        policy_runs.append(
            {
                "policy_name": policy_cls.policy_name,
                "scenario_count": len(run_records),
                "post_execution_candidate_hash_check_passed": all(post_hash_rows),
                "summary": jsonable(summarize_runs(run_records)),
                "per_scenario": per_scenario,
            }
        )
    expected_count = len(scenarios)
    return {
        "mode": "longmemeval_external_policy_smoke",
        "policy_set": policy_set,
        "policy_count": len(policy_runs),
        "policy_names": [run["policy_name"] for run in policy_runs],
        "scenario_count": expected_count,
        "policy_smoke_passed": all(
            run["scenario_count"] == expected_count for run in policy_runs
        ),
        "post_execution_candidate_hash_check_passed": all(
            run["post_execution_candidate_hash_check_passed"] for run in policy_runs
        ),
        "policies": policy_runs,
    }


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
    parser.add_argument(
        "--policy-set",
        choices=POLICY_SET_CHOICES,
        default=POLICY_SET_PHASE_2_5,
        help="Policy set to execute in the smoke run.",
    )
    parser.add_argument(
        "--allow-dirty-worktree",
        action="store_true",
        help=(
            "Record but do not fail on dirty git status. Use only for local "
            "regeneration/tests; Phase X.3 policy smoke defaults to a clean "
            "pre-run worktree check."
        ),
    )
    args = parser.parse_args()

    annotations_path = Path(args.annotations_json)
    adapter_pin_path = Path(args.adapter_pin)
    provenance = _source_provenance(allow_dirty_worktree=args.allow_dirty_worktree)
    policy_classes = _smoke_policy_classes(args.policy_set)
    policy_names = [policy_cls.policy_name for policy_cls in policy_classes]
    summary = build_dry_run_summary(
        annotations_path=annotations_path,
        case_limit=args.case_limit,
        validate_pin=not args.no_pin_validation,
        adapter_pin_path=adapter_pin_path,
        policy_names=policy_names,
    )
    policy_smoke = _policy_smoke_summary(
        annotations_path=annotations_path,
        case_limit=args.case_limit,
        policy_set=args.policy_set,
        policy_classes=policy_classes,
    )
    summary["policy_smoke"] = policy_smoke
    _write_json(args.out_summary, summary)

    manifest = {
        "artifact": "longmemeval_externalization_smoke",
        "artifact_class": "phase_x3_smoke",
        "case_limit": args.case_limit,
        "policy_set": args.policy_set,
        "adapter_sha256": summary["adapter_sha256"],
        "preregistration_lock_sha256": summary["preregistration_lock_sha256"],
        "source_provenance": provenance,
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
        "policy_smoke_passed": policy_smoke["policy_smoke_passed"],
        "post_execution_candidate_hash_check_passed": policy_smoke[
            "post_execution_candidate_hash_check_passed"
        ],
        "policy_count": policy_smoke["policy_count"],
        "policy_names": policy_smoke["policy_names"],
        "scenario_count": summary["scenario_count"],
        "candidate_count": summary["candidate_count"],
    }
    _write_json(args.out_manifest, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
