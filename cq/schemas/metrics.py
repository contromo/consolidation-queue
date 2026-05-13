from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, cast


_UNSET_FLOAT = cast(float, object())


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
    answer_correctness: float = _UNSET_FLOAT
    false_assertion_rate: float = _UNSET_FLOAT
    leakage_rate: float = 0.0
    premature_promotion_rate: float = 0.0
    poison_promotion_rate: float = 0.0
    clean_durable_displacement_rate: float = 0.0
    retraction_demotion_rate: float = 0.0
    stale_evidence_promotion_rate: float = 0.0
    narrow_scope_override_success_rate: float = 0.0
    pending_competition_resolution_rate: float = 0.0
    useful_abstention: float = 0.0
    useful_abstention_applicable: float = 0.0
    harmful_abstention: float = 0.0
    harmful_abstention_applicable: float = 0.0
    useful_recall: float = _UNSET_FLOAT
    used_pending: float = _UNSET_FLOAT
    durable_commit: float = _UNSET_FLOAT

    def __post_init__(self) -> None:
        if self.answer_correctness is _UNSET_FLOAT:
            self.answer_correctness = self.answer_correctness_after_contradiction
        if self.false_assertion_rate is _UNSET_FLOAT:
            self.false_assertion_rate = self.false_assertion_after_contradiction
        if self.useful_recall is _UNSET_FLOAT:
            self.useful_recall = self.useful_recall_before_contradiction
        if self.used_pending is _UNSET_FLOAT:
            self.used_pending = self.used_pending_before_contradiction
        if self.durable_commit is _UNSET_FLOAT:
            self.durable_commit = self.durable_commit_before_contradiction


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
    answer_correctness: float = 0.0
    false_assertion_rate: float = 0.0
    leakage_rate: float = 0.0
    premature_promotion_rate: float = 0.0
    poison_promotion_rate: float = 0.0
    clean_durable_displacement_rate: float = 0.0
    retraction_demotion_rate: float = 0.0
    stale_evidence_promotion_rate: float = 0.0
    narrow_scope_override_success_rate: float = 0.0
    pending_competition_resolution_rate: float = 0.0
    useful_abstention_rate: float = 0.0
    useful_abstention_count: float = 0.0
    useful_abstention_applicable_count: float = 0.0
    harmful_abstention_rate: float = 0.0
    harmful_abstention_count: float = 0.0
    harmful_abstention_applicable_count: float = 0.0
    useful_recall: float = 0.0
    used_pending: float = 0.0
    durable_commit: float = 0.0

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
                answer_correctness=0.0,
                false_assertion_rate=0.0,
                leakage_rate=0.0,
                premature_promotion_rate=0.0,
                poison_promotion_rate=0.0,
                clean_durable_displacement_rate=0.0,
                retraction_demotion_rate=0.0,
                stale_evidence_promotion_rate=0.0,
                narrow_scope_override_success_rate=0.0,
                pending_competition_resolution_rate=0.0,
                useful_abstention_rate=0.0,
                useful_abstention_count=0.0,
                useful_abstention_applicable_count=0.0,
                harmful_abstention_rate=0.0,
                harmful_abstention_count=0.0,
                harmful_abstention_applicable_count=0.0,
                useful_recall=0.0,
                used_pending=0.0,
                durable_commit=0.0,
            )
        demotions = [metric.time_to_demotion for metric in metrics if metric.time_to_demotion is not None]
        average_time = sum(demotions) / len(demotions) if demotions else 0.0
        useful_applicable = sum(metric.useful_abstention_applicable for metric in metrics)
        useful_count = sum(metric.useful_abstention for metric in metrics)
        harmful_applicable = sum(metric.harmful_abstention_applicable for metric in metrics)
        harmful_count = sum(metric.harmful_abstention for metric in metrics)
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
            answer_correctness=sum(metric.answer_correctness for metric in metrics) / count,
            false_assertion_rate=sum(metric.false_assertion_rate for metric in metrics) / count,
            leakage_rate=sum(metric.leakage_rate for metric in metrics) / count,
            premature_promotion_rate=sum(metric.premature_promotion_rate for metric in metrics) / count,
            poison_promotion_rate=sum(metric.poison_promotion_rate for metric in metrics) / count,
            clean_durable_displacement_rate=sum(
                metric.clean_durable_displacement_rate for metric in metrics
            )
            / count,
            retraction_demotion_rate=sum(metric.retraction_demotion_rate for metric in metrics) / count,
            stale_evidence_promotion_rate=sum(
                metric.stale_evidence_promotion_rate for metric in metrics
            )
            / count,
            narrow_scope_override_success_rate=sum(
                metric.narrow_scope_override_success_rate for metric in metrics
            )
            / count,
            pending_competition_resolution_rate=sum(
                metric.pending_competition_resolution_rate for metric in metrics
            )
            / count,
            useful_abstention_rate=(useful_count / useful_applicable if useful_applicable else 0.0),
            useful_abstention_count=useful_count,
            useful_abstention_applicable_count=useful_applicable,
            harmful_abstention_rate=(harmful_count / harmful_applicable if harmful_applicable else 0.0),
            harmful_abstention_count=harmful_count,
            harmful_abstention_applicable_count=harmful_applicable,
            useful_recall=sum(metric.useful_recall for metric in metrics) / count,
            used_pending=sum(metric.used_pending for metric in metrics) / count,
            durable_commit=sum(metric.durable_commit for metric in metrics) / count,
        )
