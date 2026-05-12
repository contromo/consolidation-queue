from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Sequence, Tuple

from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario, ScenarioEvent, TaskFamily


ADVERSARIAL_UPSTREAM_NOISE_TEMPLATE_IDS_BY_MIX: Dict[str, List[str]] = {
    "mixed": [
        "adversarial_retraction_v1",
        "adversarial_witness_conflict_v1",
        "adversarial_temporal_skew_v1",
        "adversarial_scope_narrowing_v1",
        "adversarial_pending_competition_v1",
    ],
    "dirty": [
        "adversarial_retraction_v1",
        "adversarial_witness_conflict_v1",
        "adversarial_temporal_skew_v1",
        "adversarial_scope_narrowing_v1",
        "adversarial_pending_competition_v1",
    ],
    "heldout": [
        "adversarial_retraction_v2",
        "adversarial_witness_conflict_v2",
        "adversarial_temporal_skew_v2",
        "adversarial_scope_narrowing_v2",
        "adversarial_pending_competition_v2",
    ],
}

WORLD_FACT_PAIRS: Sequence[Tuple[str, str]] = (
    ("Acme", "Northstar"),
    ("Helios", "Summit"),
    ("Lattice", "Pioneer"),
    ("Brightline", "Redwood"),
    ("Aster", "Keystone"),
    ("Vertex", "Harbor"),
)

PROJECT_SCOPE_PAIRS: Sequence[Tuple[str, str]] = (
    ("atlas", "beacon"),
    ("cedar", "delta"),
    ("ember", "forge"),
    ("granite", "harbor"),
    ("ivy", "juniper"),
)

PROJECT_NAMES: Sequence[str] = (
    "atlas",
    "cedar",
    "ember",
    "granite",
    "ivy",
    "juniper",
)

TEAM_PAIRS: Sequence[Tuple[str, str]] = (
    ("orion", "nova"),
    ("apex", "ember"),
    ("harbor", "skylark"),
    ("quartz", "rivet"),
    ("meridian", "sparrow"),
)

COMMAND_VARIANTS_V1: Sequence[Tuple[str, str, str]] = (
    ("npm test", "pytest -q", "tests"),
    ("./scripts/check", "python -m pytest -q", "checks"),
    ("make verify", "./bin/release-check", "release checks"),
)

COMMAND_VARIANTS_V2: Sequence[Tuple[str, str, str]] = (
    ("pnpm test", "uv run pytest -q", "verification"),
    ("cargo test", "just ci-test", "build validation"),
    ("./tools/audit", "python tools/release_check.py", "audit gates"),
)


def _adversarial_template_id_for_index(index: int, template_mix: str) -> str:
    if template_mix not in ADVERSARIAL_UPSTREAM_NOISE_TEMPLATE_IDS_BY_MIX:
        raise ValueError(
            "Unsupported adversarial-upstream-noise template mix: {}".format(template_mix)
        )
    template_ids = ADVERSARIAL_UPSTREAM_NOISE_TEMPLATE_IDS_BY_MIX[template_mix]
    return template_ids[index % len(template_ids)]


def _make_candidate(
    *,
    candidate_id: str,
    canonical_id: str,
    raw_text: str,
    canonical_claim: str,
    claim_type: ClaimType,
    scope_level: ScopeLevel,
    scope_key: str,
    event_time: datetime,
    source_kind: str,
    source_id: str,
    strength: float,
    observed_at: datetime | None = None,
    contradicts: List[str] | None = None,
    supports: List[str] | None = None,
) -> CandidateUpdate:
    observed_at = observed_at or event_time
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=raw_text,
        raw_claim=raw_text,
        canonical_claim=canonical_claim,
        claim_type=claim_type,
        scope_level=scope_level,
        scope_key=scope_key,
        provenance=[
            ProvenanceRecord(
                source_kind=source_kind,
                source_id=source_id,
                trust_score=strength,
                observed_at=observed_at,
            )
        ],
        verification_score=strength,
        created_at=event_time,
        updated_at=event_time,
        contradicts=contradicts or [],
        supports=supports or [],
    )


def _make_question(
    *,
    question_id: str,
    text: str,
    canonical_id: str,
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
        phase="adversarial_probe",
        gold_candidate_ids=gold_candidate_ids,
        forbidden_candidate_ids=forbidden_candidate_ids,
        asked_at=asked_at,
    )


