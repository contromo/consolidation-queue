from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Sequence

from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario, ScenarioEvent, TaskFamily


EVIDENCE_CONFLICT_TEMPLATE_IDS_BY_MIX: Dict[str, List[str]] = {
    "mixed": [
        "conflict_zero_clean_v1",
        "conflict_mild_v1",
        "conflict_moderate_v1",
        "conflict_witness_v1",
        "conflict_polluted_v1",
    ],
    "heldout": [
        "conflict_zero_clean_v2",
        "conflict_mild_v2",
        "conflict_moderate_v2",
        "conflict_witness_v2",
        "conflict_polluted_v2",
    ],
}

PROJECTS: Sequence[str] = ("atlas", "cedar", "ember", "granite", "ivy", "juniper")
TEAM_PAIRS: Sequence[tuple[str, str]] = (
    ("orion", "nova"),
    ("apex", "ember"),
    ("harbor", "skylark"),
    ("quartz", "rivet"),
    ("meridian", "sparrow"),
)
COMMANDS: Sequence[tuple[str, str]] = (
    ("npm test", "pytest -q"),
    ("make verify", "./bin/release-check"),
    ("cargo test", "just ci-test"),
    ("pnpm test", "uv run pytest -q"),
)


def _template_id_for_index(index: int, template_mix: str) -> str:
    if template_mix not in EVIDENCE_CONFLICT_TEMPLATE_IDS_BY_MIX:
        raise ValueError("Unsupported evidence-conflict template mix: {}".format(template_mix))
    template_ids = EVIDENCE_CONFLICT_TEMPLATE_IDS_BY_MIX[template_mix]
    return template_ids[index % len(template_ids)]


def _make_candidate(
    *,
    candidate_id: str,
    canonical_id: str,
    raw_text: str,
    canonical_claim: str,
    scope_key: str,
    event_time: datetime,
    source_kind: str,
    source_id: str,
    strength: float,
    contradicts: List[str] | None = None,
    supports: List[str] | None = None,
) -> CandidateUpdate:
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=raw_text,
        raw_claim=raw_text,
        canonical_claim=canonical_claim,
        claim_type=ClaimType.PROJECT_CONVENTION,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        provenance=[
            ProvenanceRecord(
                source_kind=source_kind,
                source_id=source_id,
                trust_score=strength,
                observed_at=event_time,
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
    scenario_id: str,
    text: str,
    canonical_id: str,
    scope_key: str,
    gold_candidate_ids: List[str],
    forbidden_candidate_ids: List[str],
    asked_at: datetime,
) -> QuestionSpec:
    return QuestionSpec(
        question_id=scenario_id + "-question-evidence-conflict-probe",
        text=text,
        relevant_canonical_id=canonical_id,
        scope_level=ScopeLevel.PROJECT,
        scope_key=scope_key,
        phase="evidence_conflict_probe",
        gold_candidate_ids=gold_candidate_ids,
        forbidden_candidate_ids=forbidden_candidate_ids,
        asked_at=asked_at,
    )


def _events_for_candidates(candidates: List[CandidateUpdate], question: QuestionSpec) -> List[ScenarioEvent]:
    events = [
        ScenarioEvent(
            event_id=candidate.candidate_id.replace("-candidate-", "-event-"),
            kind=EventKind.OBSERVATION,
            turn_index=index + 1,
            text=candidate.raw_text,
            candidate=candidate,
        )
        for index, candidate in enumerate(candidates)
    ]
    events.append(
        ScenarioEvent(
            event_id=question.question_id.replace("-question-", "-event-"),
            kind=EventKind.QUESTION,
            turn_index=len(candidates) + 1,
            text=question.text,
            question=question,
        )
    )
    return events


def _scenario(
    *,
    scenario_id: str,
    template_id: str,
    template_split: str,
    mechanism: str,
    intensity: str,
    description: str,
    canonical_id: str,
    scope_key: str,
    candidates: List[CandidateUpdate],
    question: QuestionSpec,
    abstention_ok: bool,
    commit_required: bool,
    should_not_promote_candidate_ids: List[str],
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.EVIDENCE_CONFLICT_SPECTRUM,
        description=description,
        latent_truth_graph={
            "mechanism": mechanism,
            "evidence_conflict_intensity": intensity,
            "canonical_id": canonical_id,
            "scope_key": scope_key,
        },
        oracle_events=_events_for_candidates(candidates, question),
        expected_lifecycle={
            "mechanism": mechanism,
            "probe_phase": "evidence_conflict_probe",
            "abstention_ok": abstention_ok,
            "commit_required": commit_required,
            "gold_candidate_ids": list(question.gold_candidate_ids),
            "forbidden_candidate_ids": list(question.forbidden_candidate_ids),
            "should_not_promote_candidate_ids": should_not_promote_candidate_ids,
            "evidence_conflict_intensity": intensity,
            "conflict_candidate_ids": [candidate.candidate_id for candidate in candidates],
        },
        template_id=template_id,
        template_kind="clean" if intensity == "zero" else "dirty",
        template_split=template_split,
    )


def _build_zero_scenario(
    scenario_id: str,
    template_id: str,
    template_split: str,
    project: str,
    command: str,
    base_time: datetime,
) -> Scenario:
    canonical_id = "evidence-conflict-{}-test-command".format(project)
    scope_key = "project-{}".format(project)
    candidate_id = scenario_id + "-candidate-correct"
    claim = "{} verification uses {}".format(project, command)
    candidate = _make_candidate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text="Project note says {} verification uses {}.".format(project, command),
        canonical_claim=claim,
        scope_key=scope_key,
        event_time=base_time,
        source_kind="project_note",
        source_id=scenario_id + "-src-correct",
        strength=0.76,
    )
    question = _make_question(
        scenario_id=scenario_id,
        text="For project {}, which command should run verification?".format(project),
        canonical_id=canonical_id,
        scope_key=scope_key,
        gold_candidate_ids=[candidate_id],
        forbidden_candidate_ids=[],
        asked_at=base_time + timedelta(minutes=1),
    )
    return _scenario(
        scenario_id=scenario_id,
        template_id=template_id,
        template_split=template_split,
        mechanism="conflict_zero",
        intensity="zero",
        description="A single coherent source should produce a concrete answer.",
        canonical_id=canonical_id,
        scope_key=scope_key,
        candidates=[candidate],
        question=question,
        abstention_ok=False,
        commit_required=True,
        should_not_promote_candidate_ids=[],
    )


