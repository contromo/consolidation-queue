import csv
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

from cq.dashboard.app import render_dashboard
from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.runner import build_run_artifact, main, write_outputs
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.lifecycle import merge_thresholds, pending_use_allowed, should_promote_candidate
from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.memory.no_memory import NoMemoryLite
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.memory.scope_blind_transcript_rag import ScopeBlindTranscriptRAGLite
from cq.memory.substrate import MemoryStore
from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
from cq.simulator.scenario_generator import generate_false_corroboration_scenarios


BASE_TIME = datetime(2026, 4, 1, 9, 0, 0)


def _candidate(
    candidate_id,
    *,
    canonical_id="canonical",
    raw_text="raw claim",
    canonical_claim="project checks use ./scripts/verify",
    claim_type=ClaimType.PROJECT_CONVENTION,
    scope_level=ScopeLevel.PROJECT,
    scope_key="project-atlas",
    source_ids=None,
    supports=None,
    corroboration_count=0,
):
    source_ids = source_ids or ["source-" + candidate_id]
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=raw_text,
        raw_claim=raw_text,
        canonical_claim=canonical_claim,
        claim_type=claim_type,
        scope_level=scope_level,
        scope_key=scope_key,
        provenance=[
            ProvenanceRecord(
                source_kind="test",
                source_id=source_id,
                trust_score=0.32,
                observed_at=BASE_TIME,
            )
            for source_id in source_ids
        ],
        verification_score=0.32,
        corroboration_count=corroboration_count,
        supports=supports or [],
        created_at=BASE_TIME,
        updated_at=BASE_TIME,
    )


def _candidate_by_id(scenario, candidate_id):
    return [
        event.candidate
        for event in scenario.oracle_events
        if event.candidate is not None and event.candidate.candidate_id == candidate_id
    ][0]


def _candidates(scenario):
    return [event.candidate for event in scenario.oracle_events if event.candidate is not None]


def _failure_types(result):
    return {example["failure_type"] for example in result["failure_examples"]}


def _failure_by_type(result, failure_type):
    for example in result["failure_examples"]:
        if example["failure_type"] == failure_type:
            return example
    raise AssertionError("Missing failure type {}".format(failure_type))


