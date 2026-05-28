from __future__ import annotations

from cq.memory.consolidation_queue import (
    WIDER_SCOPE_MATCHES,
    ConsolidationQueueLite,
)
from cq.memory.lifecycle import pending_use_allowed
from cq.memory.substrate import scope_match_relation
from cq.schemas.memory import AnswerTrace
from cq.schemas.scenario import QuestionSpec


class CQPendingMultiEvidence(ConsolidationQueueLite):
    """Follow-up CQ variant that returns all eligible same-slot pending evidence."""

    policy_name = "cq_pending_multi_evidence"
    ablation_note = (
        "Preregistered LongMemEval follow-up: pending fallback returns all eligible "
        "same-slot pending candidates instead of only the strongest one."
    )

    def answer_question(self, question: QuestionSpec) -> AnswerTrace:
        durable = self.store.active_durable(
            question.relevant_canonical_id,
            question.scope_level,
            question.scope_key,
        )
        if durable is not None:
            pending_override = None
            if (
                self.enable_wider_scope_pending_override
                and scope_match_relation(
                    durable.scope_level,
                    durable.scope_key,
                    question.scope_level,
                    question.scope_key,
                )
                in WIDER_SCOPE_MATCHES
                and durable.scope_level != question.scope_level
            ):
                pending_override = self._pending_override_for_wider_durable(question, durable)
            if pending_override is not None:
                resolved_candidate_ids = [pending_override.candidate_id]
                used_memory_ids = []
                answer_text = "[pending] {} (strength {:.2f})".format(
                    pending_override.canonical_claim,
                    pending_override.strength,
                )
                used_pending = True
            else:
                resolved_candidate_ids = list(durable.created_from_candidate_ids)
                used_memory_ids = [durable.memory_id]
                answer_text = "[durable] {} (confidence {:.2f})".format(durable.claim, durable.confidence)
                used_pending = False
        else:
            candidates = []
            if self.enable_pending_lookup_use:
                candidates = [
                    candidate
                    for candidate in self.store.strongest_pending_candidates(
                        question.relevant_canonical_id,
                        question.scope_level,
                        question.scope_key,
                    )
                    if pending_use_allowed(candidate, self.thresholds)
                ]
            if candidates:
                resolved_candidate_ids = [candidate.candidate_id for candidate in candidates]
                used_memory_ids = []
                answer_text = "[pending-multi] {} candidate(s): {}".format(
                    len(candidates),
                    "; ".join(candidate.canonical_claim for candidate in candidates),
                )
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
