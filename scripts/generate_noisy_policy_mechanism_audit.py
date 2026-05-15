"""Generate the committed noisy policy mechanism audit artifacts.

This script is intentionally read-only with respect to experiment execution: it
does not rerun extraction, policy scoring, thresholds, prompts, or validators.
It derives the compact audit evidence file and focused dashboard traces from
existing saved Phase 4 artifacts.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cq.dashboard.app import render_dashboard


GENERATOR_COMMAND = "python3 scripts/generate_noisy_policy_mechanism_audit.py"
EVIDENCE_PATH = Path("data/results/noisy_policy_mechanism_audit_evidence.json")

COUNTABLE_FAMILIES = [
    "forced_contradiction",
    "scope_contamination",
    "preference_drift",
    "useful_pending_memory",
    "memory_poisoning",
    "false_corroboration",
]

METRIC_BY_FAMILY: Dict[str, Tuple[str, bool]] = {
    "forced_contradiction": ("false_assertion_rate", False),
    "scope_contamination": ("leakage_rate", False),
    "preference_drift": ("answer_correctness", True),
    "useful_pending_memory": ("answer_correctness", True),
    "memory_poisoning": ("poison_promotion_rate", False),
    "false_corroboration": ("false_assertion_rate", False),
}

ORACLE_METRICS_PATH_BY_FAMILY = {
    "forced_contradiction": Path("data/results/forced_contradiction_oracle_heldout_metrics.csv"),
    "scope_contamination": Path("data/results/scope_contamination_oracle_heldout_metrics.csv"),
    "preference_drift": Path("data/results/preference_drift_oracle_heldout_metrics.csv"),
    "useful_pending_memory": Path("data/results/useful_pending_memory_oracle_heldout_metrics.csv"),
    "memory_poisoning": Path("data/results/memory_poisoning_oracle_metrics.csv"),
    "false_corroboration": Path("data/results/false_corroboration_oracle_metrics.csv"),
}

COMPONENT_EVAL_PATH_BY_FAMILY = {
    family: Path(
        "data/results/"
        f"component_gate_decision_{family}_local_extractor_qwen2_5_32b_q4km_"
        "general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json"
    )
    for family in COUNTABLE_FAMILIES
}
COMPONENT_EVAL_PATH_BY_FAMILY["mechanism_diverse_heldout"] = Path(
    "data/results/component_gate_decision_mechanism_diverse_heldout_local_extractor_"
    "qwen2_5_32b_q4km_general_v1_default_frozen_n3_frozen_sentinel_primary_component_eval.json"
)

NOISY_RUN_PATH_BY_FAMILY = {
    family: Path(f"data/runs/noisy_policy_comparison_{family}_default.json")
    for family in COUNTABLE_FAMILIES
}
NOISY_RUN_PATH_BY_FAMILY["mechanism_diverse_heldout"] = Path(
    "data/runs/noisy_policy_comparison_mechanism_diverse_heldout_default.json"
)

TRACE_SPECS = {
    "forced_contradiction": {
        "scenario_id": "forced_contradiction_001",
        "run_json": Path("data/runs/audit_trace_forced_contradiction_default.json"),
        "html": Path("data/results/audit_trace_forced_contradiction_default.html"),
        "description": "survival trace",
    },
    "scope_contamination": {
        "scenario_id": "scope_contamination_001",
        "run_json": Path("data/runs/audit_trace_scope_contamination_default.json"),
        "html": Path("data/results/audit_trace_scope_contamination_default.html"),
        "description": "null trace with residual 32B defects",
    },
    "useful_pending_memory": {
        "scenario_id": "useful_pending_001",
        "run_json": Path("data/runs/audit_trace_useful_pending_memory_default.json"),
        "html": Path("data/results/audit_trace_useful_pending_memory_default.html"),
        "description": "perfect-component null trace",
    },
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate noisy mechanism audit evidence and focused traces."
    )
    parser.add_argument(
        "--skip-html",
        action="store_true",
        help="Write evidence and filtered trace JSON only.",
    )
    args = parser.parse_args(argv)

    evidence = build_evidence()
    write_json(EVIDENCE_PATH, evidence)
    print(f"Wrote {EVIDENCE_PATH}")

    for family, spec in TRACE_SPECS.items():
        trace = build_filtered_trace(
            NOISY_RUN_PATH_BY_FAMILY[family],
            spec["scenario_id"],
            family,
        )
        write_json(spec["run_json"], trace)
        print(f"Wrote {spec['run_json']}")
        if not args.skip_html:
            spec["html"].parent.mkdir(parents=True, exist_ok=True)
            spec["html"].write_text(render_dashboard(trace), encoding="utf-8")
            print(f"Wrote {spec['html']}")

    return 0


def build_evidence() -> Dict[str, object]:
    summary_path = Path("data/results/noisy_policy_comparison_summary.json")
    summary = read_json(summary_path)
    rows = {}
    for family in COUNTABLE_FAMILIES:
        rows[family] = build_family_row(family, summary)

    rows["mechanism_diverse_heldout"] = {
        "frozen_primary_comparisons": summary["schema_profiles"]["default"][
            "frozen_primary_comparisons"
        ],
        "frozen_oracle_vs_noisy_gaps": frozen_oracle_vs_noisy_gaps(),
        "component_32b_default": component_summary(
            COMPONENT_EVAL_PATH_BY_FAMILY["mechanism_diverse_heldout"]
        ),
        "canonical_alignment": canonical_alignment(
            NOISY_RUN_PATH_BY_FAMILY["mechanism_diverse_heldout"]
        ),
    }

    return {
        "generated_from_existing_artifacts_only": True,
        "generator_command": GENERATOR_COMMAND,
        "date": "2026-05-15",
        "summary_source": str(summary_path),
        "rows": rows,
        "representative_traces": {
            family: {
                "scenario_id": spec["scenario_id"],
                "run_json": str(spec["run_json"]),
                "html": str(spec["html"]),
                "description": spec["description"],
                "generator_command": GENERATOR_COMMAND,
            }
            for family, spec in TRACE_SPECS.items()
        },
    }


def build_family_row(family: str, summary: Dict[str, object]) -> Dict[str, object]:
    metric_name, higher_is_better = METRIC_BY_FAMILY[family]
    noisy_rows = overall_metric_rows(
        Path(f"data/results/noisy_policy_comparison_{family}_default_metrics.csv")
    )
    oracle_rows = overall_metric_rows(ORACLE_METRICS_PATH_BY_FAMILY[family])
    cq_oracle = metric_value(
        oracle_rows.get("consolidation_queue_lite"), family, metric_name
    )
    reflection_oracle = metric_value(
        oracle_rows.get("reflection_eager_write_lite"), family, metric_name
    )
    cq_noisy = metric_value(
        noisy_rows.get("consolidation_queue_lite"), family, metric_name
    )
    reflection_noisy = metric_value(
        noisy_rows.get("reflection_eager_write_lite"), family, metric_name
    )
    primary = summary["schema_profiles"]["default"]["primary_metric_comparisons"][family]

    return {
        "primary_metric": metric_name,
        "higher_is_better": higher_is_better,
        "noisy_cq_vs_reflection": primary["reflection_eager_write_lite"],
        "noisy_cq_vs_mem0": primary["mem0_lite"],
        "oracle": {
            "cq": cq_oracle,
            "reflection": reflection_oracle,
            "improvement_delta": improvement_delta(
                cq_oracle, reflection_oracle, higher_is_better
            ),
        },
        "noisy_overall": {
            "cq": cq_noisy,
            "reflection": reflection_noisy,
            "improvement_delta": improvement_delta(
                cq_noisy, reflection_noisy, higher_is_better
            ),
            "cq_oracle_minus_noisy_gap": raw_gap(cq_noisy, cq_oracle),
        },
        "ablation_rows": {
            name: primary[name]
            for name in [
                "cq_no_contestation_demotion",
                "cq_no_wider_scope_pending_override",
                "cq_no_pending_lookup_use",
                "cq_no_source_independence_gate",
            ]
        },
        "component_32b_default": component_summary(COMPONENT_EVAL_PATH_BY_FAMILY[family]),
        "canonical_alignment": canonical_alignment(NOISY_RUN_PATH_BY_FAMILY[family]),
    }


def build_filtered_trace(
    run_path: Path, scenario_id: str, family: str
) -> Dict[str, object]:
    run_data = read_json(run_path)
    run_data["experiment"] = f"audit_trace_{family}_default"
    run_data["requested_scenario_count"] = 1
    run_data["scenario_count"] = 1
    run_data["audit_trace_source_run"] = str(run_path)
    run_data["audit_trace_generator_command"] = GENERATOR_COMMAND
    run_data["audit_trace_filter_scenario_id"] = scenario_id
    run_data["candidate_stream_audit"] = [
        row
        for row in run_data["candidate_stream_audit"]
        if row["scenario_id"] == scenario_id
    ]
    for policy in run_data["policies"]:
        policy["scenarios"] = [
            scenario
            for scenario in policy["scenarios"]
            if scenario["scenario_id"] == scenario_id
        ]
        policy["trace_filter_scenario_id"] = scenario_id
    return run_data


def overall_metric_rows(path: Path) -> Dict[str, Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {
            row["policy_name"]: row
            for row in csv.DictReader(handle)
            if row["summary_scope"] == "overall"
        }


def metric_value(
    row: Optional[Dict[str, str]], family: str, metric_name: str
) -> Optional[float]:
    if not row:
        return None
    if row.get(metric_name) not in (None, ""):
        return float(row[metric_name])
    if family == "forced_contradiction" and metric_name == "false_assertion_rate":
        return float(row["false_assertion_after_contradiction"])
    return None


def improvement_delta(
    cq_value: Optional[float],
    reflection_value: Optional[float],
    higher_is_better: bool,
) -> Optional[float]:
    if cq_value is None or reflection_value is None:
        return None
    if higher_is_better:
        return cq_value - reflection_value
    return reflection_value - cq_value


def raw_gap(noisy_value: Optional[float], oracle_value: Optional[float]) -> Optional[float]:
    if noisy_value is None or oracle_value is None:
        return None
    return noisy_value - oracle_value


def frozen_oracle_vs_noisy_gaps() -> Dict[str, Optional[float]]:
    oracle_rows = overall_metric_rows(
        Path("data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_metrics.csv")
    )
    noisy_rows = overall_metric_rows(
        Path("data/results/noisy_policy_comparison_mechanism_diverse_heldout_default_metrics.csv")
    )
    cq_oracle = oracle_rows.get("consolidation_queue_lite", {})
    cq_noisy = noisy_rows.get("consolidation_queue_lite", {})
    gaps = {}
    for metric_name in [
        "false_assertion_rate",
        "poison_promotion_rate",
        "premature_promotion_rate",
        "answer_correctness",
    ]:
        oracle_value = float(cq_oracle[metric_name]) if cq_oracle.get(metric_name) else None
        noisy_value = float(cq_noisy[metric_name]) if cq_noisy.get(metric_name) else None
        gaps[metric_name] = raw_gap(noisy_value, oracle_value)
    return gaps


def component_summary(path: Path) -> Dict[str, object]:
    component_eval = read_json(path)
    failure_counts = collections.Counter(
        (example["component"], example["failure_type"])
        for example in component_eval.get("failure_examples", [])
    )
    metric_names = [
        "candidate_detection_f1",
        "claim_type_accuracy",
        "scope_level_accuracy",
        "scope_key_accuracy",
        "canonicalization_b_cubed_f1",
        "contradiction_f1",
        "contradiction_precision",
        "contradiction_recall",
        "contradiction_tp",
        "contradiction_fn",
        "contradiction_fp",
    ]
    return {
        "source_path": str(path),
        "scenario_error_count": component_eval.get("scenario_error_count"),
        "failure_example_count": component_eval.get("failure_example_count"),
        "failure_counts_by_type": {
            f"{component}:{failure_type}": count
            for (component, failure_type), count in sorted(failure_counts.items())
        },
        "metrics": {
            metric_name: component_eval["metrics"].get(metric_name)
            for metric_name in metric_names
            if metric_name in component_eval.get("metrics", {})
        },
        "sample_failures": sample_failures(
            component_eval.get("failure_examples", []), limit=3
        ),
    }


def sample_failures(
    failure_examples: Iterable[Dict[str, object]], limit: int
) -> List[Dict[str, object]]:
    samples = []
    for example in failure_examples:
        samples.append(
            {
                key: example.get(key)
                for key in [
                    "scenario_id",
                    "event_id",
                    "component",
                    "failure_type",
                    "gold",
                    "predicted",
                ]
            }
        )
        if len(samples) >= limit:
            break
    return samples


def canonical_alignment(path: Path) -> Dict[str, object]:
    run_data = read_json(path)
    policy = next(
        policy
        for policy in run_data["policies"]
        if policy["policy_name"] == "consolidation_queue_lite"
    )
    total = 0
    exact = 0
    examples = []
    for scenario in policy["scenarios"]:
        candidate_canonical_ids = {
            candidate["canonical_id"]
            for candidate in scenario.get("extracted_candidate_stream", [])
        }
        for trace in scenario.get("question_traces", []):
            relevant_canonical_id = trace.get("relevant_canonical_id")
            if not relevant_canonical_id:
                continue
            total += 1
            if relevant_canonical_id in candidate_canonical_ids:
                exact += 1
            elif len(examples) < 3:
                examples.append(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "relevant_canonical_id": relevant_canonical_id,
                        "candidate_canonical_ids": sorted(candidate_canonical_ids),
                        "answer_text": trace.get("answer_text"),
                    }
                )
    return {
        "exact_matches": exact,
        "question_traces_with_relevant_id": total,
        "examples": examples,
    }


def read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
