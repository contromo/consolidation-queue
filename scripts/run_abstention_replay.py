#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cq.eval.abstention import abstention_artifact_for_run


DEFAULT_INPUTS = [
    Path("data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed.json"),
    Path("data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout.json"),
    Path("data/runs/mechanism_diverse_heldout_oracle_frozen_phase2_5.json"),
]
REPLAY_CSV_FIELDNAMES = [
    "policy_name",
    "summary_scope",
    "mechanism",
    "scenario_count",
    "abstention_ok_count",
    "commit_required_count",
    "gray_zone_count",
    "abstain_count",
    "useful_abstention_count",
    "harmful_abstention_count",
    "useful_abstention_rate",
    "harmful_abstention_rate",
    "abstain_rate",
    "comparison_name",
    "comparison_metric_name",
    "comparison_mechanism",
    "comparison_reference_policy_name",
    "comparison_comparator_policy_name",
    "comparison_point_estimate_delta",
    "comparison_one_sided_95_lcb",
    "comparison_one_sided_95_ucb",
]


def _write_csv(artifact: Dict[str, object], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=REPLAY_CSV_FIELDNAMES,
        )
        writer.writeheader()
        for policy in artifact.get("policies", []):
            summary = dict(policy["summary"])
            summary.update(
                {
                    "policy_name": policy["policy_name"],
                    "summary_scope": "overall",
                    "mechanism": "",
                }
            )
            writer.writerow(summary)
            for mechanism, mechanism_summary in policy.get("summary_by_mechanism", {}).items():
                row = dict(mechanism_summary)
                row.update(
                    {
                        "policy_name": policy["policy_name"],
                        "summary_scope": "mechanism",
                        "mechanism": mechanism,
                    }
                )
                writer.writerow(row)
        for comparison_name, comparison in artifact.get("pairwise_abstention_comparisons", {}).items():
            for row_kind, rows in [
                ("useful", comparison.get("useful_abstention_rows", {})),
                ("harmful", comparison.get("harmful_abstention_rows", {})),
            ]:
                for mechanism, comparison_row in rows.items():
                    writer.writerow(
                        {
                            "summary_scope": "pairwise_comparison",
                            "comparison_name": comparison_name,
                            "comparison_metric_name": comparison_row["metric_name"],
                            "comparison_mechanism": "{}:{}".format(row_kind, mechanism),
                            "comparison_reference_policy_name": comparison["reference_policy_name"],
                            "comparison_comparator_policy_name": comparison["comparator_policy_name"],
                            "comparison_point_estimate_delta": comparison_row["point_estimate_delta"],
                            "comparison_one_sided_95_lcb": comparison_row["one_sided_95_lcb"],
                            "comparison_one_sided_95_ucb": comparison_row.get("one_sided_95_ucb", ""),
                        }
                    )
        for comparison_name, comparison in artifact.get("primary_comparisons", {}).items():
            for mechanism, useful in comparison.get("useful_mechanism_rows", {}).items():
                writer.writerow(
                    {
                        "summary_scope": "comparison",
                        "comparison_name": comparison_name,
                        "comparison_metric_name": useful["metric_name"],
                        "comparison_mechanism": mechanism,
                        "comparison_reference_policy_name": comparison["reference_policy_name"],
                        "comparison_comparator_policy_name": comparison["comparator_policy_name"],
                        "comparison_point_estimate_delta": useful["point_estimate_delta"],
                        "comparison_one_sided_95_lcb": useful["one_sided_95_lcb"],
                        "comparison_one_sided_95_ucb": useful.get("one_sided_95_ucb", ""),
                    }
                )
            harmful = comparison.get("harmful_bucket_row")
            if harmful:
                writer.writerow(
                    {
                        "summary_scope": "comparison",
                        "comparison_name": comparison_name,
                        "comparison_metric_name": harmful["metric_name"],
                        "comparison_mechanism": "+".join(harmful["mechanisms"]),
                        "comparison_reference_policy_name": comparison["reference_policy_name"],
                        "comparison_comparator_policy_name": comparison["comparator_policy_name"],
                        "comparison_point_estimate_delta": harmful["point_estimate_delta"],
                        "comparison_one_sided_95_lcb": harmful["one_sided_95_lcb"],
                        "comparison_one_sided_95_ucb": harmful["one_sided_95_ucb"],
                    }
                )


def _input_summary(path: Path) -> Dict[str, object]:
    run_artifact = json.loads(path.read_text(encoding="utf-8"))
    first_policy = run_artifact["policies"][0]
    first_scenario = first_policy["scenarios"][0]
    first_trace = first_scenario["question_traces"][0]
    return {
        "path": str(path),
        "family": run_artifact.get("family"),
        "policy_count": len(run_artifact.get("policies", [])),
        "scenario_count": run_artifact.get("scenario_count"),
        "has_expected_lifecycle": isinstance(first_scenario["scenario"].get("expected_lifecycle"), dict),
        "has_resolved_candidate_ids": "resolved_candidate_ids" in first_trace,
        "has_store_snapshot": isinstance(first_scenario.get("store_snapshot"), dict),
    }


def run_replay(inputs: List[Path], output_dir: Path) -> List[Path]:
    written = []
    for input_path in inputs:
        run_artifact = json.loads(input_path.read_text(encoding="utf-8"))
        artifact = abstention_artifact_for_run(run_artifact)
        output_json = output_dir / "{}_abstention.json".format(input_path.stem)
        output_csv = output_dir / "{}_abstention.csv".format(input_path.stem)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        _write_csv(artifact, output_csv)
        written.extend([output_json, output_csv])
    return written


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay abstention metrics from saved oracle run JSON artifacts.")
    parser.add_argument("--inputs", nargs="*", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/results/abstention"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        print("Abstention predicate: not asserted_ids and not resolved_candidate_ids")
        print("Useful denominator: abstention_ok=True")
        print("Harmful denominator: commit_required=True")
        for input_path in args.inputs:
            print(json.dumps(_input_summary(input_path), sort_keys=True))
        return 0

    written = run_replay(args.inputs, args.output_dir)
    for path in written:
        print("Wrote {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
