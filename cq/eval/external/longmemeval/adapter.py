from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple, Union

from cq.eval.external.longmemeval.preregistration_lock import (
    PREREGISTRATION_PATH,
    validate_fair_stream_externalization_lock,
)
from cq.eval.extracted_candidate_runner import candidate_stream_sha256
from cq.schemas.memory import (
    CandidateUpdate,
    ClaimType,
    ProvenanceRecord,
    ScopeLevel,
    jsonable,
)
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario, ScenarioEvent, TaskFamily


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ANNOTATIONS_PATH = REPO_ROOT / "data" / "external" / "longmemeval" / "annotations_agreed.json"
ADAPTER_PIN_PATH = REPO_ROOT / "docs" / "longmemeval_adapter_pin.json"
LOCKED_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)


class LongMemEvalAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class AdaptedCandidateStream:
    scenario_id: str
    candidates: list[CandidateUpdate]
    candidate_stream_sha256: str
    candidate_ids_by_event_id: dict[str, list[str]]
    input_annotation_event_count: int
    drops: list[dict[str, object]]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def live_adapter_sha256(adapter_path: str | Path = Path(__file__)) -> str:
    return sha256_file(adapter_path)


def validate_adapter_pin(
    *,
    pin_path: str | Path = ADAPTER_PIN_PATH,
    adapter_path: str | Path = Path(__file__),
    preregistration_path: str | Path = PREREGISTRATION_PATH,
) -> dict[str, object]:
    pin = _read_json(Path(pin_path))
    pinned_sha = str(pin.get("candidate_adapter_sha256") or "")
    actual_sha = live_adapter_sha256(adapter_path)
    if pinned_sha != actual_sha:
        raise LongMemEvalAdapterError(
            "Adapter SHA mismatch: pinned {}, live {}".format(pinned_sha, actual_sha)
        )
    pinned_lock = str(pin.get("preregistration_lock_sha256") or "")
    actual_lock = validate_fair_stream_externalization_lock(Path(preregistration_path))
    if pinned_lock != actual_lock:
        raise LongMemEvalAdapterError(
            "Adapter pin preregistration lock mismatch: pinned {}, live {}".format(
                pinned_lock,
                actual_lock,
            )
        )
    return pin


def load_agreed_annotations(path: str | Path) -> list[dict[str, Any]]:
    payload = _read_json(Path(path))
    annotations = payload.get("annotations")
    if not isinstance(annotations, list):
        raise LongMemEvalAdapterError("No annotations list in {}".format(path))
    result = []
    seen = set()
    for row in annotations:
        if not isinstance(row, dict):
            raise LongMemEvalAdapterError("Annotation rows must be objects")
        case_id = str(row.get("case_id") or "")
        if not case_id:
            raise LongMemEvalAdapterError("Annotation row is missing case_id")
        if case_id in seen:
            raise LongMemEvalAdapterError("Duplicate annotation case_id: {}".format(case_id))
        seen.add(case_id)
        result.append(row)
    return result


def adapt_annotations(
    annotations: Iterable[Mapping[str, Any]],
    *,
    case_limit: Optional[int] = None,
) -> tuple[list[Scenario], dict[str, AdaptedCandidateStream]]:
    rows = sorted(annotations, key=lambda row: str(row.get("case_id") or ""))
    if case_limit is not None:
        rows = rows[:case_limit]
    scenarios = []
    streams = {}
    for row in rows:
        scenario, stream = adapt_annotation(row)
        scenarios.append(scenario)
        streams[scenario.scenario_id] = stream
    return scenarios, streams


