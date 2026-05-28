from __future__ import annotations

from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.schemas.memory import AnswerTrace
from cq.schemas.scenario import QuestionSpec


class ReflectionEagerWriteCardinalityCapped(ReflectionEagerWriteLite):
    """Diagnostic control that caps Reflection's durable answer readout to one candidate."""

    policy_name = "reflection_eager_write_cardinality_capped"
    ablation_note = (
        "Preregistered LongMemEval cardinality control: Reflection writes normally "
        "but returns one durable candidate id at answer time."
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
            candidate_id = self._strongest_durable_candidate_id(durable.created_from_candidate_ids)
            resolved_candidate_ids = [candidate_id] if candidate_id is not None else []
            used_memory_ids = [durable.memory_id]
            answer_text = "[durable-capped] {} (confidence {:.2f})".format(
                durable.claim,
                durable.confidence,
            )
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

    def _strongest_durable_candidate_id(self, candidate_ids: list[str]) -> str | None:
        candidates = [
            self.store.candidate_memories[candidate_id]
            for candidate_id in candidate_ids
            if candidate_id in self.store.candidate_memories
        ]
        if not candidates:
            return None
        candidates.sort(
            key=lambda candidate: (
                candidate.strength,
                candidate.updated_at,
                candidate.candidate_id,
            ),
            reverse=True,
        )
        return candidates[0].candidate_id
