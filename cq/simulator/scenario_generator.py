from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario, ScenarioEvent, TaskFamily


COMPANY_PAIRS: Sequence[Tuple[str, str]] = (
    ("Acme", "Northstar"),
    ("Helios", "Summit"),
    ("Lattice", "Pioneer"),
    ("Brightline", "Redwood"),
    ("Aster", "Keystone"),
    ("Vertex", "Harbor"),
    ("Crest", "Bluejay"),
    ("Polar", "Cinder"),
    ("Granite", "Skylark"),
    ("Orchid", "Forge"),
)


CLAIM_TEMPLATES = (
    "{buyer} acquired {target}.",
    "{buyer} completed the acquisition of {target}.",
    "{target} was acquired by {buyer}.",
)


CONTRADICTION_TEMPLATES = (
    "A trusted filing says {buyer}'s acquisition talks with {target} collapsed.",
    "A regulator filing says {buyer} did not acquire {target}; the talks ended.",
    "Later reporting says the {buyer}-{target} acquisition did not happen.",
)


QUESTION_TEMPLATES = (
    "What is the status of the {buyer}-{target} acquisition?",
    "Did {buyer} acquire {target}?",
    "What should we believe about {buyer} and {target} now?",
)


DIRTY_CONTRADICTION_TEMPLATES = (
    "A credible but not definitive filing suggests {buyer}'s acquisition of {target} may have fallen through.",
    "A follow-up report indicates {buyer} likely did not complete the acquisition of {target}.",
    "Later reporting casts substantial doubt on whether {buyer} acquired {target}.",
)


TEMPLATE_IDS_BY_MIX: Dict[str, List[str]] = {
    "clean": ["forced_contradiction_clean_v1"],
    "dirty": ["forced_contradiction_dirty_v1", "forced_contradiction_dirty_v2"],
    "mixed": [
        "forced_contradiction_clean_v1",
        "forced_contradiction_dirty_v1",
        "forced_contradiction_dirty_v2",
    ],
    "heldout": [
        "forced_contradiction_dirty_v3",
        "forced_contradiction_dirty_v4",
        "forced_contradiction_dirty_v5",
        "forced_contradiction_dirty_v6",
    ],
}


SCOPE_TEMPLATE_IDS_BY_MIX: Dict[str, List[str]] = {
    "clean": [
        "scope_contamination_clean_v1",
        "scope_contamination_clean_workspace_parent_v1",
    ],
    "dirty": [
        "scope_contamination_dirty_broad_claim_v1",
        "scope_contamination_dirty_workspace_parent_v1",
    ],
    "mixed": [
        "scope_contamination_clean_v1",
        "scope_contamination_dirty_broad_claim_v1",
        "scope_contamination_clean_workspace_parent_v1",
        "scope_contamination_dirty_workspace_parent_v1",
    ],
    "heldout": [
        "scope_contamination_clean_v2",
        "scope_contamination_dirty_broad_claim_v3",
        "scope_contamination_clean_workspace_parent_v2",
        "scope_contamination_dirty_workspace_parent_v2",
    ],
}


PREFERENCE_TEMPLATE_IDS_BY_MIX: Dict[str, List[str]] = {
    "clean": ["preference_drift_clean_stable_v1"],
    "dirty": [
        "preference_drift_dirty_explicit_update_v1",
        "preference_drift_dirty_one_off_exception_v1",
    ],
    "mixed": [
        "preference_drift_clean_stable_v1",
        "preference_drift_dirty_explicit_update_v1",
        "preference_drift_dirty_one_off_exception_v1",
    ],
    "heldout": [
        "preference_drift_clean_stable_v2",
        "preference_drift_dirty_drift_back_v2",
    ],
}


USEFUL_PENDING_TEMPLATE_IDS_BY_MIX: Dict[str, List[str]] = {
    "clean": ["useful_pending_clean_v1"],
    "dirty": ["useful_pending_dirty_refinement_v1"],
    "mixed": [
        "useful_pending_clean_v1",
        "useful_pending_dirty_refinement_v1",
    ],
    "heldout": [
        "useful_pending_clean_v2",
        "useful_pending_dirty_refinement_v2",
    ],
}


FALSE_CORROBORATION_TEMPLATE_IDS_BY_MIX: Dict[str, List[str]] = {
    "clean": ["false_corroboration_clean_independent_v1"],
    "dirty": ["false_corroboration_dirty_mirrored_sources_v1"],
    "mixed": [
        "false_corroboration_clean_independent_v1",
        "false_corroboration_dirty_mirrored_sources_v1",
    ],
    "heldout": [
        "false_corroboration_clean_independent_v2",
        "false_corroboration_dirty_mirrored_sources_v2",
    ],
}


PROJECT_SCOPE_PAIRS: Sequence[Tuple[str, str]] = (
    ("atlas", "beacon"),
    ("cedar", "delta"),
    ("ember", "forge"),
    ("granite", "harbor"),
    ("ivy", "juniper"),
)

USEFUL_PENDING_PROJECTS: Sequence[str] = (
    "atlas",
    "cedar",
    "ember",
    "granite",
    "ivy",
)


PREFERENCE_DIMENSIONS: Sequence[Tuple[str, str, str, str, str]] = (
    (
        "summary-format",
        "concise bullet summaries",
        "short narrative summaries",
        "concise bullet summaries for this one draft",
        "How should summaries be formatted by default?",
    ),
    (
        "review-style",
        "direct risk-first review notes",
        "explanation-first review notes",
        "direct risk-first review notes for this one pull request",
        "How should code review notes be written by default?",
    ),
    (
        "status-update-style",
        "brief status updates",
        "detailed status updates",
        "brief status updates for this one checkpoint",
        "How should status updates be written by default?",
    ),
)


def _template_id_for_index(index: int, template_mix: str) -> str:
    template_ids = TEMPLATE_IDS_BY_MIX[template_mix]
    return template_ids[index % len(template_ids)]


def _scope_template_id_for_index(index: int, template_mix: str) -> str:
    if template_mix not in SCOPE_TEMPLATE_IDS_BY_MIX:
        raise ValueError("Unsupported scope-contamination template mix: {}".format(template_mix))
    template_ids = SCOPE_TEMPLATE_IDS_BY_MIX[template_mix]
    return template_ids[index % len(template_ids)]


def _preference_template_id_for_index(index: int, template_mix: str) -> str:
    if template_mix not in PREFERENCE_TEMPLATE_IDS_BY_MIX:
        raise ValueError("Unsupported preference-drift template mix: {}".format(template_mix))
    template_ids = PREFERENCE_TEMPLATE_IDS_BY_MIX[template_mix]
    return template_ids[index % len(template_ids)]


def _useful_pending_template_id_for_index(index: int, template_mix: str) -> str:
    if template_mix not in USEFUL_PENDING_TEMPLATE_IDS_BY_MIX:
        raise ValueError("Unsupported useful-pending-memory template mix: {}".format(template_mix))
    template_ids = USEFUL_PENDING_TEMPLATE_IDS_BY_MIX[template_mix]
    return template_ids[index % len(template_ids)]


def _false_corroboration_template_id_for_index(index: int, template_mix: str) -> str:
    if template_mix not in FALSE_CORROBORATION_TEMPLATE_IDS_BY_MIX:
        raise ValueError("Unsupported false-corroboration template mix: {}".format(template_mix))
    template_ids = FALSE_CORROBORATION_TEMPLATE_IDS_BY_MIX[template_mix]
    return template_ids[index % len(template_ids)]


def _make_candidate(
    candidate_id: str,
    canonical_id: str,
    raw_text: str,
    canonical_claim: str,
    observed_at: datetime,
    trust_score: float,
    verification_score: float,
    source_kind: str,
    *,
    semantic_uncertainty: float = 0.0,
    staleness_score: float = 0.0,
    recurrence_count: int = 1,
    corroboration_count: int = 0,
    contradicts: List[str] = None,
    supports: List[str] = None,
) -> CandidateUpdate:
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=raw_text,
        raw_claim=raw_text,
        canonical_claim=canonical_claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        provenance=[
            ProvenanceRecord(
                source_kind=source_kind,
                source_id="source-" + candidate_id,
                trust_score=trust_score,
                observed_at=observed_at,
            )
        ],
        verification_score=verification_score,
        semantic_uncertainty=semantic_uncertainty,
        staleness_score=staleness_score,
        recurrence_count=recurrence_count,
        corroboration_count=corroboration_count,
        created_at=observed_at,
        updated_at=observed_at,
        contradicts=contradicts or [],
        supports=supports or [],
    )


def _make_question(
    question_id: str,
    text: str,
    canonical_id: str,
    phase: str,
    gold_candidate_ids: List[str],
    forbidden_candidate_ids: List[str],
    asked_at: datetime,
) -> QuestionSpec:
    return QuestionSpec(
        question_id=question_id,
        text=text,
        relevant_canonical_id=canonical_id,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        phase=phase,
        gold_candidate_ids=gold_candidate_ids,
        forbidden_candidate_ids=forbidden_candidate_ids,
        asked_at=asked_at,
    )


