from datetime import datetime, timedelta
import unittest

from cq.memory.mem0_lite import Mem0Lite
from cq.schemas.memory import CandidateUpdate, ClaimType, MemoryState, ProvenanceRecord, ScopeLevel
from cq.schemas.scenario import QuestionSpec


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


def make_question(question_id: str, text: str, canonical_id: str, minute_offset: int) -> QuestionSpec:
    asked_at = datetime(2026, 1, 1, 9, 0, 0) + timedelta(minutes=minute_offset)
    return QuestionSpec(
        question_id=question_id,
        text=text,
        relevant_canonical_id=canonical_id,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        phase="test",
        gold_candidate_ids=[],
        forbidden_candidate_ids=[],
        asked_at=asked_at,
    )


class Mem0LiteTests(unittest.TestCase):
    def test_add_promotes_candidate_that_clears_write_confidence(self) -> None:
        policy = Mem0Lite()
        candidate = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id="acme-northstar-status",
            claim="Acme acquired Northstar",
            minute_offset=0,
            trust_score=0.62,
            verification_score=0.62,
        )

        policy.observe_candidate(candidate)

        durable = policy.store.active_durable("acme-northstar-status", ScopeLevel.WORLD_GLOBAL, "global")
        self.assertIsNotNone(durable)
        self.assertEqual(durable.created_from_candidate_ids, ["candidate-1"])
        self.assertEqual(
            policy.store.candidate_memories["candidate-1"].state,
            MemoryState.PROMOTED,
        )

    def test_low_confidence_add_is_noop_and_stays_non_durable(self) -> None:
        policy = Mem0Lite()
        candidate = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id="helios-summit-status",
            claim="Helios acquired Summit",
            minute_offset=0,
            trust_score=0.54,
            verification_score=0.54,
        )

        policy.observe_candidate(candidate)

        durable = policy.store.active_durable("helios-summit-status", ScopeLevel.WORLD_GLOBAL, "global")
        self.assertIsNone(durable)
        self.assertEqual(
            policy.store.candidate_memories["candidate-1"].state,
            MemoryState.PENDING,
        )

    def test_does_not_answer_from_pending_candidate(self) -> None:
        policy = Mem0Lite()
        canonical_id = "lattice-pioneer-status"
        candidate = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id=canonical_id,
            claim="Lattice acquired Pioneer",
            minute_offset=0,
            trust_score=0.54,
            verification_score=0.54,
        )
        policy.observe_candidate(candidate)

        trace = policy.answer_question(
            make_question("question-1", "What should we believe?", canonical_id, 1)
        )

        self.assertEqual(trace.resolved_candidate_ids, [])
        self.assertEqual(trace.used_memory_ids, [])
        self.assertFalse(trace.used_pending)

    def test_contradictory_update_overwrites_without_margin_check(self) -> None:
        policy = Mem0Lite()
        canonical_id = "aster-keystone-status"
        old = make_world_fact_candidate(
            candidate_id="candidate-old",
            canonical_id=canonical_id,
            claim="Aster acquired Keystone",
            minute_offset=0,
            trust_score=0.90,
            verification_score=0.90,
        )
        new = make_world_fact_candidate(
            candidate_id="candidate-new",
            canonical_id=canonical_id,
            claim="Aster did not acquire Keystone",
            minute_offset=1,
            trust_score=0.56,
            verification_score=0.56,
            contradicts=["candidate-old"],
        )

        policy.observe_candidate(old)
        policy.observe_candidate(new)

        old_durable = policy.store.durable_memories["memory-candidate-old"]
        new_durable = policy.store.durable_memories["memory-candidate-new"]
        self.assertFalse(old_durable.active)
        self.assertTrue(new_durable.active)
        self.assertEqual(new_durable.created_from_candidate_ids, ["candidate-new"])

    def test_low_confidence_contradiction_is_contested_without_demoting_durable(self) -> None:
        policy = Mem0Lite()
        canonical_id = "brightline-redwood-status"
        old = make_world_fact_candidate(
            candidate_id="candidate-old",
            canonical_id=canonical_id,
            claim="Brightline acquired Redwood",
            minute_offset=0,
            trust_score=0.90,
            verification_score=0.90,
        )
        new = make_world_fact_candidate(
            candidate_id="candidate-new",
            canonical_id=canonical_id,
            claim="Brightline did not acquire Redwood",
            minute_offset=1,
            trust_score=0.54,
            verification_score=0.54,
            contradicts=["candidate-old"],
        )

        policy.observe_candidate(old)
        policy.observe_candidate(new)

        durable = policy.store.active_durable(canonical_id, ScopeLevel.WORLD_GLOBAL, "global")
        self.assertIsNotNone(durable)
        self.assertEqual(durable.created_from_candidate_ids, ["candidate-old"])
        self.assertEqual(
            policy.store.candidate_memories["candidate-old"].state,
            MemoryState.PROMOTED,
        )
        self.assertEqual(
            policy.store.candidate_memories["candidate-new"].state,
            MemoryState.CONTESTED,
        )

    def test_matching_update_reinforces_existing_durable(self) -> None:
        policy = Mem0Lite()
        canonical_id = "vertex-harbor-status"
        first = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id=canonical_id,
            claim="Vertex acquired Harbor",
            minute_offset=0,
            trust_score=0.62,
            verification_score=0.62,
        )
        second = make_world_fact_candidate(
            candidate_id="candidate-2",
            canonical_id=canonical_id,
            claim="Vertex acquired Harbor",
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


if __name__ == "__main__":
    unittest.main()
