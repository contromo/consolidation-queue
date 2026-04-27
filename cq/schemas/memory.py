from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ClaimType(str, Enum):
    WORLD_FACT = "world_fact"
    USER_PREFERENCE = "user_preference"
    PROJECT_CONVENTION = "project_convention"
    PROCEDURAL_KNOWLEDGE = "procedural_knowledge"
    IDENTITY_ATTRIBUTE = "identity_attribute"
    POLICY_CONSTRAINT = "policy_constraint"
    TEMPORARY_CONSTRAINT = "temporary_constraint"
    TOOLING_PREFERENCE = "tooling_preference"


class ScopeLevel(str, Enum):
    TURN = "turn"
    SESSION = "session"
    PROJECT = "project"
    WORKSPACE = "workspace"
    USER_GLOBAL = "user_global"
    WORLD_GLOBAL = "world_global"


class MemoryState(str, Enum):
    PENDING = "pending"
    CORROBORATED = "corroborated"
    CONTESTED = "contested"
    MIXED = "mixed"
    PROMOTED = "promoted"
    EXPIRED = "expired"
    DEMOTED = "demoted"
    REJECTED = "rejected"


class MemoryDestination(str, Enum):
    NONE = "none"
    EPISODIC = "episodic"
    DURABLE = "durable"


def slugify(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "memory"


def jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        result = {}
        for name in value.__dataclass_fields__:
            result[name] = jsonable(getattr(value, name))
        return result
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


@dataclass
class ProvenanceRecord:
    source_kind: str
    source_id: str
    trust_score: float
    observed_at: datetime


@dataclass
class CandidateUpdate:
    candidate_id: str
    raw_text: str
    raw_claim: str
    canonical_claim: str
    claim_type: ClaimType
    scope_level: ScopeLevel
    scope_key: str
    created_at: datetime
    updated_at: datetime
    canonical_id: Optional[str] = None
    state: MemoryState = MemoryState.PENDING
    destination: MemoryDestination = MemoryDestination.NONE
    provenance: List[ProvenanceRecord] = field(default_factory=list)
    recurrence_count: int = 1
    corroboration_count: int = 0
    contradiction_count: int = 0
    semantic_uncertainty: float = 0.0
    verification_score: float = 0.0
    interference_risk: float = 0.0
    staleness_score: float = 0.0
    promotion_score: float = 0.0
    decay_at: Optional[datetime] = None
    contradicts: List[str] = field(default_factory=list)
    supports: List[str] = field(default_factory=list)
    strength: float = 0.0

    def __post_init__(self) -> None:
        if not self.canonical_id:
            self.canonical_id = slugify(self.canonical_claim)
        self.refresh_scores()

    def refresh_scores(self) -> None:
        provenance_scores = [record.trust_score for record in self.provenance]
        provenance_mean = sum(provenance_scores) / len(provenance_scores) if provenance_scores else 0.5
        recurrence_bonus = min(max(self.recurrence_count - 1, 0), 3) * 0.05
        support_bonus = self.corroboration_count * 0.10
        contradiction_penalty = self.contradiction_count * 0.25
        risk_penalty = (
            self.interference_risk * 0.15
            + self.staleness_score * 0.20
            + self.semantic_uncertainty * 0.10
        )
        base = max(self.verification_score, provenance_mean)
        self.strength = round(max(0.0, min(1.0, base + recurrence_bonus - risk_penalty)), 4)
        self.promotion_score = round(
            max(0.0, min(1.0, self.strength + support_bonus - contradiction_penalty)),
            4,
        )


@dataclass
class DurableMemory:
    memory_id: str
    canonical_id: str
    claim: str
    claim_type: ClaimType
    scope_level: ScopeLevel
    scope_key: str
    created_from_candidate_ids: List[str]
    provenance: List[ProvenanceRecord]
    confidence: float
    promotion_reason: str
    created_at: datetime
    updated_at: datetime
    active: bool = True
    demoted_at: Optional[datetime] = None
    demotion_reason: Optional[str] = None


@dataclass
class ContradictionEdge:
    source_candidate_id: str
    target_object_id: str
    target_object_type: str
    reason: str
    created_at: datetime


@dataclass
class LifecycleEvent:
    timestamp: datetime
    event_type: str
    object_type: str
    object_id: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnswerTrace:
    answer_id: str
    question_id: str
    query: str
    relevant_canonical_id: str
    scope_level: ScopeLevel
    scope_key: str
    resolved_candidate_ids: List[str]
    used_memory_ids: List[str]
    answer_text: str
    used_pending: bool
    created_at: datetime
