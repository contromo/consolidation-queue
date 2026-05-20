from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.memory.cq_pending_multi_evidence import CQPendingMultiEvidence
from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
from cq.schemas.scenario import QuestionSpec


def _candidate(
    candidate_id: str,
    *,
    strength: float,
    minutes: int = 0,
    canonical_id: str = "slot-shared",
    canonical_claim: str | None = None,
    scope_level: ScopeLevel = ScopeLevel.PROJECT,
    scope_key: str = "project:alpha",
    source_id: str | None = None,
    contradicts: list[str] | None = None,
) -> CandidateUpdate:
    timestamp = datetime(2026, 5, 20, 9, 0, 0) + timedelta(minutes=minutes)
    claim = canonical_claim or "Preferred command is make test"
    return CandidateUpdate(
        candidate_id=candidate_id,
        raw_text=claim,
        raw_claim=claim,
        canonical_claim=claim,
        canonical_id=canonical_id,
        claim_type=ClaimType.PROCEDURAL_KNOWLEDGE,
        scope_level=scope_level,
        scope_key=scope_key,
        provenance=[
            ProvenanceRecord(
                source_kind="unit_test",
                source_id=source_id or "source-{}".format(candidate_id),
                trust_score=strength,
                observed_at=timestamp,
            )
        ],
        verification_score=strength,
        created_at=timestamp,
        updated_at=timestamp,
        contradicts=list(contradicts or []),
    )


def _question(
    *,
    canonical_id: str = "slot-shared",
    scope_level: ScopeLevel = ScopeLevel.PROJECT,
    scope_key: str = "project:alpha",
) -> QuestionSpec:
    return QuestionSpec(
        question_id="q1",
        text="What command should I use?",
        relevant_canonical_id=canonical_id,
        scope_level=scope_level,
        scope_key=scope_key,
        phase="eval",
        gold_candidate_ids=[],
        forbidden_candidate_ids=[],
        asked_at=datetime(2026, 5, 20, 10, 0, 0),
    )


class CQPendingMultiEvidenceTests(unittest.TestCase):
    def test_base_cq_returns_one_pending_candidate_but_variant_returns_all_eligible(self) -> None:
        candidates = [
            _candidate("c1", strength=0.55, minutes=0),
            _candidate("c2", strength=0.62, minutes=1),
        ]
        base = ConsolidationQueueLite()
        variant = CQPendingMultiEvidence()
        for candidate in candidates:
            base.observe_candidate(candidate)
            variant.observe_candidate(candidate)

        base_trace = base.answer_question(_question())
        variant_trace = variant.answer_question(_question())

        self.assertEqual(base_trace.resolved_candidate_ids, ["c2"])
        self.assertEqual(variant_trace.resolved_candidate_ids, ["c2", "c1"])
        self.assertTrue(variant_trace.used_pending)

    def test_variant_preserves_base_behavior_when_durable_memory_exists(self) -> None:
        candidate = _candidate("durable", strength=0.80)
        base = ConsolidationQueueLite()
        variant = CQPendingMultiEvidence()
        base.observe_candidate(candidate)
        variant.observe_candidate(candidate)

        base_trace = base.answer_question(_question())
        variant_trace = variant.answer_question(_question())

        self.assertEqual(base_trace.resolved_candidate_ids, ["durable"])
        self.assertEqual(variant_trace.resolved_candidate_ids, ["durable"])
        self.assertEqual(variant_trace.used_memory_ids, base_trace.used_memory_ids)


if __name__ == "__main__":
    unittest.main()
