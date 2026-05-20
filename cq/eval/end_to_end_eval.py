from __future__ import annotations

from typing import Dict, List, Optional, Type

from cq.eval.abstention import abstained_from_trace, asserted_candidate_ids, scenario_intent
from cq.eval.metrics import iso_to_datetime, minutes_between
from cq.schemas.memory import MemoryState, jsonable
from cq.schemas.metrics import PolicyScenarioMetrics, PolicySummaryMetrics
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario, TaskFamily


def execute_scenario(policy_cls: Type[object], scenario: Scenario) -> Dict[str, object]:
    policy = policy_cls()
    question_traces = []
    for event in scenario.sorted_events():
        if event.kind == EventKind.OBSERVATION and event.candidate is not None:
            policy.observe_candidate(event.candidate)
        if event.kind == EventKind.QUESTION and event.question is not None:
            question_traces.append(policy.answer_question(event.question))
    store_snapshot = policy.store.snapshot()
    metrics = compute_policy_metrics(
        policy.policy_name,
        scenario,
        question_traces,
        store_snapshot,
    )
    failure_examples = extract_failure_examples(
        policy.policy_name,
        scenario,
        question_traces,
        store_snapshot,
        is_floor_baseline=bool(getattr(policy_cls, "is_floor_baseline", False)),
    )
    return {
        "policy_name": policy.policy_name,
        "scenario_id": scenario.scenario_id,
        "scenario": jsonable(scenario),
        "question_traces": [jsonable(trace) for trace in question_traces],
        "store_snapshot": store_snapshot,
        "metrics": jsonable(metrics),
        "failure_examples": failure_examples,
        "store": policy.store,
    }


def compute_policy_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    if scenario.task_family == TaskFamily.FORCED_CONTRADICTION:
        return compute_forced_contradiction_metrics(policy_name, scenario, question_traces, store_snapshot)
    if scenario.task_family == TaskFamily.SCOPE_CONTAMINATION:
        return compute_scope_contamination_metrics(policy_name, scenario, question_traces, store_snapshot)
    if scenario.task_family == TaskFamily.PREFERENCE_DRIFT:
        return compute_preference_drift_metrics(policy_name, scenario, question_traces, store_snapshot)
    if scenario.task_family == TaskFamily.USEFUL_PENDING_MEMORY:
        return compute_useful_pending_memory_metrics(policy_name, scenario, question_traces, store_snapshot)
    if scenario.task_family == TaskFamily.FALSE_CORROBORATION:
        return compute_false_corroboration_metrics(policy_name, scenario, question_traces, store_snapshot)
    if scenario.task_family == TaskFamily.MEMORY_POISONING:
        return compute_memory_poisoning_metrics(policy_name, scenario, question_traces, store_snapshot)
    if scenario.task_family == TaskFamily.ADVERSARIAL_UPSTREAM_NOISE:
        return compute_adversarial_upstream_noise_metrics(
            policy_name,
            scenario,
            question_traces,
            store_snapshot,
        )
    if scenario.task_family == TaskFamily.EVIDENCE_CONFLICT_SPECTRUM:
        return compute_evidence_conflict_spectrum_metrics(
            policy_name,
            scenario,
            question_traces,
            store_snapshot,
        )
    if scenario.task_family == TaskFamily.LONGMEMEVAL_EXTERNAL:
        return compute_longmemeval_external_metrics(
            policy_name,
            scenario,
            question_traces,
            store_snapshot,
        )
    raise ValueError("Unsupported task family: {}".format(scenario.task_family))


DIAGNOSTIC_PHASE_BY_FAMILY = {
    TaskFamily.FORCED_CONTRADICTION: "after_contradiction",
    TaskFamily.SCOPE_CONTAMINATION: "off_scope_probe",
    TaskFamily.PREFERENCE_DRIFT: "after_drift",
    TaskFamily.USEFUL_PENDING_MEMORY: "pending_probe",
    TaskFamily.FALSE_CORROBORATION: "corroboration_probe",
    TaskFamily.MEMORY_POISONING: "poison_probe",
    TaskFamily.ADVERSARIAL_UPSTREAM_NOISE: "adversarial_probe",
    TaskFamily.EVIDENCE_CONFLICT_SPECTRUM: "evidence_conflict_probe",
    TaskFamily.LONGMEMEVAL_EXTERNAL: "longmemeval_probe",
}


