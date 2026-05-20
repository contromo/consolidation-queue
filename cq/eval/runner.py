from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

from cq.eval.abstention import (
    PRIMARY_HARMFUL_MECHANISMS,
    PRIMARY_USEFUL_MECHANISMS,
    abstention_decision_from_record,
    stratified_bucket_comparison,
    useful_mechanism_comparison,
)
from cq.eval.bootstrap import paired_bootstrap_confidence_result
from cq.eval.end_to_end_eval import execute_scenario, failure_example_sort_key, summarize_runs
from cq.eval.preregistration_lock import (
    PREREGISTRATION_PATH,
    frozen_scenario_contracts,
    validate_frozen_eval_lock,
)
from cq.memory.consolidation_queue import (
    CQDatedContestation,
    CQNoContestationDemotion,
    CQNoPendingLookupUse,
    CQNoSourceIndependenceGate,
    CQNoWiderScopePendingOverride,
    ConsolidationQueueLite,
)
from cq.memory.cq_pending_multi_evidence import CQPendingMultiEvidence
from cq.memory.mem0_lite import Mem0Lite
from cq.memory.naive_eager_write import NaiveEagerWriteLite
from cq.memory.no_memory import NoMemoryLite
from cq.memory.reflection_eager_write_cardinality_capped import ReflectionEagerWriteCardinalityCapped
from cq.memory.reflection_eager_write import ReflectionEagerWriteLite
from cq.memory.scope_blind_transcript_rag import ScopeBlindTranscriptRAGLite
from cq.schemas.memory import jsonable
from cq.simulator.scenario_generator import (
    generate_adversarial_upstream_noise_scenarios,
    generate_evidence_conflict_spectrum_scenarios,
    generate_false_corroboration_scenarios,
    generate_forced_contradiction_scenarios,
    generate_memory_poisoning_scenarios,
    generate_preference_drift_scenarios,
    generate_scope_contamination_scenarios,
    generate_useful_pending_memory_scenarios,
)
from cq.simulator.render_events import render_scenario_transcript