def _make_scoped_candidate(
    candidate_id: str,
    canonical_id: str,
    raw_text: str,
    canonical_claim: str,
    observed_at: datetime,
    trust_score: float,
    verification_score: float,
    source_kind: str,
    scope_level: ScopeLevel,
    scope_key: str,
    *,
    semantic_uncertainty: float = 0.0,
    staleness_score: float = 0.0,
    source_id: Optional[str] = None,
    contradicts: List[str] = None,
    supports: List[str] = None,
) -> CandidateUpdate:
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=raw_text,
        raw_claim=raw_text,
        canonical_claim=canonical_claim,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=scope_level,
        scope_key=scope_key,
        provenance=[
            ProvenanceRecord(
                source_kind=source_kind,
                source_id=source_id or "source-" + candidate_id,
                trust_score=trust_score,
                observed_at=observed_at,
            )
        ],
        verification_score=verification_score,
        semantic_uncertainty=semantic_uncertainty,
        staleness_score=staleness_score,
        created_at=observed_at,
        updated_at=observed_at,
        contradicts=contradicts or [],
        supports=supports or [],
    )


def _make_scoped_question(
    question_id: str,
    text: str,
    canonical_id: str,
    phase: str,
    scope_level: ScopeLevel,
    scope_key: str,
    gold_candidate_ids: List[str],
    forbidden_candidate_ids: List[str],
    asked_at: datetime,
) -> QuestionSpec:
    return QuestionSpec(
        question_id=question_id,
        text=text,
        relevant_canonical_id=canonical_id,
        scope_level=scope_level,
        scope_key=scope_key,
        phase=phase,
        gold_candidate_ids=gold_candidate_ids,
        forbidden_candidate_ids=forbidden_candidate_ids,
        asked_at=asked_at,
    )


def _make_preference_candidate(
    candidate_id: str,
    canonical_id: str,
    raw_text: str,
    canonical_claim: str,
    observed_at: datetime,
    strength: float,
    source_kind: str,
    *,
    contradicts: List[str] = None,
    supports: List[str] = None,
) -> CandidateUpdate:
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=raw_text,
        raw_claim=raw_text,
        canonical_claim=canonical_claim,
        claim_type=ClaimType.USER_PREFERENCE,
        scope_level=ScopeLevel.USER_GLOBAL,
        scope_key="user",
        provenance=[
            ProvenanceRecord(
                source_kind=source_kind,
                source_id="source-" + candidate_id,
                trust_score=strength,
                observed_at=observed_at,
            )
        ],
        verification_score=strength,
        created_at=observed_at,
        updated_at=observed_at,
        contradicts=contradicts or [],
        supports=supports or [],
    )


def _make_preference_question(
    question_id: str,
    text: str,
    canonical_id: str,
    phase: str,
    gold_candidate_ids: List[str],
    forbidden_candidate_ids: List[str],
    asked_at: datetime,
) -> QuestionSpec:
    return QuestionSpec(
        question_id=question_id,
        text=text,
        relevant_canonical_id=canonical_id,
        scope_level=ScopeLevel.USER_GLOBAL,
        scope_key="user",
        phase=phase,
        gold_candidate_ids=gold_candidate_ids,
        forbidden_candidate_ids=forbidden_candidate_ids,
        asked_at=asked_at,
    )