ASSERTION_FAILURE_BY_FAMILY = {
    TaskFamily.FORCED_CONTRADICTION: (
        "false_assertion",
        "forbidden_contradiction_candidate_asserted",
    ),
    TaskFamily.SCOPE_CONTAMINATION: (
        "scope_leakage",
        "forbidden_scope_candidate_asserted",
    ),
    TaskFamily.PREFERENCE_DRIFT: (
        "false_assertion",
        "forbidden_preference_candidate_asserted",
    ),
    TaskFamily.USEFUL_PENDING_MEMORY: (
        "false_assertion",
        "forbidden_useful_pending_candidate_asserted",
    ),
    TaskFamily.FALSE_CORROBORATION: (
        "false_assertion",
        "forbidden_false_corroboration_candidate_asserted",
    ),
    TaskFamily.MEMORY_POISONING: (
        "false_assertion",
        "forbidden_poison_candidate_asserted",
    ),
    TaskFamily.ADVERSARIAL_UPSTREAM_NOISE: (
        "false_assertion",
        "forbidden_adversarial_candidate_asserted",
    ),
    TaskFamily.EVIDENCE_CONFLICT_SPECTRUM: (
        "false_assertion",
        "forbidden_conflict_candidate_asserted",
    ),
    TaskFamily.LONGMEMEVAL_EXTERNAL: (
        "false_assertion",
        "forbidden_longmemeval_candidate_asserted",
    ),
}


PREMATURE_PROMOTION_REASON_BY_FAMILY = {
    TaskFamily.FORCED_CONTRADICTION: "should_not_promote_contradiction_candidate_promoted",
    TaskFamily.SCOPE_CONTAMINATION: "should_not_promote_scope_candidate_promoted",
    TaskFamily.PREFERENCE_DRIFT: "should_not_promote_preference_candidate_promoted",
    TaskFamily.USEFUL_PENDING_MEMORY: "should_not_promote_useful_pending_candidate_promoted",
    TaskFamily.FALSE_CORROBORATION: "false_corroboration_stack_promoted",
    TaskFamily.MEMORY_POISONING: "poison_candidate_promoted",
    TaskFamily.ADVERSARIAL_UPSTREAM_NOISE: "forbidden_adversarial_candidate_promoted",
    TaskFamily.EVIDENCE_CONFLICT_SPECTRUM: "forbidden_conflict_candidate_promoted",
    TaskFamily.LONGMEMEVAL_EXTERNAL: "longmemeval_candidate_promoted_before_policy_gate",
}


def extract_failure_examples(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
    *,
    is_floor_baseline: bool = False,
) -> List[Dict[str, object]]:
    questions = {
        event.question.phase: event.question
        for event in scenario.sorted_events()
        if event.question is not None
    }
    diagnostic_phase = DIAGNOSTIC_PHASE_BY_FAMILY.get(scenario.task_family)
    if diagnostic_phase is None:
        raise ValueError("Unsupported task family: {}".format(scenario.task_family))
    diagnostic_question = questions[diagnostic_phase]
    traces = {trace.question_id: trace for trace in question_traces}
    diagnostic_trace = traces[diagnostic_question.question_id]

    asserted_candidate_ids = _asserted_candidate_ids(diagnostic_trace, store_snapshot)
    forbidden_asserted_ids = _ordered_intersection(
        asserted_candidate_ids,
        diagnostic_question.forbidden_candidate_ids,
    )
    promoted_should_not_promote_ids = _promoted_should_not_promote_candidate_ids(
        store_snapshot,
        scenario,
    )
    displaced_clean_durable_ids = _displaced_clean_durable_candidate_ids(
        store_snapshot,
        scenario,
    )
    answer_correct = _contains_any(
        diagnostic_trace.resolved_candidate_ids,
        diagnostic_question.gold_candidate_ids,
    )

    examples = []
    assertion_failure_emitted = bool(forbidden_asserted_ids)
    if forbidden_asserted_ids:
        failure_type, reason = ASSERTION_FAILURE_BY_FAMILY[scenario.task_family]
        examples.append(
            _build_failure_example(
                policy_name=policy_name,
                scenario=scenario,
                question=diagnostic_question,
                trace=diagnostic_trace,
                store_snapshot=store_snapshot,
                failure_type=failure_type,
                failure_subtype="",
                reason=reason,
                asserted_candidate_ids=asserted_candidate_ids,
                promoted_should_not_promote_candidate_ids=[],
                displaced_clean_durable_candidate_ids=[],
            )
        )

    if promoted_should_not_promote_ids:
        reason = PREMATURE_PROMOTION_REASON_BY_FAMILY.get(scenario.task_family)
        if reason is None:
            raise ValueError(
                "Premature-promotion reason is missing for family: {}".format(
                    scenario.task_family
                )
            )
        examples.append(
            _build_failure_example(
                policy_name=policy_name,
                scenario=scenario,
                question=diagnostic_question,
                trace=diagnostic_trace,
                store_snapshot=store_snapshot,
                failure_type="premature_promotion",
                failure_subtype="",
                reason=reason,
                asserted_candidate_ids=asserted_candidate_ids,
                promoted_should_not_promote_candidate_ids=promoted_should_not_promote_ids,
                displaced_clean_durable_candidate_ids=[],
            )
        )

    if scenario.task_family == TaskFamily.MEMORY_POISONING and displaced_clean_durable_ids:
        examples.append(
            _build_failure_example(
                policy_name=policy_name,
                scenario=scenario,
                question=diagnostic_question,
                trace=diagnostic_trace,
                store_snapshot=store_snapshot,
                failure_type="clean_durable_displacement",
                failure_subtype="",
                reason="clean_durable_demoted_by_poison",
                asserted_candidate_ids=asserted_candidate_ids,
                promoted_should_not_promote_candidate_ids=[],
                displaced_clean_durable_candidate_ids=displaced_clean_durable_ids,
            )
        )

    if not answer_correct and not assertion_failure_emitted and diagnostic_question.gold_candidate_ids:
        examples.append(
            _build_failure_example(
                policy_name=policy_name,
                scenario=scenario,
                question=diagnostic_question,
                trace=diagnostic_trace,
                store_snapshot=store_snapshot,
                failure_type="incorrect_answer",
                failure_subtype="no_memory_floor" if is_floor_baseline else "",
                reason="gold_candidate_not_resolved",
                asserted_candidate_ids=asserted_candidate_ids,
                promoted_should_not_promote_candidate_ids=[],
                displaced_clean_durable_candidate_ids=[],
            )
        )

    return sorted(examples, key=failure_example_sort_key)