FORCED_CONTRADICTION = "forced_contradiction"
SCOPE_CONTAMINATION = "scope_contamination"
PREFERENCE_DRIFT = "preference_drift"
USEFUL_PENDING_MEMORY = "useful_pending_memory"
FALSE_CORROBORATION = "false_corroboration"
MEMORY_POISONING = "memory_poisoning"
ADVERSARIAL_UPSTREAM_NOISE = "adversarial_upstream_noise"
EVIDENCE_CONFLICT_SPECTRUM = "evidence_conflict_spectrum"
MECHANISM_DIVERSE_HELDOUT = "mechanism_diverse_heldout"
POLICY_SET_DEFAULT = "default"
POLICY_SET_PHASE_2_5 = "phase2_5"
POLICY_SET_FOLLOWUP = "followup"
POLICY_SET_PHASE_2_5_FOLLOWUP = "phase2_5_followup"
POLICY_SET_PHASE_2_5_FOLLOWUP_WARNING = (
    "phase2_5_followup is a diagnostic follow-up policy set for the "
    "preregistered pending multi-evidence repair and internal regression "
    "controls; do not treat it as the original phase2_5 headline comparison."
)
POLICY_SET_CHOICES = (
    POLICY_SET_DEFAULT,
    POLICY_SET_PHASE_2_5,
    POLICY_SET_FOLLOWUP,
    POLICY_SET_PHASE_2_5_FOLLOWUP,
)
MODE_ORACLE = "oracle"
MODE_EXTRACTED = "extracted"
MODE_CHOICES = (MODE_ORACLE, MODE_EXTRACTED)
CQ_ABLATION_POLICIES = (
    CQNoContestationDemotion,
    CQNoWiderScopePendingOverride,
    CQNoPendingLookupUse,
    CQNoSourceIndependenceGate,
)
TEMPLATE_MIXES_BY_FAMILY = {
    FORCED_CONTRADICTION: ("mixed", "clean", "dirty", "heldout"),
    SCOPE_CONTAMINATION: ("mixed", "clean", "dirty", "heldout"),
    PREFERENCE_DRIFT: ("mixed", "clean", "dirty", "heldout"),
    USEFUL_PENDING_MEMORY: ("mixed", "clean", "dirty", "heldout"),
    FALSE_CORROBORATION: ("mixed", "clean", "dirty", "heldout"),
    MEMORY_POISONING: ("mixed", "clean", "dirty", "heldout"),
    ADVERSARIAL_UPSTREAM_NOISE: ("mixed", "dirty", "heldout"),
    EVIDENCE_CONFLICT_SPECTRUM: ("mixed", "heldout"),
    MECHANISM_DIVERSE_HELDOUT: ("frozen",),
}
COMPONENT_EVAL_FAMILIES = (
    FORCED_CONTRADICTION,
    SCOPE_CONTAMINATION,
    PREFERENCE_DRIFT,
    USEFUL_PENDING_MEMORY,
    FALSE_CORROBORATION,
    MEMORY_POISONING,
    MECHANISM_DIVERSE_HELDOUT,
)
SUMMARY_METRIC_FORMAT = (
    "false_assertion={false:.2f} recovery={recovery:.2f} correctness={correctness:.2f} "
    "leakage={leakage:.2f} premature_promotion={premature:.2f} "
    "poison_promotion={poison:.2f} clean_displacement={clean_displacement:.2f} "
    "retraction_demotion={retraction_demotion:.2f} stale_promotion={stale_promotion:.2f} "
    "narrow_override={narrow_override:.2f} pending_competition={pending_competition:.2f}"
    " useful_abstention={useful_abstention:.2f} harmful_abstention={harmful_abstention:.2f}"
)
OVERALL_SUMMARY_FORMAT = (
    "{policy_name}: useful_recall={useful:.2f} pending_use={pending:.2f} "
    "early_durable_commit={durable:.2f} "
    + SUMMARY_METRIC_FORMAT
    + " avg_time_to_demotion={demotion:.2f}"
)
SCOPED_SUMMARY_FORMAT = "  {scope_name}={scope_value}: " + SUMMARY_METRIC_FORMAT + " count={count}"
SUMMARY_CSV_FIELDNAMES = [
    "policy_name",
    "summary_scope",
    "template_id",
    "template_kind",
    "template_split",
    "scenario_count",
    "answer_correctness",
    "false_assertion_rate",
    "leakage_rate",
    "premature_promotion_rate",
    "poison_promotion_rate",
    "clean_durable_displacement_rate",
    "retraction_demotion_rate",
    "stale_evidence_promotion_rate",
    "narrow_scope_override_success_rate",
    "pending_competition_resolution_rate",
    "useful_abstention_rate",
    "useful_abstention_count",
    "useful_abstention_applicable_count",
    "harmful_abstention_rate",
    "harmful_abstention_count",
    "harmful_abstention_applicable_count",
    "useful_recall",
    "used_pending",
    "durable_commit",
    "useful_recall_before_contradiction",
    "used_pending_before_contradiction",
    "durable_commit_before_contradiction",
    "false_assertion_after_contradiction",
    "contradiction_recovery_rate",
    "answer_correctness_after_contradiction",
    "average_time_to_demotion",
    "comparison_name",
    "comparison_metric_name",
    "comparison_reference_policy_name",
    "comparison_comparator_policy_name",
    "comparison_point_estimate_delta",
    "comparison_one_sided_95_lcb",
    "comparison_one_sided_95_ucb",
]


def _summary_metric_values(summary: dict) -> Dict[str, float]:
    return {
        "false": summary["false_assertion_rate"],
        "recovery": summary["contradiction_recovery_rate"],
        "correctness": summary["answer_correctness"],
        "leakage": summary["leakage_rate"],
        "premature": summary["premature_promotion_rate"],
        "poison": summary["poison_promotion_rate"],
        "clean_displacement": summary["clean_durable_displacement_rate"],
        "retraction_demotion": summary.get("retraction_demotion_rate", 0.0),
        "stale_promotion": summary.get("stale_evidence_promotion_rate", 0.0),
        "narrow_override": summary.get("narrow_scope_override_success_rate", 0.0),
        "pending_competition": summary.get("pending_competition_resolution_rate", 0.0),
        "useful_abstention": summary.get("useful_abstention_rate", 0.0),
        "harmful_abstention": summary.get("harmful_abstention_rate", 0.0),
    }


