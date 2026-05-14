import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.component_eval import load_predictions_by_scenario, oracle_component_predictions
from cq.eval.extracted_candidate_runner import (
    LOCKED_EPOCH,
    LOCKED_MODEL_DIGEST,
    LOCKED_MODEL_TAG,
    LOCKED_PROMPT_SHA256,
    NoisyPolicyComparisonError,
    adapt_predictions_for_scenario,
    build_extracted_run_artifact,
    candidate_stream_canonical_json,
    candidate_stream_hash_mismatches,
    live_adapter_sha256,
    policies_use_memory_store,
    validate_adapter_pin,
    validate_prediction_payload,
)
from cq.memory.consolidation_queue import (
    CQNoContestationDemotion,
    CQNoPendingLookupUse,
    CQNoSourceIndependenceGate,
    CQNoWiderScopePendingOverride,
    ConsolidationQueueLite,
)
from cq.memory.mem0_lite import Mem0Lite
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.memory.substrate import MemoryStore
from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel, jsonable
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario, ScenarioEvent, TaskFamily
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "extracted_candidate_adapter_fixture.json"


def _candidate(candidate_id: str, canonical_id: str, *, contradicts=None) -> CandidateUpdate:
    return CandidateUpdate(
        candidate_id=candidate_id,
        raw_text="raw " + candidate_id,
        raw_claim="claim " + candidate_id,
        canonical_claim=canonical_id,
        canonical_id=canonical_id,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key="project-alpha",
        created_at=LOCKED_EPOCH,
        updated_at=LOCKED_EPOCH,
        provenance=[
            ProvenanceRecord(
                source_kind="oracle",
                source_id="oracle::" + candidate_id,
                trust_score=0.9,
                observed_at=LOCKED_EPOCH,
            )
        ],
        verification_score=0.9,
        contradicts=list(contradicts or []),
    )


def _adapter_fixture_scenario(scenario_id: str = "adapter_fixture") -> Scenario:
    old_id = "oracle-old"
    new_id = "oracle-new"
    empty_id = "oracle-empty"
    question = QuestionSpec(
        question_id=scenario_id + "-question-1",
        text="How should project alpha deploy?",
        relevant_canonical_id="project-alpha-deploy-command",
        scope_level=ScopeLevel.PROJECT,
        scope_key="project-alpha",
        phase="after_contradiction",
        gold_candidate_ids=[new_id],
        forbidden_candidate_ids=[old_id],
        asked_at=LOCKED_EPOCH,
    )
    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description="adapter fixture",
        latent_truth_graph={},
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text="First deploy statement.",
                candidate=_candidate(old_id, "project-alpha-deploy-command"),
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text="Contradicting deploy statement.",
                candidate=_candidate(
                    new_id,
                    "project-alpha-deploy-command",
                    contradicts=[old_id],
                ),
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text="Malformed raw claim source.",
                candidate=_candidate(empty_id, "project-alpha-empty-raw"),
            ),
            ScenarioEvent(
                event_id=scenario_id + "-question-1",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=question.text,
                question=question,
            ),
        ],
        expected_lifecycle={
            "old_candidate_id": old_id,
            "new_candidate_id": new_id,
            "contradiction_timestamp": LOCKED_EPOCH.isoformat(),
            "should_not_promote_candidate_ids": [old_id],
        },
        template_id="adapter_fixture_template",
        template_kind="dirty",
        template_split="heldout",
    )