def _build_failure_example(
    *,
    policy_name: str,
    scenario: Scenario,
    question: QuestionSpec,
    trace: object,
    store_snapshot: Dict[str, object],
    failure_type: str,
    failure_subtype: str,
    reason: str,
    asserted_candidate_ids: List[str],
    promoted_should_not_promote_candidate_ids: List[str],
    displaced_clean_durable_candidate_ids: List[str],
) -> Dict[str, object]:
    resolved_candidate_ids = list(getattr(trace, "resolved_candidate_ids", []))
    used_memory_ids = list(getattr(trace, "used_memory_ids", []))
    involved_candidate_ids = _sorted_unique(
        list(question.gold_candidate_ids)
        + list(question.forbidden_candidate_ids)
        + list(asserted_candidate_ids)
        + list(promoted_should_not_promote_candidate_ids)
        + list(displaced_clean_durable_candidate_ids)
        + resolved_candidate_ids
    )
    return {
        "failure_type": failure_type,
        "failure_subtype": failure_subtype,
        "reason": reason,
        "policy_name": policy_name,
        "scenario_id": scenario.scenario_id,
        "template_id": scenario.template_id,
        "template_kind": scenario.template_kind,
        "template_split": scenario.template_split,
        "question_id": question.question_id,
        "question_phase": question.phase,
        "question_text": question.text,
        "answer_text": getattr(trace, "answer_text", ""),
        "gold_candidate_ids": list(question.gold_candidate_ids),
        "forbidden_candidate_ids": list(question.forbidden_candidate_ids),
        "asserted_candidate_ids": list(asserted_candidate_ids),
        "promoted_should_not_promote_candidate_ids": list(promoted_should_not_promote_candidate_ids),
        "displaced_clean_durable_candidate_ids": list(displaced_clean_durable_candidate_ids),
        "used_pending": bool(getattr(trace, "used_pending", False)),
        "used_memory_ids": used_memory_ids,
        "resolved_candidate_ids": resolved_candidate_ids,
        "candidate_claims": _candidate_claims(store_snapshot, involved_candidate_ids),
        "durable_claims": _durable_claims(store_snapshot, involved_candidate_ids, used_memory_ids),
    }


def failure_example_sort_key(example: Dict[str, object]) -> tuple:
    return (
        str(example["scenario_id"]),
        str(example["failure_type"]),
        str(example["question_phase"]),
        str(example["question_id"]),
    )