def _build_mild_scenario(
    scenario_id: str,
    template_id: str,
    template_split: str,
    project: str,
    correct_command: str,
    weak_command: str,
    weak_count: int,
    base_time: datetime,
) -> Scenario:
    canonical_id = "evidence-conflict-{}-test-command".format(project)
    scope_key = "project-{}".format(project)
    weak_candidates = []
    weak_ids = []
    weak_claim = "{} verification uses {}".format(project, weak_command)
    for index in range(weak_count):
        candidate_id = "{}-candidate-weak-{}".format(scenario_id, index + 1)
        weak_ids.append(candidate_id)
        weak_candidates.append(
            _make_candidate(
                candidate_id=candidate_id,
                canonical_id=canonical_id,
                raw_text="Low-confidence note {} suggests {} verification uses {}.".format(
                    index + 1,
                    project,
                    weak_command,
                ),
                canonical_claim=weak_claim,
                scope_key=scope_key,
                event_time=base_time + timedelta(minutes=index),
                source_kind="low_confidence_note",
                source_id="{}-src-weak-{}".format(scenario_id, index + 1),
                strength=0.32 + (index % 2) * 0.01,
            )
        )
    correct_id = scenario_id + "-candidate-correct"
    correct_claim = "{} verification uses {}".format(project, correct_command)
    correct = _make_candidate(
        candidate_id=correct_id,
        canonical_id=canonical_id,
        raw_text="Authoritative project note says {} verification uses {}.".format(project, correct_command),
        canonical_claim=correct_claim,
        scope_key=scope_key,
        event_time=base_time + timedelta(minutes=weak_count),
        source_kind="maintainer_note",
        source_id=scenario_id + "-src-correct",
        strength=0.76,
        contradicts=weak_ids,
    )
    question = _make_question(
        scenario_id=scenario_id,
        text="For project {}, which command should run verification?".format(project),
        canonical_id=canonical_id,
        scope_key=scope_key,
        gold_candidate_ids=[correct_id],
        forbidden_candidate_ids=weak_ids,
        asked_at=base_time + timedelta(minutes=weak_count + 1),
    )
    return _scenario(
        scenario_id=scenario_id,
        template_id=template_id,
        template_split=template_split,
        mechanism="conflict_mild",
        intensity="mild",
        description="Weak counterclaims should not prevent commitment to a strong source.",
        canonical_id=canonical_id,
        scope_key=scope_key,
        candidates=weak_candidates + [correct],
        question=question,
        abstention_ok=False,
        commit_required=True,
        should_not_promote_candidate_ids=weak_ids,
    )


