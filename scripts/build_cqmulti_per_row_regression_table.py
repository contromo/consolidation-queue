#!/usr/bin/env python3
"""Build the CQ-Multi internal-regression LaTeX table.

The CQPendingMultiEvidence follow-up was replayed on existing internal
families to check that the LongMemEval readout repair did not change base CQ
behavior elsewhere. The committed metrics CSVs contain aggregate policy rows,
not per-scenario CQ-Multi-vs-base-CQ rows, so this script reports per-family
overall numeric deltas only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


BASE_POLICY = "consolidation_queue_lite"
FOLLOWUP_POLICY = "cq_pending_multi_evidence"
DEFAULT_INPUT_GLOB = "data/results/cq_pending_multi_evidence_*_metrics.csv"
DEFAULT_TEX = "paper/figures/cqmulti_per_row_regression.tex"
DEFAULT_JSON = "data/results/cqmulti_per_row_regression_summary.json"

NON_METRIC_COLUMNS = {
    "policy_name",
    "summary_scope",
    "template_id",
    "template_kind",
    "template_split",
    "scenario_count",
    "comparison_name",
    "comparison_metric_name",
    "comparison_reference_policy_name",
    "comparison_comparator_policy_name",
    "comparison_point_estimate_delta",
    "comparison_one_sided_95_lcb",
    "comparison_one_sided_95_ucb",
}

FAMILY_DISPLAY_NAMES = {
    "adversarial_upstream_noise": "Adversarial upstream noise",
    "evidence_conflict_spectrum": "Evidence-conflict spectrum",
    "forced_contradiction": "Forced contradiction",
    "mechanism_diverse_heldout": "Mechanism-diverse held-out",
    "preference_drift": "Preference drift",
}

FAMILY_ORDER = {
    family: index
    for index, family in enumerate(
        [
            "forced_contradiction",
            "preference_drift",
            "mechanism_diverse_heldout",
            "adversarial_upstream_noise",
            "evidence_conflict_spectrum",
        ]
    )
}


@dataclass(frozen=True)
class FamilyDelta:
    family: str
    artifact_path: str
    scenario_count: int
    checked_metric_count: int
    max_abs_delta: float
    nonzero_metrics: tuple[str, ...]


def build_rows(paths: Iterable[Path], *, repo_root: Path) -> list[FamilyDelta]:
    rows = [_family_delta(path, repo_root=repo_root) for path in paths]
    return sorted(rows, key=lambda row: (FAMILY_ORDER.get(row.family, 999), row.family))


def write_outputs(rows: Sequence[FamilyDelta], *, tex_path: Path, json_path: Path) -> None:
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(_latex_table(rows), encoding="utf-8")
    payload = {
        "base_policy": BASE_POLICY,
        "followup_policy": FOLLOWUP_POLICY,
        "scope": "overall aggregate policy rows",
        "confidence_intervals": "not reported; committed metrics are aggregate rows, not per-scenario paired rows",
        "max_abs_delta": max((row.max_abs_delta for row in rows), default=0.0),
        "families": [
            {
                "family": row.family,
                "artifact_path": row.artifact_path,
                "scenario_count": row.scenario_count,
                "checked_metric_count": row.checked_metric_count,
                "max_abs_delta": row.max_abs_delta,
                "nonzero_metrics": list(row.nonzero_metrics),
            }
            for row in rows
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _family_delta(path: Path, *, repo_root: Path) -> FamilyDelta:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        all_rows = list(reader)
    by_policy = {
        row["policy_name"]: row
        for row in all_rows
        if row.get("summary_scope") == "overall"
        and row.get("policy_name") in {BASE_POLICY, FOLLOWUP_POLICY}
    }
    missing = sorted({BASE_POLICY, FOLLOWUP_POLICY} - set(by_policy))
    if missing:
        raise ValueError("{} missing overall rows for {}".format(path, ", ".join(missing)))

    base = by_policy[BASE_POLICY]
    followup = by_policy[FOLLOWUP_POLICY]
    checked = 0
    nonzero = []
    max_abs = 0.0
    for column in base:
        if column in NON_METRIC_COLUMNS:
            continue
        base_value = _maybe_float(base.get(column, ""))
        followup_value = _maybe_float(followup.get(column, ""))
        if base_value is None or followup_value is None:
            continue
        checked += 1
        delta = followup_value - base_value
        max_abs = max(max_abs, abs(delta))
        if not math.isclose(delta, 0.0, abs_tol=1e-12):
            nonzero.append("{} ({:+.6f})".format(column, delta))

    return FamilyDelta(
        family=_family_from_path(path),
        artifact_path=_repo_relative(path, repo_root),
        scenario_count=int(float(base["scenario_count"])),
        checked_metric_count=checked,
        max_abs_delta=round(max_abs, 12),
        nonzero_metrics=tuple(nonzero),
    )


def _family_from_path(path: Path) -> str:
    name = path.name
    prefix = "cq_pending_multi_evidence_"
    suffixes = ["_mixed_metrics.csv", "_frozen_metrics.csv", "_metrics.csv"]
    if not name.startswith(prefix):
        raise ValueError("Unexpected CQ-Multi metrics filename: {}".format(name))
    family = name[len(prefix) :]
    for suffix in suffixes:
        if family.endswith(suffix):
            return family[: -len(suffix)]
    raise ValueError("Unexpected CQ-Multi metrics filename: {}".format(name))


def _maybe_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _latex_table(rows: Sequence[FamilyDelta]) -> str:
    body = []
    for row in rows:
        body.append(
            "{} & {} & {} & {} & {} \\\\".format(
                _latex_escape(FAMILY_DISPLAY_NAMES.get(row.family, row.family.replace("_", " "))),
                row.scenario_count,
                row.checked_metric_count,
                _format_delta(row.max_abs_delta),
                _latex_escape(", ".join(row.nonzero_metrics) if row.nonzero_metrics else "none"),
            )
        )
    max_delta = max((row.max_abs_delta for row in rows), default=0.0)
    body_text = "\n".join(body)
    max_delta_text = _format_delta(max_delta)
    return f"""% Generated by scripts/build_cqmulti_per_row_regression_table.py.