def compute_forced_contradiction_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    questions = {}
    for event in scenario.sorted_events():
        if event.question is not None:
            questions[event.question.phase] = event.question
    traces = {trace.question_id: trace for trace in question_traces}
    before_question = questions["before_contradiction"]
    after_question = questions["after_contradiction"]
    before_trace = traces[before_question.question_id]
    after_trace = traces[after_question.question_id]

    useful_recall = 1.0 if _contains_any(before_trace.resolved_candidate_ids, before_question.gold_candidate_ids) else 0.0
    used_pending_before = 1.0 if before_trace.used_pending else 0.0
    durable_commit_before = (
        1.0 if _candidate_became_durable(store_snapshot, scenario.expected_lifecycle["old_candidate_id"]) else 0.0
    )
    after_asserted_ids = _asserted_candidate_ids(after_trace, store_snapshot)
    false_assertion = 1.0 if _contains_any(after_asserted_ids, after_question.forbidden_candidate_ids) else 0.0
    answer_correctness = 1.0 if _contains_any(after_trace.resolved_candidate_ids, after_question.gold_candidate_ids) else 0.0

    invalidated = _old_claim_invalidated(
        store_snapshot,
        scenario.expected_lifecycle["old_candidate_id"],
    )
    recovered = (
        1.0
        if answer_correctness == 1.0 and invalidated
        else 0.0
    )
    time_to_demotion = _time_to_invalidation(
        store_snapshot,
        scenario.expected_lifecycle["old_candidate_id"],
        scenario.expected_lifecycle["contradiction_timestamp"],
    )
    premature_promotion = _premature_promotion_rate(store_snapshot, scenario)
    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=useful_recall,
        used_pending_before_contradiction=used_pending_before,
        durable_commit_before_contradiction=durable_commit_before,
        false_assertion_after_contradiction=false_assertion,
        contradiction_recovery_rate=recovered,
        answer_correctness_after_contradiction=answer_correctness,
        time_to_demotion=time_to_demotion,
        answer_correctness=answer_correctness,
        false_assertion_rate=false_assertion,
        leakage_rate=0.0,
        premature_promotion_rate=premature_promotion,
        useful_recall=useful_recall,
        used_pending=used_pending_before,
        durable_commit=durable_commit_before,
    )


def compute_scope_contamination_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    questions = {}
    for event in scenario.sorted_events():
        if event.question is not None:
            questions[event.question.phase] = event.question
    traces = {trace.question_id: trace for trace in question_traces}
    probe_question = questions["off_scope_probe"]
    probe_trace = traces[probe_question.question_id]

    probe_asserted_ids = _asserted_candidate_ids(probe_trace, store_snapshot)
    answer_correctness = (
        1.0 if _contains_any(probe_trace.resolved_candidate_ids, probe_question.gold_candidate_ids) else 0.0
    )
    leakage = 1.0 if _contains_any(probe_asserted_ids, probe_question.forbidden_candidate_ids) else 0.0
    premature_promotion = _premature_promotion_rate(store_snapshot, scenario)

    # In this first scope family, the only false assertion is an off-scope leak.
    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=1.0 if probe_trace.used_pending else 0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=None,
        answer_correctness=answer_correctness,
        false_assertion_rate=leakage,
        leakage_rate=leakage,
        premature_promotion_rate=premature_promotion,
        useful_recall=answer_correctness,
        used_pending=1.0 if probe_trace.used_pending else 0.0,
        durable_commit=0.0,
    )


def compute_useful_pending_memory_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    values = _compute_single_probe_values(
        scenario,
        question_traces,
        store_snapshot,
        "pending_probe",
    )

    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=None,
        answer_correctness=values["answer_correctness"],
        false_assertion_rate=values["false_assertion"],
        leakage_rate=0.0,
        premature_promotion_rate=values["premature_promotion"],
        useful_recall=values["answer_correctness"],
        used_pending=values["used_pending"],
        durable_commit=values["durable_commit"],
    )


def compute_preference_drift_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    questions = {}
    for event in scenario.sorted_events():
        if event.question is not None:
            questions[event.question.phase] = event.question
    traces = {trace.question_id: trace for trace in question_traces}
    before_question = questions["before_drift"]
    after_question = questions["after_drift"]
    before_trace = traces[before_question.question_id]
    after_trace = traces[after_question.question_id]
    after_asserted_ids = _asserted_candidate_ids(after_trace, store_snapshot)

    useful_recall = 1.0 if _contains_any(before_trace.resolved_candidate_ids, before_question.gold_candidate_ids) else 0.0
    answer_correctness = 1.0 if _contains_any(after_trace.resolved_candidate_ids, after_question.gold_candidate_ids) else 0.0
    false_assertion = 1.0 if _contains_any(after_asserted_ids, after_question.forbidden_candidate_ids) else 0.0
    old_candidate_id = scenario.expected_lifecycle.get("old_candidate_id", "")
    contradiction_timestamp = scenario.expected_lifecycle.get("contradiction_timestamp")
    time_to_demotion = (
        _time_to_invalidation(store_snapshot, old_candidate_id, contradiction_timestamp)
        if old_candidate_id and contradiction_timestamp
        else None
    )
    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=time_to_demotion,
        answer_correctness=answer_correctness,
        false_assertion_rate=false_assertion,
        leakage_rate=0.0,
        premature_promotion_rate=_premature_promotion_rate(store_snapshot, scenario),
        useful_recall=useful_recall,
        used_pending=1.0 if after_trace.used_pending else 0.0,
        durable_commit=1.0 if old_candidate_id and _candidate_became_durable(store_snapshot, old_candidate_id) else 0.0,
    )


