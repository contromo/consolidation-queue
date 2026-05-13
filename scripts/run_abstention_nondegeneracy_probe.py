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

from cq.eval.abstention import abstention_decision_from_record
from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.runner import EVIDENCE_CONFLICT_SPECTRUM, generate_scenarios
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.mem0_lite import Mem0Lite


def build_probe_artifact(scenarios_per_mechanism: int, template_mix: str) -> Dict[str, object]:
    scenario_count = scenarios_per_mechanism * 5
    scenarios = generate_scenarios(EVIDENCE_CONFLICT_SPECTRUM, scenario_count, template_mix)
    policies = [ConsolidationQueueLite, Mem0Lite]
    decisions_by_policy = {}
    for policy_cls in policies:
        run_records = [execute_scenario(policy_cls, scenario) for scenario in scenarios]
        decisions_by_policy[policy_cls.policy_name] = [
            abstention_decision_from_record(policy_cls.policy_name, record, EVIDENCE_CONFLICT_SPECTRUM)
            for record in run_records
        ]

    cq_by_id = {decision.scenario_id: decision for decision in decisions_by_policy[ConsolidationQueueLite.policy_name]}
    mem0_by_id = {decision.scenario_id: decision for decision in decisions_by_policy[Mem0Lite.policy_name]}
    joint_by_mechanism = defaultdict(Counter)
    for scenario_id, cq_decision in cq_by_id.items():
        mem0_decision = mem0_by_id[scenario_id]
        joint_by_mechanism[cq_decision.mechanism][
            "{}__{}".format(cq_decision.action, mem0_decision.action)
        ] += 1

    mechanism_rows = {}
    for mechanism, counter in sorted(joint_by_mechanism.items()):
        disagreement_count = sum(
            count
            for key, count in counter.items()
            if key.split("__")[0] != key.split("__")[1]
        )
        mechanism_rows[mechanism] = {
            "joint_action_counts": dict(sorted(counter.items())),
            "disagreement_count": disagreement_count,
            "has_disagreement": disagreement_count > 0,
        }

    abstain_required_passed = all(
        mechanism_rows.get(mechanism, {}).get("has_disagreement", False)
        for mechanism in ("conflict_moderate", "conflict_witness")
    )
    return {
        "family": EVIDENCE_CONFLICT_SPECTRUM,
        "template_mix": template_mix,
        "scenarios_per_mechanism": scenarios_per_mechanism,
        "policies": [policy.policy_name for policy in policies],
        "summary_by_mechanism": mechanism_rows,
        "abstain_required_mechanisms_have_disagreement": abstain_required_passed,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the CQ-vs-Mem0 action non-degeneracy probe.")
    parser.add_argument("--scenarios-per-mechanism", type=int, default=20)
    parser.add_argument("--template-mix", choices=["mixed", "heldout"], default="mixed")
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args(argv)

    artifact = build_probe_artifact(args.scenarios_per_mechanism, args.template_mix)
    output_json = args.output_json or Path(
        "data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_nondegeneracy_{}.json".format(
            args.template_mix
        )
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print("Wrote {}".format(output_json))
    if not artifact["abstain_required_mechanisms_have_disagreement"]:
        print("Non-degeneracy probe failed: abstain-required mechanisms did not all disagree.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
