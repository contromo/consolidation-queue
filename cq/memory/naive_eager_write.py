from __future__ import annotations

from typing import Dict, List, Optional

from cq.memory.lifecycle import merge_thresholds
from cq.memory.substrate import MemoryStore, scope_matches
from cq.schemas.memory import AnswerTrace, CandidateUpdate, DurableMemory, MemoryState
from cq.schemas.scenario import QuestionSpec


class NaiveEagerWriteLite:
    """Append-only eager write baseline that does not resolve contradictory durable state."""

    policy_name = "naive_eager_write_lite"

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

        if active is None:
            self.store.promote_candidate(
                stored.candidate_id,
                max(stored.strength, self.thresholds["minimum_write_confidence"]),
                "naive immediate write",
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
            self.store.promote_candidate(
                stored.candidate_id,
                max(stored.strength, self.thresholds["minimum_write_confidence"]),
                "naive write despite contradiction",
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
        durable = self._select_answer_durable(
            question.relevant_canonical_id,
            question.scope_level,
            question.scope_key,
        )
        resolved_candidate_ids: List[str] = []
        used_memory_ids: List[str] = []
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

    def _select_answer_durable(
        self,
        canonical_id: str,
        scope_level,
        scope_key: str,
    ) -> Optional[DurableMemory]:
        candidates = [
            durable
            for durable in self.store.durable_memories.values()
            if durable.active
            and durable.canonical_id == canonical_id
            and scope_matches(durable.scope_level, durable.scope_key, scope_level, scope_key)
        ]
        if not candidates:
            return None
        # Naive answer selection is confidence-first so older stronger beliefs can outrank newer weaker ones.
        candidates.sort(key=lambda durable: (durable.confidence, durable.updated_at), reverse=True)
        return candidates[0]