def compute_false_corroboration_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    values = _compute_single_probe_values(
        scenario,
        question_traces,
        store_snapshot,
        "corroboration_probe",
    )

    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=None,
        answer_correctness=values["answer_correctness"],
        false_assertion_rate=values["false_assertion"],
        leakage_rate=0.0,
        premature_promotion_rate=values["premature_promotion"],
        useful_recall=values["answer_correctness"],
        used_pending=values["used_pending"],
        durable_commit=values["durable_commit"],
    )


def compute_memory_poisoning_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    values = _compute_single_probe_values(
        scenario,
        question_traces,
        store_snapshot,
        "poison_probe",
    )
    poison_promotion = _candidate_promotion_rate(
        store_snapshot,
        scenario.expected_lifecycle.get("poison_candidate_ids", []),
    )
    clean_displacement = _clean_durable_displacement_rate(store_snapshot, scenario)

    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=None,
        answer_correctness=values["answer_correctness"],
        false_assertion_rate=values["false_assertion"],
        leakage_rate=0.0,
        premature_promotion_rate=values["premature_promotion"],
        poison_promotion_rate=poison_promotion,
        clean_durable_displacement_rate=clean_displacement,
        useful_recall=values["answer_correctness"],
        used_pending=values["used_pending"],
        durable_commit=values["durable_commit"],
    )


def compute_adversarial_upstream_noise_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    mechanism = str(scenario.expected_lifecycle.get("mechanism", ""))
    values = _compute_single_probe_values(
        scenario,
        question_traces,
        store_snapshot,
        "adversarial_probe",
    )
    answer_correctness = values["answer_correctness"]
    false_assertion = values["false_assertion"]

    if mechanism == "adversarial_witness_conflict":
        probe_question, probe_trace = _probe_question_and_trace(
            scenario,
            question_traces,
            "adversarial_probe",
        )
        asserted_ids = _asserted_candidate_ids(probe_trace, store_snapshot)
        abstention_ok = bool(scenario.expected_lifecycle.get("abstention_ok", False))
        abstained = abstained_from_trace(probe_trace, store_snapshot)
        answer_correctness = 1.0 if abstention_ok and abstained else 0.0
        false_assertion = 1.0 if asserted_ids else 0.0

    retraction_demotion_rate = 0.0
    stale_evidence_promotion_rate = 0.0
    narrow_scope_override_success_rate = 0.0
    pending_competition_resolution_rate = 0.0

    if mechanism == "adversarial_retraction":
        retracted_ids = scenario.expected_lifecycle.get("retracted_candidate_ids", [])
        retraction_demotion_rate = _candidate_invalidated_rate(store_snapshot, retracted_ids)
    elif mechanism == "adversarial_temporal_skew":
        stale_ids = scenario.expected_lifecycle.get("stale_candidate_ids", [])
        stale_evidence_promotion_rate = _candidate_promotion_rate(store_snapshot, stale_ids)
    elif mechanism == "adversarial_scope_narrowing":
        probe_question, probe_trace = _probe_question_and_trace(
            scenario,
            question_traces,
            "adversarial_probe",
        )
        narrow_scope_override_success_rate = (
            1.0
            if _contains_any(probe_trace.resolved_candidate_ids, probe_question.gold_candidate_ids)
            else 0.0
        )
    elif mechanism == "adversarial_pending_competition":
        probe_question, probe_trace = _probe_question_and_trace(
            scenario,
            question_traces,
            "adversarial_probe",
        )
        pending_competition_resolution_rate = (
            1.0
            if _contains_any(probe_trace.resolved_candidate_ids, probe_question.gold_candidate_ids)
            else 0.0
        )

    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=None,
        answer_correctness=answer_correctness,
        false_assertion_rate=false_assertion,
        leakage_rate=0.0,
        premature_promotion_rate=values["premature_promotion"],
        useful_recall=answer_correctness,
        used_pending=values["used_pending"],
        durable_commit=values["durable_commit"],
        retraction_demotion_rate=retraction_demotion_rate,
        stale_evidence_promotion_rate=stale_evidence_promotion_rate,
        narrow_scope_override_success_rate=narrow_scope_override_success_rate,
        pending_competition_resolution_rate=pending_competition_resolution_rate,
    )