def _workspace_project_scope_keys(
    project_a: str,
    project_b: str,
    *,
    heldout: bool,
) -> Tuple[str, str]:
    workspace_scope = "workspace-{}-{}".format(project_a, project_b)
    if heldout:
        return workspace_scope, "{}/org-core/product-{}/env-prod".format(workspace_scope, project_a)
    return workspace_scope, "{}/project-{}".format(workspace_scope, project_a)


def _build_retraction_scenario(
    *,
    scenario_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    template_id: str,
    template_split: str,
    claim_text: str,
    corroboration_text: str,
    retraction_text: str,
    question_text: str,
) -> Scenario:
    canonical_id = "adversarial-upstream-{}-{}-status".format(buyer.lower(), target.lower())
    positive_claim = "{} acquired {}".format(buyer, target)
    retraction_claim = "{} did not acquire {}".format(buyer, target)
    observed_id = scenario_id + "-candidate-observed"
    corroborated_id = scenario_id + "-candidate-corroborated"
    retraction_id = scenario_id + "-candidate-retracted"

    observed_candidate = _make_candidate(
        candidate_id=observed_id,
        canonical_id=canonical_id,
        raw_text=claim_text,
        canonical_claim=positive_claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        event_time=base_time,
        source_kind="wire_report",
        source_id=scenario_id + "-src-alpha",
        strength=0.76,
    )
    corroborated_candidate = _make_candidate(
        candidate_id=corroborated_id,
        canonical_id=canonical_id,
        raw_text=corroboration_text,
        canonical_claim=positive_claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        event_time=base_time + timedelta(minutes=1),
        source_kind="filing_followup",
        source_id=scenario_id + "-src-beta",
        strength=0.76,
        supports=[observed_id],
    )
    retraction_candidate = _make_candidate(
        candidate_id=retraction_id,
        canonical_id=canonical_id,
        raw_text=retraction_text,
        canonical_claim=retraction_claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        event_time=base_time + timedelta(minutes=2),
        source_kind="retraction_notice",
        source_id=scenario_id + "-src-gamma",
        strength=0.62,
        contradicts=[observed_id, corroborated_id],
    )
    probe_question = _make_question(
        question_id=scenario_id + "-question-adversarial-probe",
        text=question_text,
        canonical_id=canonical_id,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        gold_candidate_ids=[retraction_id],
        forbidden_candidate_ids=[observed_id, corroborated_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.ADVERSARIAL_UPSTREAM_NOISE,
        description="A claim is corroborated, then later retracted before the probe.",
        latent_truth_graph={
            "mechanism": "adversarial_retraction",
            "canonical_id": canonical_id,
            "final_truth": retraction_claim,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=claim_text,
                candidate=observed_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=corroboration_text,
                candidate=corroborated_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=retraction_text,
                candidate=retraction_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "mechanism": "adversarial_retraction",
            "probe_phase": "adversarial_probe",
            "gold_candidate_ids": [retraction_id],
            "forbidden_candidate_ids": [observed_id, corroborated_id],
            "retracted_candidate_ids": [observed_id, corroborated_id],
            "retraction_candidate_ids": [retraction_id],
            "should_not_promote_candidate_ids": [],
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def _build_witness_conflict_scenario(
    *,
    scenario_id: str,
    project: str,
    team_a: str,
    team_b: str,
    base_time: datetime,
    template_id: str,
    template_split: str,
) -> Scenario:
    canonical_id = "adversarial-owner-{}".format(project)
    scope_key = "project-{}".format(project)
    claim_a = "{} deployment owner is {}".format(project, team_a)
    claim_b = "{} deployment owner is {}".format(project, team_b)
    a1_id = scenario_id + "-candidate-a1"
    a2_id = scenario_id + "-candidate-a2"
    b1_id = scenario_id + "-candidate-b1"
    b2_id = scenario_id + "-candidate-b2"

    candidate_a1 = _make_candidate(
        candidate_id=a1_id,
        canonical_id=canonical_id,
        raw_text="Incident note A says team {} owns deploy approval for project {}.".format(team_a, project),
        canonical_claim=claim_a,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        event_time=base_time,
        source_kind="incident_note",
        source_id=scenario_id + "-src-a",
        strength=0.60,
    )
    candidate_a2 = _make_candidate(
        candidate_id=a2_id,
        canonical_id=canonical_id,
        raw_text="Runbook witness B repeats that team {} owns deploy approval for project {}.".format(
            team_a, project
        ),
        canonical_claim=claim_a,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        event_time=base_time + timedelta(minutes=1),
        source_kind="runbook_witness",
        source_id=scenario_id + "-src-b",
        strength=0.60,
        supports=[a1_id],
    )
    candidate_b1 = _make_candidate(
        candidate_id=b1_id,
        canonical_id=canonical_id,
        raw_text="Escalation witness C says team {} owns deploy approval for project {}.".format(
            team_b, project
        ),
        canonical_claim=claim_b,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        event_time=base_time + timedelta(minutes=2),
        source_kind="escalation_witness",
        source_id=scenario_id + "-src-c",
        strength=0.34,
        contradicts=[a1_id, a2_id],
    )
    candidate_b2 = _make_candidate(
        candidate_id=b2_id,
        canonical_id=canonical_id,
        raw_text="Pager witness D repeats the same conflicting owner claim for project {}.".format(project),
        canonical_claim=claim_b,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        event_time=base_time + timedelta(minutes=3),
        source_kind="pager_witness",
        source_id=scenario_id + "-src-d",
        strength=0.34,
        contradicts=[a1_id, a2_id],
        supports=[b1_id, b1_id, b1_id, b1_id],
    )
    probe_question = _make_question(
        question_id=scenario_id + "-question-adversarial-probe",
        text="For project {}, who owns deploy approval right now?".format(project),
        canonical_id=canonical_id,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        gold_candidate_ids=[],
        forbidden_candidate_ids=[a1_id, a2_id, b1_id, b2_id],
        asked_at=base_time + timedelta(minutes=4),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.ADVERSARIAL_UPSTREAM_NOISE,
        description="Conflicting witness streams should force abstention rather than a forced owner pick.",
        latent_truth_graph={
            "mechanism": "adversarial_witness_conflict",
            "canonical_id": canonical_id,
            "final_truth": "abstain",
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=candidate_a1.raw_text,
                candidate=candidate_a1,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=candidate_a2.raw_text,
                candidate=candidate_a2,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=candidate_b1.raw_text,
                candidate=candidate_b1,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.OBSERVATION,
                turn_index=4,
                text=candidate_b2.raw_text,
                candidate=candidate_b2,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-5",
                kind=EventKind.QUESTION,
                turn_index=5,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "mechanism": "adversarial_witness_conflict",
            "probe_phase": "adversarial_probe",
            "abstention_ok": True,
            "gold_candidate_ids": [],
            "forbidden_candidate_ids": [a1_id, a2_id, b1_id, b2_id],
            "conflict_candidate_ids": [a1_id, a2_id, b1_id, b2_id],
            "should_not_promote_candidate_ids": [],
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def _build_temporal_skew_scenario(
    *,
    scenario_id: str,
    buyer: str,
    target: str,
    base_time: datetime,
    template_id: str,
    template_split: str,
    question_text: str,
) -> Scenario:
    canonical_id = "adversarial-temporal-{}-{}".format(buyer.lower(), target.lower())
    current_claim = "{} signed the {} contract".format(buyer, target)
    stale_claim = "{} did not sign the {} contract".format(buyer, target)
    current_id = scenario_id + "-candidate-current"
    stale_id = scenario_id + "-candidate-stale"
    corroboration_id = scenario_id + "-candidate-current-corroboration"

    current_candidate = _make_candidate(
        candidate_id=current_id,
        canonical_id=canonical_id,
        raw_text="Current ops note says {} signed the {} contract.".format(buyer, target),
        canonical_claim=current_claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        event_time=base_time,
        source_kind="ops_note",
        source_id=scenario_id + "-src-current",
        strength=0.76,
    )
    stale_candidate = _make_candidate(
        candidate_id=stale_id,
        canonical_id=canonical_id,
        raw_text="A stale archive summary claims {} never signed the {} contract.".format(buyer, target),
        canonical_claim=stale_claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        event_time=base_time + timedelta(minutes=1),
        source_kind="archive_summary",
        source_id=scenario_id + "-src-stale",
        strength=0.78,
        observed_at=base_time - timedelta(days=120),
        contradicts=[current_id],
    )
    corroboration_candidate = _make_candidate(
        candidate_id=corroboration_id,
        canonical_id=canonical_id,
        raw_text="A current follow-up confirms the {} contract is signed now.".format(target),
        canonical_claim=current_claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        event_time=base_time + timedelta(minutes=2),
        source_kind="current_followup",
        source_id=scenario_id + "-src-fresh",
        strength=0.38,
        supports=[current_id],
        contradicts=[stale_id],
    )
    probe_question = _make_question(
        question_id=scenario_id + "-question-adversarial-probe",
        text=question_text,
        canonical_id=canonical_id,
        scope_level=ScopeLevel.WORLD_GLOBAL,
        scope_key="global",
        gold_candidate_ids=[current_id, corroboration_id],
        forbidden_candidate_ids=[stale_id],
        asked_at=base_time + timedelta(minutes=3),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.ADVERSARIAL_UPSTREAM_NOISE,
        description="A stale but strong contradictor arrives after fresher truth and before a weak fresh corroboration.",
        latent_truth_graph={
            "mechanism": "adversarial_temporal_skew",
            "canonical_id": canonical_id,
            "final_truth": current_claim,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=current_candidate.raw_text,
                candidate=current_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=stale_candidate.raw_text,
                candidate=stale_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-3",
                kind=EventKind.OBSERVATION,
                turn_index=3,
                text=corroboration_candidate.raw_text,
                candidate=corroboration_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-4",
                kind=EventKind.QUESTION,
                turn_index=4,
                text=probe_question.text,
                question=probe_question,
            ),
        ],
        expected_lifecycle={
            "mechanism": "adversarial_temporal_skew",
            "probe_phase": "adversarial_probe",
            "gold_candidate_ids": [current_id, corroboration_id],
            "forbidden_candidate_ids": [stale_id],
            "stale_candidate_ids": [stale_id],
            "should_not_promote_candidate_ids": [stale_id],
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def _build_scope_narrowing_scenario(
    *,
    scenario_id: str,
    project_a: str,
    project_b: str,
    base_time: datetime,
    template_id: str,
    template_split: str,
    wider_command: str,
    narrower_command: str,
    activity: str,
    heldout: bool,
) -> Scenario:
    canonical_id = "adversarial-scope-command"
    workspace_scope, project_scope = _workspace_project_scope_keys(project_a, project_b, heldout=heldout)
    wider_id = scenario_id + "-candidate-wider"
    narrower_id = scenario_id + "-candidate-narrower"
    wider_claim = "{} {} use {}".format(workspace_scope, activity, wider_command)
    narrower_claim = "{} {} use {}".format(project_scope, activity, narrower_command)

    wider_candidate = _make_candidate(
        candidate_id=wider_id,
        canonical_id=canonical_id,
        raw_text="Workspace {} standardizes {} on {}.".format(workspace_scope, activity, wider_command),
        canonical_claim=wider_claim,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.WORKSPACE,
        scope_key=workspace_scope,
        event_time=base_time,
        source_kind="workspace_policy",
        source_id=scenario_id + "-src-workspace",
        strength=0.80,
    )
    narrower_candidate = _make_candidate(
        candidate_id=narrower_id,
        canonical_id=canonical_id,
        raw_text="Project {} overrides that default and runs {} on {}.".format(
            project_a,
            activity,
            narrower_command,
        ),
        canonical_claim=narrower_claim,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        event_time=base_time + timedelta(minutes=1),
        source_kind="project_override",
        source_id=scenario_id + "-src-project",
        strength=0.64,
        contradicts=[wider_id],
    )
    probe_question = _make_question(
        question_id=scenario_id + "-question-adversarial-probe",
        text="For project {}, which command should run {}?".format(project_a, activity),
        canonical_id=canonical_id,
        scope_level=ScopeLevel.PROJECT,
        scope_key=project_scope,
        gold_candidate_ids=[narrower_id],
        forbidden_candidate_ids=[wider_id],
        asked_at=base_time + timedelta(minutes=2),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.ADVERSARIAL_UPSTREAM_NOISE,
        description="A narrower project correction should shadow but not erase a wider workspace durable.",
        latent_truth_graph={
            "mechanism": "adversarial_scope_narrowing",
            "canonical_id": canonical_id,
            "workspace_scope_key": workspace_scope,
            "project_scope_key": project_scope,
            "final_truth": narrower_claim,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=wider_candidate.raw_text,
                candidate=wider_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=narrower_candidate.raw_text,
                candidate=narrower_candidate,
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
            "mechanism": "adversarial_scope_narrowing",
            "probe_phase": "adversarial_probe",
            "gold_candidate_ids": [narrower_id],
            "forbidden_candidate_ids": [wider_id],
            "wider_scope_candidate_ids": [wider_id],
            "narrower_scope_candidate_ids": [narrower_id],
            "workspace_scope_key": workspace_scope,
            "project_scope_key": project_scope,
            "should_not_promote_candidate_ids": [narrower_id],
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def _build_pending_competition_scenario(
    *,
    scenario_id: str,
    project: str,
    base_time: datetime,
    template_id: str,
    template_split: str,
    wrong_command: str,
    right_command: str,
    activity: str,
) -> Scenario:
    canonical_id = "adversarial-pending-choice"
    scope_key = "project-{}".format(project)
    wrong_id = scenario_id + "-candidate-y"
    right_id = scenario_id + "-candidate-x"
    wrong_claim = "{} {} use {}".format(project, activity, wrong_command)
    right_claim = "{} {} use {}".format(project, activity, right_command)

    wrong_candidate = _make_candidate(
        candidate_id=wrong_id,
        canonical_id=canonical_id,
        raw_text="An older project note says {} in {} use {}.".format(activity, project, wrong_command),
        canonical_claim=wrong_claim,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        event_time=base_time,
        source_kind="older_note",
        source_id=scenario_id + "-src-y",
        strength=0.66,
    )
    right_candidate = _make_candidate(
        candidate_id=right_id,
        canonical_id=canonical_id,
        raw_text="A stronger follow-up says {} in {} should use {} instead.".format(
            activity,
            project,
            right_command,
        ),
        canonical_claim=right_claim,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        event_time=base_time + timedelta(minutes=1),
        source_kind="followup_note",
        source_id=scenario_id + "-src-x",
        strength=0.69,
        contradicts=[wrong_id],
    )
    probe_question = _make_question(
        question_id=scenario_id + "-question-adversarial-probe",
        text="For project {}, which command should run {} now?".format(project, activity),
        canonical_id=canonical_id,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        gold_candidate_ids=[right_id],
        forbidden_candidate_ids=[wrong_id],
        asked_at=base_time + timedelta(minutes=2),
    )

    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.ADVERSARIAL_UPSTREAM_NOISE,
        description="Two pending candidates compete below promotion threshold and CQ should answer from the stronger one.",
        latent_truth_graph={
            "mechanism": "adversarial_pending_competition",
            "canonical_id": canonical_id,
            "final_truth": right_claim,
        },
        oracle_events=[
            ScenarioEvent(
                event_id=scenario_id + "-event-1",
                kind=EventKind.OBSERVATION,
                turn_index=1,
                text=wrong_candidate.raw_text,
                candidate=wrong_candidate,
            ),
            ScenarioEvent(
                event_id=scenario_id + "-event-2",
                kind=EventKind.OBSERVATION,
                turn_index=2,
                text=right_candidate.raw_text,
                candidate=right_candidate,
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
            "mechanism": "adversarial_pending_competition",
            "probe_phase": "adversarial_probe",
            "gold_candidate_ids": [right_id],
            "forbidden_candidate_ids": [wrong_id],
            "pending_competition_candidate_ids": [wrong_id, right_id],
            "should_not_promote_candidate_ids": [wrong_id, right_id],
        },
        template_id=template_id,
        template_kind="dirty",
        template_split=template_split,
    )


def generate_adversarial_upstream_noise_scenarios(
    count: int,
    seed: int = 73,
    template_mix: str = "mixed",
) -> List[Scenario]:
    rng = random.Random(seed)
    scenarios: List[Scenario] = []
    for index in range(count):
        world_buyer, world_target = rng.choice(WORLD_FACT_PAIRS)
        project_a, project_b = rng.choice(PROJECT_SCOPE_PAIRS)
        project = rng.choice(PROJECT_NAMES)
        team_a, team_b = rng.choice(TEAM_PAIRS)
        template_id = _adversarial_template_id_for_index(index, template_mix)
        scenario_id = "adversarial_upstream_noise_{:03d}".format(index + 1)
        base_time = datetime(2026, 6, 1, 9, 0, 0) + timedelta(days=index)

        if template_id == "adversarial_retraction_v1":
            scenario = _build_retraction_scenario(
                scenario_id=scenario_id,
                buyer=world_buyer,
                target=world_target,
                base_time=base_time,
                template_id=template_id,
                template_split="main",
                claim_text="Wire report: {} acquired {}.".format(world_buyer, world_target),
                corroboration_text="Independent filing later confirms {} completed the {} deal.".format(
                    world_buyer,
                    world_target,
                ),
                retraction_text="Retraction: the earlier {}-{} acquisition report was withdrawn.".format(
                    world_buyer,
                    world_target,
                ),
                question_text="What should we believe now about the {}-{} deal?".format(
                    world_buyer,
                    world_target,
                ),
            )
        elif template_id == "adversarial_retraction_v2":
            scenario = _build_retraction_scenario(
                scenario_id=scenario_id,
                buyer=world_buyer,
                target=world_target,
                base_time=base_time,
                template_id=template_id,
                template_split="heldout",
                claim_text="Desk note: {} finalized the {} purchase.".format(world_buyer, world_target),
                corroboration_text="A separate market brief says the {} purchase by {} closed.".format(
                    world_target,
                    world_buyer,
                ),
                retraction_text="Correction bulletin: editors retracted the {}-{} purchase claim.".format(
                    world_buyer,
                    world_target,
                ),
                question_text="After the correction, what is the current status of {} and {}?".format(
                    world_buyer,
                    world_target,
                ),
            )
        elif template_id == "adversarial_witness_conflict_v1":
            scenario = _build_witness_conflict_scenario(
                scenario_id=scenario_id,
                project=project,
                team_a=team_a,
                team_b=team_b,
                base_time=base_time,
                template_id=template_id,
                template_split="main",
            )
        elif template_id == "adversarial_witness_conflict_v2":
            scenario = _build_witness_conflict_scenario(
                scenario_id=scenario_id,
                project=project + "-holdout",
                team_a=team_a,
                team_b=team_b,
                base_time=base_time,
                template_id=template_id,
                template_split="heldout",
            )
        elif template_id == "adversarial_temporal_skew_v1":
            scenario = _build_temporal_skew_scenario(
                scenario_id=scenario_id,
                buyer=world_buyer,
                target=world_target,
                base_time=base_time,
                template_id=template_id,
                template_split="main",
                question_text="Did {} ultimately sign the {} contract?".format(world_buyer, world_target),
            )
        elif template_id == "adversarial_temporal_skew_v2":
            scenario = _build_temporal_skew_scenario(
                scenario_id=scenario_id,
                buyer=world_buyer,
                target=world_target,
                base_time=base_time,
                template_id=template_id,
                template_split="heldout",
                question_text="What should we believe now about {} and the {} contract?".format(
                    world_buyer,
                    world_target,
                ),
            )
        elif template_id == "adversarial_scope_narrowing_v1":
            wrong_command, right_command, activity = rng.choice(COMMAND_VARIANTS_V1)
            scenario = _build_scope_narrowing_scenario(
                scenario_id=scenario_id,
                project_a=project_a,
                project_b=project_b,
                base_time=base_time,
                template_id=template_id,
                template_split="main",
                wider_command=wrong_command,
                narrower_command=right_command,
                activity=activity,
                heldout=False,
            )
        elif template_id == "adversarial_scope_narrowing_v2":
            wrong_command, right_command, activity = rng.choice(COMMAND_VARIANTS_V2)
            scenario = _build_scope_narrowing_scenario(
                scenario_id=scenario_id,
                project_a=project_a,
                project_b=project_b,
                base_time=base_time,
                template_id=template_id,
                template_split="heldout",
                wider_command=wrong_command,
                narrower_command=right_command,
                activity=activity,
                heldout=True,
            )
        elif template_id == "adversarial_pending_competition_v1":
            wrong_command, right_command, activity = rng.choice(COMMAND_VARIANTS_V1)
            scenario = _build_pending_competition_scenario(
                scenario_id=scenario_id,
                project=project,
                base_time=base_time,
                template_id=template_id,
                template_split="main",
                wrong_command=wrong_command,
                right_command=right_command,
                activity=activity,
            )
        elif template_id == "adversarial_pending_competition_v2":
            wrong_command, right_command, activity = rng.choice(COMMAND_VARIANTS_V2)
            scenario = _build_pending_competition_scenario(
                scenario_id=scenario_id,
                project=project + "-holdout",
                base_time=base_time,
                template_id=template_id,
                template_split="heldout",
                wrong_command=wrong_command,
                right_command=right_command,
                activity=activity,
            )
        else:
            raise ValueError("Unsupported adversarial template_id: {}".format(template_id))
        scenarios.append(scenario)
    return scenarios
