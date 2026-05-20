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


METHOD_ID = "path_b_question_rewrite_v2"
DENOMINATOR_LABEL = "contradiction_edge"
SCOPE_LEVEL = "user_global"
SCOPE_KEY = "longmemeval:user"
CLAIM_TYPE = "world_fact"

_CANONICAL_REMOVAL_PATTERNS = (
    r"\b(?:a|about|after|am|an|and|are|current|currently|did|do|does)\b",
    r"\b(?:for|from|had|have|how|i|in|is|latest|many|me|my|of|on)\b",
    r"\b(?:recent|recently|the|to|was|were|what|when|where|which|who|with)\b",
)


def annotate_cases(
    cases: Iterable[RedactedLongMemEvalCase],
    denominator_ids: set[str],
    *,
    case_limit: Optional[int] = None,
) -> dict[str, Any]:
    selected = [case for case in cases if case.case_id in denominator_ids]
    selected.sort(key=lambda case: case.case_id)
    if case_limit is not None:
        selected = selected[:case_limit]
    annotations = [_annotation_for_case(case) for case in selected]
    return {
        "annotation_path": "B",
        "method_id": METHOD_ID,
        "source_contract": "redacted_longmemeval_v1_oracle",
        "denominator_code": DENOMINATOR_LABEL,
        "annotations": annotations,
        "summary": {
            "annotation_count": len(annotations),
            "in_denominator_count": sum(1 for row in annotations if row["in_denominator"]),
            "scope_levels": sorted({row["scope_level"] for row in annotations}),
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


def _annotation_for_case(case: RedactedLongMemEvalCase) -> dict[str, Any]:
    slot_id = lookup_slot_id(case.question)
    events = _events_from_sessions(case, slot_id)
    return {
        "case_id": case.case_id,
        "question_type": case.question_type,
        "question": case.question,
        "in_denominator": True,
        "mechanism_code": DENOMINATOR_LABEL,
        "relevant_canonical_id": slot_id,
        "scope_level": SCOPE_LEVEL,
        "scope_key": SCOPE_KEY,
        "claim_type": CLAIM_TYPE,
        "contradiction_edges": [],
        "candidate_events": events,
    }


def lookup_slot_id(question_text: str) -> str:
    focus = re.split(r"[?!.]", question_text.lower(), maxsplit=1)[0]
    focus = re.sub(r"\b(?:tell|remind|mark|final|answer)\b.*$", "", focus)
    for pattern in _CANONICAL_REMOVAL_PATTERNS:
        focus = re.sub(pattern, " ", focus)
    tokens = [token for token in re.findall(r"[a-z0-9]+", focus) if len(token) > 1]
    return "lme-" + ("-".join(tokens[:12]) or "memory-slot")


def _events_from_sessions(case: RedactedLongMemEvalCase, slot_id: str) -> list[dict[str, Any]]:
    events = []
    session_ids = list(case.haystack_session_ids or [])
    dates = list(case.haystack_dates or [])
    for session_index, session in enumerate(case.haystack_sessions or []):
        event_id = "obs_{}".format(session_index)
        selected_turn, selected_claim = _latest_question_overlap_turn(case.question, session)
        events.append(
            {
                "event_id": event_id,
                "session_id": _value_at(session_ids, session_index),
                "session_index": session_index,
                "session_date": _value_at(dates, session_index),
                "turn_index": selected_turn,
                "raw_claim": selected_claim,
                "canonical_id": slot_id,
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


def _latest_question_overlap_turn(question: str, session: Any) -> tuple[int, str]:
    turns = session if isinstance(session, list) else []
    markers = set(_surface_markers(question))
    choice = (0, "")
    choice_score = -1
    for turn_index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        content = str(turn.get("content") or "")
        overlap = len(markers & set(_surface_markers(content)))
        score = overlap * 10 + turn_index
        if score > choice_score:
            choice_score = score
            choice = (turn_index, re.sub(r"\s+", " ", content).strip())
    return choice


def _surface_markers(text: str) -> list[str]:
    markers = []
    for token in re.findall(r"[A-Za-z0-9]+", text):
        if len(token) >= 4 or any(character.isdigit() for character in token):
            markers.append(token.lower())
    return markers


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build LongMemEval annotation path B.")
    parser.add_argument("--oracle-json", required=True, help="LongMemEval oracle JSON/JSONL path.")
    parser.add_argument(
        "--feasibility-csv",
        required=True,
        help="Committed LongMemEval feasibility coding CSV.",
    )
    parser.add_argument("--output-json", required=True, help="Output annotation JSON path.")
    parser.add_argument("--case-limit", type=int, help="Optional case limit for smoke tests.")
    args = parser.parse_args(argv)
    write_json(
        args.output_json,
        annotate_cases(
            load_redacted_cases(args.oracle_json),
            load_denominator_ids(args.feasibility_csv),
            case_limit=args.case_limit,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
