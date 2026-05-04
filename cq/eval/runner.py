from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

from cq.eval.end_to_end_eval import execute_scenario, failure_example_sort_key, summarize_runs
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.mem0_lite import Mem0Lite
from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.memory.no_memory import NoMemoryLite
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.memory.scope_blind_transcript_rag import ScopeBlindTranscriptRAGLite
from cq.schemas.memory import jsonable
from cq.simulator.scenario_generator import (
    generate_false_corroboration_scenarios,
    generate_forced_contradiction_scenarios,
    generate_memory_poisoning_scenarios,
    generate_preference_drift_scenarios,
    generate_scope_contamination_scenarios,
    generate_useful_pending_memory_scenarios,
)
from cq.simulator.render_events import render_scenario_transcript


FORCED_CONTRADICTION = "forced_contradiction"
SCOPE_CONTAMINATION = "scope_contamination"
PREFERENCE_DRIFT = "preference_drift"
USEFUL_PENDING_MEMORY = "useful_pending_memory"
FALSE_CORROBORATION = "false_corroboration"
MEMORY_POISONING = "memory_poisoning"
POLICY_SET_DEFAULT = "default"
POLICY_SET_PHASE_2_5 = "phase2_5"
POLICY_SET_CHOICES = (POLICY_SET_DEFAULT, POLICY_SET_PHASE_2_5)
TEMPLATE_MIXES_BY_FAMILY = {
    FORCED_CONTRADICTION: ("mixed", "clean", "dirty", "heldout"),
    SCOPE_CONTAMINATION: ("mixed", "clean", "dirty", "heldout"),
    PREFERENCE_DRIFT: ("mixed", "clean", "dirty", "heldout"),
    USEFUL_PENDING_MEMORY: ("mixed", "clean", "dirty", "heldout"),
    FALSE_CORROBORATION: ("mixed", "clean", "dirty", "heldout"),
    MEMORY_POISONING: ("mixed", "clean", "dirty", "heldout"),
}
SUMMARY_METRIC_FORMAT = (
    "false_assertion={false:.2f} recovery={recovery:.2f} correctness={correctness:.2f} "
    "leakage={leakage:.2f} premature_promotion={premature:.2f} "
    "poison_promotion={poison:.2f} clean_displacement={clean_displacement:.2f}"
)
OVERALL_SUMMARY_FORMAT = (
    "{policy_name}: useful_recall={useful:.2f} pending_use={pending:.2f} "
    "early_durable_commit={durable:.2f} "
    + SUMMARY_METRIC_FORMAT
    + " avg_time_to_demotion={demotion:.2f}"
)
SCOPED_SUMMARY_FORMAT = "  {scope_name}={scope_value}: " + SUMMARY_METRIC_FORMAT + " count={count}"


def _summary_metric_values(summary: dict) -> Dict[str, float]:
    return {
        "false": summary["false_assertion_rate"],
        "recovery": summary["contradiction_recovery_rate"],
        "correctness": summary["answer_correctness"],
        "leakage": summary["leakage_rate"],
        "premature": summary["premature_promotion_rate"],
        "poison": summary["poison_promotion_rate"],
        "clean_displacement": summary["clean_durable_displacement_rate"],
    }


def _format_overall_summary(summary: dict) -> str:
    values = _summary_metric_values(summary)
    values.update(
        {
            "policy_name": summary["policy_name"],
            "useful": summary["useful_recall"],
            "pending": summary["used_pending"],
            "durable": summary["durable_commit"],
            "demotion": summary["average_time_to_demotion"],
        }
    )
    return OVERALL_SUMMARY_FORMAT.format(**values)


def _format_scoped_summary(scope_name: str, scope_value: str, summary: dict) -> str:
    values = _summary_metric_values(summary)
    values.update(
        {
            "scope_name": scope_name,
            "scope_value": scope_value,
            "count": summary["scenario_count"],
        }
    )
    return SCOPED_SUMMARY_FORMAT.format(**values)


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


def _generate_scenarios(family: str, scenario_count: int, template_mix: str):
    _validate_template_mix(family, template_mix)
    if family == FORCED_CONTRADICTION:
        return generate_forced_contradiction_scenarios(scenario_count, template_mix=template_mix)
    if family == SCOPE_CONTAMINATION:
        return generate_scope_contamination_scenarios(scenario_count, template_mix=template_mix)
    if family == PREFERENCE_DRIFT:
        return generate_preference_drift_scenarios(scenario_count, template_mix=template_mix)
    if family == USEFUL_PENDING_MEMORY:
        return generate_useful_pending_memory_scenarios(scenario_count, template_mix=template_mix)
    if family == FALSE_CORROBORATION:
        return generate_false_corroboration_scenarios(scenario_count, template_mix=template_mix)
    if family == MEMORY_POISONING:
        return generate_memory_poisoning_scenarios(scenario_count, template_mix=template_mix)
    raise ValueError("Unsupported family: {}".format(family))


def _validate_template_mix(family: str, template_mix: str) -> None:
    allowed = TEMPLATE_MIXES_BY_FAMILY.get(family)
    if allowed is None:
        raise ValueError("Unsupported family: {}".format(family))
    if template_mix not in allowed:
        raise ValueError(
            "Template mix '{}' is not supported for family '{}'. Allowed: {}".format(
                template_mix,
                family,
                ", ".join(allowed),
            )
        )


MEM0_LITE_PARTIAL_BASELINE_CAVEAT = Mem0Lite.partial_baseline_caveat