def compute_evidence_conflict_spectrum_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    probe_question, probe_trace = _probe_question_and_trace(
        scenario,
        question_traces,
        "evidence_conflict_probe",
    )
    asserted_ids = _asserted_candidate_ids(probe_trace, store_snapshot)
    abstention_ok, commit_required, _, _ = scenario_intent(
        family=scenario.task_family.value,
        template_id=scenario.template_id,
        expected_lifecycle=scenario.expected_lifecycle,
    )
    abstained = abstained_from_trace(probe_trace, store_snapshot)
    resolved_gold = _contains_any(probe_trace.resolved_candidate_ids, probe_question.gold_candidate_ids)
    answer_correctness = 1.0 if (abstention_ok and abstained) or (commit_required and resolved_gold) else 0.0
    false_assertion = 1.0 if _contains_any(asserted_ids, probe_question.forbidden_candidate_ids) else 0.0
    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=None,
        answer_correctness=answer_correctness,
        false_assertion_rate=false_assertion,
        leakage_rate=0.0,
        premature_promotion_rate=_premature_promotion_rate(store_snapshot, scenario),
        useful_recall=1.0 if resolved_gold else 0.0,
        used_pending=1.0 if probe_trace.used_pending else 0.0,
        durable_commit=1.0 if getattr(probe_trace, "used_memory_ids", []) else 0.0,
        useful_abstention=1.0 if abstention_ok and abstained else 0.0,
        useful_abstention_applicable=1.0 if abstention_ok else 0.0,
        harmful_abstention=1.0 if commit_required and abstained else 0.0,
        harmful_abstention_applicable=1.0 if commit_required else 0.0,
    )


def compute_longmemeval_external_metrics(
    policy_name: str,
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
) -> PolicyScenarioMetrics:
    _, probe_trace = _probe_question_and_trace(
        scenario,
        question_traces,
        "longmemeval_probe",
    )
    resolved_candidate_ids = list(getattr(probe_trace, "resolved_candidate_ids", []))
    used_memory_ids = list(getattr(probe_trace, "used_memory_ids", []))
    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=0.0,
        used_pending_before_contradiction=0.0,
        durable_commit_before_contradiction=0.0,
        false_assertion_after_contradiction=0.0,
        contradiction_recovery_rate=0.0,
        answer_correctness_after_contradiction=0.0,
        time_to_demotion=None,
        # Gold-side answers remain outside the policy runtime. Phase X.3 smoke
        # verifies execution, storage, and lookup plumbing; QA correctness is
        # scored later by the LongMemEval judge/PFLC path.
        answer_correctness=0.0,
        false_assertion_rate=0.0,
        leakage_rate=0.0,
        premature_promotion_rate=_premature_promotion_rate(store_snapshot, scenario),
        # LongMemEval transfer uses PFLC scoring later; these legacy runner metrics
        # are binary smoke signals for whether the policy surfaced any memory.
        useful_recall=float(bool(resolved_candidate_ids)),
        used_pending=float(bool(getattr(probe_trace, "used_pending", False))),
        durable_commit=float(bool(used_memory_ids)),
    )


def summarize_runs(run_records: List[Dict[str, object]]) -> PolicySummaryMetrics:
    metrics = []
    policy_name = ""
    for record in run_records:
        metric = record["metrics"]
        policy_name = metric["policy_name"]
        metrics.append(
            PolicyScenarioMetrics(
                scenario_id=metric["scenario_id"],
                policy_name=metric["policy_name"],
                useful_recall_before_contradiction=metric["useful_recall_before_contradiction"],
                used_pending_before_contradiction=metric["used_pending_before_contradiction"],
                durable_commit_before_contradiction=metric["durable_commit_before_contradiction"],
                false_assertion_after_contradiction=metric["false_assertion_after_contradiction"],
                contradiction_recovery_rate=metric["contradiction_recovery_rate"],
                answer_correctness_after_contradiction=metric["answer_correctness_after_contradiction"],
                time_to_demotion=metric["time_to_demotion"],
                answer_correctness=metric.get("answer_correctness", metric["answer_correctness_after_contradiction"]),
                false_assertion_rate=metric.get(
                    "false_assertion_rate",
                    metric["false_assertion_after_contradiction"],
                ),
                leakage_rate=metric.get("leakage_rate", 0.0),
                premature_promotion_rate=metric.get("premature_promotion_rate", 0.0),
                poison_promotion_rate=metric.get("poison_promotion_rate", 0.0),
                clean_durable_displacement_rate=metric.get("clean_durable_displacement_rate", 0.0),
                retraction_demotion_rate=metric.get("retraction_demotion_rate", 0.0),
                stale_evidence_promotion_rate=metric.get("stale_evidence_promotion_rate", 0.0),
                narrow_scope_override_success_rate=metric.get(
                    "narrow_scope_override_success_rate",
                    0.0,
                ),
                pending_competition_resolution_rate=metric.get(
                    "pending_competition_resolution_rate",
                    0.0,
                ),
                useful_abstention=metric.get("useful_abstention", 0.0),
                useful_abstention_applicable=metric.get("useful_abstention_applicable", 0.0),
                harmful_abstention=metric.get("harmful_abstention", 0.0),
                harmful_abstention_applicable=metric.get("harmful_abstention_applicable", 0.0),
                useful_recall=metric.get(
                    "useful_recall",
                    metric["useful_recall_before_contradiction"],
                ),
                used_pending=metric.get(
                    "used_pending",
                    metric["used_pending_before_contradiction"],
                ),
                durable_commit=metric.get(
                    "durable_commit",
                    metric["durable_commit_before_contradiction"],
                ),
            )
        )
    return PolicySummaryMetrics.from_scenarios(policy_name, metrics)


