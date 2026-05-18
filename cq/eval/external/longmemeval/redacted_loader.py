from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Union

from cq.eval.external.longmemeval.sensitive_keys import is_forbidden_answer_key


class RedactionAccessError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class RedactedField:
    """Hash-only placeholder for answer-side fields.

    The hash is available for provenance and equality checks. Any attempt to
    coerce the placeholder back into a value raises, which keeps accidental
    answer-label leakage visible during adapter development.
    """

    __slots__ = ("field_name", "sha256", "original_type", "present")

    def __init__(self, field_name: str, value: Any, *, present: bool = True) -> None:
        self.field_name = field_name
        self.sha256 = sha256_value(value)
        self.original_type = type(value).__name__
        self.present = present

    def __repr__(self) -> str:
        status = "present" if self.present else "missing"
        return "<RedactedField {} {} sha256={}>".format(
            self.field_name,
            status,
            self.sha256,
        )

    def _raise(self) -> None:
        raise RedactionAccessError(
            "Attempted to read redacted LongMemEval field '{}'.".format(self.field_name)
        )

    def __str__(self) -> str:
        self._raise()

    def __bool__(self) -> bool:
        self._raise()

    def __len__(self) -> int:
        self._raise()

    def __iter__(self):
        self._raise()

    def __eq__(self, other: object) -> bool:
        self._raise()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "sha256": self.sha256,
            "original_type": self.original_type,
            "present": self.present,
        }


@dataclass(frozen=True)
class RedactedLongMemEvalCase:
    case_id: str
    question_type: str
    question: str
    question_date: str
    haystack_session_ids: Any
    haystack_dates: Any
    haystack_sessions: Any
    raw: Mapping[str, Any]
    answer_redaction: RedactedField
    answer_session_ids_redaction: RedactedField

    @property
    def answer(self) -> str:
        raise RedactionAccessError("Attempted to read redacted LongMemEval field 'answer'.")

    @property
    def answer_session_ids(self) -> list[str]:
        raise RedactionAccessError(
            "Attempted to read redacted LongMemEval field 'answer_session_ids'."
        )

    def to_public_dict(self) -> dict[str, Any]:
        # Haystack fields are intentionally retained: they are the annotation
        # context. Answer-side fields inside them are scrubbed from ``raw``.
        return {
            "case_id": self.case_id,
            "question_type": self.question_type,
            "question": self.question,
            "question_date": self.question_date,
            "haystack_session_ids": self.haystack_session_ids,
            "haystack_dates": self.haystack_dates,
            "haystack_sessions": self.haystack_sessions,
            "answer_redaction": self.answer_redaction.to_metadata(),
            "answer_session_ids_redaction": self.answer_session_ids_redaction.to_metadata(),
        }


def load_redacted_cases(path: Union[str, Path]) -> List[RedactedLongMemEvalCase]:
    return [redact_case(row) for row in _load_records(Path(path))]


def redact_case(row: Mapping[str, Any]) -> RedactedLongMemEvalCase:
    answer_present = "answer" in row
    answer_session_ids_present = "answer_session_ids" in row
    return RedactedLongMemEvalCase(
        case_id=str(row.get("question_id") or row.get("id") or ""),
        question_type=str(row.get("question_type") or ""),
        question=str(row.get("question") or ""),
        question_date=str(row.get("question_date") or ""),
        haystack_session_ids=row.get("haystack_session_ids"),
        haystack_dates=row.get("haystack_dates"),
        haystack_sessions=row.get("haystack_sessions"),
        raw=_redacted_raw(row),
        answer_redaction=RedactedField(
            "answer",
            row.get("answer"),
            present=answer_present,
        ),
        answer_session_ids_redaction=RedactedField(
            "answer_session_ids",
            row.get("answer_session_ids"),
            present=answer_session_ids_present,
        ),
    )


def _redacted_raw(row: Mapping[str, Any]) -> dict[str, Any]:
    result = _scrub_sensitive_keys(row)
    result["answer_redaction"] = RedactedField(
        "answer",
        row.get("answer"),
        present="answer" in row,
    ).to_metadata()
    result["answer_session_ids_redaction"] = RedactedField(
        "answer_session_ids",
        row.get("answer_session_ids"),
        present="answer_session_ids" in row,
    ).to_metadata()
    return result


def _scrub_sensitive_keys(value: Any) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if is_forbidden_answer_key(key):
                result["{}_redaction".format(key)] = RedactedField(
                    str(key),
                    item,
                    present=True,
                ).to_metadata()
            else:
                result[key] = _scrub_sensitive_keys(item)
        return result
    if isinstance(value, list):
        return [_scrub_sensitive_keys(item) for item in value]
    return value


def _load_records(path: Path) -> list[Mapping[str, Any]]:
    text = _read_text(path)
    stripped = text.lstrip()
    if not stripped:
        return []
    if _looks_like_jsonl(path):
        return _assert_mapping_records((json.loads(line) for line in text.splitlines() if line.strip()), path)
    if stripped[0] == "[":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("Expected list-valued JSON in {}".format(path))
        return _assert_mapping_records(payload, path)
    if stripped[0] == "{":
        payload = json.loads(text)
        if isinstance(payload, dict):
            for key in ("cases", "annotations", "data", "records"):
                value = payload.get(key)
                if isinstance(value, list):
                    return _assert_mapping_records(value, path)
        raise ValueError("Expected list JSON or object with cases/annotations/data/records in {}".format(path))
    return _assert_mapping_records((json.loads(line) for line in text.splitlines() if line.strip()), path)


def _looks_like_jsonl(path: Path) -> bool:
    return path.name.endswith(".jsonl") or path.name.endswith(".jsonl.gz")


def _read_text(path: Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8")


def _assert_mapping_records(records: Iterable[Any], path: Path) -> list[Mapping[str, Any]]:
    parsed = list(records)
    if any(not isinstance(row, dict) for row in parsed):
        raise ValueError("Expected object records in {}".format(path))
    return parsed
