from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional

from cq.schemas.memory import (
    AnswerTrace,
    CandidateUpdate,
    ContradictionEdge,
    DurableMemory,
    LifecycleEvent,
    MemoryDestination,
    MemoryState,
    ScopeLevel,
    jsonable,
)


SCOPE_MATCH_EXACT = "exact"
SCOPE_MATCH_WORLD_GLOBAL = "world_global"
SCOPE_MATCH_WORKSPACE_PARENT = "workspace_parent"


def scope_match_relation(
    stored_scope_level: ScopeLevel,
    stored_scope_key: str,
    query_scope_level: ScopeLevel,
    query_scope_key: str,
) -> Optional[str]:
    if stored_scope_level == query_scope_level and stored_scope_key == query_scope_key:
        return SCOPE_MATCH_EXACT
    if stored_scope_level == ScopeLevel.WORLD_GLOBAL:
        return SCOPE_MATCH_WORLD_GLOBAL
    if (
        stored_scope_level == ScopeLevel.WORKSPACE
        and query_scope_level == ScopeLevel.PROJECT
        and query_scope_key.startswith(stored_scope_key + "/")
    ):
        return SCOPE_MATCH_WORKSPACE_PARENT
    return None


def scope_matches(
    stored_scope_level: ScopeLevel,
    stored_scope_key: str,
    query_scope_level: ScopeLevel,
    query_scope_key: str,
) -> bool:
    return (
        scope_match_relation(
            stored_scope_level,
            stored_scope_key,
            query_scope_level,
            query_scope_key,
        )
        is not None
    )


