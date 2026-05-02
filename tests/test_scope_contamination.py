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
from cq.schemas.memory import MemoryState, ScopeLevel
from cq.simulator.scenario_generator import generate_scope_contamination_scenarios


class ScopeContaminationScenarioTests(unittest.TestCase):
    def _scenario_by_template_id(self, template_id: str):
        scenarios = generate_scope_contamination_scenarios(2, seed=17, template_mix="mixed")
        return [scenario for scenario in scenarios if scenario.template_id == template_id][0]

    def test_mixed_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_scope_contamination_scenarios(4, seed=17, template_mix="mixed")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "scope_contamination_clean_v1",
                "scope_contamination_dirty_broad_claim_v1",
                "scope_contamination_clean_v1",
                "scope_contamination_dirty_broad_claim_v1",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"main"})

    def test_clean_template_uses_distinct_project_scopes_with_shared_canonical_id(self) -> None:
        scenario = self._scenario_by_template_id("scope_contamination_clean_v1")
        candidates = [event.candidate for event in scenario.oracle_events if event.candidate is not None]
        probe = [event.question for event in scenario.oracle_events if event.question is not None][0]

        self.assertEqual({candidate.canonical_id for candidate in candidates}, {"project-convention-test-command"})
        self.assertEqual({candidate.scope_level for candidate in candidates}, {ScopeLevel.PROJECT})
        self.assertEqual(len({candidate.scope_key for candidate in candidates}), 2)
        self.assertEqual(probe.phase, "off_scope_probe")
        self.assertEqual(len(probe.gold_candidate_ids), 1)
        self.assertEqual(len(probe.forbidden_candidate_ids), 1)

    def test_dirty_template_marks_broad_candidate_as_forbidden_and_should_not_promote(self) -> None:
        scenario = self._scenario_by_template_id("scope_contamination_dirty_broad_claim_v1")
        broad_candidate_id = scenario.scenario_id + "-candidate-broad-contaminant"
        probe = [event.question for event in scenario.oracle_events if event.question is not None][0]
        broad_candidate = [
            event.candidate
            for event in scenario.oracle_events
            if event.candidate is not None and event.candidate.candidate_id == broad_candidate_id
        ][0]

        self.assertEqual(broad_candidate.scope_level, ScopeLevel.WORLD_GLOBAL)
        self.assertEqual(probe.forbidden_candidate_ids, [broad_candidate_id])
        self.assertEqual(scenario.expected_lifecycle["should_not_promote_candidate_ids"], [broad_candidate_id])

    def test_clean_template_only_scope_blind_transcript_rag_leaks(self) -> None:
        scenario = self._scenario_by_template_id("scope_contamination_clean_v1")

        for policy_cls in (ReflectionEagerWriteLite, ConsolidationQueueLite, NaiveEagerWriteLite):
            result = execute_scenario(policy_cls, scenario)
            self.assertEqual(result["metrics"]["answer_correctness"], 1.0, msg=policy_cls.policy_name)
            self.assertEqual(result["metrics"]["leakage_rate"], 0.0, msg=policy_cls.policy_name)

        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)
        self.assertEqual(rag_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(rag_result["metrics"]["leakage_rate"], 1.0)

    def test_dirty_template_pins_broad_promotion_mechanism(self) -> None:
        scenario = self._scenario_by_template_id("scope_contamination_dirty_broad_claim_v1")
        broad_candidate_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        no_memory_result = execute_scenario(NoMemoryLite, scenario)

        self.assertEqual(reflection_result["metrics"]["leakage_rate"], 1.0)
        self.assertEqual(reflection_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(reflection_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(cq_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)

        self.assertEqual(naive_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(naive_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(naive_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(no_memory_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["premature_promotion_rate"], 0.0)

        reflection_candidate = reflection_result["store"].candidate_memories[broad_candidate_id]
        cq_candidate = cq_result["store"].candidate_memories[broad_candidate_id]
        self.assertEqual(reflection_candidate.promotion_score, cq_candidate.promotion_score)
        self.assertEqual(reflection_candidate.scope_level, cq_candidate.scope_level)
        self.assertEqual(reflection_candidate.state, MemoryState.PROMOTED)
        self.assertEqual(cq_candidate.state, MemoryState.PENDING)

    def test_scope_family_artifact_includes_transcript_baseline(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="scope_contamination")
        policy_names = {policy["policy_name"] for policy in artifact["policies"]}

        self.assertEqual(artifact["experiment"], "scope_contamination_oracle")
        self.assertIn("scope_blind_transcript_rag_lite", policy_names)

    def test_scope_family_rejects_heldout_template_mix_upfront(self) -> None:
        with self.assertRaises(ValueError):
            build_run_artifact(1, template_mix="heldout", family="scope_contamination")

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--family", "scope_contamination", "--template-mix", "heldout"])
        self.assertEqual(raised.exception.code, 2)

    def test_scope_cli_main_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "scope.json"
            output_csv = Path(tmpdir) / "scope.csv"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--family",
                        "scope_contamination",
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

    def test_scope_csv_emits_generic_and_legacy_metric_columns(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="scope_contamination")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "scope.json"
            output_csv = Path(tmpdir) / "scope.csv"
            write_outputs(artifact, output_json, output_csv)

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertIn("answer_correctness", rows[0])
        self.assertIn("leakage_rate", rows[0])
        self.assertIn("premature_promotion_rate", rows[0])
        self.assertIn("answer_correctness_after_contradiction", rows[0])

    def test_dashboard_renders_scope_and_forced_contradiction_metrics(self) -> None:
        scope_html = render_dashboard(build_run_artifact(2, template_mix="mixed", family="scope_contamination"))
        forced_html = render_dashboard(build_run_artifact(2, template_mix="mixed"))

        self.assertIn("Leakage rate", scope_html)
        self.assertIn("Premature promotion rate", scope_html)
        self.assertIn("Recovery", forced_html)
        self.assertIn("Correctness", forced_html)


if __name__ == "__main__":
    unittest.main()