\\begin{{table}}[h]
\\centering
\\caption{{CQ-Multi internal regression replay over aggregate policy rows.}}
\\label{{tab:cqmulti-regression}}
\\small
\\begin{{tabular}}{{lrrrr}}
\\toprule
Family & Scenarios & Checked metrics & Max $|\\Delta|$ & Non-zero deltas \\\\
\\midrule
{body_text}
\\bottomrule
\\end{{tabular}}
\\vspace{{2pt}}
\\begin{{minipage}}{{0.92\\linewidth}}
\\footnotesize
The aggregate maximum checked overall delta is {max_delta_text}. The committed CQ-Multi
CSV artifacts contain policy-summary rows, so this table reports per-family
overall deltas only; no per-scenario confidence intervals are inferred from
these aggregate files.
\\end{{minipage}}
\\end{{table}}
"""


def _format_delta(value: float) -> str:
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return "0.000000"
    return "{:.6f}".format(value)


def _latex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("_", r"\_")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("#", r"\#")
    )


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--input-glob", default=DEFAULT_INPUT_GLOB)
    parser.add_argument("--tex-output", default=DEFAULT_TEX)
    parser.add_argument("--json-output", default=DEFAULT_JSON)
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    paths = sorted(repo_root.glob(args.input_glob))
    if not paths:
        raise SystemExit("No CQ-Multi metrics files matched {}".format(args.input_glob))
    rows = build_rows(paths, repo_root=repo_root)
    write_outputs(
        rows,
        tex_path=repo_root / args.tex_output,
        json_path=repo_root / args.json_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