class MemoryStore:
    def __init__(self, policy_name: str) -> None:
        self.policy_name = policy_name
        self.candidate_memories: Dict[str, CandidateUpdate] = {}
        self.durable_memories: Dict[str, DurableMemory] = {}
        self.canonical_clusters: Dict[str, List[str]] = defaultdict(list)
        self.contradiction_edges: List[ContradictionEdge] = []
        self.lifecycle_events: List[LifecycleEvent] = []

    def log_event(
        self,
        event_type: str,
        object_type: str,
        object_id: str,
        details: Optional[Dict[str, object]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        self.lifecycle_events.append(
            LifecycleEvent(
                timestamp=timestamp or datetime.utcnow(),
                event_type=event_type,
                object_type=object_type,
                object_id=object_id,
                details=details or {},
            )
        )

    def add_candidate(self, candidate: CandidateUpdate) -> CandidateUpdate:
        stored = deepcopy(candidate)
        corroboration_details = self._compute_independent_corroboration(stored)
        if corroboration_details is not None:
            stored.corroboration_count = corroboration_details["corroboration_count"]
            stored.refresh_scores()
        self.candidate_memories[stored.candidate_id] = stored
        if stored.candidate_id not in self.canonical_clusters[stored.canonical_id]:
            self.canonical_clusters[stored.canonical_id].append(stored.candidate_id)
        self.log_event(
            "candidate_observed",
            "candidate",
            stored.candidate_id,
            {
                "canonical_id": stored.canonical_id,
                "claim": stored.canonical_claim,
                "state": stored.state.value,
                "strength": stored.strength,
            },
            stored.created_at,
        )
        if corroboration_details is not None:
            self.log_event(
                "candidate_corroboration_counted",
                "candidate",
                stored.candidate_id,
                corroboration_details,
                stored.created_at,
            )
        return stored

    def _compute_independent_corroboration(self, candidate: CandidateUpdate) -> Optional[Dict[str, object]]:
        if not candidate.supports or candidate.corroboration_count != 0:
            return None

        own_source_ids = _source_ids(candidate)
        distinct_source_ids = set(own_source_ids)
        counted_source_ids = set()
        ignored_source_ids = set()
        ignored_candidate_ids = []
        counted_candidate_ids = []

        for support_id in candidate.supports:
            support = self.candidate_memories.get(support_id)
            if support is None:
                ignored_candidate_ids.append(support_id)
                continue
            if not _same_corroboration_cluster(candidate, support):
                ignored_candidate_ids.append(support_id)
                continue
            support_sources = _source_ids(support)
            support_counted = False
            for source_id in support_sources:
                if source_id in distinct_source_ids:
                    ignored_source_ids.add(source_id)
                    continue
                distinct_source_ids.add(source_id)
                counted_source_ids.add(source_id)
                support_counted = True
            if support_counted:
                counted_candidate_ids.append(support_id)

        return {
            "corroboration_count": max(0, len(distinct_source_ids) - 1),
            "distinct_source_ids": sorted(distinct_source_ids),
            "counted_source_ids": sorted(counted_source_ids),
            "ignored_source_ids": sorted(ignored_source_ids),
            "new_source_ids": sorted(own_source_ids),
            "counted_candidate_ids": counted_candidate_ids,
            "ignored_candidate_ids": ignored_candidate_ids,
        }

    def add_contradiction(
        self,
        source_candidate_id: str,
        target_object_id: str,
        target_object_type: str,
        reason: str,
        timestamp: datetime,
    ) -> None:
        self.contradiction_edges.append(
            ContradictionEdge(
                source_candidate_id=source_candidate_id,
                target_object_id=target_object_id,
                target_object_type=target_object_type,
                reason=reason,
                created_at=timestamp,
            )
        )
        self.log_event(
            "contradiction_registered",
            target_object_type,
            target_object_id,
            {"source_candidate_id": source_candidate_id, "reason": reason},
            timestamp,
        )

    def update_candidate_state(
        self,
        candidate_id: str,
        new_state: MemoryState,
        reason: str,
        timestamp: Optional[datetime] = None,
        destination: Optional[MemoryDestination] = None,
    ) -> None:
        candidate = self.candidate_memories[candidate_id]
        previous = candidate.state
        candidate.state = new_state
        if destination is not None:
            candidate.destination = destination
        candidate.updated_at = timestamp or datetime.utcnow()
        self.log_event(
            "candidate_state_changed",
            "candidate",
            candidate_id,
            {
                "previous_state": previous.value,
                "new_state": new_state.value,
                "reason": reason,
                "destination": candidate.destination.value,
            },
            candidate.updated_at,
        )

    def promote_candidate(
        self,
        candidate_id: str,
        confidence: float,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> DurableMemory:
        candidate = self.candidate_memories[candidate_id]
        created_at = timestamp or datetime.utcnow()
        memory_id = "memory-" + candidate_id
        durable = DurableMemory(
            memory_id=memory_id,
            canonical_id=candidate.canonical_id,
            claim=candidate.canonical_claim,
            claim_type=candidate.claim_type,
            scope_level=candidate.scope_level,
            scope_key=candidate.scope_key,
            created_from_candidate_ids=[candidate.candidate_id],
            provenance=list(candidate.provenance),
            confidence=round(confidence, 4),
            promotion_reason=reason,
            created_at=created_at,
            updated_at=created_at,
        )
        self.durable_memories[memory_id] = durable
        self.update_candidate_state(
            candidate_id,
            MemoryState.PROMOTED,
            reason,
            created_at,
            destination=MemoryDestination.DURABLE,
        )
        self.log_event(
            "memory_promoted",
            "durable_memory",
            memory_id,
            {"candidate_id": candidate_id, "confidence": durable.confidence, "reason": reason},
            created_at,
        )
        return durable

    def reinforce_memory(
        self,
        memory_id: str,
        candidate_id: str,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        durable = self.durable_memories[memory_id]
        candidate = self.candidate_memories[candidate_id]
        if candidate_id not in durable.created_from_candidate_ids:
            durable.created_from_candidate_ids.append(candidate_id)
        durable.updated_at = timestamp or datetime.utcnow()
        durable.confidence = round(min(1.0, max(durable.confidence, candidate.strength) + 0.03), 4)
        durable.provenance.extend(candidate.provenance)
        self.update_candidate_state(
            candidate_id,
            MemoryState.CORROBORATED,
            reason,
            durable.updated_at,
            destination=MemoryDestination.DURABLE,
        )
        self.log_event(
            "memory_reinforced",
            "durable_memory",
            memory_id,
            {
                "candidate_id": candidate_id,
                "confidence": durable.confidence,
                "reason": reason,
            },
            durable.updated_at,
        )

    def demote_memory(
        self,
        memory_id: str,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        durable = self.durable_memories[memory_id]
        durable.active = False
        durable.demoted_at = timestamp or datetime.utcnow()
        durable.updated_at = durable.demoted_at
        durable.demotion_reason = reason
        self.log_event(
            "memory_demoted",
            "durable_memory",
            memory_id,
            {
                "reason": reason,
                "created_from_candidate_ids": list(durable.created_from_candidate_ids),
            },
            durable.demoted_at,
        )

    def active_durable(
        self,
        canonical_id: str,
        scope_level: ScopeLevel,
        scope_key: str,
    ) -> Optional[DurableMemory]:
        candidates = [
            durable
            for durable in self.durable_memories.values()
            if durable.active
            and durable.canonical_id == canonical_id
            and scope_matches(durable.scope_level, durable.scope_key, scope_level, scope_key)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda durable: (durable.updated_at, durable.confidence), reverse=True)
        return candidates[0]

    def scoped_candidates(
        self,
        canonical_id: str,
        scope_level: ScopeLevel,
        scope_key: str,
        excluded_states: Optional[List[MemoryState]] = None,
    ) -> List[CandidateUpdate]:
        excluded_states = excluded_states or []
        matches = []
        for candidate_id in self.canonical_clusters.get(canonical_id, []):
            candidate = self.candidate_memories[candidate_id]
            if candidate.state in excluded_states:
                continue
            if scope_matches(candidate.scope_level, candidate.scope_key, scope_level, scope_key):
                matches.append(candidate)
        matches.sort(key=lambda candidate: (candidate.updated_at, candidate.strength), reverse=True)
        return matches

    def strongest_pending_candidate(
        self,
        canonical_id: str,
        scope_level: ScopeLevel,
        scope_key: str,
    ) -> Optional[CandidateUpdate]:
        allowed = self.scoped_candidates(
            canonical_id,
            scope_level,
            scope_key,
            excluded_states=[MemoryState.CONTESTED, MemoryState.DEMOTED, MemoryState.REJECTED, MemoryState.EXPIRED],
        )
        if not allowed:
            return None
        allowed.sort(key=lambda candidate: (candidate.strength, candidate.updated_at), reverse=True)
        return allowed[0]

    def snapshot(self) -> Dict[str, object]:
        return {
            "policy_name": self.policy_name,
            "candidate_memories": [jsonable(candidate) for candidate in self.candidate_memories.values()],
            "durable_memories": [jsonable(memory) for memory in self.durable_memories.values()],
            "contradiction_edges": [jsonable(edge) for edge in self.contradiction_edges],
            "lifecycle_events": [jsonable(event) for event in self.lifecycle_events],
        }


def _source_ids(candidate: CandidateUpdate) -> set:
    return {record.source_id for record in candidate.provenance}


def _same_corroboration_cluster(candidate: CandidateUpdate, support: CandidateUpdate) -> bool:
    return (
        candidate.canonical_id == support.canonical_id
        and candidate.canonical_claim == support.canonical_claim
        and candidate.claim_type == support.claim_type
        and candidate.scope_level == support.scope_level
        and candidate.scope_key == support.scope_key
    )
