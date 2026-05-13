from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, Iterable, List, Mapping, Sequence

from cq.eval.bootstrap import (
    mean,
    one_sided_lower_confidence_bound,
    one_sided_upper_confidence_bound,
    paired_delta_point_estimate,
    stratified_paired_bootstrap_sample_means,
)
from cq.simulator.scenario_generator import MECHANISM_DIVERSE_ABSTENTION_INTENTS


ABSTAIN_REQUIRED_INTENSITIES = ("moderate", "witness")
COMMIT_REQUIRED_INTENSITIES = ("zero", "mild", "polluted")
PRIMARY_USEFUL_MECHANISMS = ("conflict_moderate", "conflict_witness")
PRIMARY_HARMFUL_MECHANISMS = ("conflict_zero", "conflict_mild", "conflict_polluted")

PROBE_PHASE_BY_FAMILY = {
    "forced_contradiction": "after_contradiction",
    "scope_contamination": "off_scope_probe",
    "preference_drift": "after_drift",
    "useful_pending_memory": "pending_probe",
    "false_corroboration": "corroboration_probe",
    "memory_poisoning": "poison_probe",
    "adversarial_upstream_noise": "adversarial_probe",
    "mechanism_diverse_heldout": "",
    "evidence_conflict_spectrum": "evidence_conflict_probe",
}

ADVERSARIAL_COMMIT_MECHANISMS = {
    "adversarial_retraction",
    "adversarial_temporal_skew",
    "adversarial_scope_narrowing",
    "adversarial_pending_competition",
}

@dataclass(frozen=True)
class AbstentionDecision:
    scenario_id: str
    policy_name: str
    family: str
    mechanism: str
    intensity: str
    abstention_ok: bool
    commit_required: bool
    abstained: bool
    useful_abstention: float
    useful_abstention_applicable: float
    harmful_abstention: float
    harmful_abstention_applicable: float

    @property
    def action(self) -> str:
        return "abstain" if self.abstained else "commit"


@dataclass(frozen=True)
class AbstentionSummary:
    scenario_count: int
    abstention_ok_count: int
    commit_required_count: int
    gray_zone_count: int
    abstain_count: int
    useful_abstention_count: int
    harmful_abstention_count: int
    useful_abstention_rate: float
    harmful_abstention_rate: float
    abstain_rate: float


@dataclass(frozen=True)
class BucketBootstrapResult:
    point_estimate_delta: float
    lower_confidence_bound: float
    upper_confidence_bound: float
    scenario_count: int
    confidence_level: float
    resamples: int
    seed: int


def as_trace_object(trace: object) -> object:
    if isinstance(trace, Mapping):
        return SimpleNamespace(**trace)
    return trace


def _trace_value(trace: object, field_name: str, default: object) -> object:
    if isinstance(trace, Mapping):
        return trace.get(field_name, default)
    return getattr(trace, field_name, default)


def asserted_candidate_ids(trace: object, store_snapshot: Dict[str, object]) -> List[str]:
    used_memory_ids = list(_trace_value(trace, "used_memory_ids", []))
    resolved_candidate_ids = list(_trace_value(trace, "resolved_candidate_ids", []))
    if not used_memory_ids:
        return resolved_candidate_ids

    asserted_ids = []
    unresolved_used_ids = []
    durable_by_id = {
        durable["memory_id"]: durable
        for durable in store_snapshot.get("durable_memories", [])
    }
    for memory_id in used_memory_ids:
        durable = durable_by_id.get(memory_id)
        if durable is None:
            unresolved_used_ids.append(memory_id)
            continue
        created_from_ids = durable.get("created_from_candidate_ids", [])
        if created_from_ids:
            # A reinforced durable asserts its original durable claim, not every corroborating source.
            asserted_ids.append(created_from_ids[0])
        else:
            unresolved_used_ids.append(memory_id)
    if asserted_ids:
        for candidate_id in resolved_candidate_ids:
            if candidate_id in unresolved_used_ids and candidate_id not in asserted_ids:
                asserted_ids.append(candidate_id)
        return asserted_ids
    return resolved_candidate_ids