def _policies_for_family(family: str, policy_set: str = POLICY_SET_DEFAULT):
    if policy_set not in POLICY_SET_CHOICES:
        raise ValueError(
            "Policy set '{}' is not supported. Allowed: {}".format(
                policy_set,
                ", ".join(POLICY_SET_CHOICES),
            )
        )
    policies = [
        ReflectionEagerWriteLite,
        ConsolidationQueueLite,
        NaiveEagerWriteLite,
        NoMemoryLite,
    ]
    if family in {
        SCOPE_CONTAMINATION,
        PREFERENCE_DRIFT,
        USEFUL_PENDING_MEMORY,
        FALSE_CORROBORATION,
        MEMORY_POISONING,
    }:
        policies.append(ScopeBlindTranscriptRAGLite)
    if policy_set == POLICY_SET_PHASE_2_5:
        policies.append(Mem0Lite)
    return policies


def build_run_artifact(
    scenario_count: int,
    template_mix: str = "mixed",
    family: str = FORCED_CONTRADICTION,
    policy_set: str = POLICY_SET_DEFAULT,
) -> dict:
    scenarios = _generate_scenarios(family, scenario_count, template_mix)
    policies = _policies_for_family(family, policy_set=policy_set)
    policy_runs = []
    for policy_cls in policies:
        run_records = [execute_scenario(policy_cls, scenario) for scenario in scenarios]
        summary = summarize_runs(run_records)
        failure_examples = sorted(
            [
                example
                for record in run_records
                for example in record.get("failure_examples", [])
            ],
            key=failure_example_sort_key,
        )
        policy_runs.append(
            {
                "policy_name": policy_cls.policy_name,
                "summary": jsonable(summary),
                "summary_by_template_kind": _summaries_by_field(run_records, "template_kind"),
                "summary_by_template_split": _summaries_by_field(run_records, "template_split"),
                "summary_by_template_id": _summaries_by_field(run_records, "template_id"),
                "failure_examples": failure_examples,
                "scenarios": [
                    {
                        "scenario_id": record["scenario_id"],
                        "transcript": render_scenario_transcript(scenarios[index]),
                        "scenario": record["scenario"],
                        "question_traces": record["question_traces"],
                        "store_snapshot": record["store_snapshot"],
                        "metrics": record["metrics"],
                        "failure_examples": record["failure_examples"],
                    }
                    for index, record in enumerate(run_records)
                ],
            }
        )
    return {
        "experiment": "{}_oracle".format(family),
        "family": family,
        "scenario_count": scenario_count,
        "template_mix": template_mix,
        "policy_set": policy_set,
        "baseline_notes": {
            Mem0Lite.policy_name: MEM0_LITE_PARTIAL_BASELINE_CAVEAT,
        }
        if policy_set == POLICY_SET_PHASE_2_5
        else {},
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
                "answer_correctness",
                "false_assertion_rate",
                "leakage_rate",
                "premature_promotion_rate",
                "poison_promotion_rate",
                "clean_durable_displacement_rate",
                "useful_recall",
                "used_pending",
                "durable_commit",
                "useful_recall_before_contradiction",
                "used_pending_before_contradiction",
                "durable_commit_before_contradiction",
                "false_assertion_after_contradiction",
                "contradiction_recovery_rate",
                "answer_correctness_after_contradiction",
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
    parser = argparse.ArgumentParser(description="Run oracle memory-governance experiments.")
    parser.add_argument(
        "--family",
        choices=[
            FORCED_CONTRADICTION,
            SCOPE_CONTAMINATION,
            PREFERENCE_DRIFT,
            USEFUL_PENDING_MEMORY,
            FALSE_CORROBORATION,
            MEMORY_POISONING,
        ],
        default=FORCED_CONTRADICTION,
        help="Oracle benchmark family to run.",
    )
    parser.add_argument("--scenarios", type=int, default=25, help="Number of oracle scenarios to generate.")
    parser.add_argument(
        "--template-mix",
        choices=["mixed", "clean", "dirty", "heldout"],
        default="mixed",
        help="Scenario template mix for the selected family.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path to the run artifact JSON.",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Path to the summary metrics CSV.",
    )
    parser.add_argument(
        "--policy-set",
        choices=POLICY_SET_CHOICES,
        default=POLICY_SET_DEFAULT,
        help="Policy set to run. Use phase2_5 to include Mem0Lite.",
    )
    args = parser.parse_args(argv)
    try:
        _validate_template_mix(args.family, args.template_mix)
    except ValueError as error:
        parser.error(str(error))

    output_json = args.output_json or "data/runs/{}_oracle.json".format(args.family)
    output_csv = args.output_csv or "data/results/{}_oracle_metrics.csv".format(args.family)
    run_artifact = build_run_artifact(
        args.scenarios,
        template_mix=args.template_mix,
        family=args.family,
        policy_set=args.policy_set,
    )
    write_outputs(run_artifact, Path(output_json), Path(output_csv))

    for policy in run_artifact["policies"]:
        summary = policy["summary"]
        print(_format_overall_summary(summary))
        for template_kind, kind_summary in policy.get("summary_by_template_kind", {}).items():
            print(_format_scoped_summary("kind", template_kind, kind_summary))
        for template_split, split_summary in policy.get("summary_by_template_split", {}).items():
            print(_format_scoped_summary("split", template_split, split_summary))
        for template_id, template_summary in policy.get("summary_by_template_id", {}).items():
            print(_format_scoped_summary("template", template_id, template_summary))
    print("Template mix: {}".format(args.template_mix))
    print("Policy set: {}".format(args.policy_set))
    print("Wrote {}".format(output_json))
    print("Wrote {}".format(output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