def _contains_any(resolved_ids: List[str], gold_ids: List[str]) -> bool:
    return any(candidate_id in resolved_ids for candidate_id in gold_ids)


def _compute_single_probe_values(
    scenario: Scenario,
    question_traces: List[object],
    store_snapshot: Dict[str, object],
    probe_phase: str,
) -> Dict[str, float]:
    questions = {}
    for event in scenario.sorted_events():
        if event.question is not None:
            questions[event.question.phase] = event.question
    traces = {trace.question_id: trace for trace in question_traces}
    probe_question = questions.get(probe_phase)
    if probe_question is None:
        raise ValueError("Scenario {} is missing {} question".format(scenario.scenario_id, probe_phase))
    probe_trace = traces.get(probe_question.question_id)
    if probe_trace is None:
        raise ValueError(
            "Scenario {} is missing trace for {} question {}".format(
                scenario.scenario_id,
                probe_phase,
                probe_question.question_id,
            )
        )

    asserted_ids = _asserted_candidate_ids(probe_trace, store_snapshot)
    answer_correctness = (
        1.0 if _contains_any(probe_trace.resolved_candidate_ids, probe_question.gold_candidate_ids) else 0.0
    )
    false_assertion = 1.0 if _contains_any(asserted_ids, probe_question.forbidden_candidate_ids) else 0.0
    return {
        "answer_correctness": answer_correctness,
        "false_assertion": false_assertion,
        "premature_promotion": _premature_promotion_rate(store_snapshot, scenario),
        "used_pending": 1.0 if probe_trace.used_pending else 0.0,
        "durable_commit": 1.0 if getattr(probe_trace, "used_memory_ids", []) else 0.0,
    }


def _probe_question_and_trace(
    scenario: Scenario,
    question_traces: List[object],
    probe_phase: str,
) -> tuple[QuestionSpec, object]:
    questions = {}
    for event in scenario.sorted_events():
        if event.question is not None:
            questions[event.question.phase] = event.question
    traces = {trace.question_id: trace for trace in question_traces}
    probe_question = questions.get(probe_phase)
    if probe_question is None:
        raise ValueError("Scenario {} is missing {} question".format(scenario.scenario_id, probe_phase))
    probe_trace = traces.get(probe_question.question_id)
    if probe_trace is None:
        raise ValueError(
            "Scenario {} is missing trace for {} question {}".format(
                scenario.scenario_id,
                probe_phase,
                probe_question.question_id,
            )
        )
    return probe_question, probe_trace


def _ordered_intersection(source_ids: List[str], target_ids: List[str]) -> List[str]:
    target_set = set(target_ids)
    return [candidate_id for candidate_id in source_ids if candidate_id in target_set]


def _sorted_unique(candidate_ids: List[str]) -> List[str]:
    return sorted(set(candidate_ids))


def _promoted_should_not_promote_candidate_ids(
    store_snapshot: Dict[str, object],
    scenario: Scenario,
) -> List[str]:
    should_not_promote_ids = scenario.expected_lifecycle.get("should_not_promote_candidate_ids", [])
    return [
        candidate_id
        for candidate_id in should_not_promote_ids
        if _candidate_became_durable(store_snapshot, candidate_id)
    ]


def _candidate_claims(store_snapshot: Dict[str, object], candidate_ids: List[str]) -> Dict[str, str]:
    candidate_by_id = {
        candidate["candidate_id"]: candidate
        for candidate in store_snapshot.get("candidate_memories", [])
    }
    return {
        candidate_id: str(candidate_by_id[candidate_id].get("canonical_claim", ""))
        for candidate_id in sorted(candidate_ids)
        if candidate_id in candidate_by_id
    }