def _build_clean_v1_scenario(
    scenario_id: str,
    canonical_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    claim_text: str,
    contradiction_text: str,
    question_before: str,
    question_after: str,
) -> Scenario:
    old_candidate_id = scenario_id + "-candidate-old"
    new_candidate_id = scenario_id + "-candidate-new"
    old_claim = "{} acquired {}".format(buyer, target)
    new_claim = "{} did not acquire {}".format(buyer, target)

    old_candidate = _make_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        trust_score=0.58,
        verification_score=0.56,
        source_kind="user",
        semantic_uncertainty=0.08,
    )
    new_candidate = _make_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=contradiction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=2),
        trust_score=0.96,
        verification_score=0.95,
        source_kind="trusted_document",
        semantic_uncertainty=0.02,
        contradicts=[old_candidate_id],
    )

    before_question = _make_question(
        question_id=scenario_id + "-question-before",
        text=question_before,
        canonical_id=canonical_id,
        phase="before_contradiction",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_question(
        question_id=scenario_id + "-question-after",
        text=question_after,
        canonical_id=canonical_id,
        phase="after_contradiction",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[old_candidate_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description="Plausible acquisition claim later contradicted by clearly stronger evidence.",
        latent_truth_graph={
            "canonical_id": canonical_id,
            "true_state_sequence": [
                {"turn": 1, "truth": "uncertain"},
                {"turn": 3, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_before,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=contradiction_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=question_after,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "contradiction_turn": 3,
            "contradiction_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": new_candidate_id,
        },
        template_id="forced_contradiction_clean_v1",
        template_kind="clean",
        template_split="main",
    )


def _build_dirty_v1_scenario(
    scenario_id: str,
    canonical_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    claim_text: str,
    contradiction_text: str,
    question_before: str,
    question_after: str,
) -> Scenario:
    old_candidate_id = scenario_id + "-candidate-old"
    new_candidate_id = scenario_id + "-candidate-new"
    old_claim = "{} acquired {}".format(buyer, target)
    new_claim = "{} did not acquire {}".format(buyer, target)

    old_candidate = _make_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        trust_score=0.92,
        verification_score=0.90,
        source_kind="press_release",
        semantic_uncertainty=0.01,
    )
    new_candidate = _make_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=contradiction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=2),
        trust_score=0.81,
        verification_score=0.80,
        source_kind="credible_followup",
        contradicts=[old_candidate_id],
    )

    before_question = _make_question(
        question_id=scenario_id + "-question-before",
        text=question_before,
        canonical_id=canonical_id,
        phase="before_contradiction",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_question(
        question_id=scenario_id + "-question-after",
        text=question_after,
        canonical_id=canonical_id,
        phase="after_contradiction",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[old_candidate_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description=(
            "Strong early acquisition claim later challenged by credible but not overwrite-strong contradictory evidence."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "true_state_sequence": [
                {"turn": 1, "truth": "uncertain"},
                {"turn": 3, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_before,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=contradiction_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=question_after,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "contradiction_turn": 3,
            "contradiction_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": new_candidate_id,
        },
        template_id="forced_contradiction_dirty_v1",
        template_kind="dirty",
        template_split="main",
    )


def _build_dirty_v2_scenario(
    scenario_id: str,
    canonical_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    claim_text: str,
    contradiction_text: str,
    question_before: str,
    question_after: str,
) -> Scenario:
    first_old_candidate_id = scenario_id + "-candidate-old-1"
    old_candidate_id = scenario_id + "-candidate-old-2"
    new_candidate_id = scenario_id + "-candidate-new"
    old_claim = "{} acquired {}".format(buyer, target)
    new_claim = "{} did not acquire {}".format(buyer, target)
    corroborating_text = "{} later confirmed the acquisition of {}.".format(buyer, target)

    first_old_candidate = _make_candidate(
        candidate_id=first_old_candidate_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        trust_score=0.74,
        verification_score=0.74,
        source_kind="analyst_note",
    )
    corroborating_candidate = _make_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=corroborating_text,
        canonical_claim=old_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=0.75,
        verification_score=0.75,
        source_kind="followup_report",
        recurrence_count=2,
        corroboration_count=1,
        supports=[first_old_candidate_id],
    )
    new_candidate = _make_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=contradiction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=3),
        trust_score=0.84,
        verification_score=0.84,
        source_kind="regulator_followup",
        contradicts=[first_old_candidate_id, old_candidate_id],
    )

    before_question = _make_question(
        question_id=scenario_id + "-question-before",
        text=question_before,
        canonical_id=canonical_id,
        phase="before_contradiction",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=2),
    )
    after_question = _make_question(
        question_id=scenario_id + "-question-after",
        text=question_after,
        canonical_id=canonical_id,
        phase="after_contradiction",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[first_old_candidate_id, old_candidate_id],
        asked_at=base_time + timedelta(minutes=4),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description=(
            "An acquisition claim is corroborated once and becomes established before a single credible contradiction arrives."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "true_state_sequence": [
                {"turn": 1, "truth": "uncertain"},
                {"turn": 2, "truth": old_claim},
                {"turn": 4, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=first_old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=corroborating_text,
                candidate=corroborating_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=question_before,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.OBSERVATION,
                turn_index=4,
                text=contradiction_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-5",
                kind=EventKind.QUESTION,
                turn_index=5,
                text=question_after,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "contradiction_turn": 4,
            "contradiction_timestamp": (base_time + timedelta(minutes=3)).isoformat(),
            "old_candidate_id": old_candidate_id,
            "old_candidate_ids": [first_old_candidate_id, old_candidate_id],
            "new_candidate_id": new_candidate_id,
        },
        template_id="forced_contradiction_dirty_v2",
        template_kind="dirty",
        template_split="main",
    )


def _build_dirty_v3_scenario(
    scenario_id: str,
    canonical_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    claim_text: str,
    contradiction_text: str,
    question_before: str,
    question_after: str,
) -> Scenario:
    old_candidate_id = scenario_id + "-candidate-old"
    new_candidate_id = scenario_id + "-candidate-new"
    old_claim = "{} acquired {}".format(buyer, target)
    new_claim = "{} did not acquire {}".format(buyer, target)

    old_candidate = _make_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        trust_score=0.97,
        verification_score=0.96,
        source_kind="archived_filing",
        staleness_score=0.22,
    )
    new_candidate = _make_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=contradiction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(days=30),
        trust_score=0.90,
        verification_score=0.90,
        source_kind="recent_regulator_update",
        contradicts=[old_candidate_id],
    )

    before_question = _make_question(
        question_id=scenario_id + "-question-before",
        text=question_before,
        canonical_id=canonical_id,
        phase="before_contradiction",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_question(
        question_id=scenario_id + "-question-after",
        text=question_after,
        canonical_id=canonical_id,
        phase="after_contradiction",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[old_candidate_id],
        asked_at=base_time + timedelta(days=30, minutes=1),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description=(
            "A once-strong acquisition belief persists long enough to become stale before a credible contradictory update arrives."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "true_state_sequence": [
                {"turn": 1, "truth": old_claim},
                {"turn": 3, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_before,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=contradiction_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=question_after,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "contradiction_turn": 3,
            "contradiction_timestamp": (base_time + timedelta(days=30)).isoformat(),
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": new_candidate_id,
        },
        template_id="forced_contradiction_dirty_v3",
        template_kind="dirty",
        template_split="heldout",
    )


def _build_dirty_v4_scenario(
    scenario_id: str,
    canonical_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    claim_text: str,
    contradiction_text: str,
    question_before: str,
    question_after: str,
) -> Scenario:
    first_old_candidate_id = scenario_id + "-candidate-old-1"
    second_old_candidate_id = scenario_id + "-candidate-old-2"
    new_candidate_id = scenario_id + "-candidate-new"
    old_claim = "{} acquired {}".format(buyer, target)
    new_claim = "{} did not acquire {}".format(buyer, target)
    corroborating_text = "A follow-up report repeats that {} completed the acquisition of {}.".format(buyer, target)

    first_old_candidate = _make_candidate(
        candidate_id=first_old_candidate_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        trust_score=0.74,
        verification_score=0.74,
        source_kind="analyst_note",
    )
    second_old_candidate = _make_candidate(
        candidate_id=second_old_candidate_id,
        canonical_id=canonical_id,
        raw_text=corroborating_text,
        canonical_claim=old_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=0.80,
        verification_score=0.80,
        source_kind="followup_report",
        recurrence_count=1,
        corroboration_count=1,
        supports=[first_old_candidate_id],
    )
    new_candidate = _make_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=contradiction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=3),
        trust_score=0.82,
        verification_score=0.82,
        source_kind="regulator_followup",
        contradicts=[first_old_candidate_id, second_old_candidate_id],
    )

    before_question = _make_question(
        question_id=scenario_id + "-question-before",
        text=question_before,
        canonical_id=canonical_id,
        phase="before_contradiction",
        gold_candidate_ids=[first_old_candidate_id, second_old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=2),
    )
    after_question = _make_question(
        question_id=scenario_id + "-question-after",
        text=question_after,
        canonical_id=canonical_id,
        phase="after_contradiction",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[first_old_candidate_id, second_old_candidate_id],
        asked_at=base_time + timedelta(minutes=4),
    )

    # Hold the new contradiction just below eager overwrite while keeping it below CQ durable promotion.
    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description=(
            "A corroborated acquisition claim becomes durable, then a credible contradiction arrives that should demote the old belief without clearing eager overwrite."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "true_state_sequence": [
                {"turn": 1, "truth": "uncertain"},
                {"turn": 2, "truth": old_claim},
                {"turn": 4, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=first_old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=corroborating_text,
                candidate=second_old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=question_before,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.OBSERVATION,
                turn_index=4,
                text=contradiction_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-5",
                kind=EventKind.QUESTION,
                turn_index=5,
                text=question_after,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "contradiction_turn": 4,
            "contradiction_timestamp": (base_time + timedelta(minutes=3)).isoformat(),
            "old_candidate_id": second_old_candidate_id,
            "old_candidate_ids": [first_old_candidate_id, second_old_candidate_id],
            "new_candidate_id": new_candidate_id,
        },
        template_id="forced_contradiction_dirty_v4",
        template_kind="dirty",
        template_split="heldout",
    )


def _build_dirty_v5_scenario(
    scenario_id: str,
    canonical_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    claim_text: str,
    contradiction_text: str,
    question_before: str,
    question_after: str,
) -> Scenario:
    old_candidate_id = scenario_id + "-candidate-old"
    first_new_candidate_id = scenario_id + "-candidate-new-1"
    second_new_candidate_id = scenario_id + "-candidate-new-2"
    old_claim = "{} acquired {}".format(buyer, target)
    new_claim = "{} did not acquire {}".format(buyer, target)
    second_correction_text = (
        "A later clarification confirms {} did not complete the acquisition of {}.".format(buyer, target)
    )

    old_candidate = _make_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        trust_score=0.86,
        verification_score=0.86,
        source_kind="press_release",
    )
    first_new_candidate = _make_candidate(
        candidate_id=first_new_candidate_id,
        canonical_id=canonical_id,
        raw_text=contradiction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=2),
        trust_score=0.72,
        verification_score=0.72,
        source_kind="preliminary_court_update",
        contradicts=[old_candidate_id],
    )
    second_new_candidate = _make_candidate(
        candidate_id=second_new_candidate_id,
        canonical_id=canonical_id,
        raw_text=second_correction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=3),
        trust_score=0.88,
        verification_score=0.88,
        source_kind="court_clarification",
        corroboration_count=1,
        contradicts=[old_candidate_id],
        supports=[first_new_candidate_id],
    )

    before_question = _make_question(
        question_id=scenario_id + "-question-before",
        text=question_before,
        canonical_id=canonical_id,
        phase="before_contradiction",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_question(
        question_id=scenario_id + "-question-after",
        text=question_after,
        canonical_id=canonical_id,
        phase="after_contradiction",
        gold_candidate_ids=[second_new_candidate_id],
        forbidden_candidate_ids=[old_candidate_id],
        asked_at=base_time + timedelta(minutes=4),
    )

    # Keep second_new below Reflection's overwrite threshold (0.88 < 0.86 + 0.05),
    # but strong enough that Naive's reinforce path lifts first_new above old (0.91 > 0.86).
    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description=(
            "A two-step correction cascade arrives after an early acquisition claim, letting CQ and Naive recover while Reflection still blocks overwrite."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "true_state_sequence": [
                {"turn": 1, "truth": old_claim},
                {"turn": 4, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_before,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=contradiction_text,
                candidate=first_new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.OBSERVATION,
                turn_index=4,
                text=second_correction_text,
                candidate=second_new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-5",
                kind=EventKind.QUESTION,
                turn_index=5,
                text=question_after,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "contradiction_turn": 3,
            "contradiction_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": second_new_candidate_id,
            "new_candidate_ids": [first_new_candidate_id, second_new_candidate_id],
        },
        template_id="forced_contradiction_dirty_v5",
        template_kind="dirty",
        template_split="heldout",
    )


def _build_dirty_v6_scenario(
    scenario_id: str,
    canonical_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    claim_text: str,
    contradiction_text: str,
    question_before: str,
    question_after: str,
) -> Scenario:
    old_candidate_id = scenario_id + "-candidate-old"
    new_candidate_id = scenario_id + "-candidate-new"
    old_claim = "{} acquired {}".format(buyer, target)
    new_claim = "{} did not acquire {}".format(buyer, target)

    old_candidate = _make_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        trust_score=0.86,
        verification_score=0.86,
        source_kind="press_release",
    )
    new_candidate = _make_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=contradiction_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=2),
        trust_score=0.84,
        verification_score=0.84,
        source_kind="court_filing_extract",
        semantic_uncertainty=0.10,
        contradicts=[old_candidate_id],
    )

    before_question = _make_question(
        question_id=scenario_id + "-question-before",
        text=question_before,
        canonical_id=canonical_id,
        phase="before_contradiction",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_question(
        question_id=scenario_id + "-question-after",
        text=question_after,
        canonical_id=canonical_id,
        phase="after_contradiction",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[old_candidate_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FORCED_CONTRADICTION,
        description=(
            "A cautious but authoritative contradiction arrives with enough uncertainty that CQ recovers through demotion-plus-pending while confidence-first eager policies cling to the old belief."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "true_state_sequence": [
                {"turn": 1, "truth": old_claim},
                {"turn": 3, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_before,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=contradiction_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=question_after,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "contradiction_turn": 3,
            "contradiction_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": new_candidate_id,
        },
        template_id="forced_contradiction_dirty_v6",
        template_kind="dirty",
        template_split="heldout",
    )


def _build_scope_clean_v1_scenario(
    scenario_id: str,
    canonical_id: str,
    project_a: str,
    project_b: str,
    base_time: datetime,
) -> Scenario:
    project_a_scope = "project-" + project_a
    project_b_scope = "project-" + project_b
    project_a_candidate_id = scenario_id + "-candidate-project-a"
    project_b_candidate_id = scenario_id + "-candidate-project-b"
    project_a_claim = "{} tests use pytest -q".format(project_a)
    project_b_claim = "{} tests use npm test".format(project_b)
    project_a_text = "In project {}, the test command is pytest -q.".format(project_a)
    project_b_text = "In project {}, the test command is npm test.".format(project_b)

    project_a_candidate = _make_scoped_candidate(
        candidate_id=project_a_candidate_id,
        canonical_id=canonical_id,
        raw_text=project_a_text,
        canonical_claim=project_a_claim,
        observed_at=base_time,
        trust_score=0.82,
        verification_score=0.82,
        source_kind="project_readme",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
    )
    project_b_candidate = _make_scoped_candidate(
        candidate_id=project_b_candidate_id,
        canonical_id=canonical_id,
        raw_text=project_b_text,
        canonical_claim=project_b_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=0.84,
        verification_score=0.84,
        source_kind="project_readme",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_b_scope,
    )
    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-off-scope-probe",
        text="For project {}, which command should run tests?".format(project_a),
        canonical_id=canonical_id,
        phase="off_scope_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
        gold_candidate_ids=[project_a_candidate_id],
        forbidden_candidate_ids=[project_b_candidate_id],
        asked_at=base_time + timedelta(minutes=2),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.SCOPE_CONTAMINATION,
        description=(
            "Two project-scoped conventions share a canonical id; scope-aware memory lookup should answer with the requested project."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "scope_truth": {
                project_a_scope: project_a_claim,
                project_b_scope: project_b_claim,
            },
            "probe_scope_key": project_a_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=project_a_text,
                candidate=project_a_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=project_b_text,
                candidate=project_b_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "off_scope_probe",
            "gold_candidate_id": project_a_candidate_id,
            "forbidden_candidate_ids": [project_b_candidate_id],
            "should_not_promote_candidate_ids": [],
        },
        template_id="scope_contamination_clean_v1",
        template_kind="clean",
        template_split="main",
    )


def _build_scope_dirty_broad_claim_v1_scenario(
    scenario_id: str,
    canonical_id: str,
    project_a: str,
    project_b: str,
    base_time: datetime,
) -> Scenario:
    project_a_scope = "project-" + project_a
    project_candidate_id = scenario_id + "-candidate-project"
    broad_candidate_id = scenario_id + "-candidate-broad-contaminant"
    project_claim = "{} tests use pytest -q".format(project_a)
    broad_claim = "All projects use npm test"
    project_text = "In project {}, the test command is pytest -q.".format(project_a)
    broad_text = (
        "A workspace note says all projects, including {}, should use npm test for tests.".format(project_b)
    )

    project_candidate = _make_scoped_candidate(
        candidate_id=project_candidate_id,
        canonical_id=canonical_id,
        raw_text=project_text,
        canonical_claim=project_claim,
        observed_at=base_time,
        trust_score=0.82,
        verification_score=0.82,
        source_kind="project_readme",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
    )
    broad_candidate = _make_scoped_candidate(
        candidate_id=broad_candidate_id,
        canonical_id=canonical_id,
        raw_text=broad_text,
        canonical_claim=broad_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=0.66,
        verification_score=0.66,
        source_kind="workspace_note",
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        semantic_uncertainty=0.02,
    )
    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-off-scope-probe",
        text="For project {}, which command should run tests?".format(project_a),
        canonical_id=canonical_id,
        phase="off_scope_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
        gold_candidate_ids=[project_candidate_id],
        forbidden_candidate_ids=[broad_candidate_id],
        asked_at=base_time + timedelta(minutes=2),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.SCOPE_CONTAMINATION,
        description=(
            "A project-scoped convention is followed by a broad lower-confidence contaminant that eager policies may promote under permissive global scope matching."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "scope_truth": {
                project_a_scope: project_claim,
                "global": "not durable enough for project-specific override",
            },
            "probe_scope_key": project_a_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=project_text,
                candidate=project_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=broad_text,
                candidate=broad_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "off_scope_probe",
            "gold_candidate_id": project_candidate_id,
            "forbidden_candidate_ids": [broad_candidate_id],
            "should_not_promote_candidate_ids": [broad_candidate_id],
        },
        template_id="scope_contamination_dirty_broad_claim_v1",
        template_kind="dirty",
        template_split="main",
    )


def _build_scope_clean_v2_scenario(
    scenario_id: str,
    canonical_id: str,
    project_a: str,
    project_b: str,
    base_time: datetime,
) -> Scenario:
    project_a_scope = "project-" + project_a
    project_b_scope = "project-" + project_b
    project_a_candidate_id = scenario_id + "-candidate-project-a-heldout"
    project_b_candidate_id = scenario_id + "-candidate-project-b-heldout"
    project_a_claim = "{} verification uses pytest -q".format(project_a)
    project_b_claim = "{} verification uses npm test".format(project_b)
    project_a_text = "For project {}, verification runs with pytest -q.".format(project_a)
    project_b_text = "For project {}, verification runs with npm test.".format(project_b)

    project_a_candidate = _make_scoped_candidate(
        candidate_id=project_a_candidate_id,
        canonical_id=canonical_id,
        raw_text=project_a_text,
        canonical_claim=project_a_claim,
        observed_at=base_time,
        trust_score=0.82,
        verification_score=0.82,
        source_kind="project_readme",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
    )
    project_b_candidate = _make_scoped_candidate(
        candidate_id=project_b_candidate_id,
        canonical_id=canonical_id,
        raw_text=project_b_text,
        canonical_claim=project_b_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=0.84,
        verification_score=0.84,
        source_kind="project_readme",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_b_scope,
    )
    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-off-scope-probe",
        text="For project {}, which command should run verification?".format(project_a),
        canonical_id=canonical_id,
        phase="off_scope_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
        gold_candidate_ids=[project_a_candidate_id],
        forbidden_candidate_ids=[project_b_candidate_id],
        asked_at=base_time + timedelta(minutes=2),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.SCOPE_CONTAMINATION,
        description=(
            "Held-out clean scope probe with two project-scoped verification commands sharing a canonical id."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "scope_truth": {
                project_a_scope: project_a_claim,
                project_b_scope: project_b_claim,
            },
            "probe_scope_key": project_a_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=project_a_text,
                candidate=project_a_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=project_b_text,
                candidate=project_b_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "off_scope_probe",
            "gold_candidate_id": project_a_candidate_id,
            "forbidden_candidate_ids": [project_b_candidate_id],
            "should_not_promote_candidate_ids": [],
        },
        template_id="scope_contamination_clean_v2",
        template_kind="clean",
        template_split="heldout",
    )


def _build_scope_dirty_broad_claim_v3_scenario(
    scenario_id: str,
    canonical_id: str,
    project_a: str,
    project_b: str,
    base_time: datetime,
) -> Scenario:
    project_a_scope = "project-" + project_a
    broad_candidate_id = scenario_id + "-candidate-broad-contaminant-heldout"
    project_candidate_id = scenario_id + "-candidate-project-override"
    broad_claim = "All projects use npm test"
    project_claim = "{} tests use pytest -q".format(project_a)
    broad_text = "A workspace-wide note says all projects should use npm test for tests."
    project_text = (
        "In project {}, tests use pytest -q, overriding the workspace-wide npm test note.".format(project_a)
    )

    broad_candidate = _make_scoped_candidate(
        candidate_id=broad_candidate_id,
        canonical_id=canonical_id,
        raw_text=broad_text,
        canonical_claim=broad_claim,
        observed_at=base_time,
        trust_score=0.66,
        verification_score=0.66,
        source_kind="workspace_note",
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
    )
    project_candidate = _make_scoped_candidate(
        candidate_id=project_candidate_id,
        canonical_id=canonical_id,
        raw_text=project_text,
        canonical_claim=project_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=0.64,
        verification_score=0.64,
        source_kind="project_override",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
        contradicts=[broad_candidate_id],
    )
    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-off-scope-probe",
        text="For project {}, which command should run tests?".format(project_a),
        canonical_id=canonical_id,
        phase="off_scope_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_a_scope,
        gold_candidate_ids=[project_candidate_id],
        forbidden_candidate_ids=[broad_candidate_id],
        asked_at=base_time + timedelta(minutes=2),
    )

    # Calibration enforced by test_heldout_dirty_template_pins_broad_first_calibration:
    # broad.promotion_score (0.66) < CQ project-convention threshold (0.70).
    # project.strength (0.64) < broad.strength + overwrite_margin (0.71), so Reflection blocks overwrite.
    # broad.strength (0.66) > project.strength (0.64), so Naive picks broad confidence-first.
    # project.strength (0.64) >= pending-use threshold (0.35), so CQ can pending-answer.
    # The project override later contests the broad candidate in-store, lowering its score further.
    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.SCOPE_CONTAMINATION,
        description=(
            "Held-out broad-first probe where a global testing convention is followed by a lower-strength project override."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "scope_truth": {
                project_a_scope: project_claim,
                "global": "broad claim should not override a project-specific command",
            },
            "probe_scope_key": project_a_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=broad_text,
                candidate=broad_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=project_text,
                candidate=project_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "off_scope_probe",
            "gold_candidate_id": project_candidate_id,
            "forbidden_candidate_ids": [broad_candidate_id],
            "should_not_promote_candidate_ids": [broad_candidate_id],
        },
        template_id="scope_contamination_dirty_broad_claim_v3",
        template_kind="dirty",
        template_split="heldout",
    )


