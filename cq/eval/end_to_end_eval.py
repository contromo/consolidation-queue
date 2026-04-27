from __future__ import annotations

from typing import Dict, List, Optional, Type

from cq.eval.metrics import iso_to_datetime, minutes_between
from cq.schemas.memory import MemoryState, jsonable
from cq.schemas.metrics import PolicyScenarioMetrics, PolicySummaryMetrics
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario


def execute_scenario(policy_cls: Type[object], scenario: Scenario) -> Dict[str, object]:
    policy = policy_cls()
    question_traces = []
    for event in scenario.sorted_events():
        if event.kind == EventKind.OBSERVATION and event.candidate is not None:
            policy.observe_candidate(event.candidate)
        if event.kind == EventKind.QUESTION and event.question is not None:
            question_traces.append(policy.answer_question(event.question))
    metrics = compute_forced_contradiction_metrics(
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
    durable_commit_before = 1.0 if _old_claim_became_durable(store_snapshot, scenario.expected_lifecycle["old_candidate_id"]) else 0.0
    false_assertion = 1.0 if _contains_any(after_trace.resolved_candidate_ids, after_question.forbidden_candidate_ids) else 0.0

    invalidated = _old_claim_invalidated(
        store_snapshot,
        scenario.expected_lifecycle["old_candidate_id"],
    )
    recovered = (
        1.0
        if _contains_any(after_trace.resolved_candidate_ids, after_question.gold_candidate_ids) and invalidated
        else 0.0
    )
    time_to_demotion = _time_to_invalidation(
        store_snapshot,
        scenario.expected_lifecycle["old_candidate_id"],
        scenario.expected_lifecycle["contradiction_timestamp"],
    )
    return PolicyScenarioMetrics(
        scenario_id=scenario.scenario_id,
        policy_name=policy_name,
        useful_recall_before_contradiction=useful_recall,
        used_pending_before_contradiction=used_pending_before,
        durable_commit_before_contradiction=durable_commit_before,
        false_assertion_after_contradiction=false_assertion,
        contradiction_recovery_rate=recovered,
        time_to_demotion=time_to_demotion,
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
                time_to_demotion=metric["time_to_demotion"],
            )
        )
    return PolicySummaryMetrics.from_scenarios(policy_name, metrics)


def _contains_any(resolved_ids: List[str], gold_ids: List[str]) -> bool:
    return any(candidate_id in resolved_ids for candidate_id in gold_ids)


def _old_claim_invalidated(store_snapshot: Dict[str, object], old_candidate_id: str) -> bool:
    for candidate in store_snapshot["candidate_memories"]:
        if candidate["candidate_id"] == old_candidate_id and candidate["state"] == MemoryState.CONTESTED.value:
            return True
    for durable in store_snapshot["durable_memories"]:
        if old_candidate_id in durable["created_from_candidate_ids"] and not durable["active"]:
            return True
    return False


def _old_claim_became_durable(store_snapshot: Dict[str, object], old_candidate_id: str) -> bool:
    for durable in store_snapshot["durable_memories"]:
        if old_candidate_id in durable["created_from_candidate_ids"]:
            return True
    return False


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