class SourceIndependenceSubstrateTests(unittest.TestCase):
    def test_distinct_supported_sources_increase_computed_corroboration(self) -> None:
        store = MemoryStore("test-policy")
        store.add_candidate(_candidate("c1", source_ids=["s1"]))
        second = store.add_candidate(_candidate("c2", source_ids=["s2"], supports=["c1"]))
        third = store.add_candidate(_candidate("c3", source_ids=["s3"], supports=["c1", "c2"]))

        self.assertEqual(second.corroboration_count, 1)
        self.assertEqual(third.corroboration_count, 2)
        self.assertEqual(third.promotion_score, 0.52)

    def test_duplicate_mirrored_sources_do_not_corroborate(self) -> None:
        store = MemoryStore("test-policy")
        store.add_candidate(_candidate("c1", source_ids=["mirror"]))
        second = store.add_candidate(_candidate("c2", source_ids=["mirror"], supports=["c1"]))

        self.assertEqual(second.corroboration_count, 0)
        event = [
            item
            for item in store.lifecycle_events
            if item.event_type == "candidate_corroboration_counted"
        ][0]
        self.assertEqual(event.details["ignored_source_ids"], ["mirror"])
        self.assertEqual(event.details["duplicate_source_ids"], ["mirror"])
        self.assertEqual(event.details["capped_source_ids"], [])
        self.assertEqual(event.details["ignored_candidate_ids"], ["c1"])

    def test_own_source_does_not_create_support_by_itself(self) -> None:
        store = MemoryStore("test-policy")
        candidate = store.add_candidate(_candidate("c1", source_ids=["s1"], supports=["missing"]))

        self.assertEqual(candidate.corroboration_count, 0)
        self.assertEqual(candidate.promotion_score, 0.32)

    def test_multi_provenance_prior_candidate_contributes_at_most_one_source(self) -> None:
        store = MemoryStore("test-policy")
        store.add_candidate(_candidate("c1", source_ids=["s1", "s2"]))
        second = store.add_candidate(_candidate("c2", source_ids=["s3"], supports=["c1"]))

        self.assertEqual(second.corroboration_count, 1)
        self.assertEqual(second.promotion_score, 0.42)
        event = [
            item
            for item in store.lifecycle_events
            if item.event_type == "candidate_corroboration_counted"
        ][0]
        self.assertEqual(event.details["counted_source_ids"], ["s1"])
        self.assertEqual(event.details["duplicate_source_ids"], [])
        self.assertEqual(event.details["capped_source_ids"], ["s2"])
        self.assertEqual(event.details["ignored_source_ids"], ["s2"])

    def test_repeated_support_ids_are_deduplicated_before_counting(self) -> None:
        store = MemoryStore("test-policy")
        store.add_candidate(_candidate("c1", source_ids=["s1", "s2"]))
        second = store.add_candidate(_candidate("c2", source_ids=["s3"], supports=["c1", "c1"]))

        self.assertEqual(second.corroboration_count, 1)
        event = [
            item
            for item in store.lifecycle_events
            if item.event_type == "candidate_corroboration_counted"
        ][0]
        self.assertEqual(event.details["counted_candidate_ids"], ["c1"])
        self.assertEqual(event.details["ignored_candidate_ids"], [])
        self.assertEqual(event.details["counted_source_ids"], ["s1"])
        self.assertEqual(event.details["capped_source_ids"], ["s2"])

    def test_mismatched_support_candidates_do_not_count(self) -> None:
        cases = [
            ("claim_type", {"claim_type": ClaimType.USER_PREFERENCE}),
            ("scope_level", {"scope_level": ScopeLevel.WORKSPACE}),
            ("scope_key", {"scope_key": "project-beacon"}),
            ("canonical_id", {"canonical_id": "different-canonical"}),
            ("canonical_claim", {"canonical_claim": "project checks use npm test"}),
        ]
        for name, overrides in cases:
            with self.subTest(name=name):
                store = MemoryStore("test-policy")
                store.add_candidate(_candidate("c1", source_ids=["s1"], **overrides))
                second = store.add_candidate(_candidate("c2", source_ids=["s2"], supports=["c1"]))
                self.assertEqual(second.corroboration_count, 0)

    def test_raw_text_variation_counts_when_canonical_claim_matches(self) -> None:
        store = MemoryStore("test-policy")
        store.add_candidate(_candidate("c1", raw_text="Use ./scripts/verify.", source_ids=["s1"]))
        second = store.add_candidate(
            _candidate(
                "c2",
                raw_text="Verification still runs through ./scripts/verify.",
                source_ids=["s2"],
                supports=["c1"],
            )
        )

        self.assertEqual(second.corroboration_count, 1)

    def test_pre_stamped_corroboration_is_not_recomputed(self) -> None:
        store = MemoryStore("test-policy")
        store.add_candidate(_candidate("c1", source_ids=["mirror"]))
        second = store.add_candidate(
            _candidate(
                "c2",
                source_ids=["mirror"],
                supports=["c1"],
                corroboration_count=3,
            )
        )

        self.assertEqual(second.corroboration_count, 3)
        self.assertEqual(
            [
                event
                for event in store.lifecycle_events
                if event.event_type == "candidate_corroboration_counted"
            ],
            [],
        )

    def test_support_free_same_canonical_observations_do_not_auto_corroborate(self) -> None:
        store = MemoryStore("test-policy")
        store.add_candidate(_candidate("c1", source_ids=["s1"]))
        second = store.add_candidate(_candidate("c2", source_ids=["s2"]))

        self.assertEqual(second.corroboration_count, 0)


