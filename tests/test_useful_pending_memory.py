import csv
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cq.dashboard.app import render_dashboard
from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.runner import build_run_artifact, main, write_outputs
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.memory.no_memory import NoMemoryLite
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.memory.scope_blind_transcript_rag import ScopeBlindTranscriptRAGLite
from cq.schemas.memory import ClaimType, MemoryState, ScopeLevel
from cq.simulator.scenario_generator import generate_useful_pending_memory_scenarios


def _failure_types(result):
    return {example["failure_type"] for example in result["failure_examples"]}


class UsefulPendingMemoryScenarioTests(unittest.TestCase):
    def _scenario_by_template_id(self, template_id: str, template_mix: str = "mixed", count: int = 2):
        scenarios = generate_useful_pending_memory_scenarios(count, seed=31, template_mix=template_mix)
        return [scenario for scenario in scenarios if scenario.template_id == template_id][0]

    def _candidate_by_id(self, scenario, candidate_id: str):
        return [
            event.candidate
            for event in scenario.oracle_events
            if event.candidate is not None and event.candidate.candidate_id == candidate_id
        ][0]

    def test_mixed_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_useful_pending_memory_scenarios(4, seed=31, template_mix="mixed")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "useful_pending_clean_v1",
                "useful_pending_dirty_refinement_v1",
                "useful_pending_clean_v1",
                "useful_pending_dirty_refinement_v1",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"main"})

    def test_heldout_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_useful_pending_memory_scenarios(4, seed=31, template_mix="heldout")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "useful_pending_clean_v2",
                "useful_pending_dirty_refinement_v2",
                "useful_pending_clean_v2",
                "useful_pending_dirty_refinement_v2",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"heldout"})

    def test_useful_pending_calibration_holds(self) -> None:
        scenarios = (
            generate_useful_pending_memory_scenarios(2, seed=31, template_mix="mixed")
            + generate_useful_pending_memory_scenarios(2, seed=31, template_mix="heldout")
        )

        for scenario in scenarios:
            candidates = [event.candidate for event in scenario.oracle_events if event.candidate is not None]
            self.assertTrue(candidates, msg=scenario.template_id)
            for candidate in candidates:
                self.assertEqual(candidate.claim_type, ClaimType.PROJECT_CONVENTION, msg=scenario.template_id)
                self.assertEqual(candidate.scope_level, ScopeLevel.PROJECT, msg=scenario.template_id)
                self.assertGreaterEqual(candidate.strength, 0.35, msg=scenario.template_id)
                self.assertLess(candidate.strength, 0.70, msg=scenario.template_id)

    def test_clean_template_pins_pending_utility_without_recall_loss(self) -> None:
        scenario = self._scenario_by_template_id("useful_pending_clean_v1")
        useful_candidate_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        no_memory_result = execute_scenario(NoMemoryLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        for result in (reflection_result, cq_result, naive_result, rag_result):
            self.assertEqual(result["metrics"]["answer_correctness"], 1.0, msg=result["policy_name"])
            self.assertEqual(result["metrics"]["useful_recall"], 1.0, msg=result["policy_name"])
            self.assertEqual(result["metrics"]["false_assertion_rate"], 0.0, msg=result["policy_name"])

        self.assertEqual(reflection_result["metrics"]["premature_promotion_rate"], 1.0)
        self.assertEqual(reflection_result["metrics"]["durable_commit"], 1.0)
        self.assertEqual(naive_result["metrics"]["premature_promotion_rate"], 1.0)
        self.assertEqual(naive_result["metrics"]["durable_commit"], 1.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["used_pending"], 1.0)
        self.assertEqual(cq_result["metrics"]["durable_commit"], 0.0)

        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(_failure_types(reflection_result), {"premature_promotion"})
        self.assertEqual(_failure_types(cq_result), set())

        reflection_candidate = reflection_result["store"].candidate_memories[useful_candidate_id]
        cq_candidate = cq_result["store"].candidate_memories[useful_candidate_id]
        self.assertEqual(reflection_candidate.state, MemoryState.PROMOTED)
        self.assertEqual(cq_candidate.state, MemoryState.PENDING)

    def test_dirty_template_pins_refinement_behavior(self) -> None:
        scenario = self._scenario_by_template_id("useful_pending_dirty_refinement_v1")
        tentative_candidate_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]
        refined_candidate_id = scenario.expected_lifecycle["gold_candidate_id"]
        tentative_candidate = self._candidate_by_id(scenario, tentative_candidate_id)
        refined_candidate = self._candidate_by_id(scenario, refined_candidate_id)

        self.assertEqual(refined_candidate.contradicts, [tentative_candidate_id])
        self.assertEqual(tentative_candidate.strength, 0.66)
        self.assertEqual(refined_candidate.strength, 0.64)

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        no_memory_result = execute_scenario(NoMemoryLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        for result in (reflection_result, naive_result):
            self.assertEqual(result["metrics"]["answer_correctness"], 0.0, msg=result["policy_name"])
            self.assertEqual(result["metrics"]["false_assertion_rate"], 1.0, msg=result["policy_name"])
            self.assertEqual(result["metrics"]["premature_promotion_rate"], 1.0, msg=result["policy_name"])
            self.assertEqual(_failure_types(result), {"false_assertion", "premature_promotion"})

        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["useful_recall"], 1.0)
        self.assertEqual(cq_result["metrics"]["used_pending"], 1.0)
        self.assertEqual(cq_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(_failure_types(cq_result), set())

        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(rag_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(rag_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)

        cq_tentative_candidate = cq_result["store"].candidate_memories[tentative_candidate_id]
        cq_refined_candidate = cq_result["store"].candidate_memories[refined_candidate_id]
        self.assertEqual(cq_tentative_candidate.state, MemoryState.CONTESTED)
        self.assertEqual(cq_refined_candidate.state, MemoryState.PENDING)

    def test_heldout_dirty_template_preserves_same_divergence_shape(self) -> None:
        scenario = self._scenario_by_template_id(
            "useful_pending_dirty_refinement_v2",
            template_mix="heldout",
            count=2,
        )

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        self.assertEqual(reflection_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(naive_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["used_pending"], 1.0)
        self.assertEqual(rag_result["metrics"]["answer_correctness"], 1.0)

    def test_useful_pending_family_artifact_includes_transcript_baseline(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="useful_pending_memory")
        policy_names = {policy["policy_name"] for policy in artifact["policies"]}

        self.assertEqual(artifact["experiment"], "useful_pending_memory_oracle")
        self.assertIn("scope_blind_transcript_rag_lite", policy_names)

    def test_useful_pending_family_accepts_heldout_template_mix(self) -> None:
        artifact = build_run_artifact(4, template_mix="heldout", family="useful_pending_memory")

        for policy in artifact["policies"]:
            self.assertIn("heldout", policy["summary_by_template_split"], msg=policy["policy_name"])
            self.assertEqual(policy["summary_by_template_split"]["heldout"]["scenario_count"], 4)
            self.assertEqual(
                {
                    "useful_pending_clean_v2",
                    "useful_pending_dirty_refinement_v2",
                },
                set(policy["summary_by_template_id"]),
                msg=policy["policy_name"],
            )
            self.assertEqual(policy["summary_by_template_id"]["useful_pending_clean_v2"]["scenario_count"], 2)
            self.assertEqual(
                policy["summary_by_template_id"]["useful_pending_dirty_refinement_v2"]["scenario_count"],
                2,
            )

    def test_useful_pending_family_rejects_unknown_template_mix_upfront(self) -> None:
        with self.assertRaises(ValueError):
            build_run_artifact(1, template_mix="nonexistent", family="useful_pending_memory")

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--family", "useful_pending_memory", "--template-mix", "nonexistent"])
        self.assertEqual(raised.exception.code, 2)

    def test_useful_pending_cli_main_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "useful_pending.json"
            output_csv = Path(tmpdir) / "useful_pending.csv"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--family",
                        "useful_pending_memory",
                        "--scenarios",
                        "1",
                        "--output-json",
                        str(output_json),
                        "--output-csv",
                        str(output_csv),
                    ]
                )

            self.assertEqual(result, 0)
            self.assertTrue(output_json.exists())
            self.assertTrue(output_csv.exists())

    def test_useful_pending_csv_and_dashboard_include_family(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="useful_pending_memory")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "useful_pending.json"
            output_csv = Path(tmpdir) / "useful_pending.csv"
            write_outputs(artifact, output_json, output_csv)

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertIn("useful_recall", rows[0])
        self.assertIn("used_pending", rows[0])
        self.assertIn("durable_commit", rows[0])

        html = render_dashboard(artifact)
        self.assertIn("Useful recall", html)
        self.assertIn("useful_pending_dirty_refinement_v1", html)
        self.assertIn("should_not_promote_useful_pending_candidate_promoted", html)


if __name__ == "__main__":
    unittest.main()