def adapt_annotation(row: Mapping[str, Any]) -> tuple[Scenario, AdaptedCandidateStream]:
    case_id = _required_text(row, "case_id")
    scenario_id = "longmemeval_{}".format(case_id)
    candidate_events = row.get("candidate_events") or []
    if not isinstance(candidate_events, list):
        raise LongMemEvalAdapterError("candidate_events must be a list for {}".format(case_id))

    candidates = []
    observation_events = []
    drops = []
    pending_contradiction_targets: dict[str, list[str]] = {}
    candidate_ids_by_event_id: dict[str, list[str]] = {}

    for event_index, event_row in enumerate(candidate_events):
        if not isinstance(event_row, Mapping):
            drops.append(_drop("", event_index, "non_object_candidate_event"))
            continue
        parsed = _candidate_from_event_row(
            scenario_id,
            event_row,
            event_index=event_index,
        )
        if isinstance(parsed, dict):
            drops.append(parsed)
            continue
        event_id, event_text, candidate = parsed
        candidates.append(candidate)
        candidate_ids_by_event_id.setdefault(event_id, []).append(candidate.candidate_id)
        pending_contradiction_targets[candidate.candidate_id] = [
            str(target_event_id)
            for target_event_id in event_row.get("contradicts_event_ids") or []
        ]
        observation_events.append(
            ScenarioEvent(
                event_id=event_id,
                kind=EventKind.OBSERVATION,
                turn_index=event_index,
                text=event_text,
                candidate=candidate,
            )
        )

    _apply_contradictions(candidates, pending_contradiction_targets, candidate_ids_by_event_id)

    question = QuestionSpec(
        question_id="{}::question".format(scenario_id),
        text=str(row.get("question") or ""),
        relevant_canonical_id=_required_text(row, "relevant_canonical_id"),
        scope_level=_scope_level(row),
        scope_key=_required_text(row, "scope_key"),
        phase="longmemeval_probe",
        gold_candidate_ids=[],
        forbidden_candidate_ids=[],
        asked_at=LOCKED_EPOCH + timedelta(seconds=len(observation_events)),
    )
    scenario = Scenario(
        scenario_id=scenario_id,
        task_family=TaskFamily.LONGMEMEVAL_EXTERNAL,
        description="LongMemEval v1 externalized case {}".format(case_id),
        latent_truth_graph={
            "case_id": case_id,
            "mechanism_code": str(row.get("mechanism_code") or ""),
            "question_type": str(row.get("question_type") or ""),
            "relevant_canonical_id": question.relevant_canonical_id,
            "hidden_answer_protocol": True,
        },
        oracle_events=observation_events
        + [
            ScenarioEvent(
                event_id=question.question_id,
                kind=EventKind.QUESTION,
                turn_index=len(observation_events),
                text=question.text,
                question=question,
            )
        ],
        expected_lifecycle={},
        template_id=case_id,
        template_kind="external",
        template_split="longmemeval_v1_agreed",
    )
    stream = AdaptedCandidateStream(
        scenario_id=scenario_id,
        candidates=candidates,
        candidate_stream_sha256=candidate_stream_sha256(candidates),
        candidate_ids_by_event_id=candidate_ids_by_event_id,
        input_annotation_event_count=len(candidate_events),
        drops=drops,
    )
    return scenario, stream


def candidate_stream_audit_rows(
    scenarios: Sequence[Scenario],
    streams: Mapping[str, AdaptedCandidateStream],
) -> list[dict[str, object]]:
    rows = []
    for scenario in scenarios:
        stream = streams[scenario.scenario_id]
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "input_annotation_event_count": stream.input_annotation_event_count,
                "candidate_count": len(stream.candidates),
                "candidate_stream_sha256": stream.candidate_stream_sha256,
                "candidate_ids_by_event_id": stream.candidate_ids_by_event_id,
                "adapter_drop_count": len(stream.drops),
                "adapter_drop_rate": (
                    len(stream.drops) / stream.input_annotation_event_count
                    if stream.input_annotation_event_count
                    else 0.0
                ),
                "drops": stream.drops,
            }
        )
    return rows


def candidate_stream_hash_report(
    streams: Mapping[str, AdaptedCandidateStream],
    policy_names: Sequence[str],
) -> dict[str, object]:
    hashes_by_policy = {
        policy_name: {
            scenario_id: stream.candidate_stream_sha256
            for scenario_id, stream in sorted(streams.items())
        }
        for policy_name in policy_names
    }
    return {
        "candidate_stream_sha256_by_policy": hashes_by_policy,
        "candidate_stream_hash_mismatches": _hash_mismatches(hashes_by_policy),
    }


def _candidate_from_event_row(
    scenario_id: str,
    event_row: Mapping[str, Any],
    *,
    event_index: int,
) -> Union[Tuple[str, str, CandidateUpdate], dict[str, object]]:
    event_id = str(event_row.get("event_id") or "obs_{}".format(event_index))
    raw_claim = str(event_row.get("raw_claim") or "").strip()
    if not raw_claim:
        return _drop(event_id, event_index, "empty_raw_claim")
    canonical_id = str(event_row.get("canonical_id") or "").strip()
    if not canonical_id:
        return _drop(event_id, event_index, "empty_canonical_id")
    try:
        claim_type = ClaimType(str(event_row.get("claim_type") or ""))
    except ValueError:
        return _drop(event_id, event_index, "unrecognized_claim_type")
    try:
        scope_level = ScopeLevel(str(event_row.get("scope_level") or ""))
    except ValueError:
        return _drop(event_id, event_index, "unrecognized_scope_level")
    scope_key = str(event_row.get("scope_key") or "").strip()
    if not scope_key:
        return _drop(event_id, event_index, "empty_scope_key")
    confidence = event_row.get("confidence")
    if isinstance(confidence, (int, float)) and 0.0 <= float(confidence) <= 1.0:
        verification_score = float(confidence)
    else:
        return _drop(event_id, event_index, "invalid_confidence")

    observed_at = LOCKED_EPOCH + timedelta(seconds=event_index)
    candidate = CandidateUpdate(
        candidate_id="{}::{}::0".format(scenario_id, event_id),
        raw_text=raw_claim,
        raw_claim=raw_claim,
        canonical_claim=canonical_id,
        claim_type=claim_type,
        scope_level=scope_level,
        scope_key=scope_key,
        created_at=observed_at,
        updated_at=observed_at,
        canonical_id=canonical_id,
        provenance=[
            ProvenanceRecord(
                source_kind="longmemeval_redacted_session",
                source_id="{}::{}::{}".format(
                    scenario_id,
                    event_id,
                    str(event_row.get("session_id") or ""),
                ),
                trust_score=verification_score,
                observed_at=observed_at,
            )
        ],
        verification_score=verification_score,
        contradicts=[],
        supports=[],
    )
    return event_id, raw_claim, candidate


