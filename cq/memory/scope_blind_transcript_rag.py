from __future__ import annotations

from typing import List, Optional

from cq.memory.substrate import MemoryStore
from cq.schemas.memory import AnswerTrace, CandidateUpdate
from cq.schemas.scenario import QuestionSpec


class ScopeBlindTranscriptRAGLite:
    """Oracle-id recency baseline that intentionally ignores scope.

    This is not lexical or embedding retrieval. It is the oracle-mode stand-in
    for transcript RAG so scope failures are inspectable before noisy retrieval.
    """

    policy_name = "scope_blind_transcript_rag_lite"

    def __init__(self) -> None:
        self.store = MemoryStore(self.policy_name)

    def observe_candidate(self, candidate: CandidateUpdate) -> None:
        self.store.add_candidate(candidate)

    def answer_question(self, question: QuestionSpec) -> AnswerTrace:
        candidate = self._newest_candidate_for_canonical(question.relevant_canonical_id)
        resolved_candidate_ids: List[str] = []
        answer_text = "No transcript match available."
        if candidate is not None:
            resolved_candidate_ids = [candidate.candidate_id]
            answer_text = "[transcript-recency] {} (scope {}:{})".format(
                candidate.canonical_claim,
                candidate.scope_level.value,
                candidate.scope_key,
            )
        trace = AnswerTrace(
            answer_id="answer-" + question.question_id,
            question_id=question.question_id,
            query=question.text,
            relevant_canonical_id=question.relevant_canonical_id,
            scope_level=question.scope_level,
            scope_key=question.scope_key,
            resolved_candidate_ids=resolved_candidate_ids,
            used_memory_ids=[],
            answer_text=answer_text,
            used_pending=False,
            created_at=question.asked_at,
        )
        self.store.log_event(
            "answer_generated",
            "question",
            question.question_id,
            {
                "resolved_candidate_ids": resolved_candidate_ids,
                "used_memory_ids": [],
                "used_pending": False,
                "retrieval_mode": "scope_blind_oracle_id_recency",
            },
            question.asked_at,
        )
        return trace

    def _newest_candidate_for_canonical(self, canonical_id: str) -> Optional[CandidateUpdate]:
        candidate_ids = self.store.canonical_clusters.get(canonical_id, [])
        candidates = [self.store.candidate_memories[candidate_id] for candidate_id in candidate_ids]
        if not candidates:
            return None
        candidates.sort(key=lambda candidate: candidate.updated_at, reverse=True)
        return candidates[0]
