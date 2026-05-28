#!/usr/bin/env python3
"""Compute a scorer-layer random-readout floor for LongMemEval all-hit.

The existing LongMemEval transfer rows expose per-policy predicted session ids
and the gold evidence count. This script builds a per-case unique session-id
pool from those committed rows, computes the closed-form probability that a
random readout of size r contains every gold evidence id, and validates the
closed form with seeded scorer-layer sampling. The calculation is policy-free:
it reads transfer artifacts only and never executes a memory policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence


DEFAULT_ROWS = "data/external/longmemeval/transfer_per_case_rows.csv"
DEFAULT_JSON = "data/external/longmemeval/all_hit_random_floor.json"
DEFAULT_TEX = "paper/figures/all_hit_random_floor.tex"
DEFAULT_SEEDS = (0, 1, 2, 3, 4)


@dataclass(frozen=True)
class CasePool:
    cell_id: str
    case_id: str
    pool: tuple[str, ...]
    gold_evidence_count: int


@dataclass(frozen=True)
class CellFloor:
    cell_id: str
    case_count: int
    mean_unique_session_pool: float
    mean_gold_evidence_count: float
    analytic_readout_1: float
    analytic_readout_2: float
    empirical_readout_2_mean: float
    empirical_readout_2_low: float
    empirical_readout_2_high: float
    analytic_empirical_abs_delta: float
    under_observed_pool_cases: int


def load_case_pools(rows_path: Path) -> list[CasePool]:
    groups: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {"session_ids": set(), "gold_counts": set()}
    )
    with rows_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (str(row["cell_id"]), str(row["case_id"]))
            group = groups[key]
            group["session_ids"].update(_json_string_list(row["predicted_session_ids_ranked"]))
            group["gold_counts"].add(int(row["gold_evidence_count"]))

    pools = []
    for (cell_id, case_id), group in sorted(groups.items()):
        gold_counts = group["gold_counts"]
        if len(gold_counts) != 1:
            raise ValueError(
                "Inconsistent gold_evidence_count for {} / {}: {}".format(
                    cell_id,
                    case_id,
                    sorted(gold_counts),
                )
            )
        pools.append(
            CasePool(
                cell_id=cell_id,
                case_id=case_id,
                pool=tuple(sorted(group["session_ids"])),
                gold_evidence_count=next(iter(gold_counts)),
            )
        )
    return pools


def summarize(pools: Iterable[CasePool], *, seeds: Sequence[int]) -> list[CellFloor]:
    by_cell: dict[str, list[CasePool]] = defaultdict(list)
    for pool in pools:
        by_cell[pool.cell_id].append(pool)

    summaries = []
    for cell_id, cell_pools in sorted(by_cell.items()):
        analytic_r1 = [_closed_form_all_hit(len(pool.pool), pool.gold_evidence_count, 1) for pool in cell_pools]
        analytic_r2 = [_closed_form_all_hit(len(pool.pool), pool.gold_evidence_count, 2) for pool in cell_pools]
        seed_rates = [
            _seeded_sample_rate(cell_pools, seed=seed, readout_size=2)
            for seed in seeds
        ]
        summaries.append(
            CellFloor(
                cell_id=cell_id,
                case_count=len(cell_pools),
                mean_unique_session_pool=mean(len(pool.pool) for pool in cell_pools),
                mean_gold_evidence_count=mean(pool.gold_evidence_count for pool in cell_pools),
                analytic_readout_1=mean(analytic_r1),
                analytic_readout_2=mean(analytic_r2),
                empirical_readout_2_mean=mean(seed_rates),
                empirical_readout_2_low=min(seed_rates),
                empirical_readout_2_high=max(seed_rates),
                analytic_empirical_abs_delta=abs(mean(analytic_r2) - mean(seed_rates)),
                under_observed_pool_cases=sum(
                    1 for pool in cell_pools if len(pool.pool) < pool.gold_evidence_count
                ),
            )
        )
    return summaries


def write_outputs(
    summaries: Sequence[CellFloor],
    *,
    repo_root: Path,
    rows_path: Path,
    json_path: Path,
    tex_path: Path,
    seeds: Sequence[int],
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_rows": _repo_relative(rows_path, repo_root),
        "unit": "unique LongMemEval session ids",
        "gold_identity_note": (
            "Seeded validation uses an arbitrary fixed gold subset of size "
            "gold_evidence_count within each case pool; the all-hit probability "
            "depends only on n, g, and readout size."
        ),
        "seeds": list(seeds),
        "cells": [
            {
                "cell_id": summary.cell_id,
                "case_count": summary.case_count,
                "mean_unique_session_pool": summary.mean_unique_session_pool,
                "mean_gold_evidence_count": summary.mean_gold_evidence_count,
                "analytic_readout_1": summary.analytic_readout_1,
                "analytic_readout_2": summary.analytic_readout_2,
                "empirical_readout_2_mean": summary.empirical_readout_2_mean,
                "empirical_readout_2_low": summary.empirical_readout_2_low,
                "empirical_readout_2_high": summary.empirical_readout_2_high,
                "analytic_empirical_abs_delta": summary.analytic_empirical_abs_delta,
                "under_observed_pool_cases": summary.under_observed_pool_cases,
            }
            for summary in summaries
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tex_path.write_text(_latex_table(summaries), encoding="utf-8")


def _json_string_list(value: str) -> list[str]:
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("Expected JSON list of strings, got {}".format(value))
    return parsed


def _closed_form_all_hit(pool_size: int, gold_count: int, readout_size: int) -> float:
    if gold_count <= 0 or pool_size <= 0:
        return 0.0
    if pool_size < gold_count:
        return 0.0
    r = min(readout_size, pool_size)
    if gold_count > r:
        return 0.0
    return math.comb(pool_size - gold_count, r - gold_count) / math.comb(pool_size, r)


def _seeded_sample_rate(pools: Sequence[CasePool], *, seed: int, readout_size: int) -> float:
    rng = random.Random(seed)
    hits = 0
    denominator = 0
    for pool in pools:
        if not pool.pool or pool.gold_evidence_count <= 0:
            continue
        denominator += 1
        gold = set(pool.pool[: pool.gold_evidence_count])
        r = min(readout_size, len(pool.pool))
        predicted = set(rng.sample(list(pool.pool), r))
        if gold <= predicted:
            hits += 1
    return hits / denominator if denominator else 0.0


def _latex_table(summaries: Sequence[CellFloor]) -> str:
    rows = []
    for summary in summaries:
        rows.append(
            "{} & {} & {:.2f} & {:.2f} & {} & {} & {}--{} \\\\".format(
                _latex_escape(summary.cell_id),
                summary.case_count,
                summary.mean_unique_session_pool,
                summary.mean_gold_evidence_count,
                _pct(summary.analytic_readout_1),
                _pct(summary.analytic_readout_2),
                _pct(summary.empirical_readout_2_low),
                _pct(summary.empirical_readout_2_high),
            )
        )
    body_text = "\n".join(rows)
    return f"""% Generated by scripts/compute_all_hit_at_50_random_floor.py.