def _durable_claims(
    store_snapshot: Dict[str, object],
    candidate_ids: List[str],
    used_memory_ids: List[str],
) -> Dict[str, Dict[str, object]]:
    candidate_id_set = set(candidate_ids)
    used_memory_id_set = set(used_memory_ids)
    involved_durables = []
    for durable in store_snapshot.get("durable_memories", []):
        created_from_ids = durable.get("created_from_candidate_ids", [])
        if durable["memory_id"] in used_memory_id_set or any(
            candidate_id in candidate_id_set for candidate_id in created_from_ids
        ):
            involved_durables.append(durable)
    return {
        durable["memory_id"]: {
            "claim": durable.get("claim", ""),
            "created_from_candidate_ids": list(durable.get("created_from_candidate_ids", [])),
            "active": bool(durable.get("active", False)),
        }
        for durable in sorted(involved_durables, key=lambda item: item["memory_id"])
    }


def _asserted_candidate_ids(trace: object, store_snapshot: Dict[str, object]) -> List[str]:
    return asserted_candidate_ids(trace, store_snapshot)


def _old_claim_invalidated(store_snapshot: Dict[str, object], old_candidate_id: str) -> bool:
    for candidate in store_snapshot["candidate_memories"]:
        if candidate["candidate_id"] == old_candidate_id and candidate["state"] == MemoryState.CONTESTED.value:
            return True
    for durable in store_snapshot["durable_memories"]:
        if old_candidate_id in durable["created_from_candidate_ids"] and not durable["active"]:
            return True
    return False


def _candidate_became_durable(store_snapshot: Dict[str, object], candidate_id: str) -> bool:
    for durable in store_snapshot["durable_memories"]:
        if candidate_id in durable["created_from_candidate_ids"]:
            return True
    return False


def _displaced_clean_durable_candidate_ids(
    store_snapshot: Dict[str, object],
    scenario: Scenario,
) -> List[str]:
    clean_candidate_ids = scenario.expected_lifecycle.get("clean_durable_candidate_ids", [])
    displaced = []
    for candidate_id in clean_candidate_ids:
        if _durable_for_candidate_was_demoted(store_snapshot, candidate_id):
            displaced.append(candidate_id)
    return displaced


def _durable_for_candidate_was_demoted(store_snapshot: Dict[str, object], candidate_id: str) -> bool:
    for durable in store_snapshot["durable_memories"]:
        if candidate_id in durable["created_from_candidate_ids"] and not durable["active"]:
            return True
    return False


def _clean_durable_displacement_rate(store_snapshot: Dict[str, object], scenario: Scenario) -> float:
    clean_candidate_ids = scenario.expected_lifecycle.get("clean_durable_candidate_ids", [])
    if not clean_candidate_ids:
        return 0.0
    displaced = _displaced_clean_durable_candidate_ids(store_snapshot, scenario)
    return len(displaced) / len(clean_candidate_ids)


def _premature_promotion_rate(store_snapshot: Dict[str, object], scenario: Scenario) -> float:
    should_not_promote = scenario.expected_lifecycle.get("should_not_promote_candidate_ids", [])
    return _candidate_promotion_rate(store_snapshot, should_not_promote)


def _candidate_promotion_rate(store_snapshot: Dict[str, object], candidate_ids: List[str]) -> float:
    if not candidate_ids:
        return 0.0
    promoted = 0
    for candidate_id in candidate_ids:
        if _candidate_became_durable(store_snapshot, candidate_id):
            promoted += 1
    return promoted / len(candidate_ids)


def _candidate_invalidated_rate(store_snapshot: Dict[str, object], candidate_ids: List[str]) -> float:
    if not candidate_ids:
        return 0.0
    invalidated = 0
    for candidate_id in candidate_ids:
        if _old_claim_invalidated(store_snapshot, candidate_id):
            invalidated += 1
    return invalidated / len(candidate_ids)


def _time_to_invalidation(
    store_snapshot: Dict[str, object],
    old_candidate_id: str,
    contradiction_timestamp: str,
) -> Optional[float]:
    contradiction_at = iso_to_datetime(contradiction_timestamp)
    for event in store_snapshot["lifecycle_events"]:
        timestamp = iso_to_datetime(event["timestamp"])
        if event["object_type"] == "candidate" and event["object_id"] == old_candidate_id:
            details = event.get("details", {})
            if details.get("new_state") == MemoryState.CONTESTED.value:
                return minutes_between(contradiction_at, timestamp)
        if event["object_type"] == "durable_memory" and event["event_type"] == "memory_demoted":
            created_from_ids = event.get("details", {}).get("created_from_candidate_ids", [])
            if old_candidate_id in created_from_ids:
                return minutes_between(contradiction_at, timestamp)
    return None
