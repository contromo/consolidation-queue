from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from cq.memory.lifecycle import merge_thresholds, pending_use_allowed, should_promote_candidate
from cq.memory.substrate import (
    SCOPE_MATCH_WORLD_GLOBAL,
    SCOPE_MATCH_WORKSPACE_PARENT,
    MemoryStore,
    scope_match_relation,
)
from cq.schemas.memory import AnswerTrace, CandidateUpdate, ClaimType, DurableMemory, MemoryState
from cq.schemas.scenario import QuestionSpec


WIDER_SCOPE_MATCHES = {
    SCOPE_MATCH_WORLD_GLOBAL,
    SCOPE_MATCH_WORKSPACE_PARENT,
}


class ConsolidationQueueLite:
    policy_name = "consolidation_queue_lite"
    ablation_note = ""
    enable_contestation_demotion = True
    enable_wider_scope_pending_override = True
    enable_pending_lookup_use = True
    enable_source_independence_gate = True

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = merge_thresholds(thresholds)
        self.store = MemoryStore(self.policy_name)

    def observe_candidate(self, candidate: CandidateUpdate) -> None:
        stored = self.store.add_candidate(candidate)
        active = self.store.active_durable(stored.canonical_id, stored.scope_level, stored.scope_key)
        wider_scope_override = False

        if self.enable_contestation_demotion:
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

        if active is not None and self.enable_contestation_demotion:
            contradicts_active = any(
                candidate_id in stored.contradicts for candidate_id in active.created_from_candidate_ids
            )
            if contradicts_active:
                active_relation = scope_match_relation(
                    active.scope_level,
                    active.scope_key,
                    stored.scope_level,
                    stored.scope_key,
                )
                self.store.add_contradiction(
                    stored.candidate_id,
                    active.memory_id,
                    "durable_memory",
                    "candidate contradicts active durable memory",
                    stored.updated_at,
                )
                if active_relation in WIDER_SCOPE_MATCHES and active.scope_level != stored.scope_level:
                    # A narrower override should not erase a still-valid wider default globally.
                    wider_scope_override = True
                else:
                    self.store.demote_memory(
                        active.memory_id,
                        "contradicted during queue consolidation",
                        stored.updated_at,
                    )

        if self._should_promote_candidate(stored):
            self.store.promote_candidate(
                stored.candidate_id,
                stored.strength,
                "promotion after queue scoring",
                stored.updated_at,
            )
        else:
            reason = (
                "retained as exact-scope override for wider durable"
                if wider_scope_override
                else "retained in queue pending more evidence"
            )
            self.store.update_candidate_state(
                stored.candidate_id,
                MemoryState.PENDING,
                reason,
                stored.updated_at,
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
            candidate = None
            if self.enable_pending_lookup_use:
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

    def _should_promote_candidate(self, candidate: CandidateUpdate) -> bool:
        if self.enable_source_independence_gate:
            return should_promote_candidate(candidate, self.thresholds)
        return self._raw_support_promotion_score(candidate) >= self._promotion_threshold(candidate)

    def _promotion_threshold(self, candidate: CandidateUpdate) -> float:
        if candidate.claim_type == ClaimType.WORLD_FACT:
            return self.thresholds["world_fact_promotion"]
        return self.thresholds["non_world_promotion"]

    def _raw_support_promotion_score(self, candidate: CandidateUpdate) -> float:
        # This ablation deliberately ignores source independence but does not mutate substrate fields.
        raw_support_bonus = len(candidate.supports) * 0.10
        contradiction_penalty = candidate.contradiction_count * 0.25
        return round(
            max(0.0, min(1.0, candidate.strength + raw_support_bonus - contradiction_penalty)),
            4,
        )

    def _pending_override_for_wider_durable(
        self,
        question: QuestionSpec,
        durable: DurableMemory,
    ) -> Optional[CandidateUpdate]:
        # Below-threshold exact overrides can shadow wider durables without inventing a new durable state.
        durable_candidate_ids = set(durable.created_from_candidate_ids)
        candidates = []
        for candidate_id in self.store.canonical_clusters.get(question.relevant_canonical_id, []):
            candidate = self.store.candidate_memories[candidate_id]
            if candidate.state != MemoryState.PENDING:
                continue
            if candidate.scope_level != question.scope_level or candidate.scope_key != question.scope_key:
                continue
            if not durable_candidate_ids.intersection(candidate.contradicts):
                continue
            if not pending_use_allowed(candidate, self.thresholds):
                continue
            candidates.append(candidate)
        if not candidates:
            return None
        candidates.sort(key=lambda candidate: (candidate.strength, candidate.updated_at), reverse=True)
        return candidates[0]


class CQNoContestationDemotion(ConsolidationQueueLite):
    policy_name = "cq_no_contestation_demotion"
    ablation_note = "Disables CQ candidate contestation and active durable demotion on contradictions."
    enable_contestation_demotion = False


class CQNoWiderScopePendingOverride(ConsolidationQueueLite):
    policy_name = "cq_no_wider_scope_pending_override"
    ablation_note = "Disables exact-scope pending override when a wider-scope durable is active."
    enable_wider_scope_pending_override = False


class CQNoPendingLookupUse(ConsolidationQueueLite):
    policy_name = "cq_no_pending_lookup_use"
    ablation_note = "Disables pending fallback lookup when no durable memory is available."
    enable_pending_lookup_use = False


class CQNoSourceIndependenceGate(ConsolidationQueueLite):
    policy_name = "cq_no_source_independence_gate"
    ablation_note = (
        "Uses raw support edge count for CQ promotion instead of independent-source corroboration; "
        "this is intentionally more permissive, especially on mirrored-source observations."
    )
    enable_source_independence_gate = False


def _candidate_observed_at(candidate: CandidateUpdate) -> datetime:
    if candidate.provenance:
        return max(record.observed_at for record in candidate.provenance)
    return candidate.updated_at


def _durable_observed_at(durable: DurableMemory) -> datetime:
    if durable.provenance:
        return max(record.observed_at for record in durable.provenance)
    return durable.updated_at


class CQDatedContestation(ConsolidationQueueLite):
    """Post-hoc dated-evidence CQ variant for the adversarial_upstream_noise follow-up.

    Uses ``provenance.observed_at`` so that a stale contradictor does not overrule
    fresher evidence. When the new (source) candidate's observation timestamp is
    strictly older than the target's, the contradiction edge is still recorded for
    inspection, but the fresher target is not penalized; the stale source is
    marked CONTESTED instead, which excludes it from promotion and from
    pending-lookup answers.

    When timestamps tie or the source is fresher than the target, behavior
    matches ``ConsolidationQueueLite`` verbatim. The ``observed_at`` for each
    side is ``max(record.observed_at for record in provenance)`` when provenance
    is present and ``updated_at`` otherwise; the fallback is applied
    independently per side.
    """

    policy_name = "cq_dated_contestation"
    ablation_note = (
        "Post-hoc dated-contestation variant: provenance-aware contradiction handling "
        "on stale contradictors."
    )

    def observe_candidate(self, candidate: CandidateUpdate) -> None:
        stored = self.store.add_candidate(candidate)
        active = self.store.active_durable(stored.canonical_id, stored.scope_level, stored.scope_key)
        wider_scope_override = False
        source_observed_at = _candidate_observed_at(stored)
        stale_against_any_target = False

        if self.enable_contestation_demotion:
            for target_candidate_id in stored.contradicts:
                if target_candidate_id not in self.store.candidate_memories:
                    continue
                target = self.store.candidate_memories[target_candidate_id]
                target_observed_at = _candidate_observed_at(target)
                if source_observed_at < target_observed_at:
                    # Stale contradictor: keep the edge for inspection but do not
                    # penalize the fresher target.
                    self.store.add_contradiction(
                        stored.candidate_id,
                        target_candidate_id,
                        "candidate",
                        "stale contradictor against fresher candidate; target not penalized",
                        stored.updated_at,
                    )
                    stale_against_any_target = True
                    continue
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

        if active is not None and self.enable_contestation_demotion:
            contradicts_active = any(
                candidate_id in stored.contradicts for candidate_id in active.created_from_candidate_ids
            )
            if contradicts_active:
                active_relation = scope_match_relation(
                    active.scope_level,
                    active.scope_key,
                    stored.scope_level,
                    stored.scope_key,
                )
                durable_observed_at = _durable_observed_at(active)
                if source_observed_at < durable_observed_at:
                    # Stale contradictor against a fresher durable: record the edge
                    # but do not demote the durable.
                    self.store.add_contradiction(
                        stored.candidate_id,
                        active.memory_id,
                        "durable_memory",
                        "stale contradictor against fresher active durable; durable not demoted",
                        stored.updated_at,
                    )
                    stale_against_any_target = True
                else:
                    self.store.add_contradiction(
                        stored.candidate_id,
                        active.memory_id,
                        "durable_memory",
                        "candidate contradicts active durable memory",
                        stored.updated_at,
                    )
                    if active_relation in WIDER_SCOPE_MATCHES and active.scope_level != stored.scope_level:
                        # A narrower override should not erase a still-valid wider default globally.
                        wider_scope_override = True
                    else:
                        self.store.demote_memory(
                            active.memory_id,
                            "contradicted during queue consolidation",
                            stored.updated_at,
                        )

        if stale_against_any_target:
            # The stale source must not be promoted nor used as a pending answer.
            self.store.update_candidate_state(
                stored.candidate_id,
                MemoryState.CONTESTED,
                "stale contradictor against fresher evidence",
                stored.updated_at,
            )
            return

        if self._should_promote_candidate(stored):
            self.store.promote_candidate(
                stored.candidate_id,
                stored.strength,
                "promotion after queue scoring",
                stored.updated_at,
            )
        else:
            reason = (
                "retained as exact-scope override for wider durable"
                if wider_scope_override
                else "retained in queue pending more evidence"
            )
            self.store.update_candidate_state(
                stored.candidate_id,
                MemoryState.PENDING,
                reason,
                stored.updated_at,
            )
