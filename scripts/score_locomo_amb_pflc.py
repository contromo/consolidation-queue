"""Score LoCoMo dialog-evidence PFLC from Agent Memory Benchmark run output.

The AMB LoCoMo run artifacts publish per-question injected context strings.
Those strings contain source snippets with original LoCoMo ``dia_id`` values.
This script treats those context-emitted ``dia_id`` values as the system-side
lookup handle and compares them with LoCoMo's gold ``qa[].evidence`` field.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any


DEFAULT_K = (1, 5, 10, 20, 50, 200)
DIA_ID_RE = re.compile(r'"dia_id"\s*:\s*"([^"]+)"')
MEMORY_BLOCK_RE = re.compile(r"(?:^|\n)## Memory \d+\n")
QUERY_ID_RE = re.compile(r"^(?P<sample>.+)_q(?P<idx>\d+)$")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json_or_gzip(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path.read_text(encoding="utf-8"))


def _memory_blocks(context: str) -> list[str]:
    starts = [m.start() for m in MEMORY_BLOCK_RE.finditer(context)]
    if not starts:
        return [context] if context else []
    starts.append(len(context))
    return [context[a:b] for a, b in zip(starts, starts[1:])]


def _extract_rows(run: dict[str, Any], locomo: list[dict[str, Any]], ks: tuple[int, ...]) -> tuple[list[dict[str, Any]], list[str]]:
    by_sample = {sample["sample_id"]: sample for sample in locomo}
    rows: list[dict[str, Any]] = []
    mismatches: list[str] = []

    for result in run.get("results", []):
        query_id = result["query_id"]
        match = QUERY_ID_RE.match(query_id)
        if not match:
            raise ValueError(f"Unexpected query_id format: {query_id}")

        sample_id = match.group("sample")
        qa_index = int(match.group("idx"))
        qa = by_sample[sample_id]["qa"][qa_index]
        if qa["question"] != result["query"]:
            mismatches.append(query_id)

        gold_evidence = set(qa.get("evidence") or [])
        blocks = _memory_blocks(result.get("context") or "")
        block_ids = [set(DIA_ID_RE.findall(block)) for block in blocks]
        all_retrieved_ids = set().union(*block_ids) if block_ids else set()

        row: dict[str, Any] = {
            "run_name": run.get("run_name"),
            "memory_provider": run.get("memory_provider"),
            "mode": run.get("mode"),
            "query_id": query_id,
            "sample_id": sample_id,
            "qa_index": qa_index,
            "category": qa.get("category"),
            "answer_correct": bool(result.get("correct")),
            "question": result.get("query", ""),
            "gold_answer": " | ".join(str(answer) for answer in (result.get("gold_answers") or [])),
            "gold_evidence_ids": " ".join(sorted(gold_evidence)),
            "gold_evidence_count": len(gold_evidence),
            "retrieved_memory_blocks": len(block_ids),
            "retrieved_dia_id_count": len(all_retrieved_ids),
            "any_hit_all_context": bool(gold_evidence & all_retrieved_ids),
            "all_hit_all_context": gold_evidence <= all_retrieved_ids if gold_evidence else False,
        }

        first_gold_rank: int | None = None
        for idx, ids in enumerate(block_ids, start=1):
            if gold_evidence & ids:
                first_gold_rank = idx
                break
        row["first_gold_memory_block_rank"] = first_gold_rank or ""

        for k in ks:
            ids_at_k = set().union(*block_ids[:k]) if block_ids[:k] else set()
            row[f"any_hit_at_{k}"] = bool(gold_evidence & ids_at_k)
            row[f"all_hit_at_{k}"] = gold_evidence <= ids_at_k if gold_evidence else False

        rows.append(row)

    return rows, mismatches


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, float]:
    if total == 0:
        return {"estimate": 0.0, "low": 0.0, "high": 0.0}
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return {"estimate": p, "low": max(0.0, center - half), "high": min(1.0, center + half)}


def _bootstrap_gap(
    rows: list[dict[str, Any]],
    metric: str,
    *,
    seed: int,
    samples: int,
) -> dict[str, float]:
    rng = random.Random(seed)
    values = [int(row["answer_correct"]) - int(row[metric]) for row in rows]
    n = len(values)
    observed = sum(values) / n if n else 0.0
    if not n or samples <= 0:
        return {"estimate": observed, "low": observed, "high": observed}

    draws: list[float] = []
    for _ in range(samples):
        draws.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    draws.sort()
    low_idx = max(0, int(0.025 * samples) - 1)
    high_idx = min(samples - 1, int(0.975 * samples) - 1)
    return {"estimate": observed, "low": draws[low_idx], "high": draws[high_idx]}


def _summarize_run(
    run: dict[str, Any],
    rows: list[dict[str, Any]],
    mismatches: list[str],
    ks: tuple[int, ...],
    *,
    bootstrap_seed: int,
    bootstrap_samples: int,
) -> dict[str, Any]:
    total = len(rows)
    summary: dict[str, Any] = {
        "run": {
            "run_name": run.get("run_name"),
            "memory_provider": run.get("memory_provider"),
            "mode": run.get("mode"),
            "split": run.get("split"),
            "reported_total_queries": run.get("total_queries"),
            "reported_accuracy": run.get("accuracy"),
            "answer_llm": run.get("answer_llm"),
            "judge_llm": run.get("judge_llm"),
            "avg_context_tokens": run.get("avg_context_tokens"),
            "avg_retrieve_time_ms": run.get("avg_retrieve_time_ms"),
            "ingested_docs": run.get("ingested_docs"),
        },
        "alignment": {
            "scored_rows": total,
            "question_mismatch_count": len(mismatches),
            "question_mismatch_ids": mismatches[:20],
            "zero_gold_evidence_count": sum(row["gold_evidence_count"] == 0 for row in rows),
        },
        "context_parse": {
            "memory_blocks": _distribution([int(row["retrieved_memory_blocks"]) for row in rows]),
            "retrieved_dia_ids": _distribution([int(row["retrieved_dia_id_count"]) for row in rows]),
        },
        "metrics": {},
        "by_category": {},
    }

    metric_summary: dict[str, Any] = summary["metrics"]
    metric_summary["answer_accuracy"] = _wilson(sum(row["answer_correct"] for row in rows), total)

    for suffix in ["all_context", *[f"at_{k}" for k in ks]]:
        for mode in ("any_hit", "all_hit"):
            key = f"{mode}_{suffix}"
            metric_summary[key] = _wilson(sum(row[key] for row in rows), total)
            metric_summary[f"answer_minus_{key}_paired_bootstrap"] = _bootstrap_gap(
                rows,
                key,
                seed=bootstrap_seed,
                samples=bootstrap_samples,
            )

    metric_summary["joint_counts_at_50"] = _joint_counts(rows, "all_hit_at_50")
    metric_summary["joint_counts_all_context"] = _joint_counts(rows, "all_hit_all_context")

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_category[str(row["category"])].append(row)
    for category, cat_rows in sorted(by_category.items(), key=lambda item: item[0]):
        cat_total = len(cat_rows)
        summary["by_category"][category] = {
            "rows": cat_total,
            "answer_accuracy": _wilson(sum(row["answer_correct"] for row in cat_rows), cat_total),
            "all_hit_at_10": _wilson(sum(row["all_hit_at_10"] for row in cat_rows), cat_total),
            "all_hit_at_20": _wilson(sum(row["all_hit_at_20"] for row in cat_rows), cat_total),
            "all_hit_at_50": _wilson(sum(row["all_hit_at_50"] for row in cat_rows), cat_total),
            "any_hit_at_50": _wilson(sum(row["any_hit_at_50"] for row in cat_rows), cat_total),
        }

    return summary


def _distribution(values: list[int]) -> dict[str, float]:
    if not values:
        return {"min": 0, "median": 0, "max": 0}
    return {"min": min(values), "median": median(values), "max": max(values)}


def _joint_counts(rows: list[dict[str, Any]], metric: str) -> dict[str, int]:
    return {
        "answer_correct_and_pflc_hit": sum(row["answer_correct"] and row[metric] for row in rows),
        "answer_correct_and_pflc_miss": sum(row["answer_correct"] and not row[metric] for row in rows),
        "answer_wrong_and_pflc_hit": sum((not row["answer_correct"]) and row[metric] for row in rows),
        "answer_wrong_and_pflc_miss": sum((not row["answer_correct"]) and not row[metric] for row in rows),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locomo-data", required=True, type=Path)
    parser.add_argument("--amb-run", required=True, action="append", type=Path)
    parser.add_argument("--out-csv", required=True, type=Path)
    parser.add_argument("--out-summary", required=True, type=Path)
    parser.add_argument("--source-url", action="append", default=[])
    parser.add_argument("--bootstrap-seed", type=int, default=1729)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--k", type=int, nargs="*", default=list(DEFAULT_K))
    args = parser.parse_args()

    ks = tuple(args.k)
    locomo = _load_json_or_gzip(args.locomo_data)
    all_rows: list[dict[str, Any]] = []
    run_summaries: list[dict[str, Any]] = []

    for run_path in args.amb_run:
        run = _load_json_or_gzip(run_path)
        rows, mismatches = _extract_rows(run, locomo, ks)
        all_rows.extend(rows)
        run_summaries.append(
            {
                "input_path": str(run_path),
                "input_sha256": _sha256(run_path),
                **_summarize_run(
                    run,
                    rows,
                    mismatches,
                    ks,
                    bootstrap_seed=args.bootstrap_seed,
                    bootstrap_samples=args.bootstrap_samples,
                ),
            }
        )

    _write_csv(args.out_csv, all_rows)
    summary = {
        "artifact": "locomo_amb_pflc",
        "artifact_class": "published-output/context-derived",
        "created_utc_date": "2026-05-18",
        "description": (
            "PFLC scoring of public Agent Memory Benchmark LoCoMo run outputs "
            "against LoCoMo qa[].evidence dialog IDs."
        ),
        "source_urls": args.source_url,
        "locomo_data_path": str(args.locomo_data),
        "locomo_data_sha256": _sha256(args.locomo_data),
        "scored_csv_path": str(args.out_csv),
        "scored_csv_sha256": _sha256(args.out_csv),
        "bootstrap_seed": args.bootstrap_seed,
        "bootstrap_samples": args.bootstrap_samples,
        "ks": list(ks),
        "runs": run_summaries,
    }
    args.out_summary.parent.mkdir(parents=True, exist_ok=True)
    args.out_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
