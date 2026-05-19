"""Dialog-evidence-id PFLC scorer for LongMemEval externalization.

This scorer implements the primary PFLC target locked in preregistration §6:
dialog-evidence-id PFLC keyed on ``answer_session_ids`` from the LongMemEval
oracle split, with cutoffs ``k = 1, 5, 10, 20, 50``.

Mirrors ``scripts/score_locomo_amb_pflc.py`` for math (Wilson CIs, paired
bootstrap, joint counts) and structure. The differences:

- Input is a typed ``PolicyPrediction`` payload (one ranked list of session
  IDs per case plus a candidate answer + correctness flag), not the AMB
  context-derived ``dia_id`` parse.
- Gold is loaded from ``gold_loader.GoldCase``; the scorer never reads
  ``answer_session_ids`` directly from the oracle JSON to keep the gold-side
  boundary clean.
- The scorer ships a degeneracy diagnostic that records when
  ``gold == haystack`` (always true on the LongMemEval oracle split), so the
  Phase X.5 writeup can frame PFLC@k accurately as a scope/policy-discrimination
  metric rather than a retrieval-quality metric on this anchor.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence, Union

from cq.eval.external.longmemeval.gold_loader import GoldCase


DEFAULT_K = (1, 5, 10, 20, 50)


@dataclass(frozen=True)
class PolicyPrediction:
    case_id: str
    policy_name: str
    predicted_session_ids_ranked: list[str]
    candidate_answer: str
    answer_correct: bool


def score_predictions(
    predictions: Iterable[PolicyPrediction],
    gold_cases: Iterable[GoldCase],
    *,
    ks: Sequence[int] = DEFAULT_K,
    bootstrap_seed: int = 1729,
    bootstrap_samples: int = 5000,
) -> dict[str, Any]:
    gold_by_case = {case.case_id: case for case in gold_cases}
    rows = []
    missing_gold: list[str] = []
    for prediction in predictions:
        gold = gold_by_case.get(prediction.case_id)
        if gold is None:
            missing_gold.append(prediction.case_id)
            continue
        rows.append(_score_row(prediction, gold, ks))
    return {
        "rows": rows,
        "summary": _summarize(
            rows,
            ks=ks,
            missing_gold=missing_gold,
            bootstrap_seed=bootstrap_seed,
            bootstrap_samples=bootstrap_samples,
        ),
    }


def degeneracy_diagnostic(gold_cases: Iterable[GoldCase]) -> dict[str, Any]:
    """Record how often ``answer_session_ids`` equals ``haystack_session_ids``.

    On the LongMemEval oracle split these sets coincide for every
    ``knowledge-update`` case because the oracle split exposes only the
    evidence sessions. The diagnostic surfaces that property explicitly so
    PFLC@k is read as a scope-filter metric (did the policy preserve evidence
    it had access to) rather than a retrieval-quality metric.
    """

    cases = list(gold_cases)
    if not cases:
        return {
            "total_cases": 0,
            "answer_equals_haystack_case_count": 0,
            "answer_equals_haystack_rate": 0.0,
            "by_question_type": {},
        }
    by_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "answer_equals_haystack": 0}
    )
    equal_count = 0
    for case in cases:
        answer_set = set(case.answer_session_ids)
        haystack_set = set(case.haystack_session_ids)
        same = bool(answer_set) and answer_set == haystack_set
        equal_count += int(same)
        bucket = by_type[case.question_type]
        bucket["total"] += 1
        if same:
            bucket["answer_equals_haystack"] += 1
    return {
        "total_cases": len(cases),
        "answer_equals_haystack_case_count": equal_count,
        "answer_equals_haystack_rate": equal_count / len(cases),
        "by_question_type": {
            question_type: dict(counts) for question_type, counts in sorted(by_type.items())
        },
    }


def _score_row(
    prediction: PolicyPrediction,
    gold: GoldCase,
    ks: Sequence[int],
) -> dict[str, Any]:
    gold_set = set(gold.answer_session_ids)
    ranked = list(prediction.predicted_session_ids_ranked)
    haystack_set = set(gold.haystack_session_ids)

    all_retrieved_set = set(ranked)
    row: dict[str, Any] = {
        "case_id": gold.case_id,
        "policy_name": prediction.policy_name,
        "question_type": gold.question_type,
        "answer_correct": bool(prediction.answer_correct),
        "candidate_answer": prediction.candidate_answer,
        "gold_evidence_count": len(gold_set),
        "lookup_relevant": bool(gold_set),
        "predicted_session_count": len(ranked),
        "any_hit_all_context": bool(gold_set & all_retrieved_set),
        "all_hit_all_context": bool(gold_set) and gold_set <= all_retrieved_set,
        "first_gold_rank": _first_gold_rank(ranked, gold_set),
        "answer_equals_haystack": bool(gold_set) and gold_set == haystack_set,
    }
    for k in ks:
        ids_at_k = set(ranked[:k])
        row["any_hit_at_{}".format(k)] = bool(gold_set & ids_at_k)
        row["all_hit_at_{}".format(k)] = bool(gold_set) and gold_set <= ids_at_k
    return row


def _first_gold_rank(ranked: Sequence[str], gold_set: set[str]) -> int | None:
    for index, session_id in enumerate(ranked, start=1):
        if session_id in gold_set:
            return index
    return None


def _summarize(
    rows: Sequence[Mapping[str, Any]],
    *,
    ks: Sequence[int],
    missing_gold: Sequence[str],
    bootstrap_seed: int,
    bootstrap_samples: int,
) -> dict[str, Any]:
    total = len(rows)
    lookup_rows = [row for row in rows if row["lookup_relevant"]]
    lookup_total = len(lookup_rows)
    metrics: dict[str, Any] = {
        "answer_accuracy_all_rows": _wilson(
            sum(1 for row in rows if row["answer_correct"]),
            total,
        ),
        "answer_accuracy_lookup_relevant": _wilson(
            sum(1 for row in lookup_rows if row["answer_correct"]),
            lookup_total,
        ),
    }
    for suffix in ["all_context", *["at_{}".format(k) for k in ks]]:
        for mode in ("any_hit", "all_hit"):
            key = "{}_{}".format(mode, suffix)
            metrics[key] = _wilson(
                sum(1 for row in lookup_rows if row[key]),
                lookup_total,
            )
            metrics["answer_minus_{}_paired_bootstrap".format(key)] = _bootstrap_gap(
                lookup_rows,
                key,
                seed=bootstrap_seed,
                samples=bootstrap_samples,
            )
    joint_at_50 = _joint_counts(lookup_rows, "all_hit_at_50") if 50 in ks else {}
    metrics["joint_counts_at_50"] = joint_at_50
    metrics["joint_counts_all_context"] = _joint_counts(lookup_rows, "all_hit_all_context")

    by_question_type: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in lookup_rows:
        by_question_type[str(row["question_type"])].append(row)

    per_type_summary = {}
    for question_type, type_rows in sorted(by_question_type.items()):
        type_total = len(type_rows)
        per_type_summary[question_type] = {
            "rows": type_total,
            "answer_accuracy": _wilson(
                sum(1 for row in type_rows if row["answer_correct"]),
                type_total,
            ),
            "any_hit_at_50": _wilson(
                sum(1 for row in type_rows if row["any_hit_at_50"]),
                type_total,
            )
            if 50 in ks
            else None,
            "all_hit_at_50": _wilson(
                sum(1 for row in type_rows if row["all_hit_at_50"]),
                type_total,
            )
            if 50 in ks
            else None,
        }

    return {
        "scored_rows": total,
        "lookup_relevant_rows": lookup_total,
        "missing_gold_case_ids": list(missing_gold)[:20],
        "missing_gold_case_count": len(list(missing_gold)),
        "ks": list(ks),
        "predicted_session_count_distribution": _distribution(
            [int(row["predicted_session_count"]) for row in rows]
        ),
        "first_gold_rank_distribution": _distribution(
            [int(row["first_gold_rank"]) for row in rows if row.get("first_gold_rank") is not None]
        ),
        "metrics": metrics,
        "by_question_type": per_type_summary,
    }


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, float]:
    if total <= 0:
        return {"estimate": 0.0, "low": 0.0, "high": 0.0}
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return {"estimate": p, "low": max(0.0, center - half), "high": min(1.0, center + half)}


def _bootstrap_gap(
    rows: Sequence[Mapping[str, Any]],
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
    draws = []
    for _ in range(samples):
        draws.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    draws.sort()
    low_idx = max(0, int(0.025 * samples) - 1)
    high_idx = min(samples - 1, int(0.975 * samples) - 1)
    return {"estimate": observed, "low": draws[low_idx], "high": draws[high_idx]}


def _joint_counts(rows: Sequence[Mapping[str, Any]], metric: str) -> dict[str, int]:
    return {
        "answer_correct_and_pflc_hit": sum(1 for row in rows if row["answer_correct"] and row[metric]),
        "answer_correct_and_pflc_miss": sum(
            1 for row in rows if row["answer_correct"] and not row[metric]
        ),
        "answer_wrong_and_pflc_hit": sum(
            1 for row in rows if not row["answer_correct"] and row[metric]
        ),
        "answer_wrong_and_pflc_miss": sum(
            1 for row in rows if not row["answer_correct"] and not row[metric]
        ),
    }


def _distribution(values: Sequence[int]) -> dict[str, float]:
    if not values:
        return {"min": 0, "median": 0, "max": 0}
    return {"min": min(values), "median": float(median(values)), "max": max(values)}


def load_policy_predictions(path: Union[str, Path]) -> list[PolicyPrediction]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("predictions") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Expected predictions list in {}".format(path))
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Prediction rows must be objects")
        parsed.append(
            PolicyPrediction(
                case_id=str(row.get("case_id") or ""),
                policy_name=str(row.get("policy_name") or ""),
                predicted_session_ids_ranked=[
                    str(item) for item in (row.get("predicted_session_ids_ranked") or [])
                ],
                candidate_answer=str(row.get("candidate_answer") or ""),
                answer_correct=bool(row.get("answer_correct")),
            )
        )
    return parsed