def _build_moderate_or_witness_scenario(
    scenario_id: str,
    template_id: str,
    template_split: str,
    project: str,
    side_a: str,
    side_b: str,
    weak_count: int,
    strong_side: str,
    base_time: datetime,
    *,
    mechanism: str,
    intensity: str,
) -> Scenario:
    canonical_id = "evidence-conflict-owner-{}".format(project)
    scope_key = "project-{}".format(project)
    strong_label = side_a if strong_side == "a" else side_b
    weak_label = side_b if strong_side == "a" else side_a
    strong_claim = "{} deploy owner is {}".format(project, strong_label)
    weak_claim = "{} deploy owner is {}".format(project, weak_label)
    strong_1_id = scenario_id + "-candidate-strong-1"
    strong_2_id = scenario_id + "-candidate-strong-2"
    strong_1_strength = 0.60 if weak_count % 2 else 0.59
    strong_1 = _make_candidate(
        candidate_id=strong_1_id,
        canonical_id=canonical_id,
        raw_text="Incident note says {} owns deploy approval for {}.".format(strong_label, project),
        canonical_claim=strong_claim,
        scope_key=scope_key,
        event_time=base_time,
        source_kind="incident_note",
        source_id=scenario_id + "-src-strong-1",
        strength=strong_1_strength,
    )
    strong_2 = _make_candidate(
        candidate_id=strong_2_id,
        canonical_id=canonical_id,
        raw_text="Runbook witness repeats that {} owns deploy approval for {}.".format(strong_label, project),
        canonical_claim=strong_claim,
        scope_key=scope_key,
        event_time=base_time + timedelta(minutes=1),
        source_kind="runbook_witness",
        source_id=scenario_id + "-src-strong-2",
        strength=0.60,
        supports=[strong_1_id],
    )
    weak_candidates = []
    weak_ids = []
    for index in range(weak_count):
        candidate_id = "{}-candidate-weak-{}".format(scenario_id, index + 1)
        weak_ids.append(candidate_id)
        weak_candidates.append(
            _make_candidate(
                candidate_id=candidate_id,
                canonical_id=canonical_id,
                raw_text="Conflicting witness {} says {} owns deploy approval for {}.".format(
                    index + 1,
                    weak_label,
                    project,
                ),
                canonical_claim=weak_claim,
                scope_key=scope_key,
                event_time=base_time + timedelta(minutes=index + 2),
                source_kind="conflict_witness",
                source_id="{}-src-weak-{}".format(scenario_id, index + 1),
                strength=0.33 + (index % 2) * 0.01,
                contradicts=[strong_1_id, strong_2_id],
                supports=[weak_ids[0]] if weak_ids else [],
            )
        )
    forbidden_ids = [strong_1_id, strong_2_id] + weak_ids
    question = _make_question(
        scenario_id=scenario_id,
        text="For project {}, who owns deploy approval right now?".format(project),
        canonical_id=canonical_id,
        scope_key=scope_key,
        gold_candidate_ids=[],
        forbidden_candidate_ids=forbidden_ids,
        asked_at=base_time + timedelta(minutes=weak_count + 2),
    )
    return _scenario(
        scenario_id=scenario_id,
        template_id=template_id,
        template_split=template_split,
        mechanism=mechanism,
        intensity=intensity,
        description="Conflicting evidence should force abstention rather than a concrete owner pick.",
        canonical_id=canonical_id,
        scope_key=scope_key,
        candidates=[strong_1, strong_2] + weak_candidates,
        question=question,
        abstention_ok=True,
        commit_required=False,
        should_not_promote_candidate_ids=[],
    )