def _format_overall_summary(summary: dict) -> str:
    values = _summary_metric_values(summary)
    values.update(
        {
            "policy_name": summary["policy_name"],
            "useful": summary["useful_recall"],
            "pending": summary["used_pending"],
            "durable": summary["durable_commit"],
            "demotion": summary["average_time_to_demotion"],
        }
    )
    return OVERALL_SUMMARY_FORMAT.format(**values)


def _format_scoped_summary(scope_name: str, scope_value: str, summary: dict) -> str:
    values = _summary_metric_values(summary)
    values.update(
        {
            "scope_name": scope_name,
            "scope_value": scope_value,
            "count": summary["scenario_count"],
        }
    )
    return SCOPED_SUMMARY_FORMAT.format(**values)


def _blank_summary_csv_row() -> Dict[str, object]:
    return {field_name: "" for field_name in SUMMARY_CSV_FIELDNAMES}


def _comparison_csv_row(
    *,
    summary_scope: str,
    template_id: str,
    comparison_name: str,
    metric_name: str,
    reference_policy_name: str,
    comparator_policy_name: str,
    point_estimate_delta: float,
    one_sided_95_lcb: float,
    scenario_count: object = "",
    one_sided_95_ucb: object = "",
) -> Dict[str, object]:
    row = _blank_summary_csv_row()
    row.update(
        {
            "summary_scope": summary_scope,
            "template_id": template_id,
            "scenario_count": scenario_count,
            "comparison_name": comparison_name,
            "comparison_metric_name": metric_name,
            "comparison_reference_policy_name": reference_policy_name,
            "comparison_comparator_policy_name": comparator_policy_name,
            "comparison_point_estimate_delta": point_estimate_delta,
            "comparison_one_sided_95_lcb": one_sided_95_lcb,
            "comparison_one_sided_95_ucb": one_sided_95_ucb,
        }
    )
    return row


def _summaries_by_field(run_records: List[dict], field_name: str) -> Dict[str, dict]:
    grouped = {}
    for record in run_records:
        field_value = record["scenario"].get(field_name, "")
        grouped.setdefault(field_value, []).append(record)
    return {
        field_value: jsonable(summarize_runs(group_records))
        for field_value, group_records in sorted(grouped.items())
        if field_value
    }


def _scenario_metric_by_field(
    run_records: List[dict],
    *,
    field_name: str,
    metric_name: str,
) -> Dict[str, List[float]]:
    grouped: Dict[str, List[float]] = {}
    for record in run_records:
        field_value = record["scenario"].get(field_name, "")
        if not field_value:
            continue
        grouped.setdefault(field_value, []).append(float(record["metrics"][metric_name]))
    return grouped


def _pairwise_metric_comparisons(
    reference_run_records: List[dict],
    comparator_run_records: List[dict],
    *,
    metric_name: str = "answer_correctness",
    field_name: str = "template_id",
) -> Dict[str, dict]:
    reference = _scenario_metric_by_field(
        reference_run_records,
        field_name=field_name,
        metric_name=metric_name,
    )
    comparator = _scenario_metric_by_field(
        comparator_run_records,
        field_name=field_name,
        metric_name=metric_name,
    )
    comparisons: Dict[str, dict] = {}
    for field_value in sorted(reference):
        reference_values = reference[field_value]
        comparator_values = comparator.get(field_value)
        if comparator_values is None or len(reference_values) != len(comparator_values):
            continue
        deltas = [left - right for left, right in zip(reference_values, comparator_values)]
        bootstrap = paired_bootstrap_confidence_result(
            deltas,
            resamples=10_000,
            confidence_level=0.95,
            seed=0,
        )
        comparisons[field_value] = {
            "metric_name": metric_name,
            "point_estimate_delta": bootstrap.point_estimate,
            "one_sided_95_lcb": bootstrap.lower_confidence_bound,
            "scenario_count": len(deltas),
            "reference_policy_name": reference_run_records[0]["policy_name"],
            "comparator_policy_name": comparator_run_records[0]["policy_name"],
        }
    return comparisons


