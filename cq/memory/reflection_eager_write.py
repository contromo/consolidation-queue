from __future__ import annotations

from typing import Dict, Optional

from cq.memory.lifecycle import merge_thresholds
from cq.memory.substrate import MemoryStore
from cq.schemas.memory import AnswerTrace, CandidateUpdate, MemoryState
from cq.schemas.scenario import QuestionSpec


class ReflectionEagerWriteLite:
    policy_name = "reflection_eager_write_lite"

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = merge_thresholds(thresholds)
        self.store = MemoryStore(self.policy_name)

    def observe_candidate(self, candidate: CandidateUpdate) -> None:
        stored = self.store.add_candidate(candidate)
        active = self.store.active_durable(stored.canonical_id, stored.scope_level, stored.scope_key)

        if active is None:
            self.store.promote_candidate(
                stored.candidate_id,
                max(stored.strength, self.thresholds["minimum_write_confidence"]),
                "immediate reflection write",
                stored.updated_at,
            )
            return

        contradicts_active = any(
            candidate_id in stored.contradicts for candidate_id in active.created_from_candidate_ids
        )
        if contradicts_active:
            self.store.add_contradiction(
                stored.candidate_id,
                active.memory_id,
                "durable_memory",
                "candidate contradicts active durable memory",
                stored.updated_at,
            )
            if stored.strength >= active.confidence + self.thresholds["overwrite_margin"]:
                self.store.demote_memory(
                    active.memory_id,
                    "superseded by stronger contradictory evidence",
                    stored.updated_at,
                )
                self.store.promote_candidate(
                    stored.candidate_id,
                    stored.strength,
                    "overwrite after reflection on contradiction",
                    stored.updated_at,
                )
            else:
                self.store.update_candidate_state(
                    stored.candidate_id,
                    MemoryState.CONTESTED,
                    "weaker contradictory evidence was not promoted",
                    stored.updated_at,
                )
            return

        self.store.reinforce_memory(
            active.memory_id,
            stored.candidate_id,
            "candidate supports existing durable memory",
            stored.updated_at,
        )

    def answer_question(self, question: QuestionSpec) -> AnswerTrace:
        durable = self.store.active_durable(
            question.relevant_canonical_id,
            question.scope_level,
            question.scope_key,
        )
        resolved_candidate_ids = []
        used_memory_ids = []
        answer_text = "No durable memory available."
        if durable is not None:
            resolved_candidate_ids = list(durable.created_from_candidate_ids)
            used_memory_ids = [durable.memory_id]
            answer_text = "[durable] {} (confidence {:.2f})".format(durable.claim, durable.confidence)
        trace = AnswerTrace(
            answer_id="answer-" + question.question_id,
            question_id=question.question_id,
            query=question.text,
            relevant_canonical_id=question.relevant_canonical_id,
            scope_level=question.scope_level,
            scope_key=question.scope_key,
            resolved_candidate_ids=resolved_candidate_ids,
            used_memory_ids=used_memory_ids,
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
                "used_memory_ids": used_memory_ids,
                "used_pending": False,
            },
            question.asked_at,
        )
        return trace
