import unittest

from cq.eval.end_to_end_eval import _contains_any, compute_forced_contradiction_metrics
from cq.schemas.memory import AnswerTrace
from cq.schemas.metrics import PolicyScenarioMetrics, PolicySummaryMetrics
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


class PolicySummaryMetricsTests(unittest.TestCase):
    def test_empty_summary_returns_zeroes(self) -> None:
        summary = PolicySummaryMetrics.from_scenarios("test-policy", [])

        self.assertEqual(summary.policy_name, "test-policy")
        self.assertEqual(summary.scenario_count, 0)
        self.assertEqual(summary.useful_recall_before_contradiction, 0.0)
        self.assertEqual(summary.used_pending_before_contradiction, 0.0)
        self.assertEqual(summary.durable_commit_before_contradiction, 0.0)
        self.assertEqual(summary.false_assertion_after_contradiction, 0.0)
        self.assertEqual(summary.contradiction_recovery_rate, 0.0)
        self.assertEqual(summary.answer_correctness_after_contradiction, 0.0)
        self.assertEqual(summary.average_time_to_demotion, 0.0)

    def test_average_time_to_demotion_ignores_missing_values(self) -> None:
        metrics = [
            PolicyScenarioMetrics(
                scenario_id="scenario-1",
                policy_name="test-policy",
                useful_recall_before_contradiction=1.0,
                used_pending_before_contradiction=0.0,
                durable_commit_before_contradiction=1.0,
                false_assertion_after_contradiction=0.0,
                contradiction_recovery_rate=1.0,
                answer_correctness_after_contradiction=1.0,
                time_to_demotion=None,
            ),
            PolicyScenarioMetrics(
                scenario_id="scenario-2",
                policy_name="test-policy",
                useful_recall_before_contradiction=1.0,
                used_pending_before_contradiction=0.0,
                durable_commit_before_contradiction=1.0,
                false_assertion_after_contradiction=0.0,
                contradiction_recovery_rate=1.0,
                answer_correctness_after_contradiction=1.0,
                time_to_demotion=2.5,
            ),
        ]

        summary = PolicySummaryMetrics.from_scenarios("test-policy", metrics)
        self.assertEqual(summary.average_time_to_demotion, 2.5)

    def test_empty_resolved_ids_do_not_match_gold_ids(self) -> None:
        self.assertFalse(_contains_any([], ["candidate-1"]))

    def test_correct_answer_without_invalidation_is_not_recovery(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, seed=9, template_mix="clean")[0]
        questions = {
            event.question.phase: event.question
            for event in scenario.sorted_events()
            if event.question is not None
        }
        before_question = questions["before_contradiction"]
        after_question = questions["after_contradiction"]
        old_candidate_id = scenario.expected_lifecycle["old_candidate_id"]
        new_candidate_id = scenario.expected_lifecycle["new_candidate_id"]

        metrics = compute_forced_contradiction_metrics(
            "test-policy",
            scenario,
            [
                AnswerTrace(
                    answer_id="answer-before",
                    question_id=before_question.question_id,
                    query=before_question.text,
                    relevant_canonical_id=before_question.relevant_canonical_id,
                    scope_level=before_question.scope_level,
                    scope_key=before_question.scope_key,
                    resolved_candidate_ids=[old_candidate_id],
                    used_memory_ids=[],
                    answer_text="before",
                    used_pending=False,
                    created_at=before_question.asked_at,
                ),
                AnswerTrace(
                    answer_id="answer-after",
                    question_id=after_question.question_id,
                    query=after_question.text,
                    relevant_canonical_id=after_question.relevant_canonical_id,
                    scope_level=after_question.scope_level,
                    scope_key=after_question.scope_key,
                    resolved_candidate_ids=[new_candidate_id],
                    used_memory_ids=[],
                    answer_text="after",
                    used_pending=False,
                    created_at=after_question.asked_at,
                ),
            ],
            {
                "candidate_memories": [],
                "durable_memories": [],
                "lifecycle_events": [],
            },
        )

        self.assertEqual(metrics.answer_correctness_after_contradiction, 1.0)
        self.assertEqual(metrics.contradiction_recovery_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
