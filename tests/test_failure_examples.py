import json
import unittest

from cq.dashboard.app import render_dashboard
from cq.eval.end_to_end_eval import execute_scenario, failure_example_sort_key
from cq.eval.runner import build_run_artifact
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


def _policies_by_name(artifact):
    return {policy["policy_name"]: policy for policy in artifact["policies"]}


def _scenario_by_template(policy, template_id):
    for scenario in policy["scenarios"]:
        if scenario["scenario"]["template_id"] == template_id:
            return scenario
    raise AssertionError("Missing template {}".format(template_id))


def _failure_types(scenario):
    return {example["failure_type"] for example in scenario["failure_examples"]}


def _failure_by_type(scenario, failure_type):
    for example in scenario["failure_examples"]:
        if example["failure_type"] == failure_type:
            return example
    raise AssertionError("Missing failure type {}".format(failure_type))


class FailureExampleTest(unittest.TestCase):
    def test_scope_examples_include_successful_premature_promotion(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="scope_contamination")
        policies = _policies_by_name(artifact)

        reflection_dirty = _scenario_by_template(
            policies["reflection_eager_write_lite"],
            "scope_contamination_dirty_broad_claim_v1",
        )
        naive_dirty = _scenario_by_template(
            policies["naive_eager_write_lite"],
            "scope_contamination_dirty_broad_claim_v1",
        )
        rag_clean = _scenario_by_template(
            policies["scope_blind_transcript_rag_lite"],
            "scope_contamination_clean_v1",
        )

        self.assertEqual(_failure_types(reflection_dirty), {"scope_leakage", "premature_promotion"})
        self.assertEqual(_failure_types(naive_dirty), {"premature_promotion"})
        self.assertEqual(naive_dirty["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(naive_dirty["metrics"]["premature_promotion_rate"], 1.0)
        self.assertEqual(_failure_types(rag_clean), {"scope_leakage"})

        premature = _failure_by_type(naive_dirty, "premature_promotion")
        self.assertEqual(premature["question_phase"], "off_scope_probe")
        self.assertEqual(premature["reason"], "should_not_promote_scope_candidate_promoted")
        self.assertTrue(premature["durable_claims"])
        self.assertNotIn("false_assertion", _failure_types(reflection_dirty))

    def test_preference_examples_pin_eager_failures_and_cq_success(self) -> None:
        artifact = build_run_artifact(2, template_mix="heldout", family="preference_drift")
        policies = _policies_by_name(artifact)

        reflection_dirty = _scenario_by_template(
            policies["reflection_eager_write_lite"],
            "preference_drift_dirty_drift_back_v2",
        )
        naive_dirty = _scenario_by_template(
            policies["naive_eager_write_lite"],
            "preference_drift_dirty_drift_back_v2",
        )
        cq_dirty = _scenario_by_template(
            policies["consolidation_queue_lite"],
            "preference_drift_dirty_drift_back_v2",
        )

        self.assertEqual(_failure_types(reflection_dirty), {"false_assertion", "premature_promotion"})
        self.assertEqual(_failure_types(naive_dirty), {"false_assertion", "premature_promotion"})
        self.assertEqual(cq_dirty["failure_examples"], [])

        false_assertion = _failure_by_type(reflection_dirty, "false_assertion")
        self.assertEqual(false_assertion["question_phase"], "after_drift")
        self.assertEqual(false_assertion["reason"], "forbidden_preference_candidate_asserted")
        self.assertTrue(false_assertion["candidate_claims"])

    def test_no_memory_incorrect_answer_is_diagnostic_probe_only(self) -> None:
        artifact = build_run_artifact(1, template_mix="mixed", family="forced_contradiction")
        policies = _policies_by_name(artifact)
        no_memory_scenario = policies["no_memory_lite"]["scenarios"][0]

        self.assertEqual(len(no_memory_scenario["failure_examples"]), 1)
        example = no_memory_scenario["failure_examples"][0]
        self.assertEqual(example["failure_type"], "incorrect_answer")
        self.assertEqual(example["failure_subtype"], "no_memory_floor")
        self.assertEqual(example["question_phase"], "after_contradiction")
        self.assertEqual(example["reason"], "gold_candidate_not_resolved")

    def test_policy_failure_index_matches_scenario_examples_and_is_sorted(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="scope_contamination")
        for policy in artifact["policies"]:
            scenario_examples = [
                example
                for scenario in policy["scenarios"]
                for example in scenario["failure_examples"]
            ]
            expected = sorted(
                scenario_examples,
                key=failure_example_sort_key,
            )
            self.assertEqual(policy["failure_examples"], expected)

    def test_forced_contradiction_premature_promotion_has_explicit_reason(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1)[0]
        should_not_promote_id = scenario.expected_lifecycle["old_candidate_id"]
        scenario.expected_lifecycle["should_not_promote_candidate_ids"] = [should_not_promote_id]

        result = execute_scenario(ReflectionEagerWriteLite, scenario)

        premature = _failure_by_type(result, "premature_promotion")
        self.assertEqual(
            premature["reason"],
            "should_not_promote_contradiction_candidate_promoted",
        )

    def test_failure_examples_match_metrics_across_mixed_runs(self) -> None:
        artifacts = [
            build_run_artifact(3, template_mix="mixed", family="forced_contradiction"),
            build_run_artifact(2, template_mix="mixed", family="scope_contamination"),
            build_run_artifact(3, template_mix="mixed", family="preference_drift"),
            build_run_artifact(2, template_mix="mixed", family="useful_pending_memory"),
            build_run_artifact(2, template_mix="mixed", family="false_corroboration"),
            build_run_artifact(3, template_mix="mixed", family="memory_poisoning"),
        ]
        for artifact in artifacts:
            for policy in artifact["policies"]:
                for scenario in policy["scenarios"]:
                    failure_types = _failure_types(scenario)
                    metrics = scenario["metrics"]
                    if artifact["family"] == "scope_contamination":
                        self.assertEqual("scope_leakage" in failure_types, metrics["leakage_rate"] == 1.0)
                        self.assertNotIn("false_assertion", failure_types)
                    else:
                        self.assertEqual("false_assertion" in failure_types, metrics["false_assertion_rate"] == 1.0)
                    self.assertEqual(
                        "premature_promotion" in failure_types,
                        metrics["premature_promotion_rate"] > 0.0,
                    )

    def test_run_artifact_json_is_byte_stable(self) -> None:
        first = json.dumps(
            build_run_artifact(4, template_mix="heldout", family="scope_contamination"),
            indent=2,
        )
        second = json.dumps(
            build_run_artifact(4, template_mix="heldout", family="scope_contamination"),
            indent=2,
        )

        self.assertEqual(first, second)

    def test_dashboard_renders_failure_examples_and_scenario_anchors(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="scope_contamination")
        html = render_dashboard(artifact)

        self.assertIn("Failure Examples", html)
        self.assertIn("href='#scenario-reflection_eager_write_lite-scope_contamination_002'", html)
        self.assertIn("off_scope_probe", html)
        self.assertIn("should_not_promote_scope_candidate_promoted", html)
        self.assertIn("failure-floor", html)


if __name__ == "__main__":
    unittest.main()
