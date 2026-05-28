from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.memory.reflection_eager_write_cardinality_capped import ReflectionEagerWriteCardinalityCapped
from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
from cq.schemas.scenario import QuestionSpec


def _candidate(candidate_id: str, *, strength: float, minutes: int) -> CandidateUpdate:
    timestamp = datetime(2026, 5, 20, 9, 0, 0) + timedelta(minutes=minutes)
    return CandidateUpdate(
        candidate_id=candidate_id,
        raw_text="Use command {}".format(candidate_id),
        raw_claim="Use command {}".format(candidate_id),
        canonical_claim="Use the local test command",
        canonical_id="slot-shared",
        claim_type=ClaimType.PROCEDURAL_KNOWLEDGE,
        scope_level=ScopeLevel.PROJECT,
        scope_key="project:alpha",
        provenance=[
            ProvenanceRecord(
                source_kind="unit_test",
                source_id="source-{}".format(candidate_id),
                trust_score=strength,
                observed_at=timestamp,
            )
        ],
        verification_score=strength,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _question() -> QuestionSpec:
    return QuestionSpec(
        question_id="q-reflection",
        text="What should I use?",
        relevant_canonical_id="slot-shared",
        scope_level=ScopeLevel.PROJECT,
        scope_key="project:alpha",
        phase="eval",
        gold_candidate_ids=[],
        forbidden_candidate_ids=[],
        asked_at=datetime(2026, 5, 20, 10, 0, 0),
    )


class ReflectionEagerWriteCardinalityCappedTests(unittest.TestCase):
    def test_capped_reflection_writes_normally_but_returns_one_candidate(self) -> None:
        candidates = [
            _candidate("first", strength=0.55, minutes=0),
            _candidate("second", strength=0.66, minutes=1),
        ]
        base = ReflectionEagerWriteLite()
        capped = ReflectionEagerWriteCardinalityCapped()
        for candidate in candidates:
            base.observe_candidate(candidate)
            capped.observe_candidate(candidate)

        base_trace = base.answer_question(_question())
        capped_trace = capped.answer_question(_question())

        self.assertEqual(base_trace.resolved_candidate_ids, ["first", "second"])
        self.assertEqual(capped_trace.resolved_candidate_ids, ["second"])
        base_durable = list(base.store.durable_memories.values())[0]
        capped_durable = list(capped.store.durable_memories.values())[0]
        self.assertEqual(capped_durable.created_from_candidate_ids, base_durable.created_from_candidate_ids)
        self.assertEqual(capped_trace.used_memory_ids, [capped_durable.memory_id])


if __name__ == "__main__":
    unittest.main()
