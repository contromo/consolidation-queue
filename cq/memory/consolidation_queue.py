from __future__ import annotations

from typing import Dict, Optional

from cq.memory.lifecycle import merge_thresholds, pending_use_allowed, should_promote_candidate
from cq.memory.substrate import MemoryStore
from cq.schemas.memory import AnswerTrace, CandidateUpdate, MemoryState
from cq.schemas.scenario import QuestionSpec


class ConsolidationQueueLite:
    policy_name = "consolidation_queue_lite"

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = merge_thresholds(thresholds)
        self.store = MemoryStore(self.policy_name)

    def observe_candidate(self, candidate: CandidateUpdate) -> None:
        stored = self.store.add_candidate(candidate)
        active = self.store.active_durable(stored.canonical_id, stored.scope_level, stored.scope_key)

        for target_candidate_id in stored.contradicts:
            if target_candidate_id in self.store.candidate_memories:
                target = self.store.candidate_memories[target_candidate_id]
                target.contradiction_count += 1
                target.refresh_scores()
                self.store.add_contradiction(
                    stored.candidate_id,
                    target_candidate_id,
                    "candidate",
                    "candidate contradicts earlier candidate",
                    stored.updated_at,
                )
                self.store.update_candidate_state(
                    target_candidate_id,
                    MemoryState.CONTESTED,
                    "newer evidence contradicts earlier candidate",
                    stored.updated_at,
                )

        if active is not None:
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
                self.store.demote_memory(
                    active.memory_id,
                    "contradicted during queue consolidation",
                    stored.updated_at,
                )

        if should_promote_candidate(stored, self.thresholds):
            self.store.promote_candidate(
                stored.candidate_id,
                stored.strength,
                "promotion after queue scoring",
                stored.updated_at,
            )
        else:
            self.store.update_candidate_state(
                stored.candidate_id,
                MemoryState.PENDING,
                "retained in queue pending more evidence",
                stored.updated_at,
            )

    def answer_question(self, question: QuestionSpec) -> AnswerTrace:
        durable = self.store.active_durable(
            question.relevant_canonical_id,
            question.scope_level,
            question.scope_key,
        )
        if durable is not None:
            resolved_candidate_ids = list(durable.created_from_candidate_ids)
            used_memory_ids = [durable.memory_id]
            answer_text = "[durable] {} (confidence {:.2f})".format(durable.claim, durable.confidence)
            used_pending = False
        else:
            candidate = self.store.strongest_pending_candidate(
                question.relevant_canonical_id,
                question.scope_level,
                question.scope_key,
            )
            if candidate is not None and pending_use_allowed(candidate, self.thresholds):
                resolved_candidate_ids = [candidate.candidate_id]
                used_memory_ids = []
                answer_text = "[pending] {} (strength {:.2f})".format(candidate.canonical_claim, candidate.strength)
                used_pending = True
            else:
                resolved_candidate_ids = []
                used_memory_ids = []
                answer_text = "No usable memory available."
                used_pending = False
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
            used_pending=used_pending,
            created_at=question.asked_at,
        )
        self.store.log_event(
            "answer_generated",
            "question",
            question.question_id,
            {
                "resolved_candidate_ids": resolved_candidate_ids,
                "used_memory_ids": used_memory_ids,
                "used_pending": used_pending,
            },
            question.asked_at,
        )
        return trace