def _build_polluted_scenario(
    scenario_id: str,
    template_id: str,
    template_split: str,
    project: str,
    correct_command: str,
    wrong_command: str,
    weak_count: int,
    base_time: datetime,
) -> Scenario:
    canonical_id = "evidence-conflict-{}-release-command".format(project)
    scope_key = "project-{}".format(project)
    weak_candidates = []
    weak_ids = []
    wrong_claim = "{} release checks use {}".format(project, wrong_command)
    for index in range(weak_count):
        candidate_id = "{}-candidate-polluted-{}".format(scenario_id, index + 1)
        weak_ids.append(candidate_id)
        weak_candidates.append(
            _make_candidate(
                candidate_id=candidate_id,
                canonical_id=canonical_id,
                raw_text="Mirrored low-trust report {} says {} release checks use {}.".format(
                    index + 1,
                    project,
                    wrong_command,
                ),
                canonical_claim=wrong_claim,
                scope_key=scope_key,
                event_time=base_time + timedelta(minutes=index),
                source_kind="mirrored_report",
                source_id="{}-src-polluted-{}".format(scenario_id, index + 1),
                strength=0.28 + (index % 3) * 0.02,
            )
        )
    correct_id = scenario_id + "-candidate-correct"
    correct_claim = "{} release checks use {}".format(project, correct_command)
    correct = _make_candidate(
        candidate_id=correct_id,
        canonical_id=canonical_id,
        raw_text="Maintainer note says {} release checks use {}.".format(project, correct_command),
        canonical_claim=correct_claim,
        scope_key=scope_key,
        event_time=base_time + timedelta(minutes=weak_count),
        source_kind="maintainer_note",
        source_id=scenario_id + "-src-correct",
        strength=0.78,
        contradicts=weak_ids,
    )
    question = _make_question(
        scenario_id=scenario_id,
        text="For project {}, which command should run release checks?".format(project),
        canonical_id=canonical_id,
        scope_key=scope_key,
        gold_candidate_ids=[correct_id],
        forbidden_candidate_ids=weak_ids,
        asked_at=base_time + timedelta(minutes=weak_count + 1),
    )
    return _scenario(
        scenario_id=scenario_id,
        template_id=template_id,
        template_split=template_split,
        mechanism="conflict_polluted",
        intensity="polluted",
        description="A strong correct source should survive many weak contradictors.",
        canonical_id=canonical_id,
        scope_key=scope_key,
        candidates=weak_candidates + [correct],
        question=question,
        abstention_ok=False,
        commit_required=True,
        should_not_promote_candidate_ids=weak_ids,
    )


def generate_evidence_conflict_spectrum_scenarios(
    count: int,
    template_mix: str = "mixed",
    seed: int = 97,
) -> List[Scenario]:
    rng = random.Random(seed)
    scenarios: List[Scenario] = []
    for index in range(count):
        template_id = _template_id_for_index(index, template_mix)
        scenario_id = "evidence_conflict_spectrum_{:03d}".format(index + 1)
        template_split = "heldout" if template_id.endswith("_v2") else "main"
        project = rng.choice(PROJECTS)
        side_a, side_b = rng.choice(TEAM_PAIRS)
        command_a, command_b = rng.choice(COMMANDS)
        variant = index // len(EVIDENCE_CONFLICT_TEMPLATE_IDS_BY_MIX[template_mix])
        base_time = datetime(2026, 7, 1, 9, 0, 0) + timedelta(days=index)

        if template_id.startswith("conflict_zero_clean"):
            scenario = _build_zero_scenario(
                scenario_id,
                template_id,
                template_split,
                project,
                command_a,
                base_time,
            )
        elif template_id.startswith("conflict_mild"):
            scenario = _build_mild_scenario(
                scenario_id,
                template_id,
                template_split,
                project,
                command_a,
                command_b,
                weak_count=1 + (variant % 3),
                base_time=base_time,
            )
        elif template_id.startswith("conflict_moderate"):
            scenario = _build_moderate_or_witness_scenario(
                scenario_id,
                template_id,
                template_split,
                project,
                side_a,
                side_b,
                weak_count=1 + (variant % 3),
                strong_side="a" if variant % 2 == 0 else "b",
                base_time=base_time,
                mechanism="conflict_moderate",
                intensity="moderate",
            )
        elif template_id.startswith("conflict_witness"):
            scenario = _build_moderate_or_witness_scenario(
                scenario_id,
                template_id,
                template_split,
                project,
                side_a,
                side_b,
                weak_count=1 + (variant % 3),
                strong_side="b" if variant % 2 == 0 else "a",
                base_time=base_time,
                mechanism="conflict_witness",
                intensity="witness",
            )
        elif template_id.startswith("conflict_polluted"):
            scenario = _build_polluted_scenario(
                scenario_id,
                template_id,
                template_split,
                project,
                command_a,
                command_b,
                weak_count=3 + (variant % 3),
                base_time=base_time,
            )
        else:
            raise ValueError("Unsupported evidence-conflict template_id: {}".format(template_id))
        scenarios.append(scenario)
    return scenarios