def abstained_from_trace(trace: object, store_snapshot: Dict[str, object]) -> bool:
    asserted_ids = asserted_candidate_ids(trace, store_snapshot)
    # This is the source-of-truth abstention predicate used by runner metrics and replay.
    return not asserted_ids and not list(_trace_value(trace, "resolved_candidate_ids", []))


def scenario_intent(
    *,
    family: str,
    template_id: str,
    expected_lifecycle: Mapping[str, object],
) -> tuple[bool, bool, str, str]:
    mechanism = str(expected_lifecycle.get("mechanism", "")) or template_id
    intensity = str(expected_lifecycle.get("evidence_conflict_intensity", ""))
    if "abstention_ok" in expected_lifecycle or "commit_required" in expected_lifecycle:
        return (
            bool(expected_lifecycle.get("abstention_ok", False)),
            bool(expected_lifecycle.get("commit_required", False)),
            mechanism,
            intensity,
        )

    if family == "adversarial_upstream_noise":
        if mechanism == "adversarial_witness_conflict":
            return True, False, mechanism, "witness"
        if mechanism in ADVERSARIAL_COMMIT_MECHANISMS:
            return False, True, mechanism, ""
    if family == "mechanism_diverse_heldout":
        intent = MECHANISM_DIVERSE_ABSTENTION_INTENTS.get(template_id)
        if intent is None:
            raise ValueError(
                "No mechanism-diverse abstention intent mapping for template '{}'".format(
                    template_id,
                )
            )
        abstention_ok, commit_required = intent
        return abstention_ok, commit_required, template_id, ""

    raise ValueError(
        "No abstention intent mapping for family '{}' template '{}' mechanism '{}'".format(
            family,
            template_id,
            mechanism,
        )
    )


def _scenario_value(scenario: object, field_name: str, default: object = None) -> object:
    if isinstance(scenario, Mapping):
        return scenario.get(field_name, default)
    return getattr(scenario, field_name, default)


def _expected_lifecycle(scenario: object) -> Mapping[str, object]:
    lifecycle = _scenario_value(scenario, "expected_lifecycle", {})
    if not isinstance(lifecycle, Mapping):
        raise ValueError("Scenario expected_lifecycle must be a mapping")
    return lifecycle


def _probe_phase_for_record(scenario: Mapping[str, object], family: str) -> str:
    lifecycle = _expected_lifecycle(scenario)
    phase = str(lifecycle.get("probe_phase", ""))
    if phase:
        return phase
    if family == "mechanism_diverse_heldout":
        events = scenario.get("oracle_events", [])
        question_phases = [
            event.get("question", {}).get("phase", "")
            for event in events
            if isinstance(event, Mapping) and event.get("question") is not None
        ]
        return question_phases[-1] if question_phases else ""
    return PROBE_PHASE_BY_FAMILY.get(family, "")


def _question_id_for_probe(scenario: Mapping[str, object], family: str) -> str:
    phase = _probe_phase_for_record(scenario, family)
    fallback_question_id = ""
    for event in scenario.get("oracle_events", []):
        if not isinstance(event, Mapping):
            continue
        question = event.get("question")
        if not isinstance(question, Mapping):
            continue
        if not phase:
            fallback_question_id = str(question["question_id"])
            continue
        if question.get("phase") == phase:
            return str(question["question_id"])
    if fallback_question_id:
        return fallback_question_id
    raise ValueError("Scenario {} is missing probe question phase {}".format(scenario.get("scenario_id"), phase))


