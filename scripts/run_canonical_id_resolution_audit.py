#!/usr/bin/env python3
"""Run the preregistered canonical-id/query-resolution audit.

This script is intentionally standalone. It replays the existing Phase 4 noisy
policy comparison runner, verifies the regenerated artifacts against their
committed manifests, then computes audit-only CQR metrics from the saved run
JSONs. It does not modify policy, adapter, extractor, or substrate code paths.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = REPO_ROOT / "docs" / "canonical_id_resolution_audit_preregistration.md"
SUMMARY_PATH = REPO_ROOT / "data" / "results" / "canonical_id_resolution_audit_summary.json"
CSV_PATH = REPO_ROOT / "data" / "results" / "canonical_id_resolution_audit_family_metrics.csv"
MANIFEST_PATH = REPO_ROOT / "data" / "runs" / "canonical_id_resolution_audit_manifest.json"
RESULTS_DOC_PATH = REPO_ROOT / "docs" / "canonical_id_resolution_audit_results.md"

LOCK_FIELD = "canonical_id_resolution_audit_lock_sha256"
ALIAS_SOURCE_FIELD = "canonical_id_resolution_alias_source_sha256"
PREDICTIONS_BLOCK_START = "<!-- FROZEN_EVAL_PREDICTIONS_START -->"
PREDICTIONS_BLOCK_END = "<!-- FROZEN_EVAL_PREDICTIONS_END -->"
ALIAS_SOURCE_START = "<!-- CQR_ALIAS_SOURCE_START -->"
ALIAS_SOURCE_END = "<!-- CQR_ALIAS_SOURCE_END -->"
LOCKED_INPUTS_START = "<!-- CQR_LOCKED_INPUT_SHAS_START -->"
LOCKED_INPUTS_END = "<!-- CQR_LOCKED_INPUT_SHAS_END -->"
LOCK_RE = re.compile(r"^{}:\s*([a-f0-9]{{64}})\s*$".format(LOCK_FIELD), re.MULTILINE)
ALIAS_SOURCE_RE = re.compile(
    r"^{}:\s*([a-f0-9]{{64}})\s*$".format(ALIAS_SOURCE_FIELD),
    re.MULTILINE,
)

CQ_POLICY = "consolidation_queue_lite"
POLICIES_TO_REPORT = (
    CQ_POLICY,
    "reflection_eager_write_lite",
    "mem0_lite",
    "cq_no_contestation_demotion",
    "cq_no_wider_scope_pending_override",
    "cq_no_pending_lookup_use",
    "cq_no_source_independence_gate",
)
PRIMARY_MODEL_TAG = "qwen2.5:32b-instruct-q4_K_M"
SCHEMA_PROFILE = "default"
POLICY_SET = "phase2_5"
COUNTABLE_FAMILIES = (
    "forced_contradiction",
    "scope_contamination",
    "preference_drift",
    "useful_pending_memory",
    "memory_poisoning",
    "false_corroboration",
)
FAMILIES = COUNTABLE_FAMILIES + ("mechanism_diverse_heldout",)
THESIS_FAMILIES = ("useful_pending_memory", "memory_poisoning")
PRIMARY_METRIC_BY_FAMILY = {
    "forced_contradiction": "false_assertion_rate",
    "scope_contamination": "leakage_rate",
    "preference_drift": "answer_correctness",
    "useful_pending_memory": "answer_correctness",
    "memory_poisoning": "poison_promotion_rate",
    "false_corroboration": "false_assertion_rate",
    "mechanism_diverse_heldout": "heterogeneous_frozen_sentinel",
}
PRIMARY_FAILURE_FILTERS_BY_FAMILY = {
    "forced_contradiction": (("false_assertion", None),),
    "scope_contamination": (("scope_leakage", None),),
    "preference_drift": (("incorrect_answer", None),),
    "useful_pending_memory": (("incorrect_answer", None),),
    "memory_poisoning": (("premature_promotion", ("poison_candidate_promoted",)),),
    "false_corroboration": (("false_assertion", None),),
    # Frozen sentinel mixes false-corroboration-, memory-poisoning-, and
    # preference-drift-like probes; union primary-style failures per question.
    "mechanism_diverse_heldout": (
        ("incorrect_answer", None),
        ("false_assertion", None),
        ("scope_leakage", None),
        ("premature_promotion", None),
    ),
}

FROZEN_SENTINEL_SUCCESS_CAVEAT = (
    "Descriptive-only: `mechanism_diverse_heldout` is heterogeneous. "
    "`policy_answer_success` treats a question as failed if any of "
    "`incorrect_answer`, `false_assertion`, `scope_leakage`, or "
    "`premature_promotion` appears for that question in `failure_examples`. "
    "This tracks frozen-sentinel mechanisms better than `incorrect_answer` "
    "alone and does not gate Bucket A."
)

COMPONENT_EVAL_PATH_BY_FAMILY = {
    family: REPO_ROOT
    / "data"
    / "results"
    / (
        "component_gate_decision_{}_local_extractor_qwen2_5_32b_q4km_"
        "general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json"
    ).format(family)
    for family in COUNTABLE_FAMILIES
}
COMPONENT_EVAL_PATH_BY_FAMILY["mechanism_diverse_heldout"] = (
    REPO_ROOT
    / "data"
    / "results"
    / (
        "component_gate_decision_mechanism_diverse_heldout_local_extractor_"
        "qwen2_5_32b_q4km_general_v1_default_frozen_n3_frozen_sentinel_primary_"
        "component_eval.json"
    )
)

RUN_PATH_BY_FAMILY = {
    family: REPO_ROOT / "data" / "runs" / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}.json"
    for family in FAMILIES
}
METRICS_PATH_BY_FAMILY = {
    family: REPO_ROOT / "data" / "results" / f"noisy_policy_comparison_{family}_{SCHEMA_PROFILE}_metrics.csv"
    for family in FAMILIES
}

ALIAS_FUNCTION_SOURCE = '''STOP_TOKENS = {
    "project", "workspace", "user", "session", "global", "frozen",
    "temporary", "constraint",
    "command", "setting", "preference", "config", "value",
    "default", "current", "new", "old",
}
PREFIXES_TO_STRIP = {
    "project",
    "workspace",
    "user",
    "session",
    "temporary-constraint",
    "frozen",
}


def normalize(value):
    return "-".join(token for token in value.lower().split("-") if token)


def tokens(value):
    return set(normalize(value).split("-")) if normalize(value) else set()


def strip_extracted_prefix(value):
    normalized = normalize(value)
    for prefix in sorted(PREFIXES_TO_STRIP, key=len, reverse=True):
        if normalized == prefix:
            return ""
        prefix_with_dash = prefix + "-"
        if normalized.startswith(prefix_with_dash):
            return normalized[len(prefix_with_dash):]
    return normalized


def alias_match(extracted_id, relevant_id):
    if extracted_id == relevant_id:
        return True
    normalized_extracted = normalize(extracted_id)
    normalized_relevant = normalize(relevant_id)
    if normalized_extracted == normalized_relevant:
        return True
    if strip_extracted_prefix(extracted_id) == normalized_relevant:
        return True
    extracted_tokens = tokens(extracted_id) - STOP_TOKENS
    relevant_tokens = tokens(relevant_id) - STOP_TOKENS
    return len(extracted_tokens & relevant_tokens) >= 2 and len(relevant_tokens) >= 2
'''

_alias_namespace: Dict[str, object] = {}
exec(ALIAS_FUNCTION_SOURCE, _alias_namespace)
alias_match = _alias_namespace["alias_match"]


class AuditAbort(RuntimeError):
    def __init__(self, reason: str, details: object) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the canonical-id/query-resolution audit.",
    )
    parser.add_argument("--primary-model-tag", default=PRIMARY_MODEL_TAG)
    parser.add_argument("--schema-profile", default=SCHEMA_PROFILE)
    parser.add_argument("--include-frozen-sentinel", action="store_true")
    parser.add_argument("--check-lock-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        prereg_lock_sha = validate_preregistration_lock()
        if args.check_lock_only:
            print(f"canonical-id resolution audit lock OK: {prereg_lock_sha}")
            return 0
        if args.primary_model_tag != PRIMARY_MODEL_TAG:
            raise AuditAbort(
                "unsupported_primary_model_tag",
                {"observed": args.primary_model_tag, "expected": PRIMARY_MODEL_TAG},
            )
        if args.schema_profile != SCHEMA_PROFILE:
            raise AuditAbort(
                "unsupported_schema_profile",
                {"observed": args.schema_profile, "expected": SCHEMA_PROFILE},
            )
        if not args.include_frozen_sentinel:
            raise AuditAbort(
                "missing_frozen_sentinel_flag",
                {"required_flag": "--include-frozen-sentinel"},
            )
        regenerate_noisy_policy_comparison(args.primary_model_tag, args.schema_profile)
        verified_inputs = verify_locked_input_shas() + verify_all_manifested_artifacts()
        summary = build_audit_summary(
            preregistration_lock_sha=prereg_lock_sha,
            verified_inputs=verified_inputs,
        )
        write_outputs(summary)
        print(f"Wrote {repo_relative(SUMMARY_PATH)}")
        print(f"Wrote {repo_relative(CSV_PATH)}")
        print(f"Wrote {repo_relative(MANIFEST_PATH)}")
        print(f"Wrote {repo_relative(RESULTS_DOC_PATH)}")
        return 0
    except AuditAbort as exc:
        write_stop_report(exc)
        print(f"canonical-id resolution audit aborted: {exc.reason}", file=sys.stderr)
        print(json.dumps(exc.details, indent=2, sort_keys=True), file=sys.stderr)
        return 1


def validate_preregistration_lock(path: Path = PREREGISTRATION_PATH) -> str:
    text = path.read_text(encoding="utf-8")
    declared = declared_lock(text)
    actual = compute_preregistration_lock_sha256(text)
    if declared != actual:
        raise AuditAbort(
            "preregistration_lock_mismatch",
            {"declared": declared, "computed": actual, "path": repo_relative(path)},
        )
    declared_alias_sha = declared_alias_source_sha(text)
    actual_alias_sha = alias_source_sha256()
    if declared_alias_sha != actual_alias_sha:
        raise AuditAbort(
            "alias_source_sha_mismatch",
            {"declared": declared_alias_sha, "computed": actual_alias_sha},
        )
    embedded_alias_source = extract_between(text, ALIAS_SOURCE_START, ALIAS_SOURCE_END)
    if embedded_alias_source != ALIAS_FUNCTION_SOURCE:
        raise AuditAbort(
            "embedded_alias_source_mismatch",
            {
                "embedded_sha256": sha256_text(embedded_alias_source),
                "runner_sha256": actual_alias_sha,
            },
        )
    return declared


def declared_lock(text: str) -> str:
    match = LOCK_RE.search(text)
    if match is None:
        raise AuditAbort("missing_preregistration_lock", {"field": LOCK_FIELD})
    return match.group(1)


def declared_alias_source_sha(text: str) -> str:
    match = ALIAS_SOURCE_RE.search(text)
    if match is None:
        raise AuditAbort("missing_alias_source_lock", {"field": ALIAS_SOURCE_FIELD})
    return match.group(1)


def compute_preregistration_lock_sha256(text: str) -> str:
    payload = "\n".join(
        [
            extract_between(text, PREDICTIONS_BLOCK_START, PREDICTIONS_BLOCK_END),
            extract_between(text, ALIAS_SOURCE_START, ALIAS_SOURCE_END),
            extract_between(text, LOCKED_INPUTS_START, LOCKED_INPUTS_END),
        ]
    )
    return sha256_text(payload)


def extract_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        raise AuditAbort("missing_marker", {"marker": start_marker})
    end = text.find(end_marker, start)
    if end == -1:
        raise AuditAbort("missing_marker", {"marker": end_marker})
    block_start = text.find("\n", start)
    if block_start == -1 or block_start > end:
        raise AuditAbort("empty_marker_block", {"marker": start_marker})
    return text[block_start + 1 : end]


def alias_source_sha256() -> str:
    return sha256_text(ALIAS_FUNCTION_SOURCE)


def regenerate_noisy_policy_comparison(primary_model_tag: str, schema_profile: str) -> None:
    status = working_tree_status_short()
    if status:
        raise AuditAbort(
            "dirty_pre_run_working_tree",
            {"working_tree_status": status},
        )
    command = [
        sys.executable,
        "scripts/run_noisy_policy_comparison.py",
        "--primary-model-tag",
        primary_model_tag,
        "--schema-profile",
        schema_profile,
        "--include-frozen-sentinel",
        "--policy-set",
        POLICY_SET,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AuditAbort(
            "noisy_policy_regeneration_failed",
            {
                "command": shlex.join(command),
                "returncode": result.returncode,
                "stdout_tail": result.stdout[-4000:],
                "stderr_tail": result.stderr[-4000:],
            },
        )


def working_tree_status_short() -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AuditAbort(
            "git_status_failed",
            {"returncode": result.returncode, "stderr": result.stderr},
        )
    return result.stdout.strip()


def verify_all_manifested_artifacts() -> List[Dict[str, object]]:
    verified = []
    for family, run_path in RUN_PATH_BY_FAMILY.items():
        manifest_path = run_path.with_name(f"{run_path.stem}_manifest.json")
        verified.extend(verify_manifested_artifacts(manifest_path))
        expected_metrics = METRICS_PATH_BY_FAMILY[family]
        if not expected_metrics.exists():
            raise AuditAbort(
                "missing_metrics_csv",
                {"family": family, "path": repo_relative(expected_metrics)},
            )
    return verified


def verify_locked_input_shas(path: Path = PREREGISTRATION_PATH) -> List[Dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    block = extract_between(text, LOCKED_INPUTS_START, LOCKED_INPUTS_END)
    verified = []
    for line in block.splitlines():
        match = re.match(r"^- `([^`]+)`: `([a-f0-9]{64})`$", line.strip())
        if match is None:
            continue
        relative_path, expected_sha = match.groups()
        input_path = REPO_ROOT / relative_path
        if not input_path.exists():
            raise AuditAbort(
                "missing_locked_input_artifact",
                {"path": relative_path, "expected_sha256": expected_sha},
            )
        observed_sha = sha256_file(input_path)
        if observed_sha != expected_sha:
            raise AuditAbort(
                "locked_input_sha_mismatch",
                {
                    "path": relative_path,
                    "expected_sha256": expected_sha,
                    "observed_sha256": observed_sha,
                },
            )
        verified.append(
            {
                "path": relative_path,
                "sha256": observed_sha,
                "bytes": input_path.stat().st_size,
                "source": repo_relative(path),
            }
        )
    if not verified:
        raise AuditAbort(
            "no_locked_input_shas_declared",
            {"path": repo_relative(path)},
        )
    return verified


def verify_manifested_artifacts(manifest_path: Path) -> List[Dict[str, object]]:
    if not manifest_path.exists():
        raise AuditAbort("missing_manifest", {"path": repo_relative(manifest_path)})
    manifest = read_json(manifest_path)
    verified = []
    for artifact in manifest.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        path = REPO_ROOT / str(artifact.get("path") or "")
        expected_sha = str(artifact.get("sha256") or "")
        if not path.exists():
            raise AuditAbort(
                "missing_manifested_artifact",
                {"manifest": repo_relative(manifest_path), "path": repo_relative(path)},
            )
        observed_sha = sha256_file(path)
        if observed_sha != expected_sha:
            raise AuditAbort(
                "manifest_sha_mismatch",
                {
                    "manifest": repo_relative(manifest_path),
                    "path": repo_relative(path),
                    "expected_sha256": expected_sha,
                    "observed_sha256": observed_sha,
                },
            )
        verified.append(
            {
                "path": repo_relative(path),
                "sha256": observed_sha,
                "bytes": path.stat().st_size,
                "manifest": repo_relative(manifest_path),
            }
        )
    return verified


def build_audit_summary(
    *,
    preregistration_lock_sha: str,
    verified_inputs: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    families = {}
    for family in FAMILIES:
        run_data = read_json(RUN_PATH_BY_FAMILY[family])
        family_metrics = compute_family_metrics(family, run_data)
        family_metrics["b_cubed_f1"] = component_b_cubed_f1(family)
        family_metrics["b_cubed_minus_cqr_gap"] = (
            None
            if family_metrics["b_cubed_f1"] is None
            else family_metrics["b_cubed_f1"] - family_metrics["cqr_set_membership"]
        )
        family_metrics["predictions"] = prediction_outcome_for_family(family, family_metrics)
        families[family] = family_metrics
    bucket = classify_bucket(families)
    return {
        "mode": "canonical_id_resolution_audit",
        "generated_at": utc_now(),
        "bucket_outcome": bucket,
        "preregistration_lock_sha256": preregistration_lock_sha,
        "alias_function_sha256": alias_source_sha256(),
        "primary_model_tag": PRIMARY_MODEL_TAG,
        "schema_profile": SCHEMA_PROFILE,
        "policy_set": POLICY_SET,
        "families": families,
        "verified_inputs": list(verified_inputs),
        "runner_command": (
            "python3 scripts/run_canonical_id_resolution_audit.py "
            "--primary-model-tag qwen2.5:32b-instruct-q4_K_M "
            "--schema-profile default --include-frozen-sentinel"
        ),
    }


def compute_family_metrics(family: str, run_data: Mapping[str, object]) -> Dict[str, object]:
    cq_policy = policy_payload(run_data, CQ_POLICY)
    cq_scenarios = scenario_payloads_by_id(cq_policy)
    exact = 0
    scope = 0
    alias = 0
    total = 0
    examples = []
    alias_examples = []

    for scenario_id, scenario in cq_scenarios.items():
        candidates = candidate_payloads(scenario)
        for trace in question_traces_with_relevant_id(scenario):
            total += 1
            exact_hit = any(
                candidate.get("canonical_id") == trace.get("relevant_canonical_id")
                for candidate in candidates
            )
            scope_hit = any(scope_matched(candidate, trace) for candidate in candidates)
            alias_hit = any(
                alias_match(
                    str(candidate.get("canonical_id") or ""),
                    str(trace.get("relevant_canonical_id") or ""),
                )
                for candidate in candidates
            )
            exact += int(exact_hit)
            scope += int(scope_hit)
            alias += int(alias_hit)
            if not exact_hit and len(examples) < 5:
                examples.append(mismatch_example(scenario_id, candidates, trace))
            if alias_hit and not exact_hit and len(alias_examples) < 5:
                alias_examples.append(mismatch_example(scenario_id, candidates, trace))

    cross_tabs = {
        policy.get("policy_name"): policy_cross_tab(family, policy, cq_scenarios)
        for policy in run_data.get("policies", [])
        if policy.get("policy_name") in POLICIES_TO_REPORT
    }
    negative_control = alias_false_positive_summary(cq_scenarios)
    return {
        "family": family,
        "question_traces_with_relevant_id": total,
        "cqr_exact_matches": exact,
        "cqr_scope_matched_matches": scope,
        "cqr_alias_matches": alias,
        "cqr_set_membership": rate(exact, total),
        "cqr_scope_matched": rate(scope, total),
        "cqr_alias_set_membership": rate(alias, total),
        "alias_false_positive_rate": negative_control["alias_false_positive_rate"],
        "alias_false_positive_numerator": negative_control["false_positive_pairs"],
        "alias_false_positive_denominator": negative_control["alias_matched_pairs"],
        "cross_tabs_by_policy": cross_tabs,
        "sample_exact_misses": examples,
        "sample_alias_only_hits": alias_examples,
    }


def policy_cross_tab(
    family: str,
    policy: Mapping[str, object],
    cq_scenarios: Mapping[str, Mapping[str, object]],
) -> Dict[str, object]:
    table = {
        "hit_success": 0,
        "hit_failure": 0,
        "miss_success": 0,
        "miss_failure": 0,
    }
    failures_by_question = policy_primary_metric_failures(policy, family)
    for scenario in policy.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("scenario_id") or "")
        cq_scenario = cq_scenarios.get(scenario_id)
        if cq_scenario is None:
            raise AuditAbort(
                "policy_scenario_stream_mismatch",
                {
                    "family": family,
                    "policy_name": policy.get("policy_name"),
                    "missing_scenario_id": scenario_id,
                },
            )
        candidates = candidate_payloads(cq_scenario)
        for trace in question_traces_with_relevant_id(scenario):
            question_id = str(trace.get("question_id") or "")
            alias_hit = any(
                alias_match(
                    str(candidate.get("canonical_id") or ""),
                    str(trace.get("relevant_canonical_id") or ""),
                )
                for candidate in candidates
            )
            answer_success = question_id not in failures_by_question.get(scenario_id, set())
            if alias_hit and answer_success:
                table["hit_success"] += 1
            elif alias_hit:
                table["hit_failure"] += 1
            elif answer_success:
                table["miss_success"] += 1
            else:
                table["miss_failure"] += 1
    hit_total = table["hit_success"] + table["hit_failure"]
    miss_total = table["miss_success"] + table["miss_failure"]
    success_given_hit = rate(table["hit_success"], hit_total)
    success_given_miss = rate(table["miss_success"], miss_total)
    answer_def: Dict[str, object] = {
        "metric": PRIMARY_METRIC_BY_FAMILY[family],
        "primary_failure_filters": [
            {"failure_type": failure_type, "reasons": list(reasons) if reasons else None}
            for failure_type, reasons in PRIMARY_FAILURE_FILTERS_BY_FAMILY[family]
        ],
    }
    if family == "mechanism_diverse_heldout":
        answer_def["caveat"] = FROZEN_SENTINEL_SUCCESS_CAVEAT
    return {
        **table,
        "answer_success_definition": answer_def,
        "alias_hit_total": hit_total,
        "alias_miss_total": miss_total,
        "answer_success_given_alias_hit": success_given_hit,
        "answer_success_given_alias_miss": success_given_miss,
        "lift": success_given_hit - success_given_miss,
        "policy_answer_success_rate": rate(
            table["hit_success"] + table["miss_success"],
            hit_total + miss_total,
        ),
        "cqr_alias_hit_rate": rate(hit_total, hit_total + miss_total),
    }


def policy_primary_metric_failures(
    policy: Mapping[str, object],
    family: str,
) -> Dict[str, set]:
    failures: Dict[str, set] = {}
    filters = PRIMARY_FAILURE_FILTERS_BY_FAMILY[family]
    for scenario in policy.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("scenario_id") or "")
        for example in scenario.get("failure_examples", []):
            if not isinstance(example, dict):
                continue
            if failure_matches_primary_metric(example, filters):
                failures.setdefault(scenario_id, set()).add(str(example.get("question_id") or ""))
    return failures


def failure_matches_primary_metric(
    example: Mapping[str, object],
    filters: Sequence[Tuple[str, Optional[Sequence[str]]]],
) -> bool:
    failure_type = str(example.get("failure_type") or "")
    reason = str(example.get("reason") or "")
    for expected_type, expected_reasons in filters:
        if failure_type != expected_type:
            continue
        if expected_reasons is None or reason in expected_reasons:
            return True
    return False


def alias_false_positive_summary(
    cq_scenarios: Mapping[str, Mapping[str, object]]
) -> Dict[str, object]:
    denominator = 0
    numerator = 0
    examples = []
    for scenario_id, scenario in cq_scenarios.items():
        traces = list(question_traces_with_relevant_id(scenario))
        relevant_ids = sorted({str(trace.get("relevant_canonical_id") or "") for trace in traces})
        for candidate in candidate_payloads(scenario):
            candidate_id = str(candidate.get("canonical_id") or "")
            matched_relevant_ids = [
                relevant_id for relevant_id in relevant_ids if alias_match(candidate_id, relevant_id)
            ]
            if not matched_relevant_ids:
                continue
            for trace in traces:
                denominator += 1
                if str(trace.get("relevant_canonical_id") or "") not in matched_relevant_ids:
                    numerator += 1
                    if len(examples) < 5:
                        examples.append(
                            {
                                "scenario_id": scenario_id,
                                "candidate_canonical_id": candidate_id,
                                "question_relevant_canonical_id": trace.get("relevant_canonical_id"),
                                "matched_other_relevant_ids": matched_relevant_ids,
                            }
                        )
    return {
        "false_positive_pairs": numerator,
        "alias_matched_pairs": denominator,
        "alias_false_positive_rate": rate(numerator, denominator),
        "examples": examples,
    }


def prediction_outcome_for_family(
    family: str,
    metrics: Mapping[str, object],
) -> Dict[str, object]:
    prediction = ALIAS_CQR_PREDICTIONS.get(family)
    if prediction is None:
        return {"gated": False}
    alias_value = float(metrics["cqr_alias_set_membership"])
    fpr_value = float(metrics["alias_false_positive_rate"])
    cq_cross_tab = metrics["cross_tabs_by_policy"].get(CQ_POLICY, {})
    lift = float(cq_cross_tab.get("lift", 0.0))
    hit_total = int(cq_cross_tab.get("alias_hit_total", 0))
    alias_pass = prediction_passes(alias_value, prediction)
    fpr_pass = fpr_value <= prediction["false_positive_cap"]
    cross_tab_pass = True
    if family in THESIS_FAMILIES:
        cross_tab_pass = hit_total >= 5 and lift >= 0.30
    return {
        "gated": family in THESIS_FAMILIES,
        "alias_prediction": prediction,
        "alias_prediction_pass": alias_pass,
        "false_positive_cap_pass": fpr_pass,
        "cq_cross_tab_lift": lift,
        "cq_alias_hit_total": hit_total,
        "cq_cross_tab_pass": cross_tab_pass,
    }


ALIAS_CQR_PREDICTIONS = {
    "useful_pending_memory": {"operator": ">=", "value": 0.40, "tolerance": 0.20, "false_positive_cap": 0.05},
    "memory_poisoning": {"operator": ">=", "value": 0.40, "tolerance": 0.20, "false_positive_cap": 0.05},
    "false_corroboration": {"operator": "band", "lower": 0.10, "upper": 0.60, "false_positive_cap": 0.10},
    "scope_contamination": {"operator": "<=", "value": 0.25, "tolerance": 0.10, "false_positive_cap": 0.05},
    "forced_contradiction": {"operator": ">=", "value": 0.85, "tolerance": 0.10, "false_positive_cap": 0.05},
    "preference_drift": {"operator": "band", "lower": 0.25, "upper": 0.60, "false_positive_cap": 0.10},
    "mechanism_diverse_heldout": {"operator": "<=", "value": 0.40, "tolerance": 0.20, "false_positive_cap": 0.10},
}


def prediction_passes(observed: float, prediction: Mapping[str, object]) -> bool:
    operator = prediction["operator"]
    if operator == ">=":
        return observed >= float(prediction["value"]) - float(prediction["tolerance"])
    if operator == "<=":
        return observed <= float(prediction["value"]) + float(prediction["tolerance"])
    if operator == "band":
        return float(prediction["lower"]) <= observed <= float(prediction["upper"])
    raise ValueError(f"Unknown prediction operator: {operator}")


def classify_bucket(families: Mapping[str, Mapping[str, object]]) -> Dict[str, object]:
    thesis_outcomes = {
        family: families[family]["predictions"]
        for family in THESIS_FAMILIES
    }
    failures_by_family = {}
    for family, outcome in thesis_outcomes.items():
        failures = []
        if not outcome["alias_prediction_pass"]:
            failures.append(f"{family}: alias-CQR outside locked band")
        if not outcome["false_positive_cap_pass"]:
            failures.append(f"{family}: alias false-positive cap exceeded")
        if not outcome["cq_cross_tab_pass"]:
            failures.append(f"{family}: CQ cross-tab lift failed or underpowered")
        failures_by_family[family] = failures
    if all(not failures for failures in failures_by_family.values()):
        return {
            "bucket": "A",
            "label": "thesis confirmed",
            "reasons": [
                "Both thesis families cleared alias-CQR bands, false-positive caps, and CQ cross-tab lift."
            ],
        }
    if partial_bucket_b(thesis_outcomes):
        return {
            "bucket": "B",
            "label": "partial / descriptive",
            "reasons": [
                reason
                for family in THESIS_FAMILIES
                for reason in failures_by_family[family]
            ],
        }
    return {
        "bucket": "C",
        "label": "thesis falsified or contaminated",
        "reasons": [
            reason
            for family in THESIS_FAMILIES
            for reason in failures_by_family[family]
        ],
    }


def partial_bucket_b(thesis_outcomes: Mapping[str, Mapping[str, object]]) -> bool:
    if any(not thesis_outcomes[family]["false_positive_cap_pass"] for family in THESIS_FAMILIES):
        return False

    def non_contaminant_fail_count(outcome: Mapping[str, object]) -> int:
        return int(not outcome["alias_prediction_pass"]) + int(not outcome["cq_cross_tab_pass"])

    counts = {family: non_contaminant_fail_count(thesis_outcomes[family]) for family in THESIS_FAMILIES}
    if all(count == 0 for count in counts.values()):
        return False
    passing = [family for family in THESIS_FAMILIES if counts[family] == 0]
    failing = [family for family in THESIS_FAMILIES if counts[family] > 0]
    if len(passing) != 1 or len(failing) != 1:
        return False
    return counts[failing[0]] == 1


def policy_payload(run_data: Mapping[str, object], policy_name: str) -> Mapping[str, object]:
    for policy in run_data.get("policies", []):
        if isinstance(policy, dict) and policy.get("policy_name") == policy_name:
            return policy
    raise AuditAbort(
        "missing_policy_payload",
        {"policy_name": policy_name, "family": run_data.get("family")},
    )


def scenario_payloads_by_id(policy: Mapping[str, object]) -> Dict[str, Mapping[str, object]]:
    return {
        str(scenario.get("scenario_id")): scenario
        for scenario in policy.get("scenarios", [])
        if isinstance(scenario, dict)
    }


def candidate_payloads(scenario: Mapping[str, object]) -> List[Mapping[str, object]]:
    return [
        candidate
        for candidate in scenario.get("extracted_candidate_stream", [])
        if isinstance(candidate, dict)
    ]


def question_traces_with_relevant_id(
    scenario: Mapping[str, object]
) -> Iterable[Mapping[str, object]]:
    for trace in scenario.get("question_traces", []):
        if isinstance(trace, dict) and trace.get("relevant_canonical_id"):
            yield trace


def scope_matched(candidate: Mapping[str, object], trace: Mapping[str, object]) -> bool:
    return (
        candidate.get("canonical_id") == trace.get("relevant_canonical_id")
        and candidate.get("scope_level") == trace.get("scope_level")
        and candidate.get("scope_key") == trace.get("scope_key")
    )


def mismatch_example(
    scenario_id: str,
    candidates: Sequence[Mapping[str, object]],
    trace: Mapping[str, object],
) -> Dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "question_id": trace.get("question_id"),
        "relevant_canonical_id": trace.get("relevant_canonical_id"),
        "scope_level": trace.get("scope_level"),
        "scope_key": trace.get("scope_key"),
        "candidate_canonical_ids": sorted(
            str(candidate.get("canonical_id") or "") for candidate in candidates
        ),
        "answer_text": trace.get("answer_text"),
    }


def component_b_cubed_f1(family: str) -> Optional[float]:
    path = COMPONENT_EVAL_PATH_BY_FAMILY[family]
    if not path.exists():
        raise AuditAbort("missing_component_eval", {"family": family, "path": repo_relative(path)})
    data = read_json(path)
    metrics = data.get("metrics", {})
    value = metrics.get("canonicalization_b_cubed_f1")
    return None if value is None else float(value)


def write_outputs(summary: Mapping[str, object]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(SUMMARY_PATH, summary)
    write_family_csv(CSV_PATH, summary["families"])
    RESULTS_DOC_PATH.write_text(render_results_doc(summary), encoding="utf-8")
    manifest = {
        "mode": "canonical_id_resolution_audit_manifest",
        "generated_at": utc_now(),
        "archive_status": "tracked",
        "preregistration_lock_sha256": summary["preregistration_lock_sha256"],
        "alias_function_sha256": summary["alias_function_sha256"],
        "input_artifacts": summary["verified_inputs"],
        "output_artifacts": [
            artifact_payload(SUMMARY_PATH),
            artifact_payload(CSV_PATH),
            artifact_payload(RESULTS_DOC_PATH),
        ],
        "runner_command": summary["runner_command"],
        "git_status_after_outputs": working_tree_status_short(),
    }
    write_json(MANIFEST_PATH, manifest)


def write_family_csv(path: Path, families: Mapping[str, Mapping[str, object]]) -> None:
    fieldnames = [
        "family",
        "bucket_gate_role",
        "question_traces_with_relevant_id",
        "b_cubed_f1",
        "cqr_set_membership",
        "cqr_scope_matched",
        "cqr_alias_set_membership",
        "b_cubed_minus_cqr_gap",
        "alias_false_positive_rate",
        "cq_cross_tab_lift",
        "cq_alias_hit_total",
        "alias_prediction_pass",
        "false_positive_cap_pass",
        "cq_cross_tab_pass",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for family, metrics in families.items():
            predictions = metrics.get("predictions", {})
            writer.writerow(
                {
                    "family": family,
                    "bucket_gate_role": "thesis" if family in THESIS_FAMILIES else "descriptive",
                    "question_traces_with_relevant_id": metrics["question_traces_with_relevant_id"],
                    "b_cubed_f1": format_optional_float(metrics["b_cubed_f1"]),
                    "cqr_set_membership": format_float(metrics["cqr_set_membership"]),
                    "cqr_scope_matched": format_float(metrics["cqr_scope_matched"]),
                    "cqr_alias_set_membership": format_float(metrics["cqr_alias_set_membership"]),
                    "b_cubed_minus_cqr_gap": format_optional_float(metrics["b_cubed_minus_cqr_gap"]),
                    "alias_false_positive_rate": format_float(metrics["alias_false_positive_rate"]),
                    "cq_cross_tab_lift": format_float(predictions.get("cq_cross_tab_lift", 0.0)),
                    "cq_alias_hit_total": predictions.get("cq_alias_hit_total", ""),
                    "alias_prediction_pass": predictions.get("alias_prediction_pass", ""),
                    "false_positive_cap_pass": predictions.get("false_positive_cap_pass", ""),
                    "cq_cross_tab_pass": predictions.get("cq_cross_tab_pass", ""),
                }
            )


def render_results_doc(summary: Mapping[str, object]) -> str:
    bucket = summary["bucket_outcome"]
    lines = [
        "# Canonical-Id Resolution Audit Results",
        "",
        f"Date: {utc_now()[:10]}",
        "",
        f"Bucket outcome: Bucket {bucket['bucket']} - {bucket['label']}.",
        "",
        "This audit is replay-only and audit-time only. It does not change the Phase 4 policy comparison, the candidate adapter, or memory-substrate lookup semantics.",
        "",
        "This file is emitted automatically as a replay stub. Before treating it as the final published readout, add an interpretive pass that ties the bucket verdict to the mechanism audit and the Phase 4 artifacts.",
        "",
        "For `mechanism_diverse_heldout`, descriptive cross-tabs use a union of primary-style failure types per question (see `answer_success_definition` in the summary JSON). Thesis gates still use only `useful_pending_memory` and `memory_poisoning`.",
        "",
        "## Verdict",
        "",
    ]
    lines.extend(f"- {reason}" for reason in bucket["reasons"])
    lines.extend(
        [
            "",
            "## Observed Family Metrics",
            "",
            "| Family | Role | B-cubed F1 | exact CQR | scope CQR | alias CQR | alias FPR | CQ lift |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for family, metrics in summary["families"].items():
        predictions = metrics["predictions"]
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                family,
                "thesis" if family in THESIS_FAMILIES else "descriptive",
                format_optional_float(metrics["b_cubed_f1"]),
                format_float(metrics["cqr_set_membership"]),
                format_float(metrics["cqr_scope_matched"]),
                format_float(metrics["cqr_alias_set_membership"]),
                format_float(metrics["alias_false_positive_rate"]),
                format_float(predictions.get("cq_cross_tab_lift", 0.0)),
            )
        )
    lines.extend(
        [
            "",
            "## Locked Inputs",
            "",
            f"- preregistration lock: `{summary['preregistration_lock_sha256']}`",
            f"- alias source SHA256: `{summary['alias_function_sha256']}`",
            "",
            "Any production aliasing would require a separate preregistration ensuring symmetric application to all policies on the same upstream candidate stream.",
            "",
        ]
    )
    return "\n".join(lines)


def write_stop_report(exc: AuditAbort) -> None:
    path = REPO_ROOT / "data" / "results" / "canonical_id_resolution_audit_stop.json"
    payload = {
        "mode": "canonical_id_resolution_audit_stop",
        "generated_at": utc_now(),
        "bucket": "D",
        "reason": exc.reason,
        "details": exc.details,
    }
    write_json(path, payload)


def artifact_payload(path: Path) -> Dict[str, object]:
    return {
        "path": repo_relative(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rate(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def format_float(value: object) -> str:
    return f"{float(value):.3f}"


def format_optional_float(value: object) -> str:
    return "" if value is None else format_float(value)


def repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
