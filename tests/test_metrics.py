from datetime import datetime
import unittest
from typing import get_type_hints

from cq.eval.end_to_end_eval import (
    _asserted_candidate_ids,
    _contains_any,
    compute_forced_contradiction_metrics,
    compute_false_corroboration_metrics,
    compute_memory_poisoning_metrics,
    compute_preference_drift_metrics,
    compute_scope_contamination_metrics,
    compute_useful_pending_memory_metrics,
)
from cq.schemas.memory import AnswerTrace
from cq.schemas.metrics import PolicyScenarioMetrics, PolicySummaryMetrics
from cq.simulator.scenario_generator import (
    generate_forced_contradiction_scenarios,
    generate_false_corroboration_scenarios,
    generate_memory_poisoning_scenarios,
    generate_preference_drift_scenarios,
    generate_scope_contamination_scenarios,
    generate_useful_pending_memory_scenarios,
)


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

    def test_generic_metric_zero_is_not_overwritten_by_legacy_alias(self) -> None:
        metric = PolicyScenarioMetrics(
            scenario_id="scenario-1",
            policy_name="test-policy",
            useful_recall_before_contradiction=1.0,
            used_pending_before_contradiction=1.0,
            durable_commit_before_contradiction=1.0,
            false_assertion_after_contradiction=1.0,
            contradiction_recovery_rate=1.0,
            answer_correctness_after_contradiction=1.0,
            time_to_demotion=None,
            answer_correctness=0.0,
            false_assertion_rate=0.0,
            useful_recall=0.0,
            used_pending=0.0,
            durable_commit=0.0,
        )

        self.assertEqual(metric.answer_correctness, 0.0)
        self.assertEqual(metric.false_assertion_rate, 0.0)
        self.assertEqual(metric.useful_recall, 0.0)
        self.assertEqual(metric.used_pending, 0.0)
        self.assertEqual(metric.durable_commit, 0.0)

    def test_generic_metric_read_annotations_are_not_optional(self) -> None:
        hints = get_type_hints(PolicyScenarioMetrics)

        self.assertIs(hints["answer_correctness"], float)
        self.assertIs(hints["false_assertion_rate"], float)
        self.assertIs(hints["poison_promotion_rate"], float)
        self.assertIs(hints["useful_recall"], float)
        self.assertIs(hints["used_pending"], float)
        self.assertIs(hints["durable_commit"], float)

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

    def test_forced_contradiction_generic_aliases_match_legacy_fields(self) -> None:
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
                    used_pending=True,
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
                "candidate_memories": [
                    {
                        "candidate_id": old_candidate_id,
                        "state": "contested",
                    }
                ],
                "durable_memories": [],
                "lifecycle_events": [],
            },
        )

        self.assertEqual(metrics.answer_correctness, metrics.answer_correctness_after_contradiction)
        self.assertEqual(metrics.false_assertion_rate, metrics.false_assertion_after_contradiction)
        self.assertEqual(metrics.useful_recall, metrics.useful_recall_before_contradiction)
        self.assertEqual(metrics.used_pending, metrics.used_pending_before_contradiction)

    def test_scope_metrics_use_forbidden_gold_and_should_not_promote_sets(self) -> None:
        scenario = generate_scope_contamination_scenarios(1, seed=17, template_mix="dirty")[0]
        probe_question = [event.question for event in scenario.sorted_events() if event.question is not None][0]
        contaminant_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]

        metrics = compute_scope_contamination_metrics(
            "test-policy",
            scenario,
            [
                AnswerTrace(
                    answer_id="answer-probe",
                    question_id=probe_question.question_id,
                    query=probe_question.text,
                    relevant_canonical_id=probe_question.relevant_canonical_id,
                    scope_level=probe_question.scope_level,
                    scope_key=probe_question.scope_key,
                    resolved_candidate_ids=[contaminant_id],
                    used_memory_ids=[],
                    answer_text="leak",
                    used_pending=False,
                    created_at=probe_question.asked_at,
                )
            ],
            {
                "candidate_memories": [],
                "durable_memories": [
                    {
                        "created_from_candidate_ids": [contaminant_id],
                    }
                ],
                "lifecycle_events": [
                    {
                        "timestamp": datetime(2026, 1, 1, 9, 0, 0).isoformat(),
                        "object_type": "durable_memory",
                        "event_type": "memory_promoted",
                        "details": {"created_from_candidate_ids": [contaminant_id]},
                    }
                ],
            },
        )

        self.assertEqual(metrics.leakage_rate, 1.0)
        self.assertEqual(metrics.answer_correctness, 0.0)
        self.assertEqual(metrics.premature_promotion_rate, 1.0)

    def test_useful_pending_metrics_use_pending_probe_sets(self) -> None:
        scenario = generate_useful_pending_memory_scenarios(2, seed=31, template_mix="mixed")[1]
        probe_question = [event.question for event in scenario.sorted_events() if event.question is not None][0]
        tentative_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]

        metrics = compute_useful_pending_memory_metrics(
            "test-policy",
            scenario,
            [
                AnswerTrace(
                    answer_id="answer-probe",
                    question_id=probe_question.question_id,
                    query=probe_question.text,
                    relevant_canonical_id=probe_question.relevant_canonical_id,
                    scope_level=probe_question.scope_level,
                    scope_key=probe_question.scope_key,
                    resolved_candidate_ids=[tentative_id],
                    used_memory_ids=["memory-" + tentative_id],
                    answer_text="premature durable answer",
                    used_pending=False,
                    created_at=probe_question.asked_at,
                )
            ],
            {
                "candidate_memories": [],
                "durable_memories": [
                    {
                        "memory_id": "memory-" + tentative_id,
                        "created_from_candidate_ids": [tentative_id],
                    }
                ],
                "lifecycle_events": [],
            },
        )

        self.assertEqual(metrics.answer_correctness, 0.0)
        self.assertEqual(metrics.useful_recall, 0.0)
        self.assertEqual(metrics.false_assertion_rate, 1.0)
        self.assertEqual(metrics.premature_promotion_rate, 1.0)
        self.assertEqual(metrics.used_pending, 0.0)
        self.assertEqual(metrics.durable_commit, 1.0)

    def test_useful_pending_metrics_requires_pending_probe_question(self) -> None:
        scenario = generate_useful_pending_memory_scenarios(1, seed=31, template_mix="clean")[0]
        probe_question = [event.question for event in scenario.sorted_events() if event.question is not None][0]
        probe_question.phase = "renamed_probe"

        with self.assertRaisesRegex(ValueError, "missing pending_probe question"):
            compute_useful_pending_memory_metrics(
                "test-policy",
                scenario,
                [],
                {"candidate_memories": [], "durable_memories": [], "lifecycle_events": []},
            )

    def test_useful_pending_metrics_requires_pending_probe_trace(self) -> None:
        scenario = generate_useful_pending_memory_scenarios(1, seed=31, template_mix="clean")[0]

        with self.assertRaisesRegex(ValueError, "missing trace for pending_probe question"):
            compute_useful_pending_memory_metrics(
                "test-policy",
                scenario,
                [],
                {"candidate_memories": [], "durable_memories": [], "lifecycle_events": []},
            )

    def test_false_corroboration_metrics_still_use_single_probe_sets(self) -> None:
        scenario = generate_false_corroboration_scenarios(2, seed=37, template_mix="mixed")[1]
        probe_question = [event.question for event in scenario.sorted_events() if event.question is not None][0]
        poison_like_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]

        metrics = compute_false_corroboration_metrics(
            "test-policy",
            scenario,
            [
                AnswerTrace(
                    answer_id="answer-probe",
                    question_id=probe_question.question_id,
                    query=probe_question.text,
                    relevant_canonical_id=probe_question.relevant_canonical_id,
                    scope_level=probe_question.scope_level,
                    scope_key=probe_question.scope_key,
                    resolved_candidate_ids=[poison_like_id],
                    used_memory_ids=[],
                    answer_text="false corroboration answer",
                    used_pending=True,
                    created_at=probe_question.asked_at,
                )
            ],
            {"candidate_memories": [], "durable_memories": [], "lifecycle_events": []},
        )

        self.assertEqual(metrics.answer_correctness, 0.0)
        self.assertEqual(metrics.false_assertion_rate, 1.0)
        self.assertEqual(metrics.used_pending, 1.0)
        self.assertEqual(metrics.durable_commit, 0.0)

    def test_memory_poisoning_metrics_use_poison_probe_sets(self) -> None:
        scenario = generate_memory_poisoning_scenarios(3, seed=41, template_mix="mixed")[2]
        probe_question = [event.question for event in scenario.sorted_events() if event.question is not None][0]
        poison_id = scenario.expected_lifecycle["poison_candidate_ids"][0]

        metrics = compute_memory_poisoning_metrics(
            "test-policy",
            scenario,
            [
                AnswerTrace(
                    answer_id="answer-probe",
                    question_id=probe_question.question_id,
                    query=probe_question.text,
                    relevant_canonical_id=probe_question.relevant_canonical_id,
                    scope_level=probe_question.scope_level,
                    scope_key=probe_question.scope_key,
                    resolved_candidate_ids=[poison_id],
                    used_memory_ids=["memory-" + poison_id],
                    answer_text="poison durable answer",
                    used_pending=False,
                    created_at=probe_question.asked_at,
                )
            ],
            {
                "candidate_memories": [],
                "durable_memories": [
                    {
                        "memory_id": "memory-" + poison_id,
                        "created_from_candidate_ids": [poison_id],
                    }
                ],
                "lifecycle_events": [],
            },
        )

        self.assertEqual(metrics.answer_correctness, 0.0)
        self.assertEqual(metrics.false_assertion_rate, 1.0)
        self.assertEqual(metrics.premature_promotion_rate, 1.0)
        self.assertEqual(metrics.poison_promotion_rate, 1.0)
        self.assertEqual(metrics.used_pending, 0.0)
        self.assertEqual(metrics.durable_commit, 1.0)

    def test_memory_poisoning_metrics_requires_poison_probe_question(self) -> None:
        scenario = generate_memory_poisoning_scenarios(1, seed=41, template_mix="clean")[0]
        probe_question = [event.question for event in scenario.sorted_events() if event.question is not None][0]
        probe_question.phase = "renamed_probe"

        with self.assertRaisesRegex(ValueError, "missing poison_probe question"):
            compute_memory_poisoning_metrics(
                "test-policy",
                scenario,
                [],
                {"candidate_memories": [], "durable_memories": [], "lifecycle_events": []},
            )

    def test_memory_poisoning_metrics_requires_poison_probe_trace(self) -> None:
        scenario = generate_memory_poisoning_scenarios(1, seed=41, template_mix="clean")[0]

        with self.assertRaisesRegex(ValueError, "missing trace for poison_probe question"):
            compute_memory_poisoning_metrics(
                "test-policy",
                scenario,
                [],
                {"candidate_memories": [], "durable_memories": [], "lifecycle_events": []},
            )

    def test_asserted_candidate_ids_use_primary_durable_source(self) -> None:
        trace = AnswerTrace(
            answer_id="answer-1",
            question_id="question-1",
            query="query",
            relevant_canonical_id="canonical",
            scope_level=generate_preference_drift_scenarios(1)[0].oracle_events[0].candidate.scope_level,
            scope_key="user",
            resolved_candidate_ids=["old-candidate", "reinforcer-candidate"],
            used_memory_ids=["memory-old-candidate"],
            answer_text="answer",
            used_pending=False,
            created_at=datetime(2026, 1, 1, 9, 0, 0),
        )

        asserted_ids = _asserted_candidate_ids(
            trace,
            {
                "durable_memories": [
                    {
                        "memory_id": "memory-old-candidate",
                        "created_from_candidate_ids": ["old-candidate", "reinforcer-candidate"],
                    }
                ]
            },
        )

        self.assertEqual(asserted_ids, ["old-candidate"])

    def test_asserted_candidate_ids_preserve_mixed_pending_sources(self) -> None:
        trace = AnswerTrace(
            answer_id="answer-1",
            question_id="question-1",
            query="query",
            relevant_canonical_id="canonical",
            scope_level=generate_preference_drift_scenarios(1)[0].oracle_events[0].candidate.scope_level,
            scope_key="user",
            resolved_candidate_ids=["old-candidate", "pending-candidate"],
            used_memory_ids=["memory-old-candidate", "pending-candidate"],
            answer_text="answer",
            used_pending=True,
            created_at=datetime(2026, 1, 1, 9, 0, 0),
        )

        asserted_ids = _asserted_candidate_ids(
            trace,
            {
                "durable_memories": [
                    {
                        "memory_id": "memory-old-candidate",
                        "created_from_candidate_ids": ["old-candidate", "reinforcer-candidate"],
                    }
                ]
            },
        )

        self.assertEqual(asserted_ids, ["old-candidate", "pending-candidate"])

    def test_preference_metrics_do_not_treat_reinforcer_as_asserted_answer(self) -> None:
        scenario = generate_preference_drift_scenarios(3, seed=23, template_mix="mixed")[2]
        before_question = [
            event.question for event in scenario.sorted_events() if event.question and event.question.phase == "before_drift"
        ][0]
        after_question = [
            event.question for event in scenario.sorted_events() if event.question and event.question.phase == "after_drift"
        ][0]
        old_candidate_id = scenario.expected_lifecycle["old_candidate_id"]
        one_off_candidate_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]

        metrics = compute_preference_drift_metrics(
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
                    used_memory_ids=["memory-" + old_candidate_id],
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
                    resolved_candidate_ids=[old_candidate_id, one_off_candidate_id],
                    used_memory_ids=["memory-" + old_candidate_id],
                    answer_text="after",
                    used_pending=False,
                    created_at=after_question.asked_at,
                ),
            ],
            {
                "candidate_memories": [],
                "durable_memories": [
                    {
                        "memory_id": "memory-" + old_candidate_id,
                        "created_from_candidate_ids": [old_candidate_id, one_off_candidate_id],
                    }
                ],
                "lifecycle_events": [],
            },
        )

        self.assertEqual(metrics.answer_correctness, 1.0)
        self.assertEqual(metrics.false_assertion_rate, 0.0)
        self.assertEqual(metrics.premature_promotion_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