def generate_scenarios(
    family: str,
    scenario_count: int,
    template_mix: str,
    preregistration_path: Path = PREREGISTRATION_PATH,
):
    _validate_template_mix(family, template_mix)
    if family == MECHANISM_DIVERSE_HELDOUT:
        validate_frozen_eval_lock(preregistration_path)
        return frozen_scenario_contracts()
    if family == FORCED_CONTRADICTION:
        return generate_forced_contradiction_scenarios(scenario_count, template_mix=template_mix)
    if family == SCOPE_CONTAMINATION:
        return generate_scope_contamination_scenarios(scenario_count, template_mix=template_mix)
    if family == PREFERENCE_DRIFT:
        return generate_preference_drift_scenarios(scenario_count, template_mix=template_mix)
    if family == USEFUL_PENDING_MEMORY:
        return generate_useful_pending_memory_scenarios(scenario_count, template_mix=template_mix)
    if family == FALSE_CORROBORATION:
        return generate_false_corroboration_scenarios(scenario_count, template_mix=template_mix)
    if family == MEMORY_POISONING:
        return generate_memory_poisoning_scenarios(scenario_count, template_mix=template_mix)
    if family == ADVERSARIAL_UPSTREAM_NOISE:
        return generate_adversarial_upstream_noise_scenarios(scenario_count, template_mix=template_mix)
    if family == EVIDENCE_CONFLICT_SPECTRUM:
        return generate_evidence_conflict_spectrum_scenarios(scenario_count, template_mix=template_mix)
    raise ValueError("Unsupported family: {}".format(family))


def _validate_template_mix(family: str, template_mix: str) -> None:
    allowed = TEMPLATE_MIXES_BY_FAMILY.get(family)
    if allowed is None:
        raise ValueError("Unsupported family: {}".format(family))
    if template_mix not in allowed:
        raise ValueError(
            "Template mix '{}' is not supported for family '{}'. Allowed: {}".format(
                template_mix,
                family,
                ", ".join(allowed),
            )
        )


def _policies_for_family(family: str, policy_set: str = POLICY_SET_DEFAULT):
    if policy_set not in POLICY_SET_CHOICES:
        raise ValueError(
            "Policy set '{}' is not supported. Allowed: {}".format(
                policy_set,
                ", ".join(POLICY_SET_CHOICES),
            )
        )
    if policy_set == POLICY_SET_FOLLOWUP and family != ADVERSARIAL_UPSTREAM_NOISE:
        raise ValueError(
            "Policy set '{}' is only valid for family '{}'; received family '{}'.".format(
                POLICY_SET_FOLLOWUP,
                ADVERSARIAL_UPSTREAM_NOISE,
                family,
            )
        )
    policies = [
        ReflectionEagerWriteLite,
        ConsolidationQueueLite,
    ]
    if policy_set in (POLICY_SET_PHASE_2_5, POLICY_SET_FOLLOWUP, POLICY_SET_PHASE_2_5_FOLLOWUP):
        policies.extend(CQ_ABLATION_POLICIES)
    policies.extend(
        [
            NaiveEagerWriteLite,
            NoMemoryLite,
        ]
    )
    if family in {
        SCOPE_CONTAMINATION,
        PREFERENCE_DRIFT,
        USEFUL_PENDING_MEMORY,
        FALSE_CORROBORATION,
        MEMORY_POISONING,
        ADVERSARIAL_UPSTREAM_NOISE,
        EVIDENCE_CONFLICT_SPECTRUM,
        MECHANISM_DIVERSE_HELDOUT,
    }:
        policies.append(ScopeBlindTranscriptRAGLite)
    if policy_set in (POLICY_SET_PHASE_2_5, POLICY_SET_FOLLOWUP, POLICY_SET_PHASE_2_5_FOLLOWUP):
        policies.append(Mem0Lite)
    if policy_set == POLICY_SET_FOLLOWUP:
        policies.append(CQDatedContestation)
    if policy_set == POLICY_SET_PHASE_2_5_FOLLOWUP:
        policies.extend(
            [
                CQPendingMultiEvidence,
                ReflectionEagerWriteCardinalityCapped,
            ]
        )
    return policies


