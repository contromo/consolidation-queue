import json
import unittest

from cq.eval.end_to_end_eval import execute_scenario
from cq.memory.consolidation_queue import (
    CQNoContestationDemotion,
    CQNoPendingLookupUse,
    CQNoSourceIndependenceGate,
    CQNoWiderScopePendingOverride,
    ConsolidationQueueLite,
)
from cq.simulator.scenario_generator import (
    generate_false_corroboration_scenarios,
    generate_memory_poisoning_scenarios,
    generate_scope_contamination_scenarios,
    generate_useful_pending_memory_scenarios,
)
from cq.simulator.adversarial_upstream_noise import generate_adversarial_upstream_noise_scenarios


def _scenario_by_template(scenarios, template_id):
    return [scenario for scenario in scenarios if scenario.template_id == template_id][0]


def _trace_json(result):
    return json.dumps(result["question_traces"], sort_keys=True)


def _lifecycle_json(result):
    return json.dumps(result["store_snapshot"]["lifecycle_events"], sort_keys=True)


class CQAblationTests(unittest.TestCase):
    def test_no_contestation_demotion_keeps_clean_durable_on_override_attack(self) -> None:
        scenario = _scenario_by_template(
            generate_memory_poisoning_scenarios(5, seed=41, template_mix="mixed"),
            "memory_poisoning_dirty_override_shadow_v1",
        )

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoContestationDemotion, scenario)

        self.assertEqual(full_result["metrics"]["clean_durable_displacement_rate"], 1.0)
        self.assertEqual(full_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(ablated_result["metrics"]["clean_durable_displacement_rate"], 0.0)
        self.assertEqual(ablated_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(ablated_result["metrics"]["answer_correctness"], 1.0)

    def test_no_wider_scope_pending_override_leaks_workspace_parent_durable(self) -> None:
        scenario = _scenario_by_template(
            generate_scope_contamination_scenarios(4, seed=17, template_mix="mixed"),
            "scope_contamination_dirty_workspace_parent_v1",
        )

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoWiderScopePendingOverride, scenario)

        self.assertEqual(full_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(full_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(ablated_result["metrics"]["leakage_rate"], 1.0)
        self.assertEqual(ablated_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(ablated_result["metrics"]["used_pending"], 0.0)

    def test_no_pending_lookup_use_disables_no_durable_pending_fallback_only(self) -> None:
        scenario = generate_useful_pending_memory_scenarios(1, seed=31, template_mix="clean")[0]

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoPendingLookupUse, scenario)

        self.assertEqual(full_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(full_result["metrics"]["used_pending"], 1.0)
        self.assertEqual(ablated_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(ablated_result["metrics"]["used_pending"], 0.0)
        self.assertEqual(ablated_result["metrics"]["premature_promotion_rate"], 0.0)

    def test_no_source_independence_gate_promotes_mirrored_raw_support_stack(self) -> None:
        scenario = _scenario_by_template(
            generate_false_corroboration_scenarios(2, seed=37, template_mix="mixed"),
            "false_corroboration_dirty_mirrored_sources_v1",
        )

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoSourceIndependenceGate, scenario)

        self.assertEqual(full_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(full_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(ablated_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(ablated_result["metrics"]["premature_promotion_rate"], 0.2)
        self.assertEqual(ablated_result["metrics"]["durable_commit"], 1.0)

    def test_neutral_scenario_containment_for_all_cq_ablations(self) -> None:
        scenario = _scenario_by_template(
            generate_memory_poisoning_scenarios(1, seed=41, template_mix="clean"),
            "memory_poisoning_clean_trusted_v1",
        )
        full_result = execute_scenario(ConsolidationQueueLite, scenario)

        for policy_cls in (
            CQNoContestationDemotion,
            CQNoWiderScopePendingOverride,
            CQNoPendingLookupUse,
            CQNoSourceIndependenceGate,
        ):
            with self.subTest(policy=policy_cls.policy_name):
                ablated_result = execute_scenario(policy_cls, scenario)
                self.assertEqual(_trace_json(ablated_result), _trace_json(full_result))
                self.assertEqual(_lifecycle_json(ablated_result), _lifecycle_json(full_result))

    def test_adversarial_retraction_regression_for_no_contestation_demotion(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_retraction_v1",
        )

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoContestationDemotion, scenario)

        self.assertEqual(full_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(ablated_result["metrics"]["answer_correctness"], 0.0)

    def test_adversarial_scope_narrowing_regression_for_no_wider_scope_override(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_scope_narrowing_v1",
        )

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoWiderScopePendingOverride, scenario)

        self.assertEqual(full_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(ablated_result["metrics"]["answer_correctness"], 0.0)

    def test_adversarial_pending_competition_regression_for_no_pending_lookup_use(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_pending_competition_v1",
        )

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoPendingLookupUse, scenario)

        self.assertEqual(full_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(ablated_result["metrics"]["answer_correctness"], 0.0)

    def test_adversarial_witness_conflict_regression_for_no_source_independence_gate(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_witness_conflict_v1",
        )

        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoSourceIndependenceGate, scenario)

        self.assertEqual(full_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(ablated_result["metrics"]["answer_correctness"], 0.0)

    def test_adversarial_candidate_stream_is_identical_across_policies(self) -> None:
        scenario = generate_adversarial_upstream_noise_scenarios(1, template_mix="mixed")[0]
        full_result = execute_scenario(ConsolidationQueueLite, scenario)
        ablated_result = execute_scenario(CQNoPendingLookupUse, scenario)

        full_candidates = json.dumps(full_result["store_snapshot"]["candidate_memories"], sort_keys=True)
        ablated_candidates = json.dumps(ablated_result["store_snapshot"]["candidate_memories"], sort_keys=True)

        self.assertEqual(full_candidates, ablated_candidates)


if __name__ == "__main__":
    unittest.main()