def _workspace_parent_scope_keys(
    project_a: str,
    project_b: str,
    *,
    multi_level: bool,
) -> Tuple[str, str]:
    workspace_scope = "workspace-{}-{}".format(project_a, project_b)
    if multi_level:
        return workspace_scope, "{}/group-core/project-{}".format(workspace_scope, project_a)
    return workspace_scope, "{}/project-{}".format(workspace_scope, project_a)


def _build_scope_clean_workspace_parent_scenario(
    scenario_id: str,
    canonical_id: str,
    project_a: str,
    project_b: str,
    base_time: datetime,
    *,
    template_id: str,
    template_split: str,
    workspace_strength: float,
    multi_level: bool,
) -> Scenario:
    workspace_scope, project_scope = _workspace_parent_scope_keys(
        project_a,
        project_b,
        multi_level=multi_level,
    )
    workspace_candidate_id = scenario_id + "-candidate-workspace-default"
    workspace_claim = "{} default tests use npm test".format(workspace_scope)
    workspace_text = "Workspace {} defines npm test as the default test command.".format(workspace_scope)

    workspace_candidate = _make_scoped_candidate(
        candidate_id=workspace_candidate_id,
        canonical_id=canonical_id,
        raw_text=workspace_text,
        canonical_claim=workspace_claim,
        observed_at=base_time,
        trust_score=workspace_strength,
        verification_score=workspace_strength,
        source_kind="workspace_readme",
        scope_level=ScopeLevel.WORKSPACE,
        scope_key=workspace_scope,
    )
    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-off-scope-probe",
        text="For project {} in workspace {}, which command should run tests?".format(
            project_a,
            workspace_scope,
        ),
        canonical_id=canonical_id,
        phase="off_scope_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        gold_candidate_ids=[workspace_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.SCOPE_CONTAMINATION,
        description=(
            "A clean workspace default should answer a project query through shared parent-scope matching."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "scope_truth": {
                workspace_scope: workspace_claim,
                project_scope: "inherits {}".format(workspace_claim),
            },
            "probe_scope_key": project_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=workspace_text,
                candidate=workspace_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "off_scope_probe",
            "gold_candidate_id": workspace_candidate_id,
            "forbidden_candidate_ids": [],
            "should_not_promote_candidate_ids": [],
            "workspace_candidate_id": workspace_candidate_id,
            "workspace_scope_key": workspace_scope,
            "project_scope_key": project_scope,
        },
        template_id=template_id,
        template_kind="clean",
        template_split=template_split,
    )


