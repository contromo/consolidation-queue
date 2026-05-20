from __future__ import annotations


SAFE_REDACTION_KEYS = {
    "answer_redaction",
    "answer_session_ids_redaction",
}

FORBIDDEN_EXACT_KEYS = {
    "answer",
    "answers",
    "answer_session_ids",
    "correct",
    "correct_answer",
    "correct_answers",
    "correct_session_ids",
    "evidence",
    "evidence_session_ids",
    "expected",
    "expected_answer",
    "expected_output",
    "gold",
    "gold_answer",
    "gold_session_ids",
    "ground_truth",
    "ground_truth_answer",
    "label",
    "labels",
    "oracle_output",
    "reference",
    "reference_answer",
    "rubric",
    "solution",
    "target",
    "target_answer",
    "truth_value",
    "verdict",
}

FORBIDDEN_KEY_SUBSTRINGS = (
    "answer",
    "correct",
    "evidence",
    "expected",
    "gold",
    "ground_truth",
    "oracle",
    "reference",
    "rubric",
    "solution",
    "target",
    "truth",
    "verdict",
)


def normalize_key(key: object) -> str:
    return str(key).strip().lower().replace("-", "_")


def is_forbidden_answer_key(key: object) -> bool:
    normalized = normalize_key(key)
    if normalized in SAFE_REDACTION_KEYS:
        return False
    if normalized in FORBIDDEN_EXACT_KEYS:
        return True
    if normalized.endswith("_label") or normalized.endswith("_labels"):
        return True
    return any(fragment in normalized for fragment in FORBIDDEN_KEY_SUBSTRINGS)
