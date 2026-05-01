from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PolicyScenarioMetrics:
    scenario_id: str
    policy_name: str
    useful_recall_before_contradiction: float
    used_pending_before_contradiction: float
    durable_commit_before_contradiction: float
    false_assertion_after_contradiction: float
    contradiction_recovery_rate: float
    answer_correctness_after_contradiction: float
    time_to_demotion: Optional[float]


@dataclass
class PolicySummaryMetrics:
    policy_name: str
    scenario_count: int
    useful_recall_before_contradiction: float
    used_pending_before_contradiction: float
    durable_commit_before_contradiction: float
    false_assertion_after_contradiction: float
    contradiction_recovery_rate: float
    answer_correctness_after_contradiction: float
    average_time_to_demotion: float

    @classmethod
    def from_scenarios(cls, policy_name: str, metrics: List[PolicyScenarioMetrics]) -> "PolicySummaryMetrics":
        count = len(metrics)
        if not count:
            return cls(
                policy_name=policy_name,
                scenario_count=0,
                useful_recall_before_contradiction=0.0,
                used_pending_before_contradiction=0.0,
                durable_commit_before_contradiction=0.0,
                false_assertion_after_contradiction=0.0,
                contradiction_recovery_rate=0.0,
                answer_correctness_after_contradiction=0.0,
                average_time_to_demotion=0.0,
            )
        demotions = [metric.time_to_demotion for metric in metrics if metric.time_to_demotion is not None]
        average_time = sum(demotions) / len(demotions) if demotions else 0.0
        return cls(
            policy_name=policy_name,
            scenario_count=count,
            useful_recall_before_contradiction=sum(
                metric.useful_recall_before_contradiction for metric in metrics
            )
            / count,
            used_pending_before_contradiction=sum(metric.used_pending_before_contradiction for metric in metrics)
            / count,
            durable_commit_before_contradiction=sum(
                metric.durable_commit_before_contradiction for metric in metrics
            )
            / count,
            false_assertion_after_contradiction=sum(
                metric.false_assertion_after_contradiction for metric in metrics
            )
            / count,
            contradiction_recovery_rate=sum(metric.contradiction_recovery_rate for metric in metrics) / count,
            answer_correctness_after_contradiction=sum(
                metric.answer_correctness_after_contradiction for metric in metrics
            )
            / count,
            average_time_to_demotion=average_time,
        )