def _build_scope_dirty_workspace_parent_scenario(
    scenario_id: str,
    canonical_id: str,
    project_a: str,
    project_b: str,
    base_time: datetime,
    *,
    template_id: str,
    template_split: str,
    workspace_strength: float,
    project_strength: float,
    multi_level: bool,
) -> Scenario:
    workspace_scope, project_scope = _workspace_parent_scope_keys(
        project_a,
        project_b,
        multi_level=multi_level,
    )
    workspace_candidate_id = scenario_id + "-candidate-workspace-default"
    project_candidate_id = scenario_id + "-candidate-project-override"
    workspace_claim = "{} default tests use npm test".format(workspace_scope)
    project_claim = "{} tests use pytest -q".format(project_a)
    workspace_text = "Workspace {} defines npm test as the default test command.".format(workspace_scope)
    project_text = (
        "Project {} overrides the workspace default and runs tests with pytest -q.".format(project_a)
    )

    workspace_candidate = _make_scoped_candidate(
        candidate_id=workspace_candidate_id,
        canonical_id=canonical_id,
        raw_text=workspace_text,
        canonical_claim=workspace_claim,
        observed_at=base_time,
        trust_score=workspace_strength,
        verification_score=workspace_strength,
        source_kind="workspace_readme",
        scope_level=ScopeLevel.WORKSPACE,
        scope_key=workspace_scope,
    )
    project_candidate = _make_scoped_candidate(
        candidate_id=project_candidate_id,
        canonical_id=canonical_id,
        raw_text=project_text,
        canonical_claim=project_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=project_strength,
        verification_score=project_strength,
        source_kind="project_override",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        contradicts=[workspace_candidate_id],
    )
    project_probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-off-scope-probe",
        text="For project {} in workspace {}, which command should run tests?".format(
            project_a,
            workspace_scope,
        ),
        canonical_id=canonical_id,
        phase="off_scope_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        gold_candidate_ids=[project_candidate_id],
        forbidden_candidate_ids=[workspace_candidate_id],
        asked_at=base_time + timedelta(minutes=2),
    )
    workspace_probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-workspace-probe",
        text="For workspace {}, what is the default test command?".format(workspace_scope),
        canonical_id=canonical_id,
        phase="workspace_probe",
        scope_level=ScopeLevel.WORKSPACE,
        scope_key=workspace_scope,
        gold_candidate_ids=[workspace_candidate_id],
        forbidden_candidate_ids=[project_candidate_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    # Calibration enforced by workspace-parent scope tests:
    # workspace.strength is durable-eligible and remains a legitimate workspace default.
    # project.strength is pending-eligible but below the project-convention promotion threshold.
    # project.strength < workspace.confidence + overwrite_margin, so Reflection refuses overwrite.
    # project.contradicts carries the load-bearing edge CQ uses for exact-scope pending override lookup.
    # Naive still selects the workspace durable confidence-first when both workspace and project durables match.
    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.SCOPE_CONTAMINATION,
        description=(
            "A durable workspace default remains valid generally, but a project override should shadow it for that project only."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "scope_truth": {
                workspace_scope: workspace_claim,
                project_scope: project_claim,
            },
            "probe_scope_key": project_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=workspace_text,
                candidate=workspace_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=project_text,
                candidate=project_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=project_probe_question.text,
                question=project_probe_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=workspace_probe_question.text,
                question=workspace_probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "off_scope_probe",
            "workspace_probe_phase": "workspace_probe",
            "gold_candidate_id": project_candidate_id,
            "forbidden_candidate_ids": [workspace_candidate_id],
            "should_not_promote_candidate_ids": [],
            "workspace_candidate_id": workspace_candidate_id,
            "project_candidate_id": project_candidate_id,
            "workspace_scope_key": workspace_scope,
            "project_scope_key": project_scope,
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def _build_useful_pending_clean_scenario(
    scenario_id: str,
    canonical_id: str,
    project: str,
    base_time: datetime,
    *,
    template_id: str,
    template_split: str,
    command: str,
    activity: str,
    strength: float,
) -> Scenario:
    project_scope = "project-" + project
    candidate_id = scenario_id + "-candidate-useful-pending"
    claim = "{} {} use {}".format(project, activity, command)
    text = "A project note says {} in project {} use {}, pending confirmation.".format(
        activity,
        project,
        command,
    )
    candidate = _make_scoped_candidate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=text,
        canonical_claim=claim,
        observed_at=base_time,
        trust_score=strength,
        verification_score=strength,
        source_kind="project_note",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
    )
    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-pending-probe",
        text="For project {}, which command should run {}?".format(project, activity),
        canonical_id=canonical_id,
        phase="pending_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        gold_candidate_ids=[candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.USEFUL_PENDING_MEMORY,
        description=(
            "A useful project convention stays below the durable-promotion threshold but is strong enough for pending use."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "pending_truth": {
                project_scope: claim,
            },
            "probe_scope_key": project_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=text,
                candidate=candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "pending_probe",
            "gold_candidate_id": candidate_id,
            "forbidden_candidate_ids": [],
            "should_not_promote_candidate_ids": [candidate_id],
        },
        template_id=template_id,
        template_kind="clean",
        template_split=template_split,
    )


