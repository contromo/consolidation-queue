from __future__ import annotations


SAFE_REDACTION_KEYS = {
    "answer_redaction",
    "answer_session_ids_redaction",
}

FORBIDDEN_EXACT_KEYS = {
    "answer",
    "answers",
    "answer_session_ids",
    "gold",
    "gold_answer",
    "ground_truth",
    "ground_truth_answer",
    "label",
    "labels",
    "reference_answer",
    "rubric",
}

FORBIDDEN_KEY_SUBSTRINGS = (
    "answer",
    "gold",
    "ground_truth",
    "rubric",
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

