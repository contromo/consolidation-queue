from __future__ import annotations

from typing import Dict, List, Optional, Type

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
    metrics = compute_policy_metrics(
        policy.policy_name,
        scenario,
        question_traces,
        policy.store.snapshot(),
    )
    return {
        "policy_name": policy.policy_name,
        "scenario_id": scenario.scenario_id,
        "scenario": jsonable(scenario),
        "question_traces": [jsonable(trace) for trace in question_traces],
        "store_snapshot": policy.store.snapshot(),
        "metrics": jsonable(metrics),
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
    raise ValueError("Unsupported task family: {}".format(scenario.task_family))


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


def _asserted_candidate_ids(trace: object, store_snapshot: Dict[str, object]) -> List[str]:
    used_memory_ids = getattr(trace, "used_memory_ids", [])
    if not used_memory_ids:
        return list(getattr(trace, "resolved_candidate_ids", []))

    asserted_ids = []
    durable_by_id = {
        durable["memory_id"]: durable
        for durable in store_snapshot.get("durable_memories", [])
    }
    for memory_id in used_memory_ids:
        durable = durable_by_id.get(memory_id)
        if durable is None:
            continue
        created_from_ids = durable.get("created_from_candidate_ids", [])
        if created_from_ids:
            asserted_ids.append(created_from_ids[0])
    if asserted_ids:
        return asserted_ids
    return list(getattr(trace, "resolved_candidate_ids", []))


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


def _premature_promotion_rate(store_snapshot: Dict[str, object], scenario: Scenario) -> float:
    should_not_promote = scenario.expected_lifecycle.get("should_not_promote_candidate_ids", [])
    if not should_not_promote:
        return 0.0
    promoted = 0
    for candidate_id in should_not_promote:
        if _candidate_became_durable(store_snapshot, candidate_id):
            promoted += 1
    return promoted / len(should_not_promote)


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
