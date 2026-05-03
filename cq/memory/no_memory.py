from __future__ import annotations

from cq.memory.substrate import MemoryStore
from cq.schemas.memory import AnswerTrace, CandidateUpdate
from cq.schemas.scenario import QuestionSpec


class NoMemoryLite:
    policy_name = "no_memory_lite"
    is_floor_baseline = True

    def __init__(self) -> None:
        self.store = MemoryStore(self.policy_name)

    def observe_candidate(self, candidate: CandidateUpdate) -> None:
        self.store.log_event(
            "observation_ignored",
            "candidate",
            candidate.candidate_id,
            {
                "canonical_id": candidate.canonical_id,
                "claim": candidate.canonical_claim,
                "reason": "no memory baseline",
            },
            candidate.created_at,
        )

    def answer_question(self, question: QuestionSpec) -> AnswerTrace:
        trace = AnswerTrace(
            answer_id="answer-" + question.question_id,
            question_id=question.question_id,
            query=question.text,
            relevant_canonical_id=question.relevant_canonical_id,
            scope_level=question.scope_level,
            scope_key=question.scope_key,
            resolved_candidate_ids=[],
            used_memory_ids=[],
            answer_text="No memory available.",
            used_pending=False,
            created_at=question.asked_at,
        )
        self.store.log_event(
            "answer_generated",
            "question",
            question.question_id,
            {
                "resolved_candidate_ids": [],
                "used_memory_ids": [],
                "used_pending": False,
            },
            question.asked_at,
        )
        return trace
