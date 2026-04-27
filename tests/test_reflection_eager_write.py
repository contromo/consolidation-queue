from datetime import datetime, timedelta
import unittest

from cq.eval.end_to_end_eval import execute_scenario
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.schemas.memory import CandidateUpdate, ClaimType, MemoryState, ProvenanceRecord, ScopeLevel
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


def make_world_fact_candidate(
    candidate_id: str,
    canonical_id: str,
    claim: str,
    minute_offset: int,
    trust_score: float,
    verification_score: float,
    contradicts=None,
) -> CandidateUpdate:
    observed_at = datetime(2026, 1, 1, 9, 0, 0) + timedelta(minutes=minute_offset)
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=claim,
        raw_claim=claim,
        canonical_claim=claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        provenance=[
            ProvenanceRecord(
                source_kind="test",
                source_id="source-" + candidate_id,
                trust_score=trust_score,
                observed_at=observed_at,
            )
        ],
        verification_score=verification_score,
        created_at=observed_at,
        updated_at=observed_at,
        contradicts=contradicts or [],
    )


class ReflectionEagerWriteTests(unittest.TestCase):
    def test_immediate_write_then_overwrite_on_stronger_contradiction(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, seed=2)[0]
        result = execute_scenario(ReflectionEagerWriteLite, scenario)
        snapshot = result["store_snapshot"]

        old_candidate_id = scenario.expected_lifecycle["old_candidate_id"]
        new_candidate_id = scenario.expected_lifecycle["new_candidate_id"]

        active_old = [
            memory
            for memory in snapshot["durable_memories"]
            if old_candidate_id in memory["created_from_candidate_ids"] and memory["active"]
        ]
        active_new = [
            memory
            for memory in snapshot["durable_memories"]
            if new_candidate_id in memory["created_from_candidate_ids"] and memory["active"]
        ]

        self.assertEqual(active_old, [])
        self.assertEqual(len(active_new), 1)
        self.assertEqual(result["metrics"]["false_assertion_after_contradiction"], 0.0)

    def test_supporting_candidate_reinforces_existing_durable_memory(self) -> None:
        policy = ReflectionEagerWriteLite()
        canonical_id = "acme-northstar-status"

        first = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id=canonical_id,
            claim="Acme acquired Northstar",
            minute_offset=0,
            trust_score=0.62,
            verification_score=0.62,
        )
        second = make_world_fact_candidate(
            candidate_id="candidate-2",
            canonical_id=canonical_id,
            claim="Acme acquired Northstar",
            minute_offset=1,
            trust_score=0.66,
            verification_score=0.66,
        )

        policy.observe_candidate(first)
        policy.observe_candidate(second)

        durable = policy.store.active_durable(canonical_id, ScopeLevel.WORLD_GLOBAL, "global")
        self.assertIsNotNone(durable)
        self.assertEqual(durable.created_from_candidate_ids, ["candidate-1", "candidate-2"])
        self.assertEqual(
            policy.store.candidate_memories["candidate-2"].state,
            MemoryState.CORROBORATED,
        )
        self.assertGreater(durable.confidence, 0.62)

    def test_weaker_contradictory_candidate_is_contested_not_promoted(self) -> None:
        policy = ReflectionEagerWriteLite()
        canonical_id = "helios-summit-status"

        first = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id=canonical_id,
            claim="Helios acquired Summit",
            minute_offset=0,
            trust_score=0.82,
            verification_score=0.82,
        )
        second = make_world_fact_candidate(
            candidate_id="candidate-2",
            canonical_id=canonical_id,
            claim="Helios did not acquire Summit",
            minute_offset=1,
            trust_score=0.60,
            verification_score=0.60,
            contradicts=["candidate-1"],
        )

        policy.observe_candidate(first)
        policy.observe_candidate(second)

        durable = policy.store.active_durable(canonical_id, ScopeLevel.WORLD_GLOBAL, "global")
        self.assertIsNotNone(durable)
        self.assertEqual(durable.created_from_candidate_ids, ["candidate-1"])
        self.assertEqual(
            policy.store.candidate_memories["candidate-2"].state,
            MemoryState.CONTESTED,
        )
        self.assertNotIn("candidate-2", durable.created_from_candidate_ids)


if __name__ == "__main__":
    unittest.main()