def abstention_decision_from_record(policy_name: str, record: Mapping[str, object], family: str) -> AbstentionDecision:
    scenario = record["scenario"]
    if not isinstance(scenario, Mapping):
        raise ValueError("Replay record scenario must be a mapping")
    expected = _expected_lifecycle(scenario)
    template_id = str(scenario.get("template_id", ""))
    abstention_ok, commit_required, mechanism, intensity = scenario_intent(
        family=family,
        template_id=template_id,
        expected_lifecycle=expected,
    )
    question_id = _question_id_for_probe(scenario, family)
    traces = {
        str(trace["question_id"]): trace
        for trace in record.get("question_traces", [])
        if isinstance(trace, Mapping)
    }
    if question_id not in traces:
        raise ValueError("Record {} missing trace {}".format(record.get("scenario_id"), question_id))
    trace = traces[question_id]
    store_snapshot = record.get("store_snapshot", {})
    if not isinstance(store_snapshot, dict):
        raise ValueError("Record store_snapshot must be a mapping")
    abstained = abstained_from_trace(trace, store_snapshot)
    return AbstentionDecision(
        scenario_id=str(record["scenario_id"]),
        policy_name=policy_name,
        family=family,
        mechanism=mechanism,
        intensity=intensity,
        abstention_ok=abstention_ok,
        commit_required=commit_required,
        abstained=abstained,
        useful_abstention=1.0 if abstention_ok and abstained else 0.0,
        useful_abstention_applicable=1.0 if abstention_ok else 0.0,
        harmful_abstention=1.0 if commit_required and abstained else 0.0,
        harmful_abstention_applicable=1.0 if commit_required else 0.0,
    )


def summarize_decisions(decisions: Sequence[AbstentionDecision]) -> AbstentionSummary:
    count = len(decisions)
    abstention_ok_count = sum(1 for decision in decisions if decision.abstention_ok)
    commit_required_count = sum(1 for decision in decisions if decision.commit_required)
    gray_zone_count = sum(1 for decision in decisions if not decision.abstention_ok and not decision.commit_required)
    abstain_count = sum(1 for decision in decisions if decision.abstained)
    useful_count = sum(int(decision.useful_abstention) for decision in decisions)
    harmful_count = sum(int(decision.harmful_abstention) for decision in decisions)
    return AbstentionSummary(
        scenario_count=count,
        abstention_ok_count=abstention_ok_count,
        commit_required_count=commit_required_count,
        gray_zone_count=gray_zone_count,
        abstain_count=abstain_count,
        useful_abstention_count=useful_count,
        harmful_abstention_count=harmful_count,
        useful_abstention_rate=(useful_count / abstention_ok_count if abstention_ok_count else 0.0),
        harmful_abstention_rate=(harmful_count / commit_required_count if commit_required_count else 0.0),
        abstain_rate=(abstain_count / count if count else 0.0),
    )


def grouped_decisions(
    decisions: Iterable[AbstentionDecision],
    *,
    field_name: str,
) -> Dict[str, List[AbstentionDecision]]:
    grouped: Dict[str, List[AbstentionDecision]] = {}
    for decision in decisions:
        field_value = str(getattr(decision, field_name))
        grouped.setdefault(field_value, []).append(decision)
    return grouped


def _summary_json(summary: AbstentionSummary) -> Dict[str, object]:
    return {
        "scenario_count": summary.scenario_count,
        "abstention_ok_count": summary.abstention_ok_count,
        "commit_required_count": summary.commit_required_count,
        "gray_zone_count": summary.gray_zone_count,
        "abstain_count": summary.abstain_count,
        "useful_abstention_count": summary.useful_abstention_count,
        "harmful_abstention_count": summary.harmful_abstention_count,
        "useful_abstention_rate": summary.useful_abstention_rate,
        "harmful_abstention_rate": summary.harmful_abstention_rate,
        "abstain_rate": summary.abstain_rate,
    }


def decisions_by_policy_from_run_artifact(run_artifact: Mapping[str, object]) -> Dict[str, List[AbstentionDecision]]:
    family = str(run_artifact["family"])
    by_policy: Dict[str, List[AbstentionDecision]] = {}
    for policy in run_artifact.get("policies", []):
        if not isinstance(policy, Mapping):
            continue
        policy_name = str(policy["policy_name"])
        by_policy[policy_name] = [
            abstention_decision_from_record(policy_name, scenario_record, family)
            for scenario_record in policy.get("scenarios", [])
            if isinstance(scenario_record, Mapping)
        ]
    return by_policy


