import csv
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cq.dashboard.app import render_dashboard
from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.runner import (
    FORCED_CONTRADICTION,
    PREFERENCE_DRIFT,
    USEFUL_PENDING_MEMORY,
    build_run_artifact,
    main,
    write_outputs,
)
from cq.memory.lifecycle import merge_thresholds, pending_use_allowed, should_promote_candidate
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.memory.no_memory import NoMemoryLite
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.memory.scope_blind_transcript_rag import ScopeBlindTranscriptRAGLite
from cq.memory.substrate import (
    SCOPE_MATCH_EXACT,
    SCOPE_MATCH_WORKSPACE_PARENT,
    scope_match_relation,
    scope_matches,
)
from cq.schemas.memory import ClaimType, MemoryState, ScopeLevel
from cq.simulator.scenario_generator import generate_scope_contamination_scenarios


class ScopeContaminationScenarioTests(unittest.TestCase):
    def _scenario_by_template_id(self, template_id: str, template_mix: str = "mixed", count: int = 2):
        scenarios = generate_scope_contamination_scenarios(count, seed=17, template_mix=template_mix)
        return [scenario for scenario in scenarios if scenario.template_id == template_id][0]

    def _candidate_by_id(self, scenario, candidate_id: str):
        return [
            event.candidate
            for event in scenario.oracle_events
            if event.candidate is not None and event.candidate.candidate_id == candidate_id
        ][0]

    def _trace_by_question_id(self, result, question_id: str):
        return [trace for trace in result["question_traces"] if trace["question_id"] == question_id][0]

    def test_scope_relation_supports_workspace_parent_keys(self) -> None:
        workspace_key = "workspace-atlas-beacon"
        direct_project_key = "workspace-atlas-beacon/project-atlas"
        nested_project_key = "workspace-atlas-beacon/group-core/project-atlas"

        self.assertEqual(
            scope_match_relation(
                ScopeLevel.WORKSPACE,
                workspace_key,
                ScopeLevel.PROJECT,
                direct_project_key,
            ),
            SCOPE_MATCH_WORKSPACE_PARENT,
        )
        self.assertEqual(
            scope_match_relation(
                ScopeLevel.WORKSPACE,
                workspace_key,
                ScopeLevel.PROJECT,
                nested_project_key,
            ),
            SCOPE_MATCH_WORKSPACE_PARENT,
        )
        self.assertFalse(
            scope_matches(
                ScopeLevel.WORKSPACE,
                workspace_key,
                ScopeLevel.PROJECT,
                "workspace-atlas-beacon-2/project-atlas",
            )
        )
        self.assertFalse(
            scope_matches(
                ScopeLevel.PROJECT,
                direct_project_key,
                ScopeLevel.WORKSPACE,
                workspace_key,
            )
        )
        self.assertEqual(
            scope_match_relation(
                ScopeLevel.PROJECT,
                direct_project_key,
                ScopeLevel.PROJECT,
                direct_project_key,
            ),
            SCOPE_MATCH_EXACT,
        )
        self.assertTrue(
            scope_matches(
                ScopeLevel.WORLD_GLOBAL,
                "global",
                ScopeLevel.PROJECT,
                direct_project_key,
            )
        )

    def test_mixed_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_scope_contamination_scenarios(4, seed=17, template_mix="mixed")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "scope_contamination_clean_v1",
                "scope_contamination_dirty_broad_claim_v1",
                "scope_contamination_clean_workspace_parent_v1",
                "scope_contamination_dirty_workspace_parent_v1",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"main"})

    def test_heldout_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_scope_contamination_scenarios(4, seed=17, template_mix="heldout")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "scope_contamination_clean_v2",
                "scope_contamination_dirty_broad_claim_v3",
                "scope_contamination_clean_workspace_parent_v2",
                "scope_contamination_dirty_workspace_parent_v2",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"heldout"})

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

    def test_heldout_clean_template_only_scope_blind_transcript_rag_leaks(self) -> None:
        scenario = self._scenario_by_template_id(
            "scope_contamination_clean_v2",
            template_mix="heldout",
            count=2,
        )
        candidates = [event.candidate for event in scenario.oracle_events if event.candidate is not None]

        self.assertEqual(sorted(candidate.strength for candidate in candidates), [0.82, 0.84])
        for policy_cls in (ReflectionEagerWriteLite, ConsolidationQueueLite, NaiveEagerWriteLite):
            result = execute_scenario(policy_cls, scenario)
            self.assertEqual(result["metrics"]["answer_correctness"], 1.0, msg=policy_cls.policy_name)
            self.assertEqual(result["metrics"]["leakage_rate"], 0.0, msg=policy_cls.policy_name)
            self.assertEqual(result["metrics"]["premature_promotion_rate"], 0.0, msg=policy_cls.policy_name)

        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)
        self.assertEqual(rag_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(rag_result["metrics"]["leakage_rate"], 1.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)

        no_memory_result = execute_scenario(NoMemoryLite, scenario)
        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["premature_promotion_rate"], 0.0)

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

    def test_heldout_dirty_template_pins_broad_first_calibration(self) -> None:
        scenario = self._scenario_by_template_id(
            "scope_contamination_dirty_broad_claim_v3",
            template_mix="heldout",
            count=2,
        )
        broad_candidate_id = scenario.scenario_id + "-candidate-broad-contaminant-heldout"
        project_candidate_id = scenario.scenario_id + "-candidate-project-override"
        broad_candidate = self._candidate_by_id(scenario, broad_candidate_id)
        project_candidate = self._candidate_by_id(scenario, project_candidate_id)
        thresholds = merge_thresholds()

        self.assertEqual(broad_candidate.strength, 0.66)
        self.assertEqual(project_candidate.strength, 0.64)
        self.assertEqual(project_candidate.contradicts, [broad_candidate_id])
        self.assertIn("overriding the workspace-wide npm test note", project_candidate.raw_text)
        self.assertLess(broad_candidate.promotion_score, 0.70)
        self.assertLess(project_candidate.strength, broad_candidate.strength + thresholds["overwrite_margin"])
        self.assertGreater(broad_candidate.strength, project_candidate.strength)
        self.assertGreaterEqual(project_candidate.strength, 0.35)

    def test_heldout_dirty_template_pins_broad_first_policy_behavior(self) -> None:
        scenario = self._scenario_by_template_id(
            "scope_contamination_dirty_broad_claim_v3",
            template_mix="heldout",
            count=2,
        )
        broad_candidate_id = scenario.expected_lifecycle["should_not_promote_candidate_ids"][0]

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        no_memory_result = execute_scenario(NoMemoryLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        self.assertEqual(reflection_result["metrics"]["leakage_rate"], 1.0)
        self.assertEqual(reflection_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(reflection_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(cq_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertTrue(cq_result["question_traces"][0]["used_pending"])

        self.assertEqual(naive_result["metrics"]["leakage_rate"], 1.0)
        self.assertEqual(naive_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(naive_result["metrics"]["premature_promotion_rate"], 1.0)

        self.assertEqual(no_memory_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["premature_promotion_rate"], 0.0)

        self.assertEqual(rag_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(rag_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)

        cq_broad_candidate = cq_result["store"].candidate_memories[broad_candidate_id]
        self.assertEqual(cq_broad_candidate.state, MemoryState.CONTESTED)
        self.assertEqual(cq_broad_candidate.promotion_score, 0.41)

    def test_clean_workspace_parent_template_uses_parent_scope_match(self) -> None:
        scenario = self._scenario_by_template_id(
            "scope_contamination_clean_workspace_parent_v1",
            template_mix="mixed",
            count=4,
        )
        workspace_candidate_id = scenario.expected_lifecycle["workspace_candidate_id"]
        workspace_candidate = self._candidate_by_id(scenario, workspace_candidate_id)
        probe = [event.question for event in scenario.oracle_events if event.question is not None][0]

        self.assertEqual(workspace_candidate.claim_type, ClaimType.PROJECT_CONVENTION)
        self.assertEqual(workspace_candidate.scope_level, ScopeLevel.WORKSPACE)
        self.assertEqual(probe.scope_level, ScopeLevel.PROJECT)
        self.assertEqual(probe.gold_candidate_ids, [workspace_candidate_id])
        self.assertEqual(probe.forbidden_candidate_ids, [])
        self.assertTrue(probe.scope_key.startswith(workspace_candidate.scope_key + "/"))

        for policy_cls in (
            ReflectionEagerWriteLite,
            ConsolidationQueueLite,
            NaiveEagerWriteLite,
            ScopeBlindTranscriptRAGLite,
        ):
            result = execute_scenario(policy_cls, scenario)
            self.assertEqual(result["metrics"]["answer_correctness"], 1.0, msg=policy_cls.policy_name)
            self.assertEqual(result["metrics"]["leakage_rate"], 0.0, msg=policy_cls.policy_name)
            self.assertEqual(result["metrics"]["premature_promotion_rate"], 0.0, msg=policy_cls.policy_name)

    def _assert_dirty_workspace_parent_calibration(
        self,
        template_id: str,
        template_mix: str,
        count: int,
        workspace_strength: float,
        project_strength: float,
        multi_level: bool,
    ) -> None:
        scenario = self._scenario_by_template_id(template_id, template_mix=template_mix, count=count)
        workspace_candidate_id = scenario.expected_lifecycle["workspace_candidate_id"]
        project_candidate_id = scenario.expected_lifecycle["project_candidate_id"]
        workspace_candidate = self._candidate_by_id(scenario, workspace_candidate_id)
        project_candidate = self._candidate_by_id(scenario, project_candidate_id)
        thresholds = merge_thresholds()

        self.assertEqual(workspace_candidate.claim_type, ClaimType.PROJECT_CONVENTION)
        self.assertEqual(project_candidate.claim_type, ClaimType.PROJECT_CONVENTION)
        self.assertEqual(workspace_candidate.scope_level, ScopeLevel.WORKSPACE)
        self.assertEqual(project_candidate.scope_level, ScopeLevel.PROJECT)
        self.assertEqual(workspace_candidate.strength, workspace_strength)
        self.assertEqual(project_candidate.strength, project_strength)
        self.assertEqual(project_candidate.contradicts, [workspace_candidate_id])
        self.assertEqual(scenario.expected_lifecycle["should_not_promote_candidate_ids"], [])
        self.assertTrue(should_promote_candidate(workspace_candidate, thresholds))
        self.assertFalse(should_promote_candidate(project_candidate, thresholds))
        self.assertTrue(pending_use_allowed(project_candidate, thresholds))
        self.assertLess(
            project_candidate.strength,
            workspace_candidate.strength + thresholds["overwrite_margin"],
        )
        self.assertTrue(project_candidate.scope_key.startswith(workspace_candidate.scope_key + "/"))
        self.assertEqual(
            "/group-core/" in project_candidate.scope_key,
            multi_level,
        )

    def test_dirty_workspace_parent_template_pins_calibration(self) -> None:
        self._assert_dirty_workspace_parent_calibration(
            "scope_contamination_dirty_workspace_parent_v1",
            "mixed",
            4,
            0.80,
            0.64,
            False,
        )

    def test_heldout_dirty_workspace_parent_template_pins_calibration(self) -> None:
        self._assert_dirty_workspace_parent_calibration(
            "scope_contamination_dirty_workspace_parent_v2",
            "heldout",
            4,
            0.71,
            0.66,
            True,
        )

    def test_dirty_workspace_parent_policy_behavior(self) -> None:
        scenario = self._scenario_by_template_id(
            "scope_contamination_dirty_workspace_parent_v1",
            template_mix="mixed",
            count=4,
        )
        workspace_candidate_id = scenario.expected_lifecycle["workspace_candidate_id"]
        project_candidate_id = scenario.expected_lifecycle["project_candidate_id"]
        workspace_question_id = scenario.scenario_id + "-question-workspace-probe"

        reflection_result = execute_scenario(ReflectionEagerWriteLite, scenario)
        cq_result = execute_scenario(ConsolidationQueueLite, scenario)
        naive_result = execute_scenario(NaiveEagerWriteLite, scenario)
        no_memory_result = execute_scenario(NoMemoryLite, scenario)
        rag_result = execute_scenario(ScopeBlindTranscriptRAGLite, scenario)

        self.assertEqual(reflection_result["metrics"]["leakage_rate"], 1.0)
        self.assertEqual(reflection_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(reflection_result["metrics"]["premature_promotion_rate"], 0.0)

        self.assertEqual(cq_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(cq_result["question_traces"][0]["resolved_candidate_ids"], [project_candidate_id])
        self.assertTrue(cq_result["question_traces"][0]["used_pending"])

        self.assertEqual(naive_result["metrics"]["leakage_rate"], 1.0)
        self.assertEqual(naive_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(naive_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(
            naive_result["question_traces"][0]["used_memory_ids"],
            ["memory-" + workspace_candidate_id],
        )

        self.assertEqual(no_memory_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(no_memory_result["metrics"]["premature_promotion_rate"], 0.0)

        self.assertEqual(rag_result["metrics"]["leakage_rate"], 0.0)
        self.assertEqual(rag_result["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)

        cq_workspace_memory = cq_result["store"].durable_memories["memory-" + workspace_candidate_id]
        cq_project_candidate = cq_result["store"].candidate_memories[project_candidate_id]
        self.assertTrue(cq_workspace_memory.active)
        self.assertEqual(cq_project_candidate.state, MemoryState.PENDING)

        cq_workspace_trace = self._trace_by_question_id(cq_result, workspace_question_id)
        self.assertEqual(cq_workspace_trace["resolved_candidate_ids"], [workspace_candidate_id])
        self.assertEqual(cq_workspace_trace["used_memory_ids"], ["memory-" + workspace_candidate_id])
        self.assertFalse(cq_workspace_trace["used_pending"])

    def test_scope_family_artifact_includes_transcript_baseline(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="scope_contamination")
        policy_names = {policy["policy_name"] for policy in artifact["policies"]}

        self.assertEqual(artifact["experiment"], "scope_contamination_oracle")
        self.assertIn("scope_blind_transcript_rag_lite", policy_names)

    def test_scope_family_accepts_heldout_template_mix(self) -> None:
        artifact = build_run_artifact(4, template_mix="heldout", family="scope_contamination")

        for policy in artifact["policies"]:
            self.assertIn("heldout", policy["summary_by_template_split"], msg=policy["policy_name"])
            self.assertEqual(
                policy["summary_by_template_split"]["heldout"]["scenario_count"],
                4,
                msg=policy["policy_name"],
            )
            self.assertEqual(
                {
                    "scope_contamination_clean_v2",
                    "scope_contamination_dirty_broad_claim_v3",
                    "scope_contamination_clean_workspace_parent_v2",
                    "scope_contamination_dirty_workspace_parent_v2",
                },
                set(policy["summary_by_template_id"]),
                msg=policy["policy_name"],
            )
            self.assertEqual(
                policy["summary_by_template_id"]["scope_contamination_clean_v2"]["scenario_count"],
                1,
                msg=policy["policy_name"],
            )
            self.assertEqual(
                policy["summary_by_template_id"]["scope_contamination_dirty_broad_claim_v3"]["scenario_count"],
                1,
                msg=policy["policy_name"],
            )
            self.assertEqual(
                policy["summary_by_template_id"]["scope_contamination_clean_workspace_parent_v2"]["scenario_count"],
                1,
                msg=policy["policy_name"],
            )
            self.assertEqual(
                policy["summary_by_template_id"]["scope_contamination_dirty_workspace_parent_v2"]["scenario_count"],
                1,
                msg=policy["policy_name"],
            )

    def test_existing_scope_template_metrics_remain_pinned(self) -> None:
        mixed_artifact = build_run_artifact(2, template_mix="mixed", family="scope_contamination")
        heldout_artifact = build_run_artifact(4, template_mix="heldout", family="scope_contamination")
        mixed_policies = {policy["policy_name"]: policy for policy in mixed_artifact["policies"]}
        heldout_policies = {policy["policy_name"]: policy for policy in heldout_artifact["policies"]}

        reflection_dirty_v1 = mixed_policies["reflection_eager_write_lite"]["summary_by_template_id"][
            "scope_contamination_dirty_broad_claim_v1"
        ]
        cq_dirty_v1 = mixed_policies["consolidation_queue_lite"]["summary_by_template_id"][
            "scope_contamination_dirty_broad_claim_v1"
        ]
        naive_dirty_v3 = heldout_policies["naive_eager_write_lite"]["summary_by_template_id"][
            "scope_contamination_dirty_broad_claim_v3"
        ]
        rag_clean_v2 = heldout_policies["scope_blind_transcript_rag_lite"]["summary_by_template_id"][
            "scope_contamination_clean_v2"
        ]

        self.assertEqual(reflection_dirty_v1["leakage_rate"], 1.0)
        self.assertEqual(reflection_dirty_v1["answer_correctness"], 0.0)
        self.assertEqual(cq_dirty_v1["leakage_rate"], 0.0)
        self.assertEqual(cq_dirty_v1["answer_correctness"], 1.0)
        self.assertEqual(naive_dirty_v3["leakage_rate"], 1.0)
        self.assertEqual(naive_dirty_v3["answer_correctness"], 0.0)
        self.assertEqual(rag_clean_v2["leakage_rate"], 1.0)
        self.assertEqual(rag_clean_v2["answer_correctness"], 0.0)

    def test_scope_parent_matching_does_not_shift_other_family_summaries(self) -> None:
        forced = {
            policy["policy_name"]: policy["summary"]
            for policy in build_run_artifact(3, template_mix="mixed", family=FORCED_CONTRADICTION)["policies"]
        }
        preference = {
            policy["policy_name"]: policy["summary"]
            for policy in build_run_artifact(3, template_mix="mixed", family=PREFERENCE_DRIFT)["policies"]
        }
        useful = {
            policy["policy_name"]: policy["summary"]
            for policy in build_run_artifact(2, template_mix="mixed", family=USEFUL_PENDING_MEMORY)["policies"]
        }

        self.assertAlmostEqual(forced["reflection_eager_write_lite"]["false_assertion_rate"], 2 / 3)
        self.assertEqual(forced["consolidation_queue_lite"]["answer_correctness"], 1.0)
        self.assertEqual(forced["no_memory_lite"]["answer_correctness"], 0.0)

        self.assertAlmostEqual(preference["reflection_eager_write_lite"]["false_assertion_rate"], 1 / 3)
        self.assertEqual(preference["consolidation_queue_lite"]["answer_correctness"], 1.0)
        self.assertAlmostEqual(preference["scope_blind_transcript_rag_lite"]["false_assertion_rate"], 1 / 3)

        self.assertEqual(useful["reflection_eager_write_lite"]["false_assertion_rate"], 0.5)
        self.assertEqual(useful["consolidation_queue_lite"]["answer_correctness"], 1.0)
        self.assertEqual(useful["scope_blind_transcript_rag_lite"]["answer_correctness"], 1.0)

    def test_scope_family_rejects_unknown_template_mix_upfront(self) -> None:
        with self.assertRaises(ValueError):
            build_run_artifact(1, template_mix="nonexistent", family="scope_contamination")

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--family", "scope_contamination", "--template-mix", "nonexistent"])
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
        heldout_scope_html = render_dashboard(
            build_run_artifact(2, template_mix="heldout", family="scope_contamination")
        )
        forced_html = render_dashboard(build_run_artifact(2, template_mix="mixed"))

        self.assertIn("Leakage rate", scope_html)
        self.assertIn("Premature promotion rate", scope_html)
        self.assertIn("<strong>Template mix:</strong> heldout", heldout_scope_html)
        self.assertIn("scope_contamination_dirty_broad_claim_v3", heldout_scope_html)
        self.assertIn("Recovery", forced_html)
        self.assertIn("Correctness", forced_html)


if __name__ == "__main__":
    unittest.main()
