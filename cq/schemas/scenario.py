from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from cq.schemas.memory import CandidateUpdate, ScopeLevel


class TaskFamily(str, Enum):
    FORCED_CONTRADICTION = "forced_contradiction"
    SCOPE_CONTAMINATION = "scope_contamination"
    PREFERENCE_DRIFT = "preference_drift"
    USEFUL_PENDING_MEMORY = "useful_pending_memory"
    FALSE_CORROBORATION = "false_corroboration"
    MEMORY_POISONING = "memory_poisoning"
    ADVERSARIAL_UPSTREAM_NOISE = "adversarial_upstream_noise"
    EVIDENCE_CONFLICT_SPECTRUM = "evidence_conflict_spectrum"
    LONGMEMEVAL_EXTERNAL = "longmemeval_external"


class EventKind(str, Enum):
    OBSERVATION = "observation"
    QUESTION = "question"


@dataclass
class QuestionSpec:
    question_id: str
    text: str
    relevant_canonical_id: str
    scope_level: ScopeLevel
    scope_key: str
    phase: str
    gold_candidate_ids: List[str]
    forbidden_candidate_ids: List[str]
    asked_at: datetime


@dataclass
class ScenarioEvent:
    event_id: str
    kind: EventKind
    turn_index: int
    text: str
    candidate: Optional[CandidateUpdate] = None
    question: Optional[QuestionSpec] = None


@dataclass
class Scenario:
    scenario_id: str
    task_family: TaskFamily
    description: str
    latent_truth_graph: Dict[str, Any]
    oracle_events: List[ScenarioEvent]
    expected_lifecycle: Dict[str, Any] = field(default_factory=dict)
    template_id: str = ""
    template_kind: str = "clean"
    template_split: str = "main"

    def sorted_events(self) -> List[ScenarioEvent]:
        return sorted(self.oracle_events, key=lambda event: event.turn_index)