def _paired_deltas(
    reference: Sequence[AbstentionDecision],
    comparator: Sequence[AbstentionDecision],
    *,
    mechanism: str,
    metric_name: str,
) -> List[float]:
    reference_by_id = {decision.scenario_id: decision for decision in reference if decision.mechanism == mechanism}
    comparator_by_id = {decision.scenario_id: decision for decision in comparator if decision.mechanism == mechanism}
    if set(reference_by_id) != set(comparator_by_id):
        raise ValueError("Policy scenario sets differ for mechanism {}".format(mechanism))
    return [
        float(getattr(reference_by_id[scenario_id], metric_name))
        - float(getattr(comparator_by_id[scenario_id], metric_name))
        for scenario_id in sorted(reference_by_id)
    ]


def useful_mechanism_comparison(
    reference: Sequence[AbstentionDecision],
    comparator: Sequence[AbstentionDecision],
    *,
    mechanism: str,
    resamples: int = 10_000,
    seed: int = 0,
) -> Dict[str, object]:
    bootstrap = stratified_bucket_comparison(
        reference,
        comparator,
        mechanisms=(mechanism,),
        metric_name="useful_abstention",
        resamples=resamples,
        seed=seed,
    )
    return {
        "metric_name": "useful_abstention_rate",
        "mechanism": mechanism,
        "point_estimate_delta": bootstrap.point_estimate_delta,
        "one_sided_95_lcb": bootstrap.lower_confidence_bound,
        "scenario_count": bootstrap.scenario_count,
    }


def mechanism_indicator_comparison(
    reference: Sequence[AbstentionDecision],
    comparator: Sequence[AbstentionDecision],
    *,
    mechanism: str,
    metric_name: str,
    resamples: int = 10_000,
    seed: int = 0,
) -> Dict[str, object]:
    bootstrap = stratified_bucket_comparison(
        reference,
        comparator,
        mechanisms=(mechanism,),
        metric_name=metric_name,
        resamples=resamples,
        seed=seed,
    )
    return {
        "metric_name": metric_name,
        "mechanism": mechanism,
        "point_estimate_delta": bootstrap.point_estimate_delta,
        "one_sided_95_lcb": bootstrap.lower_confidence_bound,
        "scenario_count": bootstrap.scenario_count,
    }


def _sample_mean(values: Sequence[float]) -> float:
    return mean(values)


def stratified_bucket_comparison(
    reference: Sequence[AbstentionDecision],
    comparator: Sequence[AbstentionDecision],
    *,
    mechanisms: Sequence[str],
    metric_name: str,
    resamples: int = 10_000,
    seed: int = 0,
) -> BucketBootstrapResult:
    deltas_by_mechanism = {
        mechanism: _paired_deltas(reference, comparator, mechanism=mechanism, metric_name=metric_name)
        for mechanism in mechanisms
    }
    point_estimate = _sample_mean(
        [paired_delta_point_estimate(deltas) for deltas in deltas_by_mechanism.values()]
    )
    samples = stratified_paired_bootstrap_sample_means(
        list(deltas_by_mechanism.values()),
        resamples=resamples,
        seed=seed,
    )
    return BucketBootstrapResult(
        point_estimate_delta=point_estimate,
        lower_confidence_bound=one_sided_lower_confidence_bound(samples, confidence_level=0.95),
        upper_confidence_bound=one_sided_upper_confidence_bound(samples, confidence_level=0.95),
        scenario_count=sum(len(deltas) for deltas in deltas_by_mechanism.values()),
        confidence_level=0.95,
        resamples=resamples,
        seed=seed,
    )