def build_run_artifact(
    scenario_count: int,
    template_mix: str = "mixed",
    family: str = FORCED_CONTRADICTION,
    policy_set: str = POLICY_SET_DEFAULT,
    preregistration_path: Path = PREREGISTRATION_PATH,
) -> dict:
    scenarios = generate_scenarios(
        family,
        scenario_count,
        template_mix,
        preregistration_path=preregistration_path,
    )
    policies = _policies_for_family(family, policy_set=policy_set)
    policy_runs = []
    run_records_by_policy = {}
    for policy_cls in policies:
        run_records = [execute_scenario(policy_cls, scenario) for scenario in scenarios]
        run_records_by_policy[policy_cls.policy_name] = run_records
        summary = summarize_runs(run_records)
        failure_examples = sorted(
            [
                example
                for record in run_records
                for example in record.get("failure_examples", [])
            ],
            key=failure_example_sort_key,
        )
        policy_runs.append(
            {
                "policy_name": policy_cls.policy_name,
                "summary": jsonable(summary),
                "summary_by_template_kind": _summaries_by_field(run_records, "template_kind"),
                "summary_by_template_split": _summaries_by_field(run_records, "template_split"),
                "summary_by_template_id": _summaries_by_field(run_records, "template_id"),
                "failure_examples": failure_examples,
                "scenarios": [
                    {
                        "scenario_id": record["scenario_id"],
                        "transcript": render_scenario_transcript(scenarios[index]),
                        "scenario": record["scenario"],
                        "question_traces": record["question_traces"],
                        "store_snapshot": record["store_snapshot"],
                        "metrics": record["metrics"],
                        "failure_examples": record["failure_examples"],
                    }
                    for index, record in enumerate(run_records)
                ],
            }
        )
    primary_abstention_comparisons, primary_abstention_warnings = _build_primary_abstention_comparisons(
        run_records_by_policy,
        family=family,
        policy_set=policy_set,
    )
    baseline_notes: Dict[str, str] = {}
    ablation_notes: Dict[str, str] = {}
    if policy_set in (POLICY_SET_PHASE_2_5, POLICY_SET_FOLLOWUP, POLICY_SET_PHASE_2_5_FOLLOWUP):
        baseline_notes[Mem0Lite.policy_name] = Mem0Lite.partial_baseline_caveat
        for policy in CQ_ABLATION_POLICIES:
            ablation_notes[policy.policy_name] = policy.ablation_note
    if policy_set == POLICY_SET_FOLLOWUP:
        ablation_notes[CQDatedContestation.policy_name] = CQDatedContestation.ablation_note
    if policy_set == POLICY_SET_PHASE_2_5_FOLLOWUP:
        ablation_notes[CQPendingMultiEvidence.policy_name] = CQPendingMultiEvidence.ablation_note
        ablation_notes[ReflectionEagerWriteCardinalityCapped.policy_name] = (
            ReflectionEagerWriteCardinalityCapped.ablation_note
        )
    return {
        "experiment": "{}_oracle".format(family),
        "family": family,
        "scenario_count": len(scenarios),
        "template_mix": template_mix,
        "policy_set": policy_set,
        "policy_set_warning": (
            POLICY_SET_PHASE_2_5_FOLLOWUP_WARNING
            if policy_set == POLICY_SET_PHASE_2_5_FOLLOWUP
            else ""
        ),
        "baseline_notes": baseline_notes,
        "ablation_notes": ablation_notes,
        "pairwise_template_id_comparisons": _build_pairwise_comparisons(
            run_records_by_policy,
            policy_set=policy_set,
        ),
        "primary_abstention_comparisons": primary_abstention_comparisons,
        "primary_abstention_comparison_warnings": primary_abstention_warnings,
        "policies": policy_runs,
    }


