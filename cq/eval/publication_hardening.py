"""Publication-hardening contract checks.

These helpers make the preregistered paper-hardening definitions executable
without running any external benchmark or hosted model.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable, Mapping, Sequence


HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_API_COST_CEILING_USD = 10_000.0

PAPER_POLICY_TO_RUNNER_KEY = {
    "Base CQ": "consolidation_queue_lite",
    "CQ-Multi": "cq_pending_multi_evidence",
    "Reflection": "reflection_eager_write_lite",
    "Capped Reflection": "reflection_eager_write_cardinality_capped",
    "Mem0 WritePolicy Lite": "mem0_lite",
    "NoMemory": "no_memory_lite",
}

POLICY_SET_KEYS = {
    "original_internal_headline": "phase2_5",
    "cq_multi_followup": "phase2_5_followup",
    # Intentional duplicate: the fresh archived CQR replay reuses the original
    # Phase 4 policy set while changing archival/replay requirements.
    "fresh_archived_cqr_replay": "phase2_5",
}

STEP3_CQR_SCOPE = {
    "primary_model": "qwen2.5:32b-instruct-q4_K_M",
    "schema_profile": "default",
    "policy_set": "phase2_5",
    "thesis_families": ("useful_pending_memory", "memory_poisoning"),
    "descriptive_families": ("false_corroboration", "mechanism_diverse_heldout"),
    "minimum_alias_cqr_hits_per_thesis_family": 5,
}


@dataclass(frozen=True)
class DistractorFloorRow:
    """One scored case after adapter drops."""

    case_id: str
    gold_ids: Sequence[str]
    policy_visible_ids: Sequence[str]


@dataclass(frozen=True)
class DistractorFloorResult:
    passed: bool
    average_non_gold_to_gold: float
    minimum_case_ratio: float
    case_count: int
    errors: tuple[str, ...]


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(_is_nonempty_string(item) for item in value)


def _is_nonempty_string_list(value: Any) -> bool:
    return _is_string_list(value) and bool(value)


def validate_pflc_record(record: Mapping[str, Any]) -> list[str]:
    """Validate one PFLC JSONL record.

    The contract supports evidence-id surfaces and fact-id worked examples.
    Evidence rows use ``gold_evidence_ids`` and ``returned_evidence_ids``.
    Fact rows use ``gold_fact_ids`` plus either ``returned_fact_ids`` or
    ``returned_memory_ids``.
    """

    errors: list[str] = []
    for field in ("question_id", "source_sha256", "answer_text", "system_label", "manifest_path"):
        if not _is_nonempty_string(record.get(field)):
            errors.append(f"{field} must be a non-empty string")

    source_sha = record.get("source_sha256")
    if _is_nonempty_string(source_sha) and not HEX_SHA256.match(source_sha):
        errors.append("source_sha256 must be a lowercase 64-character hex sha256")

    target_kind = record.get("target_kind")
    if target_kind == "evidence_id":
        if not _is_nonempty_string_list(record.get("gold_evidence_ids")):
            errors.append("gold_evidence_ids must be a non-empty string list")
        if not _is_string_list(record.get("returned_evidence_ids")):
            errors.append("returned_evidence_ids must be a string list")
    elif target_kind == "fact_id":
        if not _is_nonempty_string_list(record.get("gold_fact_ids")):
            errors.append("gold_fact_ids must be a non-empty string list")
        has_fact_ids = _is_string_list(record.get("returned_fact_ids"))
        has_memory_ids = _is_string_list(record.get("returned_memory_ids"))
        if not (has_fact_ids or has_memory_ids):
            errors.append("fact_id rows require returned_fact_ids or returned_memory_ids")
    else:
        errors.append("target_kind must be evidence_id or fact_id")

    return errors


def validate_pflc_jsonl_lines(lines: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            errors.append(f"line {index}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            errors.append(f"line {index}: record must be a JSON object")
            continue
        errors.extend(f"line {index}: {error}" for error in validate_pflc_record(record))
    return errors


def evaluate_distractor_floor(
    rows: Sequence[DistractorFloorRow],
    *,
    minimum_average_ratio: float = 10.0,
) -> DistractorFloorResult:
    """Evaluate the locked post-adapter distractor floor.

    Ratios are computed per scored case using unique ids:
    ``len(policy_visible_ids - gold_ids) / len(gold_ids)``. The mean ratio is
    the hard gate; the minimum case ratio is diagnostic.
    """

    errors: list[str] = []
    ratios: list[float] = []
    for row in rows:
        if not _is_nonempty_string(row.case_id):
            errors.append("case_id must be a non-empty string")
            continue
        gold_ids = {item for item in row.gold_ids if _is_nonempty_string(item)}
        visible_ids = {item for item in row.policy_visible_ids if _is_nonempty_string(item)}
        if not gold_ids:
            errors.append(f"{row.case_id}: gold_ids must contain at least one id")
            continue
        non_gold_count = len(visible_ids - gold_ids)
        ratios.append(non_gold_count / len(gold_ids))

    average = sum(ratios) / len(ratios) if ratios else 0.0
    minimum = min(ratios) if ratios else 0.0
    return DistractorFloorResult(
        passed=not errors and average >= minimum_average_ratio,
        average_non_gold_to_gold=average,
        minimum_case_ratio=minimum,
        case_count=len(ratios),
        errors=tuple(errors),
    )


def validate_api_model_pin(pin: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("provider", "model_id", "fallback_model_id", "stability_check"):
        if not _is_nonempty_string(pin.get(field)):
            errors.append(f"{field} must be a non-empty string")
    cost_ceiling = pin.get("cost_ceiling_usd")
    if not isinstance(cost_ceiling, (int, float)) or cost_ceiling <= 0:
        errors.append("cost_ceiling_usd must be a positive number")
    elif cost_ceiling > MAX_API_COST_CEILING_USD:
        errors.append(
            "cost_ceiling_usd must be <= {}".format(int(MAX_API_COST_CEILING_USD))
        )
    if pin.get("cache_required") is not True:
        errors.append("cache_required must be true")
    return errors


def validate_policy_name_mapping(mapping: Mapping[str, str] = PAPER_POLICY_TO_RUNNER_KEY) -> list[str]:
    errors: list[str] = []
    required = {
        "Base CQ",
        "CQ-Multi",
        "Reflection",
        "Capped Reflection",
        "Mem0 WritePolicy Lite",
        "NoMemory",
    }
    missing = sorted(required - set(mapping))
    if missing:
        errors.append("missing paper policy names: {}".format(", ".join(missing)))
    if mapping.get("Mem0 WritePolicy Lite") != "mem0_lite":
        errors.append("Mem0 WritePolicy Lite must map to mem0_lite")
    for paper_name, runner_key in mapping.items():
        if not _is_nonempty_string(paper_name) or not _is_nonempty_string(runner_key):
            errors.append("policy mapping keys and values must be non-empty strings")
    return errors
