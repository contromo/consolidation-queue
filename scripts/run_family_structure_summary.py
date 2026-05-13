#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cq.eval.runner import EVIDENCE_CONFLICT_SPECTRUM, generate_scenarios


def _candidate_events(scenario) -> list:
    return [event for event in scenario.sorted_events() if event.candidate is not None]


def _top_strength_rank_and_side(scenario) -> tuple[int, str]:
    candidates = [event.candidate for event in _candidate_events(scenario)]
    top_candidate = max(candidates, key=lambda candidate: candidate.strength)
    top_rank = [candidate.candidate_id for candidate in candidates].index(top_candidate.candidate_id) + 1
    if "-correct" in top_candidate.candidate_id:
        side = "correct"
    elif "-strong" in top_candidate.candidate_id:
        side = "strong"
    elif "-weak" in top_candidate.candidate_id or "-polluted" in top_candidate.candidate_id:
        side = "weak"
    else:
        side = "unknown"
    return top_rank, side


def build_structure_summary(family: str, scenarios: int, template_mix: str) -> Dict[str, object]:
    generated = generate_scenarios(family, scenarios, template_mix)
    by_mechanism = defaultdict(list)
    for scenario in generated:
        by_mechanism[scenario.expected_lifecycle.get("mechanism", scenario.template_id)].append(scenario)

    mechanism_rows = {}
    for mechanism, mechanism_scenarios in sorted(by_mechanism.items()):
        gold_counts = Counter()
        conflict_counts = Counter()
        source_counts = Counter()
        strength_values = Counter()
        top_rank_values = Counter()
        top_side_values = Counter()
        abstention_ok_count = 0
        commit_required_count = 0
        for scenario in mechanism_scenarios:
            lifecycle = scenario.expected_lifecycle
            abstention_ok_count += 1 if lifecycle.get("abstention_ok") else 0
            commit_required_count += 1 if lifecycle.get("commit_required") else 0
            gold_counts[len(lifecycle.get("gold_candidate_ids", []))] += 1
            conflict_counts[len(lifecycle.get("conflict_candidate_ids", []))] += 1
            candidates = [event.candidate for event in _candidate_events(scenario)]
            source_ids = {
                provenance.source_id
                for candidate in candidates
                for provenance in candidate.provenance
            }
            source_counts[len(source_ids)] += 1
            for candidate in candidates:
                strength_values["{:.2f}".format(candidate.strength)] += 1
            top_rank, top_side = _top_strength_rank_and_side(scenario)
            top_rank_values[top_rank] += 1
            top_side_values[top_side] += 1
        gray_zone_count = len(mechanism_scenarios) - abstention_ok_count - commit_required_count
        mechanism_rows[mechanism] = {
            "scenario_count": len(mechanism_scenarios),
            "abstention_ok_rate": abstention_ok_count / len(mechanism_scenarios),
            "commit_required_rate": commit_required_count / len(mechanism_scenarios),
            "gray_zone_rate": gray_zone_count / len(mechanism_scenarios),
            "gold_candidate_count_distribution": dict(sorted(gold_counts.items())),
            "conflict_candidate_count_distribution": dict(sorted(conflict_counts.items())),
            "distinct_source_count_distribution": dict(sorted(source_counts.items())),
            "candidate_strength_distribution": dict(sorted(strength_values.items())),
            "top_strength_rank_distribution": dict(sorted(top_rank_values.items())),
            "top_strength_side_distribution": dict(sorted(top_side_values.items())),
        }

    variance_checks = {}
    for mechanism in ("conflict_moderate", "conflict_witness", "conflict_polluted"):
        row = mechanism_rows.get(mechanism, {})
        conflict_distinct = len(row.get("conflict_candidate_count_distribution", {}))
        source_distinct = len(row.get("distinct_source_count_distribution", {}))
        top_rank_distinct = len(row.get("top_strength_rank_distribution", {}))
        top_side_distinct = len(row.get("top_strength_side_distribution", {}))
        variance_checks[mechanism] = {
            "conflict_or_gold_cardinality_distinct_values": conflict_distinct,
            "source_count_distinct_values": source_distinct,
            "top_strength_rank_or_side_distinct_values": max(top_rank_distinct, top_side_distinct),
            "passed": conflict_distinct >= 3 and source_distinct >= 3 and max(top_rank_distinct, top_side_distinct) >= 2,
        }

    return {
        "family": family,
        "template_mix": template_mix,
        "scenario_count": len(generated),
        "summary_by_mechanism": mechanism_rows,
        "variance_checks": variance_checks,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a structure-only summary for an oracle family.")
    parser.add_argument("--family", default=EVIDENCE_CONFLICT_SPECTRUM, choices=[EVIDENCE_CONFLICT_SPECTRUM])
    parser.add_argument("--scenarios", type=int, default=600)
    parser.add_argument("--template-mix", choices=["mixed", "heldout"], default="mixed")
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args(argv)

    artifact = build_structure_summary(args.family, args.scenarios, args.template_mix)
    output_json = args.output_json or Path(
        "data/results/{}/{}_structure_{}.json".format(args.family, args.family, args.template_mix)
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print("Wrote {}".format(output_json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
