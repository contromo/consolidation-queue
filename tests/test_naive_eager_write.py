from datetime import datetime, timedelta
import unittest

from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
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


class NaiveEagerWriteTests(unittest.TestCase):
    def test_first_candidate_promotes_immediately(self) -> None:
        policy = NaiveEagerWriteLite()
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
        self.assertGreaterEqual(durable.confidence, 0.62)

    def test_supporting_candidate_reinforces_existing_durable(self) -> None:
        policy = NaiveEagerWriteLite()
        canonical_id = "helios-summit-status"
        first = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id=canonical_id,
            claim="Helios acquired Summit",
            minute_offset=0,
            trust_score=0.62,
            verification_score=0.62,
        )
        second = make_world_fact_candidate(
            candidate_id="candidate-2",
            canonical_id=canonical_id,
            claim="Helios acquired Summit",
            minute_offset=1,
            trust_score=0.66,
            verification_score=0.66,
        )

        policy.observe_candidate(first)
        policy.observe_candidate(second)

        durable = policy.store.active_durable(canonical_id, ScopeLevel.WORLD_GLOBAL, "global")
        self.assertIsNotNone(durable)
        self.assertEqual(durable.created_from_candidate_ids, ["candidate-1", "candidate-2"])
        self.assertGreater(durable.confidence, 0.62)

    def test_contradictory_candidate_promotes_second_durable_without_demoting_first(self) -> None:
        policy = NaiveEagerWriteLite()
        canonical_id = "lattice-pioneer-status"
        first = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id=canonical_id,
            claim="Lattice acquired Pioneer",
            minute_offset=0,
            trust_score=0.90,
            verification_score=0.90,
        )
        second = make_world_fact_candidate(
            candidate_id="candidate-2",
            canonical_id=canonical_id,
            claim="Lattice did not acquire Pioneer",
            minute_offset=1,
            trust_score=0.80,
            verification_score=0.80,
            contradicts=["candidate-1"],
        )

        policy.observe_candidate(first)
        policy.observe_candidate(second)

        active = [durable for durable in policy.store.durable_memories.values() if durable.active]
        self.assertEqual(len(active), 2)
        self.assertEqual({durable.claim for durable in active}, {"Lattice acquired Pioneer", "Lattice did not acquire Pioneer"})

    def test_answer_selection_is_confidence_first_not_recency_first(self) -> None:
        policy = NaiveEagerWriteLite()
        canonical_id = "aster-keystone-status"
        old = make_world_fact_candidate(
            candidate_id="candidate-old",
            canonical_id=canonical_id,
            claim="Aster acquired Keystone",
            minute_offset=0,
            trust_score=0.93,
            verification_score=0.93,
        )
        new = make_world_fact_candidate(
            candidate_id="candidate-new",
            canonical_id=canonical_id,
            claim="Aster did not acquire Keystone",
            minute_offset=30,
            trust_score=0.90,
            verification_score=0.90,
            contradicts=["candidate-old"],
        )

        policy.observe_candidate(old)
        policy.observe_candidate(new)

        trace = policy.answer_question(
            make_question("question-1", "What should we believe now?", canonical_id, 31)
        )

        self.assertEqual(trace.resolved_candidate_ids, ["candidate-old"])
        self.assertEqual(trace.used_memory_ids, ["memory-candidate-old"])
        self.assertFalse(trace.used_pending)


if __name__ == "__main__":
    unittest.main()