def build_extracted_candidate_run_artifact(
    scenario_count: int,
    template_mix: str,
    family: str,
    policy_set: str,
    extracted_predictions_dir: Path,
    schema_profile: str,
    frozen_preregistration_path: Path = PREREGISTRATION_PATH,
    noisy_preregistration_path: Path | None = None,
    *,
    verify_pin: bool = True,
) -> dict:
    if family not in COMPONENT_EVAL_FAMILIES:
        raise ValueError(
            "Extracted mode only supports component-eval families. Allowed: {}".format(
                ", ".join(sorted(COMPONENT_EVAL_FAMILIES)),
            )
        )
    from cq.eval.extracted_candidate_runner import (
        build_extracted_run_artifact,
        load_extracted_predictions,
        policies_use_memory_store,
        prediction_cell_paths,
        PREREGISTRATION_PATH as NOISY_PREREGISTRATION_PATH,
        validate_adapter_pin,
        validate_noisy_preregistration_lock,
    )

    noisy_preregistration_path = noisy_preregistration_path or NOISY_PREREGISTRATION_PATH
    lock_sha = validate_noisy_preregistration_lock(noisy_preregistration_path)
    adapter_pin = (
        validate_adapter_pin(preregistration_path=noisy_preregistration_path)
        if verify_pin
        else {}
    )
    scenarios = generate_scenarios(
        family,
        scenario_count,
        template_mix,
        preregistration_path=frozen_preregistration_path,
    )
    policies = _policies_for_family(family, policy_set=policy_set)
    if not policies_use_memory_store(policies):
        raise ValueError("All extracted-mode policies must use the shared MemoryStore class.")
    paths = prediction_cell_paths(
        predictions_dir=extracted_predictions_dir,
        family=family,
        schema_profile=schema_profile,
    )
    predictions_by_scenario, scenario_errors = load_extracted_predictions(paths.predictions)
    return build_extracted_run_artifact(
        scenarios=scenarios,
        policy_classes=policies,
        predictions_by_scenario=predictions_by_scenario,
        scenario_errors=scenario_errors,
        family=family,
        requested_scenario_count=scenario_count,
        template_mix=template_mix,
        policy_set=policy_set,
        schema_profile=schema_profile,
        predictions_path=paths.predictions,
        adapter_sha256=str(adapter_pin.get("candidate_adapter_sha256") or ""),
        preregistration_lock_sha256=lock_sha,
    )


def _build_pairwise_comparisons(
    run_records_by_policy: Dict[str, List[dict]],
    *,
    policy_set: str,
) -> Dict[str, Dict[str, dict]]:
    comparisons: Dict[str, Dict[str, dict]] = {}
    reflection = run_records_by_policy.get(ReflectionEagerWriteLite.policy_name)
    cq = run_records_by_policy.get(ConsolidationQueueLite.policy_name)
    if reflection is not None and cq is not None:
        comparisons["consolidation_queue_vs_reflection_by_template_id"] = _pairwise_metric_comparisons(
            cq,
            reflection,
        )
    if policy_set in (POLICY_SET_PHASE_2_5, POLICY_SET_FOLLOWUP, POLICY_SET_PHASE_2_5_FOLLOWUP):
        mem0 = run_records_by_policy.get(Mem0Lite.policy_name)
        if reflection is not None and mem0 is not None:
            comparisons["mem0_vs_reflection_by_template_id"] = _pairwise_metric_comparisons(
                mem0,
                reflection,
            )
    return comparisons


def _decisions_for_policy(policy_name: str, run_records: List[dict], family: str):
    return [
        abstention_decision_from_record(policy_name, record, family)
        for record in run_records
    ]


def _build_primary_abstention_comparisons(
    run_records_by_policy: Dict[str, List[dict]],
    *,
    family: str,
    policy_set: str,
) -> tuple[Dict[str, dict], List[str]]:
    if family != EVIDENCE_CONFLICT_SPECTRUM:
        return {}, []
    if policy_set != POLICY_SET_PHASE_2_5:
        return {}, [
            "Primary abstention comparisons require policy_set='{}' so Mem0Lite is present.".format(
                POLICY_SET_PHASE_2_5,
            )
        ]
    cq_records = run_records_by_policy.get(ConsolidationQueueLite.policy_name)
    mem0_records = run_records_by_policy.get(Mem0Lite.policy_name)
    if cq_records is None or mem0_records is None:
        return {}, [
            "Primary abstention comparisons require both {} and {} records.".format(
                ConsolidationQueueLite.policy_name,
                Mem0Lite.policy_name,
            )
        ]
    cq = _decisions_for_policy(ConsolidationQueueLite.policy_name, cq_records, family)
    mem0 = _decisions_for_policy(Mem0Lite.policy_name, mem0_records, family)
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
            "mechanisms": list(harmful_mechanisms),
            "point_estimate_delta": harmful.point_estimate_delta,
            "one_sided_95_lcb": harmful.lower_confidence_bound,
            "one_sided_95_ucb": harmful.upper_confidence_bound,
            "resamples": harmful.resamples,
            "seed": harmful.seed,
        }
    return (
        {
            "consolidation_queue_vs_mem0_primary_abstention": {
                "reference_policy_name": ConsolidationQueueLite.policy_name,
                "comparator_policy_name": Mem0Lite.policy_name,
                "useful_mechanism_rows": useful_rows,
                "harmful_bucket_row": harmful_row,
            }
        },
        [],
    )


