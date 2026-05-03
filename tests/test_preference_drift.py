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
from cq.schemas.memory import ClaimType, ScopeLevel
from cq.simulator.scenario_generator import generate_preference_drift_scenarios


class PreferenceDriftScenarioTests(unittest.TestCase):
    def _scenario_by_template_id(self, template_id: str, template_mix: str = "mixed", count: int = 3):
        scenarios = generate_preference_drift_scenarios(count, seed=23, template_mix=template_mix)
        return [scenario for scenario in scenarios if scenario.template_id == template_id][0]

    def _candidates(self, scenario):
        return [event.candidate for event in scenario.oracle_events if event.candidate is not None]

    def _candidate_by_id(self, scenario, candidate_id: str):
        return [candidate for candidate in self._candidates(scenario) if candidate.candidate_id == candidate_id][0]

    def test_mixed_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_preference_drift_scenarios(6, seed=23, template_mix="mixed")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "preference_drift_clean_stable_v1",
                "preference_drift_dirty_explicit_update_v1",
                "preference_drift_dirty_one_off_exception_v1",
                "preference_drift_clean_stable_v1",
                "preference_drift_dirty_explicit_update_v1",
                "preference_drift_dirty_one_off_exception_v1",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"main"})

    def test_heldout_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_preference_drift_scenarios(4, seed=23, template_mix="heldout")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "preference_drift_clean_stable_v2",
                "preference_drift_dirty_drift_back_v2",
                "preference_drift_clean_stable_v2",
                "preference_drift_dirty_drift_back_v2",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"heldout"})

    def test_preference_candidates_use_user_preference_global_scope(self) -> None:
        scenario = self._scenario_by_template_id("preference_drift_dirty_drift_back_v2", "heldout", 2)

        for candidate in self._candidates(scenario):
            self.assertEqual(candidate.claim_type, ClaimType.USER_PREFERENCE)
            self.assertEqual(candidate.scope_level, ScopeLevel.USER_GLOBAL)
            self.assertEqual(candidate.scope_key, "user")

    def test_calibration_pins_pre_policy_strengths_and_scores(self) -> None:
        explicit = self._scenario_by_template_id("preference_drift_dirty_explicit_update_v1")
        old_candidate = self._candidate_by_id(explicit, explicit.expected_lifecycle["old_candidate_id"])
        new_candidate = self._candidate_by_id(explicit, explicit.expected_lifecycle["new_candidate_id"])
        one_off = self._scenario_by_template_id("preference_drift_dirty_one_off_exception_v1")
        one_off_candidate_id = one_off.expected_lifecycle["should_not_promote_candidate_ids"][0]
        one_off_candidate = self._candidate_by_id(one_off, one_off_candidate_id)

        self.assertEqual(old_candidate.strength, 0.86)
        self.assertEqual(old_candidate.promotion_score, 0.86)
        self.assertEqual(old_candidate.provenance[0].trust_score, 0.86)
        self.assertEqual(old_candidate.verification_score, 0.86)

        self.assertEqual(new_candidate.strength, 0.64)
        self.assertEqual(new_candidate.promotion_score, 0.64)
        self.assertEqual(new_candidate.provenance[0].trust_score, 0.64)
        self.assertEqual(new_candidate.verification_score, 0.64)
        self.assertEqual(new_candidate.contradicts, [old_candidate.candidate_id])

        self.assertEqual(one_off_candidate.strength, 0.30)
        self.assertEqual(one_off_candidate.promotion_score, 0.30)
        self.assertEqual(one_off_candidate.provenance[0].trust_score, 0.30)
        self.assertEqual(one_off_candidate.verification_score, 0.30)
        self.assertEqual(one_off_candidate.contradicts, [])

    def test_clean_stable_template_memory_and_rag_policies_recall(self) -> None:
        scenario = self._scenario_by_template_id("preference_drift_clean_stable_v1")

        for policy_cls in (
            ReflectionEagerWriteLite,
            ConsolidationQueueLite,
            NaiveEagerWriteLite,
            ScopeBlindTranscriptRAGLite,
        ):
            result = execute_scenario(policy_cls, scenario)
            self.assertEqual(result["metrics"]["answer_correctness"], 1.0, msg=policy_cls.policy_name)
            self.assertEqual(result["metrics"]["false_assertion_rate"], 0.0, msg=policy_cls.policy_name)

        no_memory_result = execute_scenario(NoMemoryLite, scenario)
        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)

    def test_explicit_update_distinguishes_cq_from_eager_and_rag_ties_cq(self) -> None:
        scenario = self._scenario_by_template_id("preference_drift_dirty_explicit_update_v1")

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        self.assertEqual(reflection_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(reflection_result["metrics"]["answer_correctness"], 0.0)

        self.assertEqual(cq_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["used_pending"], 1.0)

        self.assertEqual(naive_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(naive_result["metrics"]["answer_correctness"], 0.0)

        self.assertEqual(rag_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(rag_result["metrics"]["answer_correctness"], 1.0)

    def test_one_off_exception_blocks_recency_and_premature_promotion(self) -> None:
        scenario = self._scenario_by_template_id("preference_drift_dirty_one_off_exception_v1")

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        self.assertEqual(reflection_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(reflection_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(reflection_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["used_pending"], 0.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)

        self.assertEqual(naive_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(naive_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(naive_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(rag_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(rag_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)

    def test_heldout_drift_back_distinguishes_cq_from_eager_and_recency(self) -> None:
        scenario = self._scenario_by_template_id("preference_drift_dirty_drift_back_v2", "heldout", 2)

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        self.assertEqual(reflection_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(reflection_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(reflection_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["used_pending"], 1.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)

        self.assertEqual(naive_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(naive_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(naive_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(rag_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(rag_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)

    def test_preference_family_artifact_includes_transcript_baseline(self) -> None:
        artifact = build_run_artifact(3, template_mix="mixed", family="preference_drift")
        policy_names = {policy["policy_name"] for policy in artifact["policies"]}

        self.assertEqual(artifact["experiment"], "preference_drift_oracle")
        self.assertIn("scope_blind_transcript_rag_lite", policy_names)

    def test_preference_family_accepts_heldout_template_mix(self) -> None:
        artifact = build_run_artifact(4, template_mix="heldout", family="preference_drift")

        for policy in artifact["policies"]:
            self.assertIn("heldout", policy["summary_by_template_split"], msg=policy["policy_name"])
            self.assertEqual(policy["summary_by_template_split"]["heldout"]["scenario_count"], 4)
            self.assertEqual(
                {
                    "preference_drift_clean_stable_v2",
                    "preference_drift_dirty_drift_back_v2",
                },
                set(policy["summary_by_template_id"]),
            )

    def test_preference_family_rejects_unknown_template_mix_upfront(self) -> None:
        with self.assertRaises(ValueError):
            build_run_artifact(1, template_mix="nonexistent", family="preference_drift")

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--family", "preference_drift", "--template-mix", "nonexistent"])
        self.assertEqual(raised.exception.code, 2)

    def test_preference_cli_main_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "preference.json"
            output_csv = Path(tmpdir) / "preference.csv"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--family",
                        "preference_drift",
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

    def test_preference_csv_emits_generic_metric_columns(self) -> None:
        artifact = build_run_artifact(3, template_mix="mixed", family="preference_drift")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "preference.json"
            output_csv = Path(tmpdir) / "preference.csv"
            write_outputs(artifact, output_json, output_csv)

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertIn("answer_correctness", rows[0])
        self.assertIn("false_assertion_rate", rows[0])
        self.assertIn("premature_promotion_rate", rows[0])

    def test_dashboard_renders_preference_drift_templates(self) -> None:
        html = render_dashboard(build_run_artifact(2, template_mix="heldout", family="preference_drift"))

        self.assertIn("preference_drift_dirty_drift_back_v2", html)
        self.assertIn("Premature promotion rate", html)


if __name__ == "__main__":
    unittest.main()