def abstention_artifact_for_run(run_artifact: Mapping[str, object]) -> Dict[str, object]:
    by_policy = decisions_by_policy_from_run_artifact(run_artifact)
    policy_rows = []
    for policy_name, decisions in sorted(by_policy.items()):
        mechanism_summaries = {
            mechanism: _summary_json(summarize_decisions(mechanism_decisions))
            for mechanism, mechanism_decisions in sorted(
                grouped_decisions(decisions, field_name="mechanism").items()
            )
        }
        policy_rows.append(
            {
                "policy_name": policy_name,
                "summary": _summary_json(summarize_decisions(decisions)),
                "summary_by_mechanism": mechanism_summaries,
            }
        )

    comparisons: Dict[str, object] = {}
    cq = by_policy.get("consolidation_queue_lite")
    mem0 = by_policy.get("mem0_lite")
    pairwise_comparisons: Dict[str, object] = {}
    if cq is not None:
        for comparator_name in ("mem0_lite", "reflection_eager_write_lite"):
            comparator = by_policy.get(comparator_name)
            if comparator is None:
                continue
            useful_rows = {}
            harmful_rows = {}
            mechanisms = sorted({decision.mechanism for decision in cq})
            for mechanism in mechanisms:
                mechanism_decisions = [decision for decision in cq if decision.mechanism == mechanism]
                if any(decision.abstention_ok for decision in mechanism_decisions):
                    useful_rows[mechanism] = mechanism_indicator_comparison(
                        cq,
                        comparator,
                        mechanism=mechanism,
                        metric_name="useful_abstention",
                    )
                if any(decision.commit_required for decision in mechanism_decisions):
                    harmful_rows[mechanism] = mechanism_indicator_comparison(
                        cq,
                        comparator,
                        mechanism=mechanism,
                        metric_name="harmful_abstention",
                    )
            pairwise_comparisons["consolidation_queue_vs_{}".format(comparator_name.replace("_lite", ""))] = {
                "reference_policy_name": "consolidation_queue_lite",
                "comparator_policy_name": comparator_name,
                "useful_abstention_rows": useful_rows,
                "harmful_abstention_rows": harmful_rows,
            }
    if cq is not None and mem0 is not None:
        useful_rows = {}
        for mechanism in PRIMARY_USEFUL_MECHANISMS:
            if any(decision.mechanism == mechanism for decision in cq):
                useful_rows[mechanism] = useful_mechanism_comparison(cq, mem0, mechanism=mechanism)
        harmful_mechanisms = [
            mechanism
            for mechanism in PRIMARY_HARMFUL_MECHANISMS
            if any(decision.mechanism == mechanism for decision in cq)
        ]
        harmful_row = None
        if harmful_mechanisms:
            harmful = stratified_bucket_comparison(
                cq,
                mem0,
                mechanisms=harmful_mechanisms,
                metric_name="harmful_abstention",
            )
            harmful_row = {
                "metric_name": "harmful_abstention_rate",
                "mechanisms": harmful_mechanisms,
                "point_estimate_delta": harmful.point_estimate_delta,
                "one_sided_95_lcb": harmful.lower_confidence_bound,
                "one_sided_95_ucb": harmful.upper_confidence_bound,
                "resamples": harmful.resamples,
                "seed": harmful.seed,
            }
        comparisons["consolidation_queue_vs_mem0_primary_abstention"] = {
            "reference_policy_name": "consolidation_queue_lite",
            "comparator_policy_name": "mem0_lite",
            "useful_mechanism_rows": useful_rows,
            "harmful_bucket_row": harmful_row,
        }

    return {
        "experiment": str(run_artifact.get("experiment", "")),
        "family": str(run_artifact.get("family", "")),
        "template_mix": str(run_artifact.get("template_mix", "")),
        "policy_set": str(run_artifact.get("policy_set", "")),
        "policies": policy_rows,
        "pairwise_abstention_comparisons": pairwise_comparisons,
        "primary_comparisons": comparisons,
    }
