from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from cq.eval.external.longmemeval.redacted_loader import (
    RedactedLongMemEvalCase,
    load_redacted_cases,
)


METHOD_ID = "path_a_question_slug_v1"
DENOMINATOR_LABEL = "contradiction_edge"
SCOPE_LEVEL = "user_global"
SCOPE_KEY = "longmemeval:user"
CLAIM_TYPE = "world_fact"

_STOPWORDS = {
    "a",
    "about",
    "after",
    "am",
    "an",
    "and",
    "are",
    "current",
    "currently",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "have",
    "how",
    "i",
    "in",
    "is",
    "latest",
    "many",
    "me",
    "my",
    "of",
    "on",
    "recent",
    "recently",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


def annotate_cases(
    cases: Iterable[RedactedLongMemEvalCase],
    denominator_ids: set[str],
    *,
    case_limit: Optional[int] = None,
) -> dict[str, Any]:
    rows = []
    selected = [case for case in cases if case.case_id in denominator_ids]
    selected.sort(key=lambda case: case.case_id)
    if case_limit is not None:
        selected = selected[:case_limit]
    for case in selected:
        rows.append(_annotate_case(case))
    return {
        "annotation_path": "A",
        "method_id": METHOD_ID,
        "source_contract": "redacted_longmemeval_v1_oracle",
        "denominator_code": DENOMINATOR_LABEL,
        "annotations": rows,
        "summary": {
            "annotation_count": len(rows),
            "in_denominator_count": sum(1 for row in rows if row["in_denominator"]),
            "scope_levels": sorted({row["scope_level"] for row in rows}),
        },
    }


def load_denominator_ids(path: str | Path, *, label: str = DENOMINATOR_LABEL) -> set[str]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return {
            row["question_id"]
            for row in csv.DictReader(handle)
            if row.get("label") == label
        }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _annotate_case(case: RedactedLongMemEvalCase) -> dict[str, Any]:
    canonical_id = derive_relevant_canonical_id(case.question)
    candidate_events = _candidate_events(case, canonical_id)
    return {
        "case_id": case.case_id,
        "question_type": case.question_type,
        "question": case.question,
        "in_denominator": True,
        "mechanism_code": DENOMINATOR_LABEL,
        "relevant_canonical_id": canonical_id,
        "scope_level": SCOPE_LEVEL,
        "scope_key": SCOPE_KEY,
        "claim_type": CLAIM_TYPE,
        "contradiction_edges": [],
        "candidate_events": candidate_events,
    }


def derive_relevant_canonical_id(question: str) -> str:
    focus = question.split("?")[0]
    focus = re.sub(r"\b(?:tell|remind|mark|final|answer)\b.*$", "", focus, flags=re.I)
    tokens = []
    for token in re.findall(r"[A-Za-z0-9]+", focus.lower()):
        if token not in _STOPWORDS and len(token) > 1:
            tokens.append(token)
    return "lme-" + ("-".join(tokens[:12]) or "memory-slot")


def _candidate_events(case: RedactedLongMemEvalCase, canonical_id: str) -> list[dict[str, Any]]:
    session_ids = list(case.haystack_session_ids or [])
    dates = list(case.haystack_dates or [])
    sessions = list(case.haystack_sessions or [])
    events = []
    for index, session in enumerate(sessions):
        turn_index, claim = _select_claim_turn(case.question, session)
        event_id = "obs_{}".format(index)
        events.append(
            {
                "event_id": event_id,
                "session_id": _value_at(session_ids, index),
                "session_index": index,
                "session_date": _value_at(dates, index),
                "turn_index": turn_index,
                "raw_claim": claim,
                "canonical_id": canonical_id,
                "claim_type": CLAIM_TYPE,
                "scope_level": SCOPE_LEVEL,
                "scope_key": SCOPE_KEY,
                "confidence": 0.70,
                "contradicts_event_ids": [],
            }
        )
    return events


def _value_at(values: list[Any], index: int) -> str:
    return str(values[index]) if index < len(values) else ""


def _select_claim_turn(question: str, session: Any) -> tuple[int, str]:
    turns = session if isinstance(session, list) else []
    query_terms = {
        token
        for token in re.findall(r"[A-Za-z0-9]+", question.lower())
        if token not in _STOPWORDS and len(token) > 2
    }
    best_index = 0
    best_score = -1
    best_text = ""
    for index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        text = str(turn.get("content") or "")
        role = str(turn.get("role") or "")
        score = sum(1 for term in query_terms if term in text.lower())
        if role == "user":
            score += 1
        if score > best_score:
            best_index = index
            best_score = score
            best_text = text
    return best_index, _collapse(best_text)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build LongMemEval annotation path A.")
    parser.add_argument("--oracle-json", required=True, help="LongMemEval oracle JSON/JSONL path.")
    parser.add_argument(
        "--feasibility-csv",
        required=True,
        help="Committed LongMemEval feasibility coding CSV.",
    )
    parser.add_argument("--output-json", required=True, help="Output annotation JSON path.")
    parser.add_argument("--case-limit", type=int, help="Optional case limit for smoke tests.")
    args = parser.parse_args(argv)
    payload = annotate_cases(
        load_redacted_cases(args.oracle_json),
        load_denominator_ids(args.feasibility_csv),
        case_limit=args.case_limit,
    )
    write_json(args.output_json, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