def _apply_contradictions(
    candidates: Sequence[CandidateUpdate],
    pending_contradiction_targets: Mapping[str, Sequence[str]],
    candidate_ids_by_event_id: Mapping[str, Sequence[str]],
) -> None:
    for candidate in candidates:
        targets = []
        seen = set()
        for target_event_id in pending_contradiction_targets.get(candidate.candidate_id, []):
            for target_candidate_id in candidate_ids_by_event_id.get(target_event_id, []):
                if target_candidate_id not in seen:
                    targets.append(target_candidate_id)
                    seen.add(target_candidate_id)
        candidate.contradicts = targets


def _hash_mismatches(
    hashes_by_policy: Mapping[str, Mapping[str, str]],
) -> list[dict[str, object]]:
    policies = sorted(hashes_by_policy)
    scenario_ids = sorted(
        {
            scenario_id
            for policy_hashes in hashes_by_policy.values()
            for scenario_id in policy_hashes
        }
    )
    mismatches = []
    for scenario_id in scenario_ids:
        observed = {
            policy_name: hashes_by_policy[policy_name].get(scenario_id)
            for policy_name in policies
        }
        values = {value for value in observed.values() if value is not None}
        if len(values) > 1 or any(value is None for value in observed.values()):
            mismatches.append({"scenario_id": scenario_id, "hashes_by_policy": observed})
    return mismatches


def _scope_level(row: Mapping[str, Any]) -> ScopeLevel:
    try:
        return ScopeLevel(_required_text(row, "scope_level"))
    except ValueError as exc:
        raise LongMemEvalAdapterError("Unrecognized scope_level") from exc


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LongMemEvalAdapterError("Missing or empty {}".format(key))
    return value


def _drop(event_id: str, event_index: int, reason: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_index": event_index,
        "reason": reason,
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LongMemEvalAdapterError("Expected JSON object in {}".format(path))
    return payload


def _repo_relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_dry_run_summary(
    *,
    annotations_path: Path,
    case_limit: Optional[int] = None,
    policy_names: Sequence[str] = (
        "consolidation_queue_lite",
        "reflection_eager_write_lite",
        "mem0_lite",
    ),
) -> dict[str, object]:
    scenarios, streams = adapt_annotations(
        load_agreed_annotations(annotations_path),
        case_limit=case_limit,
    )
    hash_report = candidate_stream_hash_report(streams, policy_names)
    mismatches = hash_report["candidate_stream_hash_mismatches"]
    return {
        "mode": "longmemeval_external_adapter_dry_run",
        "annotations_path": _repo_relative_path(annotations_path),
        "case_limit": case_limit,
        "scenario_count": len(scenarios),
        "candidate_count": sum(len(stream.candidates) for stream in streams.values()),
        "candidate_stream_audit": candidate_stream_audit_rows(scenarios, streams),
        "candidate_stream_hash_invariant_passed": not mismatches,
        **hash_report,
        "adapter_sha256": live_adapter_sha256(),
        "preregistration_lock_sha256": validate_fair_stream_externalization_lock(),
    }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build LongMemEval externalized candidate streams.")
    parser.add_argument("--annotations-json", default=str(DEFAULT_ANNOTATIONS_PATH))
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--output-json")
    parser.add_argument("--check-pin", action="store_true")
    args = parser.parse_args(argv)

    if args.check_pin:
        validate_adapter_pin()
    summary = build_dry_run_summary(
        annotations_path=Path(args.annotations_json),
        case_limit=args.case_limit,
    )
    if args.output_json:
        write_json(args.output_json, summary)
    else:
        print(json.dumps(jsonable(summary), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
