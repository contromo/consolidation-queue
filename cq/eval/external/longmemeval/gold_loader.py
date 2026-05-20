"""Scoring-only access to LongMemEval gold ``answer_session_ids``.

This module exposes the gold dialog-evidence ID target needed for PFLC scoring
and judge calibration. It is the ONLY licensed gold-side reader in this
externalization workstream.

Strict scoping rules — preregistration §1 invariants:

- Importable from scorer (``cq.eval.external.longmemeval.scorer``), judge
  stability (``cq.eval.external.longmemeval.judge_stability``), and the
  scoring-side LongMemEval calibration/transfer helpers only.
- MUST NOT be imported by ``annotator_path_a``, ``annotator_path_b``,
  ``dual_path_audit``, ``verifier``, ``redacted_loader``, ``adapter``, or any
  policy code.
- A test (``tests/test_longmemeval_external_gold_loader.py``) enforces the
  import-graph contract.

The hidden-answer protocol forbids feeding ``answer_session_ids`` into policy
input or annotation logic. Scoring-side use against policy outputs is the
licensed path the preregistration §6 PFLC target depends on.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Union


@dataclass(frozen=True)
class GoldCase:
    case_id: str
    question_type: str
    question: str
    answer: str
    answer_session_ids: list[str]
    haystack_session_ids: list[str]


def load_gold_cases(path: Union[str, Path]) -> List[GoldCase]:
    """Load LongMemEval oracle cases with gold fields intact for scoring."""

    records = _load_records(Path(path))
    cases = []
    for row in records:
        case_id = str(row.get("question_id") or row.get("id") or "")
        if not case_id:
            raise ValueError("Gold row missing question_id/id in {}".format(path))
        answer_session_ids = _string_list(row.get("answer_session_ids"))
        haystack_session_ids = _string_list(row.get("haystack_session_ids"))
        cases.append(
            GoldCase(
                case_id=case_id,
                question_type=str(row.get("question_type") or ""),
                question=str(row.get("question") or ""),
                answer=str(row.get("answer") or ""),
                answer_session_ids=answer_session_ids,
                haystack_session_ids=haystack_session_ids,
            )
        )
    return cases


def gold_session_ids_by_case_id(
    cases: Iterable[GoldCase],
    *,
    restrict_to: Optional[Iterable[str]] = None,
) -> dict[str, list[str]]:
    allowed = set(restrict_to) if restrict_to is not None else None
    return {
        case.case_id: list(case.answer_session_ids)
        for case in cases
        if allowed is None or case.case_id in allowed
    }


def gold_answers_by_case_id(
    cases: Iterable[GoldCase],
    *,
    restrict_to: Optional[Iterable[str]] = None,
) -> dict[str, str]:
    allowed = set(restrict_to) if restrict_to is not None else None
    return {
        case.case_id: case.answer
        for case in cases
        if allowed is None or case.case_id in allowed
    }


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Expected list, got {}".format(type(value).__name__))
    return [str(item) for item in value]


def _load_records(path: Path) -> list[Mapping[str, object]]:
    text = _read_text(path)
    stripped = text.lstrip()
    if not stripped:
        return []
    if path.name.endswith(".jsonl") or path.name.endswith(".jsonl.gz"):
        return _ensure_object_rows(
            (json.loads(line) for line in text.splitlines() if line.strip()),
            path,
        )
    if stripped[0] == "[":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("Expected list JSON in {}".format(path))
        return _ensure_object_rows(payload, path)
    if stripped[0] == "{":
        payload = json.loads(text)
        if isinstance(payload, dict):
            for key in ("cases", "records", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return _ensure_object_rows(value, path)
        raise ValueError("Expected list JSON or object with cases/records/data in {}".format(path))
    return _ensure_object_rows(
        (json.loads(line) for line in text.splitlines() if line.strip()),
        path,
    )


def _read_text(path: Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8")


def _ensure_object_rows(records: Iterable[object], path: Path) -> list[Mapping[str, object]]:
    parsed = list(records)
    for row in parsed:
        if not isinstance(row, dict):
            raise ValueError("Expected object records in {}".format(path))
    return parsed  # type: ignore[return-value]
