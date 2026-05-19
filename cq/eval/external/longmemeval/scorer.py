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
    expected_case_ids: Iterable[str] | None = None,
    ks: Sequence[int] = DEFAULT_K,
    bootstrap_seed: int = 1729,
    bootstrap_samples: int = 5000,
) -> dict[str, Any]:
    gold_by_case = {case.case_id: case for case in gold_cases}
    expected_ids = _expected_case_id_set(
        expected_case_ids if expected_case_ids is not None else gold_by_case
    )
    predictions_list = list(predictions)
    _validate_exact_prediction_denominator(predictions_list, expected_ids, gold_by_case)

    rows = []
    for prediction in predictions_list:
        gold = gold_by_case[prediction.case_id]
        rows.append(_score_row(prediction, gold, ks))
    return {
        "rows": rows,
        "summary": _summarize(
            rows,
            ks=ks,
            missing_gold=[],
            expected_case_ids=expected_ids,
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
    expected_case_ids: set[str],
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
        "expected_case_count": len(expected_case_ids),
        "policy_count": len({str(row["policy_name"]) for row in rows}),
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


def _expected_case_id_set(case_ids: Iterable[str]) -> set[str]:
    expected = {str(case_id) for case_id in case_ids if str(case_id)}
    if not expected:
        raise ValueError("Expected case denominator is empty")
    return expected


def _validate_exact_prediction_denominator(
    predictions: Sequence[PolicyPrediction],
    expected_case_ids: set[str],
    gold_by_case: Mapping[str, GoldCase],
) -> None:
    missing_gold = sorted(case_id for case_id in expected_case_ids if case_id not in gold_by_case)
    predictions_by_policy: dict[str, set[str]] = defaultdict(set)
    duplicate_keys = []
    unexpected_case_ids = []
    for prediction in predictions:
        if prediction.case_id in predictions_by_policy[prediction.policy_name]:
            duplicate_keys.append("{}:{}".format(prediction.policy_name, prediction.case_id))
        predictions_by_policy[prediction.policy_name].add(prediction.case_id)
        if prediction.case_id not in expected_case_ids:
            unexpected_case_ids.append("{}:{}".format(prediction.policy_name, prediction.case_id))
    missing_predictions = {
        policy_name: sorted(expected_case_ids - case_ids)
        for policy_name, case_ids in sorted(predictions_by_policy.items())
        if expected_case_ids - case_ids
    }
    if expected_case_ids and not predictions_by_policy:
        missing_predictions["<no-policy>"] = sorted(expected_case_ids)

    errors = []
    if missing_gold:
        errors.append("expected cases missing gold: {}".format(", ".join(missing_gold[:10])))
    if duplicate_keys:
        errors.append("duplicate predictions: {}".format(", ".join(sorted(duplicate_keys)[:10])))
    if unexpected_case_ids:
        errors.append(
            "predictions outside expected denominator: {}".format(
                ", ".join(sorted(unexpected_case_ids)[:10])
            )
        )
    if missing_predictions:
        rendered = [
            "{} missing {}".format(policy_name, ", ".join(case_ids[:10]))
            for policy_name, case_ids in missing_predictions.items()
        ]
        errors.append("incomplete predictions by policy: {}".format("; ".join(rendered[:10])))
    if errors:
        raise ValueError("LongMemEval PFLC denominator check failed: {}".format(" | ".join(errors)))


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
    low_idx = _percentile_index(samples, 0.025)
    high_idx = _percentile_index(samples, 0.975)
    return {"estimate": observed, "low": draws[low_idx], "high": draws[high_idx]}


def _percentile_index(samples: int, quantile: float) -> int:
    if samples <= 0:
        raise ValueError("samples must be positive")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    return int(quantile * (samples - 1))


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
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("Prediction rows must be objects")
        case_id = _required_prediction_text(row, "case_id", row_index)
        policy_name = _required_prediction_text(row, "policy_name", row_index)
        ranked = row.get("predicted_session_ids_ranked")
        if not isinstance(ranked, list) or any(not isinstance(item, str) for item in ranked):
            raise ValueError(
                "Prediction row {} must include predicted_session_ids_ranked as a list of strings".format(
                    row_index
                )
            )
        answer_correct = row.get("answer_correct")
        if not isinstance(answer_correct, bool):
            raise ValueError("Prediction row {} answer_correct must be boolean".format(row_index))
        candidate_answer = row.get("candidate_answer")
        if candidate_answer is None:
            candidate_answer = ""
        if not isinstance(candidate_answer, str):
            raise ValueError("Prediction row {} candidate_answer must be a string".format(row_index))
        parsed.append(
            PolicyPrediction(
                case_id=case_id,
                policy_name=policy_name,
                predicted_session_ids_ranked=list(ranked),
                candidate_answer=candidate_answer,
                answer_correct=answer_correct,
            )
        )
    return parsed


def _required_prediction_text(row: Mapping[str, Any], key: str, row_index: int) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Prediction row {} must include non-empty string {}".format(row_index, key))
    return value
