#!/usr/bin/env python3
"""Run a small judged smoke for LongMemEval answer-correctness discrimination."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.external.longmemeval.adapter import (
    DEFAULT_ANNOTATIONS_PATH,
    adapt_annotations,
    candidate_stream_hash_report,
    load_agreed_annotations,
)
from cq.eval.external.longmemeval.gold_loader import load_gold_cases
from cq.eval.external.longmemeval.judge_stability import (
    DEFAULT_PRIMARY_JUDGE,
    CalibrationCase,
    run_judge,
)
from cq.eval.external.longmemeval.transfer import _predicted_session_ids
from cq.eval.runner import POLICY_SET_PHASE_2_5, _policies_for_family
from cq.schemas.scenario import TaskFamily


CASE_COUNT = 3
ORACLE_JSON = Path("/tmp/longmemeval_oracle.json")
OUT_JSON = REPO_ROOT / "data" / "external" / "longmemeval" / "answer_correct_smoke.json"


def run_smoke(
    *,
    case_count: int = CASE_COUNT,
    oracle_json: str | Path = ORACLE_JSON,
    output_json: str | Path = OUT_JSON,
    judge_model: str = DEFAULT_PRIMARY_JUDGE,
) -> dict[str, object]:
    annotations = sorted(
        load_agreed_annotations(DEFAULT_ANNOTATIONS_PATH),
        key=lambda row: str(row["case_id"]),
    )[:case_count]
    scenarios, streams = adapt_annotations(annotations)
    policies = _policies_for_family(
        TaskFamily.LONGMEMEVAL_EXTERNAL.value,
        policy_set=POLICY_SET_PHASE_2_5,
    )
    policy_names = [policy.policy_name for policy in policies]
    hash_report = candidate_stream_hash_report(streams, policy_names)
    if hash_report["candidate_stream_hash_mismatches"]:
        raise RuntimeError("candidate stream hash mismatch")

    gold_by_case = {case.case_id: case for case in load_gold_cases(oracle_json)}
    rows = []
    judge_cases = []
    for policy_cls in policies:
        for scenario in scenarios:
            case_id = str(scenario.latent_truth_graph["case_id"])
            trace = (execute_scenario(policy_cls, scenario).get("question_traces") or [{}])[0]
            answer = str(trace.get("answer_text") or "")
            predicted_session_ids = _predicted_session_ids(
                trace.get("resolved_candidate_ids", []),
                streams[scenario.scenario_id].source_session_id_by_candidate_id,
            )
            judge_case_id = "smoke::{}::{}".format(policy_cls.policy_name, case_id)
            rows.append(
                {
                    "judge_case_id": judge_case_id,
                    "policy_name": policy_cls.policy_name,
                    "case_id": case_id,
                    "candidate_answer": answer,
                    "predicted_session_ids_ranked": predicted_session_ids,
                }
            )
            judge_cases.append(
                CalibrationCase(
                    case_id=judge_case_id,
                    question=gold_by_case[case_id].question,
                    gold_answer=gold_by_case[case_id].answer,
                    candidate_answer=answer,
                    source_case_id=case_id,
                    source_policy=policy_cls.policy_name,
                )
            )

    verdicts = run_judge(judge_cases, model_id=judge_model)
    verdict_by_case = {verdict.case_id: verdict.verdict for verdict in verdicts}
    correct_by_policy = {}
    verdict_counts_by_policy = {}
    for row in rows:
        verdict = verdict_by_case[row["judge_case_id"]]
        row["judge_verdict"] = verdict
        correct_by_policy[row["policy_name"]] = correct_by_policy.get(row["policy_name"], 0) + int(
            verdict == "correct"
        )
        verdict_counts_by_policy.setdefault(row["policy_name"], {})
        verdict_counts_by_policy[row["policy_name"]][verdict] = (
            verdict_counts_by_policy[row["policy_name"]].get(verdict, 0) + 1
        )

    summary = {
        "mode": "longmemeval_answer_correct_smoke",
        "case_count": len(scenarios),
        "policy_count": len(policies),
        "judge_model": judge_model,
        "total_judged": len(rows),
        "correct_total": sum(correct_by_policy.values()),
        "correct_by_policy": dict(sorted(correct_by_policy.items())),
        "verdict_counts_by_policy": dict(sorted(verdict_counts_by_policy.items())),
        "case_ids": [str(scenario.latent_truth_graph["case_id"]) for scenario in scenarios],
        "rows": rows,
    }
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a small judged smoke for LongMemEval answer_correct.",
    )
    parser.add_argument("--case-count", type=int, default=CASE_COUNT)
    parser.add_argument("--oracle-json", default=str(ORACLE_JSON))
    parser.add_argument("--output-json", default=str(OUT_JSON))
    parser.add_argument("--judge-model", default=DEFAULT_PRIMARY_JUDGE)
    args = parser.parse_args(argv)

    summary = run_smoke(
        case_count=args.case_count,
        oracle_json=args.oracle_json,
        output_json=args.output_json,
        judge_model=args.judge_model,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2, sort_keys=True))
    print("wrote {}".format(args.output_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
