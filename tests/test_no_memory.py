from datetime import datetime, timedelta
import unittest

from cq.memory.no_memory import NoMemoryLite
from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
from cq.schemas.scenario import QuestionSpec


def make_world_fact_candidate(
    candidate_id: str,
    canonical_id: str,
    claim: str,
    minute_offset: int,
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
                trust_score=0.75,
                observed_at=observed_at,
            )
        ],
        verification_score=0.75,
        created_at=observed_at,
        updated_at=observed_at,
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


class NoMemoryLiteTests(unittest.TestCase):
    def test_observation_is_ignored_without_creating_memory(self) -> None:
        policy = NoMemoryLite()
        candidate = make_world_fact_candidate(
            candidate_id="candidate-1",
            canonical_id="acme-northstar-status",
            claim="Acme acquired Northstar",
            minute_offset=0,
        )

        policy.observe_candidate(candidate)

        self.assertEqual(policy.store.candidate_memories, {})
        self.assertEqual(policy.store.durable_memories, {})
        self.assertEqual(len(policy.store.lifecycle_events), 1)
        self.assertEqual(policy.store.lifecycle_events[0].event_type, "observation_ignored")

    def test_answers_are_always_empty_memory_answers(self) -> None:
        policy = NoMemoryLite()

        trace = policy.answer_question(
            make_question("question-1", "What happened to Northstar?", "acme-northstar-status", 1)
        )

        self.assertEqual(trace.resolved_candidate_ids, [])
        self.assertEqual(trace.used_memory_ids, [])
        self.assertFalse(trace.used_pending)
        self.assertEqual(trace.answer_text, "No memory available.")
        self.assertEqual(policy.store.lifecycle_events[-1].event_type, "answer_generated")


if __name__ == "__main__":
    unittest.main()