class FalseCorroborationScenarioTests(unittest.TestCase):
    def _scenario_by_template_id(self, template_id: str, template_mix: str = "mixed", count: int = 2):
        scenarios = generate_false_corroboration_scenarios(count, seed=37, template_mix=template_mix)
        return [scenario for scenario in scenarios if scenario.template_id == template_id][0]

    def test_mixed_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_false_corroboration_scenarios(4, seed=37, template_mix="mixed")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "false_corroboration_clean_independent_v1",
                "false_corroboration_dirty_mirrored_sources_v1",
                "false_corroboration_clean_independent_v1",
                "false_corroboration_dirty_mirrored_sources_v1",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"main"})

    def test_heldout_generation_rotates_clean_and_dirty_templates(self) -> None:
        scenarios = generate_false_corroboration_scenarios(4, seed=37, template_mix="heldout")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "false_corroboration_clean_independent_v2",
                "false_corroboration_dirty_mirrored_sources_v2",
                "false_corroboration_clean_independent_v2",
                "false_corroboration_dirty_mirrored_sources_v2",
            ],
        )
        self.assertEqual({scenario.template_kind for scenario in scenarios}, {"clean", "dirty"})
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"heldout"})

    def test_dirty_template_marks_all_false_candidates_as_forbidden_and_should_not_promote(self) -> None:
        scenario = self._scenario_by_template_id("false_corroboration_dirty_mirrored_sources_v1")
        false_ids = [candidate.candidate_id for candidate in _candidates(scenario)]
        question = [event.question for event in scenario.oracle_events if event.question is not None][0]

        self.assertEqual(len(false_ids), 5)
        self.assertEqual(question.gold_candidate_ids, [])
        self.assertEqual(question.forbidden_candidate_ids, false_ids)
        self.assertEqual(scenario.expected_lifecycle["should_not_promote_candidate_ids"], false_ids)

    def test_support_edges_and_source_ids_encode_independence(self) -> None:
        clean = self._scenario_by_template_id("false_corroboration_clean_independent_v1")
        dirty = self._scenario_by_template_id("false_corroboration_dirty_mirrored_sources_v1")
        clean_candidates = _candidates(clean)
        dirty_candidates = _candidates(dirty)

        self.assertEqual(clean_candidates[-1].supports, [candidate.candidate_id for candidate in clean_candidates[:-1]])
        self.assertEqual(dirty_candidates[-1].supports, [candidate.candidate_id for candidate in dirty_candidates[:-1]])
        self.assertEqual(len({candidate.provenance[0].source_id for candidate in clean_candidates}), 5)
        self.assertEqual(len({candidate.provenance[0].source_id for candidate in dirty_candidates}), 1)

    def test_corroboration_lifecycle_events_cover_follow_up_observations(self) -> None:
        clean = self._scenario_by_template_id("false_corroboration_clean_independent_v1")
        dirty = self._scenario_by_template_id("false_corroboration_dirty_mirrored_sources_v1")

        for scenario in (clean, dirty):
            result = execute_scenario(ConsolidationQueueLite, scenario)
            events = [
                event
                for event in result["store"].lifecycle_events
                if event.event_type == "candidate_corroboration_counted"
            ]

            self.assertEqual(len(events), 4, msg=scenario.template_id)
            if scenario.template_kind == "dirty":
                expected_ignored_ids = scenario.expected_lifecycle["should_not_promote_candidate_ids"][:-1]
                self.assertEqual(events[-1].details["ignored_candidate_ids"], expected_ignored_ids)

    def test_calibration_uses_computed_independent_corroboration(self) -> None:
        clean = self._scenario_by_template_id("false_corroboration_clean_independent_v1")
        dirty = self._scenario_by_template_id("false_corroboration_dirty_mirrored_sources_v1")
        thresholds = merge_thresholds()

        clean_result = execute_scenario(ConsolidationQueueLite, clean)
        dirty_result = execute_scenario(ConsolidationQueueLite, dirty)
        clean_final_id = clean.expected_lifecycle["gold_candidate_id"]
        dirty_final_id = dirty.expected_lifecycle["should_not_promote_candidate_ids"][-1]
        clean_final = clean_result["store"].candidate_memories[clean_final_id]
        dirty_final = dirty_result["store"].candidate_memories[dirty_final_id]

        self.assertLess(clean_final.strength, 0.35)
        self.assertGreaterEqual(clean_final.promotion_score, 0.70)
        self.assertTrue(should_promote_candidate(clean_final, thresholds))
        self.assertFalse(pending_use_allowed(dirty_final, thresholds))
        self.assertFalse(should_promote_candidate(dirty_final, thresholds))

    def test_clean_template_policy_behavior(self) -> None:
        scenario = self._scenario_by_template_id("false_corroboration_clean_independent_v1")
        final_id = scenario.expected_lifecycle["gold_candidate_id"]

        for policy_cls in (
            ReflectionEagerWriteLite,
            ConsolidationQueueLite,
            NaiveEagerWriteLite,
            ScopeBlindTranscriptRAGLite,
        ):
            result = execute_scenario(policy_cls, scenario)
            trace = result["question_traces"][0]
            self.assertEqual(result["metrics"]["answer_correctness"], 1.0, msg=policy_cls.policy_name)
            self.assertEqual(result["metrics"]["false_assertion_rate"], 0.0, msg=policy_cls.policy_name)
            self.assertIn(final_id, trace["resolved_candidate_ids"], msg=policy_cls.policy_name)

        no_memory_result = execute_scenario(NoMemoryLite, scenario)
        self.assertEqual(no_memory_result["metrics"]["answer_correctness"], 0.0)
        self.assertEqual(_failure_types(no_memory_result), {"incorrect_answer"})

    def test_dirty_template_policy_behavior(self) -> None:
        scenario = self._scenario_by_template_id("false_corroboration_dirty_mirrored_sources_v1")
        false_ids = scenario.expected_lifecycle["should_not_promote_candidate_ids"]

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
            premature = _failure_by_type(result, "premature_promotion")
            self.assertEqual(premature["promoted_should_not_promote_candidate_ids"], false_ids)

        self.assertEqual(cq_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(cq_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(cq_result["failure_examples"], [])
        self.assertEqual(no_memory_result["metrics"]["false_assertion_rate"], 0.0)
        self.assertEqual(no_memory_result["failure_examples"], [])
        self.assertEqual(rag_result["metrics"]["false_assertion_rate"], 1.0)
        self.assertEqual(rag_result["metrics"]["premature_promotion_rate"], 0.0)
        self.assertEqual(_failure_types(rag_result), {"false_assertion"})

    def test_false_corroboration_family_artifact_includes_transcript_baseline(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="false_corroboration")
        policy_names = {policy["policy_name"] for policy in artifact["policies"]}

        self.assertEqual(artifact["experiment"], "false_corroboration_oracle")
        self.assertIn("scope_blind_transcript_rag_lite", policy_names)

    def test_false_corroboration_family_accepts_heldout_template_mix(self) -> None:
        artifact = build_run_artifact(4, template_mix="heldout", family="false_corroboration")

        for policy in artifact["policies"]:
            self.assertIn("heldout", policy["summary_by_template_split"], msg=policy["policy_name"])
            self.assertEqual(policy["summary_by_template_split"]["heldout"]["scenario_count"], 4)
            self.assertEqual(
                {
                    "false_corroboration_clean_independent_v2",
                    "false_corroboration_dirty_mirrored_sources_v2",
                },
                set(policy["summary_by_template_id"]),
                msg=policy["policy_name"],
            )

    def test_false_corroboration_family_rejects_unknown_template_mix_upfront(self) -> None:
        with self.assertRaises(ValueError):
            build_run_artifact(1, template_mix="nonexistent", family="false_corroboration")

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main(["--family", "false_corroboration", "--template-mix", "nonexistent"])
        self.assertEqual(raised.exception.code, 2)

    def test_false_corroboration_cli_main_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "false_corroboration.json"
            output_csv = Path(tmpdir) / "false_corroboration.csv"

            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "--family",
                        "false_corroboration",
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

    def test_csv_and_dashboard_include_false_corroboration_details(self) -> None:
        artifact = build_run_artifact(2, template_mix="mixed", family="false_corroboration")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "false_corroboration.json"
            output_csv = Path(tmpdir) / "false_corroboration.csv"
            write_outputs(artifact, output_json, output_csv)

            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertTrue(rows)
        self.assertIn("premature_promotion_rate", rows[0])

        html = render_dashboard(artifact)
        self.assertIn("false_corroboration_dirty_mirrored_sources_v1", html)
        self.assertIn("forbidden_false_corroboration_candidate_asserted", html)
        self.assertIn("false_corroboration_stack_promoted", html)
        self.assertIn("candidate_corroboration_counted", html)
        self.assertIn("counted_source_ids", html)
        self.assertIn("duplicate_source_ids", html)
        self.assertIn("capped_source_ids", html)
        self.assertIn("ignored_source_ids", html)
        self.assertIn("mirrored-", html)


if __name__ == "__main__":
    unittest.main()
