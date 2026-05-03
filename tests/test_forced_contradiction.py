import csv
import tempfile
import unittest
from pathlib import Path

from cq.dashboard.app import render_dashboard
from cq.eval.runner import build_run_artifact
from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.runner import write_outputs
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.memory.no_memory import NoMemoryLite
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


class ForcedContradictionScenarioTests(unittest.TestCase):
    def _scenario_by_template_id(self, template_id: str):
        if template_id == "forced_contradiction_clean_v1":
            return generate_forced_contradiction_scenarios(1, seed=9, template_mix="clean")[0]
        if template_id in {"forced_contradiction_dirty_v1", "forced_contradiction_dirty_v2"}:
            scenarios = generate_forced_contradiction_scenarios(2, seed=11, template_mix="dirty")
            return [scenario for scenario in scenarios if scenario.template_id == template_id][0]
        if template_id in {
            "forced_contradiction_dirty_v3",
            "forced_contradiction_dirty_v4",
            "forced_contradiction_dirty_v5",
            "forced_contradiction_dirty_v6",
        }:
            scenarios = generate_forced_contradiction_scenarios(4, seed=13, template_mix="heldout")
            return [scenario for scenario in scenarios if scenario.template_id == template_id][0]
        raise AssertionError("Unsupported template id: {}".format(template_id))

    def test_mixed_generation_contains_clean_and_dirty_templates(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(6, seed=9, template_mix="mixed")
        template_kinds = {scenario.template_kind for scenario in scenarios}
        template_splits = {scenario.template_split for scenario in scenarios}
        template_ids = [scenario.template_id for scenario in scenarios]

        self.assertEqual(template_kinds, {"clean", "dirty"})
        self.assertEqual(template_splits, {"main"})
        self.assertEqual(
            template_ids,
            [
                "forced_contradiction_clean_v1",
                "forced_contradiction_dirty_v1",
                "forced_contradiction_dirty_v2",
                "forced_contradiction_clean_v1",
                "forced_contradiction_dirty_v1",
                "forced_contradiction_dirty_v2",
            ],
        )

    def test_dirty_template_creates_policy_divergence(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, seed=9, template_mix="dirty")[0]

        eager_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)

        self.assertEqual(eager_result["metrics"]["false_assertion_after_contradiction"], 1.0)
        self.assertEqual(eager_result["metrics"]["contradiction_recovery_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["false_assertion_after_contradiction"], 0.0)
        self.assertEqual(cq_result["metrics"]["contradiction_recovery_rate"], 1.0)
        self.assertEqual(cq_result["question_traces"][1]["used_pending"], True)

    def test_dirty_rotation_is_explicit(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(4, seed=11, template_mix="dirty")
        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "forced_contradiction_dirty_v1",
                "forced_contradiction_dirty_v2",
                "forced_contradiction_dirty_v1",
                "forced_contradiction_dirty_v2",
            ],
        )
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"main"})

    def test_dirty_variants_create_policy_divergence(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(2, seed=11, template_mix="dirty")
        for scenario in scenarios:
            eager_result = execute_scenario(ReflectionEagerWriteLite, scenario)
            cq_result = execute_scenario(ConsolidationQueueLite, scenario)

            self.assertEqual(eager_result["metrics"]["false_assertion_after_contradiction"], 1.0)
            self.assertEqual(eager_result["metrics"]["contradiction_recovery_rate"], 0.0)
            self.assertEqual(cq_result["metrics"]["false_assertion_after_contradiction"], 0.0)
            self.assertEqual(cq_result["metrics"]["contradiction_recovery_rate"], 1.0)

    def test_dirty_v2_forbids_both_old_candidates(self) -> None:
        scenario = self._scenario_by_template_id("forced_contradiction_dirty_v2")
        after_question = [event.question for event in scenario.oracle_events if event.question and event.question.phase == "after_contradiction"][0]

        self.assertEqual(
            after_question.forbidden_candidate_ids,
            [scenario.scenario_id + "-candidate-old-1", scenario.scenario_id + "-candidate-old-2"],
        )
        self.assertEqual(
            scenario.expected_lifecycle["old_candidate_ids"],
            [scenario.scenario_id + "-candidate-old-1", scenario.scenario_id + "-candidate-old-2"],
        )

    def test_heldout_rotation_is_explicit(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(4, seed=13, template_mix="heldout")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "forced_contradiction_dirty_v3",
                "forced_contradiction_dirty_v4",
                "forced_contradiction_dirty_v5",
                "forced_contradiction_dirty_v6",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"heldout"})

    def test_heldout_dirty_variants_are_reserved_and_run(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(4, seed=13, template_mix="heldout")

        # Naive is intentionally excluded here because dirty_v5 is a held-out recovery case for it.
        for scenario in scenarios:
            eager_result = execute_scenario(ReflectionEagerWriteLite, scenario)
            cq_result = execute_scenario(ConsolidationQueueLite, scenario)

            self.assertEqual(eager_result["metrics"]["false_assertion_after_contradiction"], 1.0)
            self.assertEqual(cq_result["metrics"]["false_assertion_after_contradiction"], 0.0)

    def test_dirty_v4_creates_heldout_policy_divergence(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(4, seed=13, template_mix="heldout")
        scenario = [item for item in scenarios if item.template_id == "forced_contradiction_dirty_v4"][0]

        after_question = [event.question for event in scenario.oracle_events if event.question and event.question.phase == "after_contradiction"][0]
        self.assertEqual(
            after_question.forbidden_candidate_ids,
            [scenario.scenario_id + "-candidate-old-1", scenario.scenario_id + "-candidate-old-2"],
        )

        eager_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)

        self.assertEqual(eager_result["metrics"]["false_assertion_after_contradiction"], 1.0)
        self.assertEqual(eager_result["metrics"]["contradiction_recovery_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["false_assertion_after_contradiction"], 0.0)
        self.assertEqual(cq_result["metrics"]["contradiction_recovery_rate"], 1.0)
        self.assertEqual(cq_result["question_traces"][1]["used_pending"], True)

    def test_dirty_v6_uses_pending_for_cq_recovery(self) -> None:
        scenario = self._scenario_by_template_id("forced_contradiction_dirty_v6")

        cq_result = execute_scenario(ConsolidationQueueLite, scenario)

        self.assertEqual(cq_result["metrics"]["false_assertion_after_contradiction"], 0.0)
        self.assertEqual(cq_result["metrics"]["contradiction_recovery_rate"], 1.0)
        self.assertEqual(cq_result["question_traces"][1]["used_pending"], True)

    def test_naive_results_are_pinned_by_template(self) -> None:
        expectations = {
            "forced_contradiction_clean_v1": (0.0, 1.0),
            "forced_contradiction_dirty_v1": (1.0, 0.0),
            "forced_contradiction_dirty_v2": (0.0, 1.0),
            "forced_contradiction_dirty_v3": (1.0, 0.0),
            "forced_contradiction_dirty_v4": (1.0, 0.0),
            "forced_contradiction_dirty_v5": (0.0, 1.0),
            "forced_contradiction_dirty_v6": (1.0, 0.0),
        }

        for template_id, (false_assertion, recovery) in expectations.items():
            scenario = self._scenario_by_template_id(template_id)
            naive_result = execute_scenario(NaiveEagerWriteLite, scenario)

            self.assertEqual(
                naive_result["metrics"]["false_assertion_after_contradiction"],
                false_assertion,
                msg=template_id,
            )
            self.assertEqual(
                naive_result["metrics"]["contradiction_recovery_rate"],
                recovery,
                msg=template_id,
            )

    def test_no_memory_is_a_zero_history_floor(self) -> None:
        scenario = self._scenario_by_template_id("forced_contradiction_clean_v1")

        result = execute_scenario(NoMemoryLite, scenario)

        self.assertEqual(result["metrics"]["durable_commit_before_contradiction"], 0.0)
        self.assertEqual(result["metrics"]["useful_recall_before_contradiction"], 0.0)
        self.assertEqual(result["metrics"]["false_assertion_after_contradiction"], 0.0)
        self.assertEqual(result["metrics"]["contradiction_recovery_rate"], 0.0)
        self.assertEqual(result["metrics"]["answer_correctness_after_contradiction"], 0.0)

    def test_run_artifact_summarizes_by_template_kind(self) -> None:
        artifact = build_run_artifact(6, template_mix="mixed")
        eager_policy = [
            policy
            for policy in artifact["policies"]
            if policy["policy_name"] == "reflection_eager_write_lite"
        ][0]

        clean_summary = eager_policy["summary_by_template_kind"]["clean"]
        dirty_summary = eager_policy["summary_by_template_kind"]["dirty"]

        self.assertEqual(clean_summary["scenario_count"], 2)
        self.assertEqual(dirty_summary["scenario_count"], 4)
        self.assertEqual(clean_summary["false_assertion_after_contradiction"], 0.0)
        self.assertGreater(dirty_summary["false_assertion_after_contradiction"], 0.0)

    def test_run_artifact_summarizes_by_template_id(self) -> None:
        mixed_artifact = build_run_artifact(6, template_mix="mixed")
        heldout_artifact = build_run_artifact(4, template_mix="heldout")
        eager_mixed = [
            policy
            for policy in mixed_artifact["policies"]
            if policy["policy_name"] == "reflection_eager_write_lite"
        ][0]
        eager_heldout = [
            policy
            for policy in heldout_artifact["policies"]
            if policy["policy_name"] == "reflection_eager_write_lite"
        ][0]
        policy_names = {policy["policy_name"] for policy in mixed_artifact["policies"]}

        self.assertEqual(eager_mixed["summary_by_template_id"]["forced_contradiction_clean_v1"]["scenario_count"], 2)
        self.assertEqual(eager_mixed["summary_by_template_id"]["forced_contradiction_dirty_v1"]["scenario_count"], 2)
        self.assertEqual(eager_mixed["summary_by_template_id"]["forced_contradiction_dirty_v2"]["scenario_count"], 2)
        self.assertEqual(eager_heldout["summary_by_template_id"]["forced_contradiction_dirty_v3"]["scenario_count"], 1)
        self.assertEqual(eager_heldout["summary_by_template_id"]["forced_contradiction_dirty_v4"]["scenario_count"], 1)
        self.assertEqual(eager_heldout["summary_by_template_id"]["forced_contradiction_dirty_v5"]["scenario_count"], 1)
        self.assertEqual(eager_heldout["summary_by_template_id"]["forced_contradiction_dirty_v6"]["scenario_count"], 1)
        self.assertEqual(
            policy_names,
            {
                "reflection_eager_write_lite",
                "consolidation_queue_lite",
                "naive_eager_write_lite",
                "no_memory_lite",
            },
        )

    def test_existing_forced_contradiction_template_metrics_remain_pinned(self) -> None:
        artifact = build_run_artifact(6, template_mix="mixed")
        policies = {policy["policy_name"]: policy for policy in artifact["policies"]}

        reflection_dirty_v2 = policies["reflection_eager_write_lite"]["summary_by_template_id"][
            "forced_contradiction_dirty_v2"
        ]
        cq_dirty_v2 = policies["consolidation_queue_lite"]["summary_by_template_id"][
            "forced_contradiction_dirty_v2"
        ]
        naive_dirty_v2 = policies["naive_eager_write_lite"]["summary_by_template_id"][
            "forced_contradiction_dirty_v2"
        ]

        self.assertEqual(reflection_dirty_v2["useful_recall"], 1.0)
        self.assertEqual(reflection_dirty_v2["false_assertion_rate"], 1.0)
        self.assertEqual(reflection_dirty_v2["answer_correctness"], 0.0)
        self.assertEqual(cq_dirty_v2["false_assertion_rate"], 0.0)
        self.assertEqual(cq_dirty_v2["answer_correctness"], 1.0)
        self.assertEqual(naive_dirty_v2["false_assertion_rate"], 0.0)
        self.assertEqual(naive_dirty_v2["answer_correctness"], 1.0)

    def test_csv_emits_template_id_rows_and_correctness_column(self) -> None:
        artifact = build_run_artifact(4, template_mix="heldout")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "run.json"
            output_csv = Path(tmpdir) / "metrics.csv"
            write_outputs(artifact, output_json, output_csv)

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)

        template_rows = [row for row in rows if row["summary_scope"] == "template_id"]
        self.assertTrue(template_rows)
        self.assertIn("answer_correctness_after_contradiction", rows[0])
        self.assertEqual(
            {row["template_id"] for row in template_rows},
            {
                "forced_contradiction_dirty_v3",
                "forced_contradiction_dirty_v4",
                "forced_contradiction_dirty_v5",
                "forced_contradiction_dirty_v6",
            },
        )

    def test_dashboard_renders_template_id_summary_and_timeline(self) -> None:
        artifact = build_run_artifact(2, template_mix="heldout")
        html_text = render_dashboard(artifact)

        self.assertIn("By Template ID", html_text)
        self.assertIn("Timeline", html_text)
        self.assertLess(html_text.index("Recovery"), html_text.index("Correctness"))

        turn_marker = "id='scenario-consolidation_queue_lite-forced_contradiction_001-turn-1'"
        turn_start = html_text.index(turn_marker)
        turn_end = html_text.index("</div>", turn_start)
        turn_html = html_text[turn_start:turn_end]
        self.assertIn("candidate_observed", turn_html)

        # This assumes the first two held-out slots remain v3 and v4.
        demotion_turn_marker = "id='scenario-consolidation_queue_lite-forced_contradiction_002-turn-4'"
        demotion_turn_start = html_text.index(demotion_turn_marker)
        demotion_turn_end = html_text.index("</div>", demotion_turn_start)
        demotion_turn_html = html_text[demotion_turn_start:demotion_turn_end]
        self.assertIn("memory_demoted", demotion_turn_html)
        self.assertIn("demoted", demotion_turn_html)

        no_memory_turn_marker = "id='scenario-no_memory_lite-forced_contradiction_001-turn-1'"
        no_memory_turn_start = html_text.index(no_memory_turn_marker)
        no_memory_turn_end = html_text.index("</div>", no_memory_turn_start)
        no_memory_turn_html = html_text[no_memory_turn_start:no_memory_turn_end]
        self.assertIn("observation_ignored", no_memory_turn_html)
        self.assertIn("ignored", no_memory_turn_html)


if __name__ == "__main__":
    unittest.main()