class ExtractedCandidateRunnerTests(unittest.TestCase):
    def test_adapter_contract_spot_check_fixture(self) -> None:
        predictions = load_predictions_by_scenario(FIXTURE_PATH)["adapter_fixture"]
        adapted = adapt_predictions_for_scenario(_adapter_fixture_scenario(), predictions)

        self.assertEqual(
            [candidate.candidate_id for candidate in adapted.candidates],
            [
                "adapter_fixture::adapter_fixture-event-1::0",
                "adapter_fixture::adapter_fixture-event-1::1",
                "adapter_fixture::adapter_fixture-event-2::0",
            ],
        )
        self.assertEqual(
            [drop["reason"] for drop in adapted.drops],
            [
                "duplicate_within_event",
                "invalid_confidence",
                "empty_raw_claim",
                "unknown_or_non_observation_event",
            ],
        )
        self.assertEqual(adapted.input_prediction_count, 7)

        first, second, third = adapted.candidates
        self.assertEqual(first.raw_text, "First deploy statement.")
        self.assertEqual(first.raw_claim, "Project alpha deploys with make deploy.")
        self.assertEqual(first.canonical_claim, first.canonical_id)
        self.assertEqual(first.verification_score, 0.5)
        self.assertEqual(first.provenance[0].source_id, "extractor::adapter_fixture::adapter_fixture-event-1")
        self.assertEqual(first.created_at.isoformat(), "2026-01-01T00:00:01+00:00")

        self.assertEqual(second.canonical_id, "project-alpha-deploy-reviewer")
        self.assertEqual(second.verification_score, 0.8)
        self.assertEqual(third.verification_score, 0.7)
        self.assertEqual(
            third.contradicts,
            [
                "adapter_fixture::adapter_fixture-event-1::0",
                "adapter_fixture::adapter_fixture-event-1::1",
            ],
        )
        self.assertEqual(third.supports, ["adapter_fixture::adapter_fixture-event-1::0"])

        expected_stream = [
            {
                "candidate_id": "adapter_fixture::adapter_fixture-event-1::0",
                "raw_text": "First deploy statement.",
                "raw_claim": "Project alpha deploys with make deploy.",
                "canonical_claim": "project-alpha-deploy-command",
                "claim_type": "project_convention",
                "scope_level": "project",
                "scope_key": "project-alpha",
                "canonical_id": "project-alpha-deploy-command",
                "verification_score": 0.5,
                "contradicts": [],
                "supports": [],
            },
            {
                "candidate_id": "adapter_fixture::adapter_fixture-event-1::1",
                "raw_text": "First deploy statement.",
                "raw_claim": "Project alpha deploys need Morgan's review.",
                "canonical_claim": "project-alpha-deploy-reviewer",
                "claim_type": "project_convention",
                "scope_level": "project",
                "scope_key": "project-alpha",
                "canonical_id": "project-alpha-deploy-reviewer",
                "verification_score": 0.8,
                "contradicts": [],
                "supports": [],
            },
            {
                "candidate_id": "adapter_fixture::adapter_fixture-event-2::0",
                "raw_text": "Contradicting deploy statement.",
                "raw_claim": "Project alpha now deploys with ./ship.sh.",
                "canonical_claim": "project-alpha-deploy-command",
                "claim_type": "project_convention",
                "scope_level": "project",
                "scope_key": "project-alpha",
                "canonical_id": "project-alpha-deploy-command",
                "verification_score": 0.7,
                "contradicts": [
                    "adapter_fixture::adapter_fixture-event-1::0",
                    "adapter_fixture::adapter_fixture-event-1::1",
                ],
                "supports": ["adapter_fixture::adapter_fixture-event-1::0"],
            },
        ]
        observed_subset = [
            {
                key: jsonable(candidate)[key]
                for key in expected_stream[index]
            }
            for index, candidate in enumerate(adapted.candidates)
        ]
        self.assertEqual(observed_subset, expected_stream)

    def test_adapter_is_deterministic(self) -> None:
        predictions = load_predictions_by_scenario(FIXTURE_PATH)["adapter_fixture"]
        scenario = _adapter_fixture_scenario()

        first = adapt_predictions_for_scenario(scenario, predictions)
        second = adapt_predictions_for_scenario(scenario, predictions)

        self.assertEqual(
            candidate_stream_canonical_json(first.candidates),
            candidate_stream_canonical_json(second.candidates),
        )
        self.assertEqual(first.candidate_stream_sha256, second.candidate_stream_sha256)

    def test_scenario_error_propagates_empty_stream(self) -> None:
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        scenario_error = payload["scenario_errors"]["adapter_error"]

        adapted = adapt_predictions_for_scenario(
            _adapter_fixture_scenario("adapter_error"),
            [],
            scenario_error=scenario_error,
        )

        self.assertEqual(adapted.candidates, [])
        self.assertEqual(adapted.scenario_error, scenario_error)
        self.assertEqual(adapted.input_prediction_count, 0)

    def test_stream_hash_equality_across_policies(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="clean")[0]
        predictions_by_scenario = {
            scenario.scenario_id: oracle_component_predictions(scenario),
        }
        policies = [
            ReflectionEagerWriteLite,
            ConsolidationQueueLite,
            CQNoContestationDemotion,
            CQNoWiderScopePendingOverride,
            CQNoPendingLookupUse,
            CQNoSourceIndependenceGate,
            Mem0Lite,
        ]

        artifact = build_extracted_run_artifact(
            scenarios=[scenario],
            policy_classes=policies,
            predictions_by_scenario=predictions_by_scenario,
            scenario_errors={},
            family="forced_contradiction",
            requested_scenario_count=1,
            template_mix="clean",
            policy_set="phase2_5",
            schema_profile="default",
        )

        self.assertTrue(artifact["candidate_stream_hash_invariant_passed"])
        self.assertEqual(artifact["candidate_stream_hash_mismatches"], [])
        self.assertEqual(
            artifact["candidate_stream_audit"][0]["adapter_drop_count"],
            0,
        )
        self.assertEqual(
            artifact["candidate_stream_audit"][0]["input_prediction_count"],
            len(predictions_by_scenario[scenario.scenario_id]),
        )
        self.assertEqual(
            candidate_stream_hash_mismatches(artifact["candidate_stream_sha256_by_policy"]),
            [],
        )

    def test_substrate_isolation_keeps_input_stream_immutable(self) -> None:
        predictions = load_predictions_by_scenario(FIXTURE_PATH)["adapter_fixture"]
        adapted = adapt_predictions_for_scenario(_adapter_fixture_scenario(), predictions)
        before = candidate_stream_canonical_json(adapted.candidates)

        store_a = MemoryStore("a")
        store_b = MemoryStore("b")
        store_a.add_candidate(adapted.candidates[0])
        store_a.candidate_memories[adapted.candidates[0].candidate_id].raw_claim = "mutated"
        store_b.add_candidate(adapted.candidates[0])

        self.assertEqual(candidate_stream_canonical_json(adapted.candidates), before)
        self.assertEqual(
            store_b.candidate_memories[adapted.candidates[0].candidate_id].raw_claim,
            "Project alpha deploys with make deploy.",
        )

    def test_digest_and_adapter_version_provenance_reject_mismatches(self) -> None:
        good_payload = {
            "model_id": LOCKED_MODEL_TAG,
            "model_digest": LOCKED_MODEL_DIGEST,
            "prompt_template_sha256": LOCKED_PROMPT_SHA256,
            "family": "forced_contradiction",
            "model_diagnostics": {"schema_profile": "default"},
        }
        validate_prediction_payload(
            good_payload,
            family="forced_contradiction",
            schema_profile="default",
        )
        bad_payload = dict(good_payload)
        bad_payload["model_digest"] = "sha256:bad"
        with self.assertRaises(NoisyPolicyComparisonError):
            validate_prediction_payload(
                bad_payload,
                family="forced_contradiction",
                schema_profile="default",
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            pin_path = Path(tmpdir) / "pin.json"
            pin_path.write_text(
                json.dumps(
                    {
                        "candidate_adapter_sha256": "0" * 64,
                        "preregistration_lock_sha256": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(NoisyPolicyComparisonError):
                validate_adapter_pin(pin_path=pin_path)
        self.assertEqual(len(live_adapter_sha256()), 64)

    def test_policies_use_memory_store_class(self) -> None:
        self.assertTrue(
            policies_use_memory_store(
                [
                    ReflectionEagerWriteLite,
                    ConsolidationQueueLite,
                    Mem0Lite,
                ]
            )
        )

    def test_independent_corroboration_round_trip(self) -> None:
        predictions = load_predictions_by_scenario(FIXTURE_PATH)["adapter_fixture"]
        adapted = adapt_predictions_for_scenario(_adapter_fixture_scenario(), predictions)
        store = MemoryStore("roundtrip")

        for candidate in adapted.candidates:
            store.add_candidate(candidate)

        third = store.candidate_memories["adapter_fixture::adapter_fixture-event-2::0"]
        self.assertEqual(third.supports, ["adapter_fixture::adapter_fixture-event-1::0"])
        self.assertGreater(third.corroboration_count, 0)


if __name__ == "__main__":
    unittest.main()