def write_outputs(run_artifact: dict, output_json: Path, output_csv: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(run_artifact, indent=2), encoding="utf-8")

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=SUMMARY_CSV_FIELDNAMES,
        )
        writer.writeheader()
        for policy in run_artifact["policies"]:
            overall_row = dict(policy["summary"])
            overall_row.update(
                {
                    "summary_scope": "overall",
                    "template_id": "",
                    "template_kind": "",
                    "template_split": "",
                }
            )
            writer.writerow(overall_row)
            for template_kind, summary in policy.get("summary_by_template_kind", {}).items():
                row = dict(summary)
                row.update(
                    {
                        "summary_scope": "template_kind",
                        "template_id": "",
                        "template_kind": template_kind,
                        "template_split": "",
                    }
                )
                writer.writerow(row)
            for template_split, summary in policy.get("summary_by_template_split", {}).items():
                row = dict(summary)
                row.update(
                    {
                        "summary_scope": "template_split",
                        "template_id": "",
                        "template_kind": "",
                        "template_split": template_split,
                    }
                )
                writer.writerow(row)
            for template_id, summary in policy.get("summary_by_template_id", {}).items():
                row = dict(summary)
                row.update(
                    {
                        "summary_scope": "template_id",
                        "template_id": template_id,
                        "template_kind": "",
                        "template_split": "",
                    }
                )
                writer.writerow(row)
        for comparison_name, comparison_rows in run_artifact.get(
            "pairwise_template_id_comparisons",
            {},
        ).items():
            for template_id, comparison in comparison_rows.items():
                writer.writerow(
                    _comparison_csv_row(
                        summary_scope="template_id_comparison",
                        template_id=template_id,
                        scenario_count=comparison["scenario_count"],
                        comparison_name=comparison_name,
                        metric_name=comparison["metric_name"],
                        reference_policy_name=comparison["reference_policy_name"],
                        comparator_policy_name=comparison["comparator_policy_name"],
                        point_estimate_delta=comparison["point_estimate_delta"],
                        one_sided_95_lcb=comparison["one_sided_95_lcb"],
                        one_sided_95_ucb=comparison.get("one_sided_95_ucb", ""),
                    )
                )
        for comparison_name, comparison in run_artifact.get("primary_abstention_comparisons", {}).items():
            for mechanism, useful in comparison.get("useful_mechanism_rows", {}).items():
                writer.writerow(
                    _comparison_csv_row(
                        summary_scope="abstention_comparison",
                        template_id=mechanism,
                        scenario_count=useful["scenario_count"],
                        comparison_name=comparison_name,
                        metric_name=useful["metric_name"],
                        reference_policy_name=comparison["reference_policy_name"],
                        comparator_policy_name=comparison["comparator_policy_name"],
                        point_estimate_delta=useful["point_estimate_delta"],
                        one_sided_95_lcb=useful["one_sided_95_lcb"],
                        one_sided_95_ucb=useful.get("one_sided_95_ucb", ""),
                    )
                )
            harmful = comparison.get("harmful_bucket_row")
            if harmful:
                writer.writerow(
                    _comparison_csv_row(
                        summary_scope="abstention_comparison",
                        template_id="+".join(harmful["mechanisms"]),
                        comparison_name=comparison_name,
                        metric_name=harmful["metric_name"],
                        reference_policy_name=comparison["reference_policy_name"],
                        comparator_policy_name=comparison["comparator_policy_name"],
                        point_estimate_delta=harmful["point_estimate_delta"],
                        one_sided_95_lcb=harmful["one_sided_95_lcb"],
                        one_sided_95_ucb=harmful["one_sided_95_ucb"],
                    )
                )


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Run memory-governance experiments.")
    parser.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default=MODE_ORACLE,
        help="Run oracle candidates or extracted-candidate predictions.",
    )
    parser.add_argument(
        "--family",
        choices=[
            FORCED_CONTRADICTION,
            SCOPE_CONTAMINATION,
            PREFERENCE_DRIFT,
            USEFUL_PENDING_MEMORY,
            FALSE_CORROBORATION,
            MEMORY_POISONING,
            ADVERSARIAL_UPSTREAM_NOISE,
            EVIDENCE_CONFLICT_SPECTRUM,
            MECHANISM_DIVERSE_HELDOUT,
        ],
        default=FORCED_CONTRADICTION,
        help="Oracle benchmark family to run.",
    )
    parser.add_argument("--scenarios", type=int, default=25, help="Number of oracle scenarios to generate.")
    parser.add_argument(
        "--template-mix",
        choices=["mixed", "clean", "dirty", "heldout", "frozen"],
        default="mixed",
        help="Scenario template mix for the selected family.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path to the run artifact JSON.",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Path to the summary metrics CSV.",
    )
    parser.add_argument(
        "--policy-set",
        choices=POLICY_SET_CHOICES,
        default=POLICY_SET_DEFAULT,
        help=(
            "Policy set to run. Use phase2_5 to include Mem0Lite. Use followup to add "
            "CQDatedContestation on adversarial_upstream_noise only. Use phase2_5_followup "
            "for the pending multi-evidence LongMemEval follow-up variants."
        ),
    )
    parser.add_argument(
        "--extracted-predictions-dir",
        default="data/results",
        help="Directory containing component gate prediction artifacts for --mode extracted.",
    )
    parser.add_argument(
        "--schema-profile",
        choices=["default", "scenario_conditioned"],
        default="default",
        help="Extractor schema profile to use in --mode extracted.",
    )
    args = parser.parse_args(argv)
    try:
        _validate_template_mix(args.family, args.template_mix)
    except ValueError as error:
        parser.error(str(error))

    if args.mode == MODE_EXTRACTED and args.template_mix == "mixed":
        parser.error("--mode extracted requires an explicit heldout or frozen template mix")
    if args.mode == MODE_EXTRACTED:
        output_json = args.output_json or "data/runs/noisy_policy_comparison_{}_{}.json".format(
            args.family,
            args.schema_profile,
        )
        output_csv = args.output_csv or "data/results/noisy_policy_comparison_{}_{}_metrics.csv".format(
            args.family,
            args.schema_profile,
        )
    else:
        output_json = args.output_json or "data/runs/{}_oracle.json".format(args.family)
        output_csv = args.output_csv or "data/results/{}_oracle_metrics.csv".format(args.family)
    try:
        if args.mode == MODE_EXTRACTED:
            run_artifact = build_extracted_candidate_run_artifact(
                args.scenarios,
                template_mix=args.template_mix,
                family=args.family,
                policy_set=args.policy_set,
                extracted_predictions_dir=Path(args.extracted_predictions_dir),
                schema_profile=args.schema_profile,
            )
        else:
            run_artifact = build_run_artifact(
                args.scenarios,
                template_mix=args.template_mix,
                family=args.family,
                policy_set=args.policy_set,
            )
    except ValueError as error:
        parser.error(str(error))
    write_outputs(run_artifact, Path(output_json), Path(output_csv))

    for policy in run_artifact["policies"]:
        summary = policy["summary"]
        print(_format_overall_summary(summary))
        for template_kind, kind_summary in policy.get("summary_by_template_kind", {}).items():
            print(_format_scoped_summary("kind", template_kind, kind_summary))
        for template_split, split_summary in policy.get("summary_by_template_split", {}).items():
            print(_format_scoped_summary("split", template_split, split_summary))
        for template_id, template_summary in policy.get("summary_by_template_id", {}).items():
            print(_format_scoped_summary("template", template_id, template_summary))
    print("Template mix: {}".format(args.template_mix))
    print("Policy set: {}".format(args.policy_set))
    for policy_name, note in run_artifact.get("baseline_notes", {}).items():
        print("Baseline note ({}): {}".format(policy_name, note))
    for warning in run_artifact.get("primary_abstention_comparison_warnings", []):
        print("Warning: {}".format(warning))
    print("Wrote {}".format(output_json))
    print("Wrote {}".format(output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
