from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

from cq.eval.end_to_end_eval import execute_scenario, summarize_runs
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.schemas.memory import jsonable
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios
from cq.simulator.render_events import render_scenario_transcript


def _summaries_by_field(run_records: List[dict], field_name: str) -> Dict[str, dict]:
    grouped = {}
    for record in run_records:
        field_value = record["scenario"].get(field_name, "")
        grouped.setdefault(field_value, []).append(record)
    return {
        field_value: jsonable(summarize_runs(group_records))
        for field_value, group_records in sorted(grouped.items())
        if field_value
    }


def build_run_artifact(scenario_count: int, template_mix: str = "mixed") -> dict:
    scenarios = generate_forced_contradiction_scenarios(scenario_count, template_mix=template_mix)
    policies = [ReflectionEagerWriteLite, ConsolidationQueueLite, NaiveEagerWriteLite]
    policy_runs = []
    for policy_cls in policies:
        run_records = [execute_scenario(policy_cls, scenario) for scenario in scenarios]
        summary = summarize_runs(run_records)
        policy_runs.append(
            {
                "policy_name": policy_cls.policy_name,
                "summary": jsonable(summary),
                "summary_by_template_kind": _summaries_by_field(run_records, "template_kind"),
                "summary_by_template_split": _summaries_by_field(run_records, "template_split"),
                "summary_by_template_id": _summaries_by_field(run_records, "template_id"),
                "scenarios": [
                    {
                        "scenario_id": record["scenario_id"],
                        "transcript": render_scenario_transcript(scenarios[index]),
                        "scenario": record["scenario"],
                        "question_traces": record["question_traces"],
                        "store_snapshot": record["store_snapshot"],
                        "metrics": record["metrics"],
                    }
                    for index, record in enumerate(run_records)
                ],
            }
        )
    return {
        "experiment": "forced_contradiction_oracle",
        "scenario_count": scenario_count,
        "template_mix": template_mix,
        "policies": policy_runs,
    }


def write_outputs(run_artifact: dict, output_json: Path, output_csv: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(run_artifact, indent=2), encoding="utf-8")

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "policy_name",
                "summary_scope",
                "template_id",
                "template_kind",
                "template_split",
                "scenario_count",
                "useful_recall_before_contradiction",
                "used_pending_before_contradiction",
                "durable_commit_before_contradiction",
                "false_assertion_after_contradiction",
                "contradiction_recovery_rate",
                "average_time_to_demotion",
            ],
        )
        writer.writeheader()
        for policy in run_artifact["policies"]:
            overall_row = dict(policy["summary"])
            overall_row.update(
                {
                    "summary_scope": "overall",
                    "template_id": "",
                    "template_kind": "",
                    "template_split": "",
                }
            )
            writer.writerow(overall_row)
            for template_kind, summary in policy.get("summary_by_template_kind", {}).items():
                row = dict(summary)
                row.update(
                    {
                        "summary_scope": "template_kind",
                        "template_id": "",
                        "template_kind": template_kind,
                        "template_split": "",
                    }
                )
                writer.writerow(row)
            for template_split, summary in policy.get("summary_by_template_split", {}).items():
                row = dict(summary)
                row.update(
                    {
                        "summary_scope": "template_split",
                        "template_id": "",
                        "template_kind": "",
                        "template_split": template_split,
                    }
                )
                writer.writerow(row)
            for template_id, summary in policy.get("summary_by_template_id", {}).items():
                row = dict(summary)
                row.update(
                    {
                        "summary_scope": "template_id",
                        "template_id": template_id,
                        "template_kind": "",
                        "template_split": "",
                    }
                )
                writer.writerow(row)


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Run oracle forced-contradiction experiments.")
    parser.add_argument("--scenarios", type=int, default=25, help="Number of oracle scenarios to generate.")
    parser.add_argument(
        "--template-mix",
        choices=["mixed", "clean", "dirty", "heldout"],
        default="mixed",
        help="Scenario template mix for forced-contradiction generation.",
    )
    parser.add_argument(
        "--output-json",
        default="data/runs/forced_contradiction_oracle.json",
        help="Path to the run artifact JSON.",
    )
    parser.add_argument(
        "--output-csv",
        default="data/results/forced_contradiction_oracle_metrics.csv",
        help="Path to the summary metrics CSV.",
    )
    args = parser.parse_args(argv)

    run_artifact = build_run_artifact(args.scenarios, template_mix=args.template_mix)
    write_outputs(run_artifact, Path(args.output_json), Path(args.output_csv))

    for policy in run_artifact["policies"]:
        summary = policy["summary"]
        print(
            "{policy_name}: useful_recall={useful:.2f} pending_use={pending:.2f} "
            "early_durable_commit={durable:.2f} false_assertion={false:.2f} "
            "recovery={recovery:.2f} avg_time_to_demotion={demotion:.2f}".format(
                policy_name=summary["policy_name"],
                useful=summary["useful_recall_before_contradiction"],
                pending=summary["used_pending_before_contradiction"],
                durable=summary["durable_commit_before_contradiction"],
                false=summary["false_assertion_after_contradiction"],
                recovery=summary["contradiction_recovery_rate"],
                demotion=summary["average_time_to_demotion"],
            )
        )
        for template_kind, kind_summary in policy.get("summary_by_template_kind", {}).items():
            print(
                "  kind={template_kind}: false_assertion={false:.2f} recovery={recovery:.2f} count={count}".format(
                    template_kind=template_kind,
                    false=kind_summary["false_assertion_after_contradiction"],
                    recovery=kind_summary["contradiction_recovery_rate"],
                    count=kind_summary["scenario_count"],
                )
            )
        for template_split, split_summary in policy.get("summary_by_template_split", {}).items():
            print(
                "  split={template_split}: false_assertion={false:.2f} recovery={recovery:.2f} count={count}".format(
                    template_split=template_split,
                    false=split_summary["false_assertion_after_contradiction"],
                    recovery=split_summary["contradiction_recovery_rate"],
                    count=split_summary["scenario_count"],
                )
            )
        for template_id, template_summary in policy.get("summary_by_template_id", {}).items():
            print(
                "  template={template_id}: false_assertion={false:.2f} recovery={recovery:.2f} count={count}".format(
                    template_id=template_id,
                    false=template_summary["false_assertion_after_contradiction"],
                    recovery=template_summary["contradiction_recovery_rate"],
                    count=template_summary["scenario_count"],
                )
            )
    print("Template mix: {}".format(args.template_mix))
    print("Wrote {}".format(args.output_json))
    print("Wrote {}".format(args.output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