def _build_useful_pending_dirty_refinement_scenario(
    scenario_id: str,
    canonical_id: str,
    project: str,
    base_time: datetime,
    *,
    template_id: str,
    template_split: str,
    tentative_command: str,
    refined_command: str,
    activity: str,
    tentative_strength: float,
    refined_strength: float,
    refinement_reason: str,
) -> Scenario:
    project_scope = "project-" + project
    tentative_candidate_id = scenario_id + "-candidate-tentative"
    refined_candidate_id = scenario_id + "-candidate-refinement"
    tentative_claim = "{} {} use {}".format(project, activity, tentative_command)
    refined_claim = "{} {} use {}".format(project, activity, refined_command)
    tentative_text = "A draft project note says {} in project {} use {}.".format(
        activity,
        project,
        tentative_command,
    )
    refined_text = "A maintainer clarified that {} in project {} use {}; {}.".format(
        activity,
        project,
        refined_command,
        refinement_reason,
    )

    tentative_candidate = _make_scoped_candidate(
        candidate_id=tentative_candidate_id,
        canonical_id=canonical_id,
        raw_text=tentative_text,
        canonical_claim=tentative_claim,
        observed_at=base_time,
        trust_score=tentative_strength,
        verification_score=tentative_strength,
        source_kind="draft_project_note",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
    )
    refined_candidate = _make_scoped_candidate(
        candidate_id=refined_candidate_id,
        canonical_id=canonical_id,
        raw_text=refined_text,
        canonical_claim=refined_claim,
        observed_at=base_time + timedelta(minutes=1),
        trust_score=refined_strength,
        verification_score=refined_strength,
        source_kind="maintainer_clarification",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        contradicts=[tentative_candidate_id],
    )
    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-pending-probe",
        text="For project {}, which command should run {}?".format(project, activity),
        canonical_id=canonical_id,
        phase="pending_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        gold_candidate_ids=[refined_candidate_id],
        forbidden_candidate_ids=[tentative_candidate_id],
        asked_at=base_time + timedelta(minutes=2),
    )

    # Calibration enforced by test_useful_pending_calibration_holds and
    # test_dirty_template_pins_refinement_behavior:
    # - both strengths stay in [0.35, 0.70), so neither candidate is durable-eligible for CQ.
    # - refined_strength < tentative_strength + overwrite_margin (0.05), so Reflection contests it.
    # - Naive's confidence-first answer selection picks the older, stronger tentative durable.
    # - CQ excludes CONTESTED candidates and answers from the refined pending candidate.
    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.USEFUL_PENDING_MEMORY,
        description=(
            "A tentative project convention is refined before any candidate clears the durable-promotion threshold."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "pending_truth": {
                project_scope: refined_claim,
            },
            "probe_scope_key": project_scope,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=tentative_text,
                candidate=tentative_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=refined_text,
                candidate=refined_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "probe_phase": "pending_probe",
            "gold_candidate_id": refined_candidate_id,
            "forbidden_candidate_ids": [tentative_candidate_id],
            "should_not_promote_candidate_ids": [tentative_candidate_id],
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def _false_corroboration_supports(candidate_ids: List[str], index: int) -> List[str]:
    return candidate_ids[:index]


def _build_false_corroboration_clean_scenario(
    scenario_id: str,
    canonical_id: str,
    project: str,
    base_time: datetime,
    *,
    template_id: str,
    template_split: str,
    command: str,
    activity: str,
) -> Scenario:
    project_scope = "project-" + project
    candidate_ids = [
        "{}-candidate-independent-{}".format(scenario_id, index + 1)
        for index in range(5)
    ]
    claim = "{} {} use {}".format(project, activity, command)
    events = []
    for index, candidate_id in enumerate(candidate_ids):
        text = "Independent source {} says {} in project {} use {}.".format(
            index + 1,
            activity,
            project,
            command,
        )
        candidate = _make_scoped_candidate(
            candidate_id=candidate_id,
            canonical_id=canonical_id,
            raw_text=text,
            canonical_claim=claim,
            observed_at=base_time + timedelta(minutes=index),
            trust_score=0.32,
            verification_score=0.32,
            source_kind="independent_project_note",
            source_id="independent-{}-{}".format(project, index + 1),
            scope_level=ScopeLevel.PROJECT,
            scope_key=project_scope,
            supports=_false_corroboration_supports(candidate_ids, index),
        )
        events.append(
            ScenarioEvent(
                event_id="{}-event-{}".format(scenario_id, index + 1),
                kind=EventKind.OBSERVATION,
                turn_index=index + 1,
                text=text,
                candidate=candidate,
            )
        )

    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-corroboration-probe",
        text="For project {}, which command should run {}?".format(project, activity),
        canonical_id=canonical_id,
        phase="corroboration_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        gold_candidate_ids=[candidate_ids[-1]],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=5),
    )
    events.append(
        ScenarioEvent(
            event_id=scenario_id + "-event-6",
            kind=EventKind.QUESTION,
            turn_index=6,
            text=probe_question.text,
            question=probe_question,
        )
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FALSE_CORROBORATION,
        description=(
            "Independent weak project-convention sources should count as corroboration and become durable."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "source_independence": "distinct",
            "scope_truth": {project_scope: claim},
            "probe_scope_key": project_scope,
            "final_candidate_id": candidate_ids[-1],
        },
        oracle_events=events,
        expected_lifecycle={
            "probe_phase": "corroboration_probe",
            "gold_candidate_id": candidate_ids[-1],
            "source_candidate_ids": candidate_ids,
            "should_not_promote_candidate_ids": [],
        },
        template_id=template_id,
        template_kind="clean",
        template_split=template_split,
    )