\\begin{{table}}[h]
\\centering
\\caption{{Scorer-only random-readout floor for LongMemEval \\code{{all_hit_at_50}}.}}
\\label{{tab:all-hit-random-floor}}
\\small
\\resizebox{{\\linewidth}}{{!}}{{%
\\begin{{tabular}}{{lrrrrrr}}
\\toprule
Cell & Cases & Mean pool & Mean gold & Random $r{{=}}1$ & Random $r{{=}}2$ & 5-seed $r{{=}}2$ band \\\\
\\midrule
{body_text}
\\bottomrule
\\end{{tabular}}
}}
\\end{{table}}
"""


def _pct(value: float) -> str:
    return "{:.1f}\\%".format(value * 100.0)


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
    parser.add_argument("--rows", default=DEFAULT_ROWS)
    parser.add_argument("--json-output", default=DEFAULT_JSON)
    parser.add_argument("--tex-output", default=DEFAULT_TEX)
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in DEFAULT_SEEDS))
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    seeds = tuple(int(seed) for seed in str(args.seeds).split(",") if seed != "")
    if not seeds:
        raise SystemExit("At least one seed is required")
    rows_path = repo_root / args.rows
    summaries = summarize(load_case_pools(rows_path), seeds=seeds)
    write_outputs(
        summaries,
        repo_root=repo_root,
        rows_path=rows_path,
        json_path=repo_root / args.json_output,
        tex_path=repo_root / args.tex_output,
        seeds=seeds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