def _build_false_corroboration_dirty_scenario(
    scenario_id: str,
    canonical_id: str,
    project: str,
    base_time: datetime,
    *,
    template_id: str,
    template_split: str,
    command: str,
    activity: str,
) -> Scenario:
    project_scope = "project-" + project
    candidate_ids = [
        "{}-candidate-mirrored-{}".format(scenario_id, index + 1)
        for index in range(5)
    ]
    claim = "{} {} use {}".format(project, activity, command)
    mirror_source_id = "mirrored-{}-source".format(project)
    events = []
    for index, candidate_id in enumerate(candidate_ids):
        text = "Mirrored source variant {} repeats that {} in project {} use {}.".format(
            index + 1,
            activity,
            project,
            command,
        )
        candidate = _make_scoped_candidate(
            candidate_id=candidate_id,
            canonical_id=canonical_id,
            raw_text=text,
            canonical_claim=claim,
            observed_at=base_time + timedelta(minutes=index),
            trust_score=0.32,
            verification_score=0.32,
            source_kind="mirrored_project_note",
            source_id=mirror_source_id,
            scope_level=ScopeLevel.PROJECT,
            scope_key=project_scope,
            supports=_false_corroboration_supports(candidate_ids, index),
        )
        events.append(
            ScenarioEvent(
                event_id="{}-event-{}".format(scenario_id, index + 1),
                kind=EventKind.OBSERVATION,
                turn_index=index + 1,
                text=text,
                candidate=candidate,
            )
        )

    probe_question = _make_scoped_question(
        question_id=scenario_id + "-question-corroboration-probe",
        text="For project {}, which command should run {}?".format(project, activity),
        canonical_id=canonical_id,
        phase="corroboration_probe",
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        gold_candidate_ids=[],
        forbidden_candidate_ids=candidate_ids,
        asked_at=base_time + timedelta(minutes=5),
    )
    events.append(
        ScenarioEvent(
            event_id=scenario_id + "-event-6",
            kind=EventKind.QUESTION,
            turn_index=6,
            text=probe_question.text,
            question=probe_question,
        )
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.FALSE_CORROBORATION,
        description=(
            "Mirrored weak project-convention sources should not count as independent corroboration."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "source_independence": "mirrored",
            "scope_truth": {project_scope: "no durable convention established by mirrored sources"},
            "probe_scope_key": project_scope,
            "mirror_source_id": mirror_source_id,
            "false_candidate_ids": candidate_ids,
        },
        oracle_events=events,
        expected_lifecycle={
            "probe_phase": "corroboration_probe",
            "false_corroboration_candidate_ids": candidate_ids,
            "should_not_promote_candidate_ids": candidate_ids,
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def _build_preference_clean_stable_v1_scenario(
    scenario_id: str,
    canonical_id: str,
    option_a: str,
    option_b: str,
    one_off_option: str,
    question_text: str,
    base_time: datetime,
) -> Scenario:
    del option_b, one_off_option
    stable_candidate_id = scenario_id + "-candidate-stable"
    stable_claim = "User prefers {} by default".format(option_a)
    stable_text = "I prefer {} by default.".format(option_a)

    stable_candidate = _make_preference_candidate(
        candidate_id=stable_candidate_id,
        canonical_id=canonical_id,
        raw_text=stable_text,
        canonical_claim=stable_claim,
        observed_at=base_time,
        strength=0.76,
        source_kind="user",
    )
    before_question = _make_preference_question(
        question_id=scenario_id + "-question-before",
        text=question_text,
        canonical_id=canonical_id,
        phase="before_drift",
        gold_candidate_ids=[stable_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_preference_question(
        question_id=scenario_id + "-question-after",
        text=question_text,
        canonical_id=canonical_id,
        phase="after_drift",
        gold_candidate_ids=[stable_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=2),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.PREFERENCE_DRIFT,
        description="Stable user preference with no drift pressure.",
        latent_truth_graph={
            "canonical_id": canonical_id,
            "standing_preference_sequence": [
                {"turn": 1, "truth": stable_claim},
                {"turn": 3, "truth": stable_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=stable_text,
                candidate=stable_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_text,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=question_text,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "old_candidate_id": stable_candidate_id,
            "new_candidate_id": stable_candidate_id,
            "should_not_promote_candidate_ids": [],
        },
        template_id="preference_drift_clean_stable_v1",
        template_kind="clean",
        template_split="main",
    )


def _build_preference_dirty_explicit_update_v1_scenario(
    scenario_id: str,
    canonical_id: str,
    option_a: str,
    option_b: str,
    one_off_option: str,
    question_text: str,
    base_time: datetime,
) -> Scenario:
    del one_off_option
    old_candidate_id = scenario_id + "-candidate-old-preference"
    new_candidate_id = scenario_id + "-candidate-updated-preference"
    old_claim = "User prefers {} by default".format(option_a)
    new_claim = "User prefers {} by default".format(option_b)
    old_text = "I prefer {} by default.".format(option_a)
    new_text = "Actually, update that: I prefer {} by default now.".format(option_b)

    old_candidate = _make_preference_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=old_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        strength=0.86,
        source_kind="user",
    )
    new_candidate = _make_preference_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=new_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=2),
        strength=0.64,
        source_kind="user_update",
        contradicts=[old_candidate_id],
    )
    before_question = _make_preference_question(
        question_id=scenario_id + "-question-before",
        text=question_text,
        canonical_id=canonical_id,
        phase="before_drift",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_preference_question(
        question_id=scenario_id + "-question-after",
        text=question_text,
        canonical_id=canonical_id,
        phase="after_drift",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[old_candidate_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.PREFERENCE_DRIFT,
        description="A strong standing preference is explicitly updated by weaker but usable current evidence.",
        latent_truth_graph={
            "canonical_id": canonical_id,
            "standing_preference_sequence": [
                {"turn": 1, "truth": old_claim},
                {"turn": 3, "truth": new_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=old_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_text,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=new_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=question_text,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": new_candidate_id,
            "contradiction_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "should_not_promote_candidate_ids": [],
        },
        template_id="preference_drift_dirty_explicit_update_v1",
        template_kind="dirty",
        template_split="main",
    )


def _build_preference_dirty_one_off_exception_v1_scenario(
    scenario_id: str,
    canonical_id: str,
    option_a: str,
    option_b: str,
    one_off_option: str,
    question_text: str,
    base_time: datetime,
) -> Scenario:
    del option_b
    old_candidate_id = scenario_id + "-candidate-standing-preference"
    one_off_candidate_id = scenario_id + "-candidate-one-off"
    old_claim = "User prefers {} by default".format(option_a)
    one_off_claim = "User wants {} only for the current one-off request".format(one_off_option)
    old_text = "I prefer {} by default.".format(option_a)
    one_off_text = "For this one request, use {}.".format(one_off_option)

    old_candidate = _make_preference_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=old_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        strength=0.86,
        source_kind="user",
    )
    one_off_candidate = _make_preference_candidate(
        candidate_id=one_off_candidate_id,
        canonical_id=canonical_id,
        raw_text=one_off_text,
        canonical_claim=one_off_claim,
        observed_at=base_time + timedelta(minutes=2),
        strength=0.30,
        source_kind="user_one_off",
    )
    before_question = _make_preference_question(
        question_id=scenario_id + "-question-before",
        text=question_text,
        canonical_id=canonical_id,
        phase="before_drift",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_preference_question(
        question_id=scenario_id + "-question-after",
        text=question_text,
        canonical_id=canonical_id,
        phase="after_drift",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[one_off_candidate_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.PREFERENCE_DRIFT,
        description="A low-strength one-off request should not replace the standing user preference.",
        latent_truth_graph={
            "canonical_id": canonical_id,
            "standing_preference_sequence": [
                {"turn": 1, "truth": old_claim},
                {"turn": 3, "truth": old_claim},
            ],
            "one_off_candidate_id": one_off_candidate_id,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=old_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_text,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=one_off_text,
                candidate=one_off_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=question_text,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": one_off_candidate_id,
            "should_not_promote_candidate_ids": [one_off_candidate_id],
        },
        template_id="preference_drift_dirty_one_off_exception_v1",
        template_kind="dirty",
        template_split="main",
    )


def _build_preference_clean_stable_v2_scenario(
    scenario_id: str,
    canonical_id: str,
    option_a: str,
    option_b: str,
    one_off_option: str,
    question_text: str,
    base_time: datetime,
) -> Scenario:
    del option_b, one_off_option
    stable_candidate_id = scenario_id + "-candidate-stable-heldout"
    stable_claim = "User prefers {} as the standing default".format(option_a)
    stable_text = "As a standing default, use {}.".format(option_a)

    stable_candidate = _make_preference_candidate(
        candidate_id=stable_candidate_id,
        canonical_id=canonical_id,
        raw_text=stable_text,
        canonical_claim=stable_claim,
        observed_at=base_time,
        strength=0.76,
        source_kind="user",
    )
    before_question = _make_preference_question(
        question_id=scenario_id + "-question-before",
        text=question_text,
        canonical_id=canonical_id,
        phase="before_drift",
        gold_candidate_ids=[stable_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_preference_question(
        question_id=scenario_id + "-question-after",
        text=question_text,
        canonical_id=canonical_id,
        phase="after_drift",
        gold_candidate_ids=[stable_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=2),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.PREFERENCE_DRIFT,
        description="Held-out stable user preference with no drift pressure.",
        latent_truth_graph={
            "canonical_id": canonical_id,
            "standing_preference_sequence": [
                {"turn": 1, "truth": stable_claim},
                {"turn": 3, "truth": stable_claim},
            ],
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=stable_text,
                candidate=stable_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_text,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.QUESTION,
                turn_index=3,
                text=question_text,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "old_candidate_id": stable_candidate_id,
            "new_candidate_id": stable_candidate_id,
            "should_not_promote_candidate_ids": [],
        },
        template_id="preference_drift_clean_stable_v2",
        template_kind="clean",
        template_split="heldout",
    )


def _build_preference_dirty_drift_back_v2_scenario(
    scenario_id: str,
    canonical_id: str,
    option_a: str,
    option_b: str,
    one_off_option: str,
    question_text: str,
    base_time: datetime,
) -> Scenario:
    old_candidate_id = scenario_id + "-candidate-old-heldout"
    new_candidate_id = scenario_id + "-candidate-updated-heldout"
    one_off_candidate_id = scenario_id + "-candidate-one-off-back-heldout"
    old_claim = "User prefers {} by default".format(option_a)
    new_claim = "User prefers {} by default".format(option_b)
    one_off_claim = "User wants {} only for the current one-off request".format(one_off_option)
    old_text = "I prefer {} by default.".format(option_a)
    new_text = "Change the default: use {} from now on.".format(option_b)
    one_off_text = "For this one checkpoint, use {}.".format(one_off_option)

    old_candidate = _make_preference_candidate(
        candidate_id=old_candidate_id,
        canonical_id=canonical_id,
        raw_text=old_text,
        canonical_claim=old_claim,
        observed_at=base_time,
        strength=0.86,
        source_kind="user",
    )
    new_candidate = _make_preference_candidate(
        candidate_id=new_candidate_id,
        canonical_id=canonical_id,
        raw_text=new_text,
        canonical_claim=new_claim,
        observed_at=base_time + timedelta(minutes=2),
        strength=0.64,
        source_kind="user_update",
        contradicts=[old_candidate_id],
    )
    one_off_candidate = _make_preference_candidate(
        candidate_id=one_off_candidate_id,
        canonical_id=canonical_id,
        raw_text=one_off_text,
        canonical_claim=one_off_claim,
        observed_at=base_time + timedelta(minutes=3),
        strength=0.30,
        source_kind="user_one_off",
    )
    before_question = _make_preference_question(
        question_id=scenario_id + "-question-before",
        text=question_text,
        canonical_id=canonical_id,
        phase="before_drift",
        gold_candidate_ids=[old_candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    after_question = _make_preference_question(
        question_id=scenario_id + "-question-after",
        text=question_text,
        canonical_id=canonical_id,
        phase="after_drift",
        gold_candidate_ids=[new_candidate_id],
        forbidden_candidate_ids=[old_candidate_id, one_off_candidate_id],
        asked_at=base_time + timedelta(minutes=4),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.PREFERENCE_DRIFT,
        description=(
            "Held-out drift-back probe where an explicit update is followed by a low-strength one-off return to the old style."
        ),
        latent_truth_graph={
            "canonical_id": canonical_id,
            "standing_preference_sequence": [
                {"turn": 1, "truth": old_claim},
                {"turn": 3, "truth": new_claim},
                {"turn": 5, "truth": new_claim},
            ],
            "one_off_candidate_id": one_off_candidate_id,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=old_text,
                candidate=old_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.QUESTION,
                turn_index=2,
                text=question_text,
                question=before_question,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=new_text,
                candidate=new_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.OBSERVATION,
                turn_index=4,
                text=one_off_text,
                candidate=one_off_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-5",
                kind=EventKind.QUESTION,
                turn_index=5,
                text=question_text,
                question=after_question,
            ),
        ],
        expected_lifecycle={
            "old_candidate_id": old_candidate_id,
            "new_candidate_id": new_candidate_id,
            "contradiction_timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "should_not_promote_candidate_ids": [one_off_candidate_id],
        },
        template_id="preference_drift_dirty_drift_back_v2",
        template_kind="dirty",
        template_split="heldout",
    )


def generate_preference_drift_scenarios(
    count: int,
    seed: int = 23,
    template_mix: str = "mixed",
) -> List[Scenario]:
    rng = random.Random(seed)
    scenarios = []
    for index in range(count):
        dimension, option_a, option_b, one_off_option, question_text = rng.choice(PREFERENCE_DIMENSIONS)
        template_id = _preference_template_id_for_index(index, template_mix)
        scenario_id = "preference_drift_{:03d}".format(index + 1)
        canonical_id = "user-preference-" + dimension
        base_time = datetime(2026, 3, 1, 9, 0, 0) + timedelta(days=index)

        if template_id == "preference_drift_clean_stable_v1":
            scenario = _build_preference_clean_stable_v1_scenario(
                scenario_id,
                canonical_id,
                option_a,
                option_b,
                one_off_option,
                question_text,
                base_time,
            )
        elif template_id == "preference_drift_dirty_explicit_update_v1":
            scenario = _build_preference_dirty_explicit_update_v1_scenario(
                scenario_id,
                canonical_id,
                option_a,
                option_b,
                one_off_option,
                question_text,
                base_time,
            )
        elif template_id == "preference_drift_dirty_one_off_exception_v1":
            scenario = _build_preference_dirty_one_off_exception_v1_scenario(
                scenario_id,
                canonical_id,
                option_a,
                option_b,
                one_off_option,
                question_text,
                base_time,
            )
        elif template_id == "preference_drift_clean_stable_v2":
            scenario = _build_preference_clean_stable_v2_scenario(
                scenario_id,
                canonical_id,
                option_a,
                option_b,
                one_off_option,
                question_text,
                base_time,
            )
        elif template_id == "preference_drift_dirty_drift_back_v2":
            scenario = _build_preference_dirty_drift_back_v2_scenario(
                scenario_id,
                canonical_id,
                option_a,
                option_b,
                one_off_option,
                question_text,
                base_time,
            )
        else:
            raise ValueError("Unsupported template_id: {}".format(template_id))
        scenarios.append(scenario)
    return scenarios


def generate_scope_contamination_scenarios(
    count: int,
    seed: int = 17,
    template_mix: str = "mixed",
) -> List[Scenario]:
    rng = random.Random(seed)
    scenarios = []
    for index in range(count):
        project_a, project_b = rng.choice(PROJECT_SCOPE_PAIRS)
        template_id = _scope_template_id_for_index(index, template_mix)
        scenario_id = "scope_contamination_{:03d}".format(index + 1)
        canonical_id = "project-convention-test-command"
        base_time = datetime(2026, 2, 1, 9, 0, 0) + timedelta(days=index)

        if template_id == "scope_contamination_clean_v1":
            scenario = _build_scope_clean_v1_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
            )
        elif template_id == "scope_contamination_dirty_broad_claim_v1":
            scenario = _build_scope_dirty_broad_claim_v1_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
            )
        elif template_id == "scope_contamination_clean_v2":
            scenario = _build_scope_clean_v2_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
            )
        elif template_id == "scope_contamination_dirty_broad_claim_v3":
            scenario = _build_scope_dirty_broad_claim_v3_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
            )
        elif template_id == "scope_contamination_clean_workspace_parent_v1":
            scenario = _build_scope_clean_workspace_parent_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
                template_id=template_id,
                template_split="main",
                workspace_strength=0.80,
                multi_level=False,
            )
        elif template_id == "scope_contamination_dirty_workspace_parent_v1":
            scenario = _build_scope_dirty_workspace_parent_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
                template_id=template_id,
                template_split="main",
                workspace_strength=0.80,
                project_strength=0.64,
                multi_level=False,
            )
        elif template_id == "scope_contamination_clean_workspace_parent_v2":
            scenario = _build_scope_clean_workspace_parent_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
                template_id=template_id,
                template_split="heldout",
                workspace_strength=0.71,
                multi_level=True,
            )
        elif template_id == "scope_contamination_dirty_workspace_parent_v2":
            scenario = _build_scope_dirty_workspace_parent_scenario(
                scenario_id,
                canonical_id,
                project_a,
                project_b,
                base_time,
                template_id=template_id,
                template_split="heldout",
                workspace_strength=0.71,
                project_strength=0.66,
                multi_level=True,
            )
        else:
            raise ValueError("Unsupported template_id: {}".format(template_id))
        scenarios.append(scenario)
    return scenarios


def generate_useful_pending_memory_scenarios(
    count: int,
    seed: int = 31,
    template_mix: str = "mixed",
) -> List[Scenario]:
    rng = random.Random(seed)
    scenarios = []
    for index in range(count):
        project_a = rng.choice(USEFUL_PENDING_PROJECTS)
        template_id = _useful_pending_template_id_for_index(index, template_mix)
        scenario_id = "useful_pending_{:03d}".format(index + 1)
        canonical_id = "useful-pending-project-command"
        base_time = datetime(2026, 3, 1, 9, 0, 0) + timedelta(days=index)

        if template_id == "useful_pending_clean_v1":
            scenario = _build_useful_pending_clean_scenario(
                scenario_id,
                canonical_id,
                project_a,
                base_time,
                template_id=template_id,
                template_split="main",
                command="pytest -q",
                activity="local checks",
                strength=0.62,
            )
        elif template_id == "useful_pending_dirty_refinement_v1":
            scenario = _build_useful_pending_dirty_refinement_scenario(
                scenario_id,
                canonical_id,
                project_a,
                base_time,
                template_id=template_id,
                template_split="main",
                tentative_command="npm test",
                refined_command="pytest -q",
                activity="local checks",
                tentative_strength=0.66,
                refined_strength=0.64,
                refinement_reason="the npm test note was for CI only",
            )
        elif template_id == "useful_pending_clean_v2":
            scenario = _build_useful_pending_clean_scenario(
                scenario_id,
                canonical_id,
                project_a,
                base_time,
                template_id=template_id,
                template_split="heldout",
                command="./scripts/check",
                activity="pre-merge checks",
                strength=0.61,
            )
        elif template_id == "useful_pending_dirty_refinement_v2":
            scenario = _build_useful_pending_dirty_refinement_scenario(
                scenario_id,
                canonical_id,
                project_a,
                base_time,
                template_id=template_id,
                template_split="heldout",
                tentative_command="make verify",
                refined_command="./scripts/check",
                activity="pre-merge checks",
                tentative_strength=0.65,
                refined_strength=0.63,
                refinement_reason="make verify was an old alias that is no longer used",
            )
        else:
            raise ValueError("Unsupported template_id: {}".format(template_id))
        scenarios.append(scenario)
    return scenarios


def generate_false_corroboration_scenarios(
    count: int,
    seed: int = 37,
    template_mix: str = "mixed",
) -> List[Scenario]:
    rng = random.Random(seed)
    scenarios = []
    for index in range(count):
        project = rng.choice(USEFUL_PENDING_PROJECTS)
        template_id = _false_corroboration_template_id_for_index(index, template_mix)
        scenario_id = "false_corroboration_{:03d}".format(index + 1)
        canonical_id = "false-corroboration-project-command"
        base_time = datetime(2026, 4, 1, 9, 0, 0) + timedelta(days=index)

        if template_id == "false_corroboration_clean_independent_v1":
            scenario = _build_false_corroboration_clean_scenario(
                scenario_id,
                canonical_id,
                project,
                base_time,
                template_id=template_id,
                template_split="main",
                command="./scripts/verify",
                activity="deployment checks",
            )
        elif template_id == "false_corroboration_dirty_mirrored_sources_v1":
            scenario = _build_false_corroboration_dirty_scenario(
                scenario_id,
                canonical_id,
                project,
                base_time,
                template_id=template_id,
                template_split="main",
                command="npm run verify",
                activity="deployment checks",
            )
        elif template_id == "false_corroboration_clean_independent_v2":
            scenario = _build_false_corroboration_clean_scenario(
                scenario_id,
                canonical_id,
                project,
                base_time,
                template_id=template_id,
                template_split="heldout",
                command="make audit",
                activity="release audit",
            )
        elif template_id == "false_corroboration_dirty_mirrored_sources_v2":
            scenario = _build_false_corroboration_dirty_scenario(
                scenario_id,
                canonical_id,
                project,
                base_time,
                template_id=template_id,
                template_split="heldout",
                command="bash ci.sh",
                activity="release audit",
            )
        else:
            raise ValueError("Unsupported template_id: {}".format(template_id))
        scenarios.append(scenario)
    return scenarios


def generate_forced_contradiction_scenarios(
    count: int,
    seed: int = 7,
    template_mix: str = "mixed",
) -> List[Scenario]:
    rng = random.Random(seed)
    scenarios = []
    for index in range(count):
        buyer, target = rng.choice(COMPANY_PAIRS)
        template_id = _template_id_for_index(index, template_mix)
        claim_text = rng.choice(CLAIM_TEMPLATES).format(buyer=buyer, target=target)
        contradiction_templates = (
            CONTRADICTION_TEMPLATES
            if template_id == "forced_contradiction_clean_v1"
            else DIRTY_CONTRADICTION_TEMPLATES
        )
        contradiction_text = rng.choice(contradiction_templates).format(buyer=buyer, target=target)
        question_before = rng.choice(QUESTION_TEMPLATES).format(buyer=buyer, target=target)
        question_after = rng.choice(QUESTION_TEMPLATES).format(buyer=buyer, target=target)
        scenario_id = "forced_contradiction_{:03d}".format(index + 1)
        canonical_id = "world-fact-{}-{}-acquisition-status".format(buyer.lower(), target.lower())
        base_time = datetime(2026, 1, 1, 9, 0, 0) + timedelta(days=index)

        if template_id == "forced_contradiction_clean_v1":
            scenario = _build_clean_v1_scenario(
                scenario_id,
                canonical_id,
                buyer,
                target,
                base_time,
                claim_text,
                contradiction_text,
                question_before,
                question_after,
            )
        elif template_id == "forced_contradiction_dirty_v1":
            scenario = _build_dirty_v1_scenario(
                scenario_id,
                canonical_id,
                buyer,
                target,
                base_time,
                claim_text,
                contradiction_text,
                question_before,
                question_after,
            )
        elif template_id == "forced_contradiction_dirty_v2":
            scenario = _build_dirty_v2_scenario(
                scenario_id,
                canonical_id,
                buyer,
                target,
                base_time,
                claim_text,
                contradiction_text,
                question_before,
                question_after,
            )
        elif template_id == "forced_contradiction_dirty_v3":
            scenario = _build_dirty_v3_scenario(
                scenario_id,
                canonical_id,
                buyer,
                target,
                base_time,
                claim_text,
                contradiction_text,
                question_before,
                question_after,
            )
        elif template_id == "forced_contradiction_dirty_v4":
            scenario = _build_dirty_v4_scenario(
                scenario_id,
                canonical_id,
                buyer,
                target,
                base_time,
                claim_text,
                contradiction_text,
                question_before,
                question_after,
            )
        elif template_id == "forced_contradiction_dirty_v5":
            scenario = _build_dirty_v5_scenario(
                scenario_id,
                canonical_id,
                buyer,
                target,
                base_time,
                claim_text,
                contradiction_text,
                question_before,
                question_after,
            )
        elif template_id == "forced_contradiction_dirty_v6":
            scenario = _build_dirty_v6_scenario(
                scenario_id,
                canonical_id,
                buyer,
                target,
                base_time,
                claim_text,
                contradiction_text,
                question_before,
                question_after,
            )
        else:
            raise ValueError("Unsupported template_id: {}".format(template_id))
        scenarios.append(scenario)
    return scenarios
