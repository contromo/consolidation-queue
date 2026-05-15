from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Type

from cq.eval.component_eval import (
    CandidateComponentPrediction,
    load_predictions_by_scenario,
    load_scenario_errors,
)
from cq.eval.end_to_end_eval import (
    compute_policy_metrics,
    extract_failure_examples,
    failure_example_sort_key,
    summarize_runs,
)
from cq.memory.substrate import MemoryStore
from cq.schemas.memory import (
    CandidateUpdate,
    ClaimType,
    ProvenanceRecord,
    ScopeLevel,
    jsonable,
)
from cq.schemas.scenario import EventKind, QuestionSpec, Scenario, ScenarioEvent
from cq.simulator.render_events import render_scenario_transcript


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION_PATH = REPO_ROOT / "docs" / "noisy_policy_comparison_preregistration.md"
ADAPTER_PIN_PATH = REPO_ROOT / "docs" / "noisy_policy_comparison_adapter_pin.json"
LOCK_FIELD = "noisy_policy_comparison_lock_sha256"
PREDICTIONS_BLOCK_START = "<!-- FROZEN_EVAL_PREDICTIONS_START -->"
PREDICTIONS_BLOCK_END = "<!-- FROZEN_EVAL_PREDICTIONS_END -->"
LOCK_RE = re.compile(r"^noisy_policy_comparison_lock_sha256:\s*([a-f0-9]{64})\s*$", re.MULTILINE)

LOCKED_EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
LOCKED_MODEL_TAG = "qwen2.5:32b-instruct-q4_K_M"
LOCKED_MODEL_DIGEST = "sha256:9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368"
LOCKED_PROMPT_SHA256 = "ca9ec418156b4cc12bcf5457683844f023684bbc5cee2b7460a6c5030a475633"
SCHEMA_PROFILES = ("default", "scenario_conditioned")
PRIMARY_SCENARIO_COUNT = 60
FROZEN_SENTINEL_SCENARIO_COUNT = 3


class NoisyPolicyComparisonError(ValueError):
    pass


@dataclass(frozen=True)
class PredictionCellPaths:
    summary: Path
    manifest: Path
    predictions: Path
    component_eval: Path


@dataclass(frozen=True)
class AdaptedCandidateStream:
    scenario_id: str
    candidates: List[CandidateUpdate]
    candidate_stream_sha256: str
    candidate_ids_by_event_id: Dict[str, List[str]]
    candidate_ids_by_oracle_candidate_id: Dict[str, List[str]]
    input_prediction_count: int
    drops: List[Dict[str, object]]
    scenario_error: Optional[object] = None


def compute_noisy_preregistration_lock_sha256(
    preregistration_text: str,
) -> str:
    block = extract_predictions_block(preregistration_text)
    return hashlib.sha256(block.encode("utf-8")).hexdigest()


def extract_predictions_block(preregistration_text: str) -> str:
    start = preregistration_text.find(PREDICTIONS_BLOCK_START)
    if start == -1:
        raise NoisyPolicyComparisonError("Missing {}".format(PREDICTIONS_BLOCK_START))
    end = preregistration_text.find(PREDICTIONS_BLOCK_END, start)
    if end == -1:
        raise NoisyPolicyComparisonError("Missing {}".format(PREDICTIONS_BLOCK_END))
    block_start = preregistration_text.find("\n", start)
    if block_start == -1 or block_start > end:
        raise NoisyPolicyComparisonError("Predictions block is empty or malformed")
    return preregistration_text[block_start + 1 : end]


def declared_noisy_preregistration_lock(preregistration_text: str) -> str:
    match = LOCK_RE.search(preregistration_text)
    if match is None:
        raise NoisyPolicyComparisonError("Missing {}".format(LOCK_FIELD))
    return match.group(1)


def validate_noisy_preregistration_lock(
    preregistration_path: Path = PREREGISTRATION_PATH,
) -> str:
    text = preregistration_path.read_text(encoding="utf-8")
    declared = declared_noisy_preregistration_lock(text)
    actual = compute_noisy_preregistration_lock_sha256(text)
    if declared != actual:
        raise NoisyPolicyComparisonError(
            "Noisy policy preregistration lock mismatch: declared {}, computed {}".format(
                declared,
                actual,
            )
        )
    return declared


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def live_adapter_sha256(adapter_path: Path = Path(__file__)) -> str:
    return sha256_file(adapter_path)


def validate_adapter_pin(
    *,
    pin_path: Path = ADAPTER_PIN_PATH,
    adapter_path: Path = Path(__file__),
    preregistration_path: Path = PREREGISTRATION_PATH,
) -> Dict[str, object]:
    if not pin_path.exists():
        raise NoisyPolicyComparisonError("Missing adapter pin file: {}".format(pin_path))
    pin = _read_json(pin_path)
    pinned_sha = str(pin.get("candidate_adapter_sha256") or "")
    actual_sha = live_adapter_sha256(adapter_path)
    if pinned_sha != actual_sha:
        raise NoisyPolicyComparisonError(
            "Adapter SHA mismatch: pinned {}, live {}".format(pinned_sha, actual_sha)
        )
    declared_lock = str(pin.get("preregistration_lock_sha256") or "")
    actual_lock = validate_noisy_preregistration_lock(preregistration_path)
    if declared_lock != actual_lock:
        raise NoisyPolicyComparisonError(
            "Adapter pin preregistration lock mismatch: pinned {}, live {}".format(
                declared_lock,
                actual_lock,
            )
        )
    return pin


def prediction_cell_paths(
    *,
    predictions_dir: Path,
    family: str,
    schema_profile: str,
) -> PredictionCellPaths:
    if schema_profile not in SCHEMA_PROFILES:
        raise NoisyPolicyComparisonError(
            "Unsupported schema profile '{}'. Allowed: {}".format(
                schema_profile,
                ", ".join(SCHEMA_PROFILES),
            )
        )
    summary_path = predictions_dir / (
        "component_gate_decision_qwen2_5_32b-instruct-q4_K_M_{}_summary.json".format(
            schema_profile
        )
    )
    manifest_path = predictions_dir / (
        "component_gate_decision_qwen2_5_32b-instruct-q4_K_M_{}_manifest.json".format(
            schema_profile
        )
    )
    if not summary_path.exists():
        raise NoisyPolicyComparisonError("Missing component gate summary: {}".format(summary_path))
    if not manifest_path.exists():
        raise NoisyPolicyComparisonError("Missing component gate manifest: {}".format(manifest_path))
    summary = _read_json(summary_path)
    _validate_gate_summary(summary, schema_profile=schema_profile, summary_path=summary_path)
    _validate_gate_manifest(manifest_path, summary_path)
    rows = list(summary.get("rows") or []) + list(summary.get("frozen_sentinel_rows") or [])
    row = None
    for candidate in rows:
        if isinstance(candidate, dict) and candidate.get("family") == family:
            row = candidate
            break
    if row is None:
        raise NoisyPolicyComparisonError(
            "Family '{}' not found in component gate summary {}".format(family, summary_path)
        )
    paths = row.get("paths")
    if not isinstance(paths, dict):
        raise NoisyPolicyComparisonError("Gate row for '{}' is missing paths".format(family))
    predictions_path = _repo_path(str(paths.get("predictions") or ""))
    component_eval_path = _repo_path(str(paths.get("component_eval") or ""))
    if not predictions_path.exists():
        raise NoisyPolicyComparisonError("Missing predictions artifact: {}".format(predictions_path))
    if not component_eval_path.exists():
        raise NoisyPolicyComparisonError("Missing component-eval artifact: {}".format(component_eval_path))
    validate_prediction_payload(
        _read_json(predictions_path),
        family=family,
        schema_profile=schema_profile,
    )
    return PredictionCellPaths(
        summary=summary_path,
        manifest=manifest_path,
        predictions=predictions_path,
        component_eval=component_eval_path,
    )


def validate_prediction_payload(
    payload: Mapping[str, object],
    *,
    family: str,
    schema_profile: str,
) -> None:
    diagnostics = payload.get("model_diagnostics")
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    checks = [
        ("model_id", payload.get("model_id"), LOCKED_MODEL_TAG),
        ("model_digest", payload.get("model_digest") or diagnostics.get("model_digest"), LOCKED_MODEL_DIGEST),
        ("prompt_template_sha256", payload.get("prompt_template_sha256"), LOCKED_PROMPT_SHA256),
        ("family", payload.get("family"), family),
        ("model_diagnostics.schema_profile", diagnostics.get("schema_profile"), schema_profile),
    ]
    for field_name, observed, expected in checks:
        if observed != expected:
            raise NoisyPolicyComparisonError(
                "Prediction payload {} mismatch: observed {!r}, expected {!r}".format(
                    field_name,
                    observed,
                    expected,
                )
            )


def load_extracted_predictions(
    predictions_path: Path,
) -> Tuple[Dict[str, List[CandidateComponentPrediction]], Dict[str, object]]:
    return load_predictions_by_scenario(predictions_path), load_scenario_errors(predictions_path)


def adapt_predictions_for_scenario(
    scenario: Scenario,
    predictions: Sequence[CandidateComponentPrediction],
    *,
    scenario_error: Optional[object] = None,
) -> AdaptedCandidateStream:
    candidate_ids_by_oracle_candidate_id = _candidate_ids_by_oracle_candidate_id(scenario, {})
    if scenario_error is not None:
        return AdaptedCandidateStream(
            scenario_id=scenario.scenario_id,
            candidates=[],
            candidate_stream_sha256=candidate_stream_sha256([]),
            candidate_ids_by_event_id={},
            candidate_ids_by_oracle_candidate_id=candidate_ids_by_oracle_candidate_id,
            input_prediction_count=len(predictions),
            drops=[],
            scenario_error=scenario_error,
        )

    predictions_by_event: Dict[str, List[CandidateComponentPrediction]] = {}
    for prediction in predictions:
        predictions_by_event.setdefault(prediction.event_id, []).append(prediction)

    event_by_id = {event.event_id: event for event in scenario.sorted_events()}
    observation_event_ids = {
        event.event_id
        for event in scenario.sorted_events()
        if event.kind == EventKind.OBSERVATION
    }
    candidates: List[CandidateUpdate] = []
    emitted_by_event: Dict[str, List[CandidateUpdate]] = {}
    drops: List[Dict[str, object]] = []
    pending_contradiction_targets: Dict[str, List[str]] = {}

    for event in scenario.sorted_events():
        if event.kind != EventKind.OBSERVATION:
            continue
        dedup_keys = set()
        valid_for_event: List[Tuple[CandidateComponentPrediction, CandidateUpdate]] = []
        for prediction_index, prediction in enumerate(predictions_by_event.get(event.event_id, [])):
            parsed, drop_reason = _candidate_from_prediction(
                scenario,
                event,
                prediction,
                prediction_index=prediction_index,
                prediction_ordinal=len(valid_for_event),
            )
            if drop_reason is not None:
                drops.append(drop_reason)
                continue
            candidate = parsed
            key = (
                candidate.canonical_id,
                candidate.claim_type.value,
                candidate.scope_level.value,
                candidate.scope_key,
            )
            if key in dedup_keys:
                drops.append(
                    _drop(
                        event_id=event.event_id,
                        prediction_index=prediction_index,
                        reason="duplicate_within_event",
                        canonical_id=candidate.canonical_id or "",
                    )
                )
                continue
            dedup_keys.add(key)
            valid_for_event.append((prediction, candidate))
        if valid_for_event:
            emitted_by_event[event.event_id] = []
        for prediction, candidate in valid_for_event:
            candidates.append(candidate)
            emitted_by_event[event.event_id].append(candidate)
            pending_contradiction_targets[candidate.candidate_id] = list(prediction.contradicts_event_ids)

    for event_id in sorted(set(predictions_by_event) - observation_event_ids):
        for prediction_index, prediction in enumerate(predictions_by_event[event_id]):
            drops.append(
                _drop(
                    event_id=event_id,
                    prediction_index=prediction_index,
                    reason="unknown_or_non_observation_event",
                    canonical_id=prediction.canonical_id,
                )
            )

    emitted_ids_by_event = {
        event_id: [candidate.candidate_id for candidate in event_candidates]
        for event_id, event_candidates in emitted_by_event.items()
    }
    _apply_contradictions(candidates, pending_contradiction_targets, emitted_ids_by_event)
    _apply_supports(candidates, event_by_id)
    candidate_ids_by_oracle_candidate_id = _candidate_ids_by_oracle_candidate_id(
        scenario,
        emitted_ids_by_event,
    )
    return AdaptedCandidateStream(
        scenario_id=scenario.scenario_id,
        candidates=candidates,
        candidate_stream_sha256=candidate_stream_sha256(candidates),
        candidate_ids_by_event_id=emitted_ids_by_event,
        candidate_ids_by_oracle_candidate_id=candidate_ids_by_oracle_candidate_id,
        input_prediction_count=len(predictions),
        drops=drops,
        scenario_error=None,
    )


def adapt_predictions_for_scenarios(
    scenarios: Sequence[Scenario],
    predictions_by_scenario: Mapping[str, List[CandidateComponentPrediction]],
    scenario_errors: Mapping[str, object],
) -> Dict[str, AdaptedCandidateStream]:
    return {
        scenario.scenario_id: adapt_predictions_for_scenario(
            scenario,
            predictions_by_scenario.get(scenario.scenario_id, []),
            scenario_error=scenario_errors.get(scenario.scenario_id),
        )
        for scenario in scenarios
    }


def candidate_stream_audit_for_adapted_scenarios(
    scenarios: Sequence[Scenario],
    adapted_by_scenario: Mapping[str, AdaptedCandidateStream],
) -> List[Dict[str, object]]:
    return [
        _candidate_stream_audit_row(
            scenario.scenario_id,
            adapted_by_scenario[scenario.scenario_id],
        )
        for scenario in scenarios
    ]


def _candidate_stream_audit_row(
    scenario_id: str,
    adapted: AdaptedCandidateStream,
) -> Dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "input_prediction_count": adapted.input_prediction_count,
        "candidate_count": len(adapted.candidates),
        "candidate_stream_sha256": adapted.candidate_stream_sha256,
        "candidate_ids_by_event_id": adapted.candidate_ids_by_event_id,
        "adapter_drop_count": len(adapted.drops),
        "adapter_drop_rate": (
            len(adapted.drops) / adapted.input_prediction_count
            if adapted.input_prediction_count
            else 0.0
        ),
        "drops": adapted.drops,
        "scenario_error": adapted.scenario_error,
    }


def candidate_stream_sha256(candidates: Sequence[CandidateUpdate]) -> str:
    return hashlib.sha256(candidate_stream_canonical_json(candidates).encode("utf-8")).hexdigest()


def candidate_stream_canonical_json(candidates: Sequence[CandidateUpdate]) -> str:
    return json.dumps(
        jsonable(list(candidates)),
        sort_keys=True,
        separators=(",", ":"),
    )


def scenario_with_extracted_metric_ids(
    scenario: Scenario,
    adapted: AdaptedCandidateStream,
) -> Scenario:
    expected_lifecycle = _map_expected_lifecycle_ids(
        scenario,
        adapted.candidate_ids_by_oracle_candidate_id,
    )
    events = []
    for event in scenario.oracle_events:
        if event.question is None:
            events.append(event)
            continue
        events.append(
            replace(
                event,
                question=_map_question_ids(
                    event.question,
                    adapted.candidate_ids_by_oracle_candidate_id,
                ),
            )
        )
    return replace(
        scenario,
        oracle_events=events,
        expected_lifecycle=expected_lifecycle,
    )


def execute_extracted_scenario(
    policy_cls: Type[object],
    scenario: Scenario,
    adapted: AdaptedCandidateStream,
) -> Dict[str, object]:
    metric_scenario = scenario_with_extracted_metric_ids(scenario, adapted)
    policy = policy_cls()
    question_traces = []
    candidates_by_event: Dict[str, List[CandidateUpdate]] = {}
    for candidate in adapted.candidates:
        event_id = _event_id_from_rewritten_candidate_id(candidate.candidate_id)
        candidates_by_event.setdefault(event_id, []).append(candidate)

    for event in scenario.sorted_events():
        if event.kind == EventKind.OBSERVATION:
            for candidate in candidates_by_event.get(event.event_id, []):
                policy.observe_candidate(candidate)
        if event.kind == EventKind.QUESTION and event.question is not None:
            mapped_question = _question_by_id(metric_scenario, event.question.question_id)
            question_traces.append(policy.answer_question(mapped_question))

    store_snapshot = policy.store.snapshot()
    metrics = compute_policy_metrics(
        policy.policy_name,
        metric_scenario,
        question_traces,
        store_snapshot,
    )
    failure_examples = extract_failure_examples(
        policy.policy_name,
        metric_scenario,
        question_traces,
        store_snapshot,
        is_floor_baseline=bool(getattr(policy_cls, "is_floor_baseline", False)),
    )
    return {
        "policy_name": policy.policy_name,
        "scenario_id": scenario.scenario_id,
        "scenario": jsonable(metric_scenario),
        "question_traces": [jsonable(trace) for trace in question_traces],
        "store_snapshot": store_snapshot,
        "metrics": jsonable(metrics),
        "failure_examples": failure_examples,
        "store": policy.store,
        "candidate_stream_sha256": adapted.candidate_stream_sha256,
    }


def build_extracted_run_artifact(
    *,
    scenarios: Sequence[Scenario],
    policy_classes: Sequence[Type[object]],
    predictions_by_scenario: Mapping[str, List[CandidateComponentPrediction]],
    scenario_errors: Mapping[str, object],
    family: str,
    requested_scenario_count: int,
    template_mix: str,
    policy_set: str,
    schema_profile: str,
    predictions_path: Optional[Path] = None,
    adapter_sha256: str = "",
    preregistration_lock_sha256: str = "",
) -> dict:
    adapted_by_scenario = adapt_predictions_for_scenarios(
        scenarios,
        predictions_by_scenario,
        scenario_errors,
    )
    policy_runs = []
    run_records_by_policy: Dict[str, List[dict]] = {}
    candidate_stream_audit = candidate_stream_audit_for_adapted_scenarios(
        scenarios,
        adapted_by_scenario,
    )

    stream_hashes_by_policy: Dict[str, Dict[str, str]] = {}
    for policy_cls in policy_classes:
        run_records = [
            execute_extracted_scenario(
                policy_cls,
                scenario,
                adapted_by_scenario[scenario.scenario_id],
            )
            for scenario in scenarios
        ]
        run_records_by_policy[policy_cls.policy_name] = run_records
        stream_hashes_by_policy[policy_cls.policy_name] = {
            record["scenario_id"]: record["candidate_stream_sha256"]
            for record in run_records
        }
        summary = summarize_runs(run_records)
        failure_examples = sorted(
            [
                example
                for record in run_records
                for example in record.get("failure_examples", [])
            ],
            key=failure_example_sort_key,
        )
        policy_runs.append(
            {
                "policy_name": policy_cls.policy_name,
                "summary": jsonable(summary),
                "summary_by_template_kind": _summaries_by_field(run_records, "template_kind"),
                "summary_by_template_split": _summaries_by_field(run_records, "template_split"),
                "summary_by_template_id": _summaries_by_field(run_records, "template_id"),
                "failure_examples": failure_examples,
                "scenarios": [
                    {
                        "scenario_id": record["scenario_id"],
                        "transcript": render_scenario_transcript(scenarios[index]),
                        "scenario": record["scenario"],
                        "question_traces": record["question_traces"],
                        "store_snapshot": record["store_snapshot"],
                        "metrics": record["metrics"],
                        "failure_examples": record["failure_examples"],
                        "candidate_stream_sha256": record["candidate_stream_sha256"],
                        "extracted_candidate_stream": jsonable(
                            adapted_by_scenario[record["scenario_id"]].candidates
                        ),
                        "adapter_drops": adapted_by_scenario[record["scenario_id"]].drops,
                    }
                    for index, record in enumerate(run_records)
                ],
            }
        )

    hash_mismatches = candidate_stream_hash_mismatches(stream_hashes_by_policy)
    if hash_mismatches:
        raise NoisyPolicyComparisonError(
            "Candidate stream hash mismatch across policies: {}".format(hash_mismatches)
        )
    return {
        "experiment": "noisy_policy_comparison_{}_{}".format(family, schema_profile),
        "mode": "extracted",
        "family": family,
        "requested_scenario_count": requested_scenario_count,
        "scenario_count": len(scenarios),
        "template_mix": template_mix,
        "policy_set": policy_set,
        "schema_profile": schema_profile,
        "predictions_path": str(predictions_path) if predictions_path else "",
        "predictions_sha256": sha256_file(predictions_path) if predictions_path else "",
        "candidate_adapter_sha256": adapter_sha256,
        "preregistration_lock_sha256": preregistration_lock_sha256,
        "candidate_stream_audit": candidate_stream_audit,
        "candidate_stream_sha256_by_policy": stream_hashes_by_policy,
        "candidate_stream_hash_mismatches": hash_mismatches,
        "candidate_stream_hash_invariant_passed": not hash_mismatches,
        "policies": policy_runs,
    }


def candidate_stream_hash_mismatches(
    stream_hashes_by_policy: Mapping[str, Mapping[str, str]],
) -> List[Dict[str, object]]:
    policies = sorted(stream_hashes_by_policy)
    if not policies:
        return []
    scenario_ids = sorted(
        {
            scenario_id
            for policy_hashes in stream_hashes_by_policy.values()
            for scenario_id in policy_hashes
        }
    )
    mismatches = []
    for scenario_id in scenario_ids:
        observed = {
            policy_name: stream_hashes_by_policy[policy_name].get(scenario_id)
            for policy_name in policies
        }
        values = {value for value in observed.values() if value is not None}
        if len(values) > 1 or any(value is None for value in observed.values()):
            mismatches.append({"scenario_id": scenario_id, "hashes_by_policy": observed})
    return mismatches


def store_class_for_policy(policy_cls: Type[object]) -> Type[object]:
    policy = policy_cls()
    return policy.store.__class__


def policies_use_memory_store(policy_classes: Iterable[Type[object]]) -> bool:
    return all(store_class_for_policy(policy_cls) is MemoryStore for policy_cls in policy_classes)


def _candidate_from_prediction(
    scenario: Scenario,
    event: ScenarioEvent,
    prediction: CandidateComponentPrediction,
    *,
    prediction_index: int,
    prediction_ordinal: int,
) -> Tuple[Optional[CandidateUpdate], Optional[Dict[str, object]]]:
    raw_claim = _required_text(prediction.raw_claim)
    if not raw_claim.strip():
        return None, _drop(event_id=event.event_id, prediction_index=prediction_index, reason="empty_raw_claim")
    canonical_id = _required_text(prediction.canonical_id)
    if not canonical_id.strip():
        return None, _drop(event_id=event.event_id, prediction_index=prediction_index, reason="empty_canonical_id")
    try:
        claim_type = ClaimType(prediction.claim_type)
    except ValueError:
        return None, _drop(
            event_id=event.event_id,
            prediction_index=prediction_index,
            reason="unrecognized_claim_type",
            value=prediction.claim_type,
        )
    try:
        scope_level = ScopeLevel(prediction.scope_level)
    except ValueError:
        return None, _drop(
            event_id=event.event_id,
            prediction_index=prediction_index,
            reason="unrecognized_scope_level",
            value=prediction.scope_level,
        )
    scope_key = _required_text(prediction.scope_key)
    if not scope_key.strip():
        return None, _drop(event_id=event.event_id, prediction_index=prediction_index, reason="empty_scope_key")
    confidence = prediction.confidence
    if confidence is None:
        verification_score = 0.5
    elif isinstance(confidence, float) and 0.0 <= confidence <= 1.0 and not math.isnan(confidence):
        verification_score = float(confidence)
    else:
        return None, _drop(
            event_id=event.event_id,
            prediction_index=prediction_index,
            reason="invalid_confidence",
            value=confidence,
        )
    observed_at = LOCKED_EPOCH + timedelta(seconds=event.turn_index)
    candidate = CandidateUpdate(
        candidate_id="{}::{}::{}".format(
            scenario.scenario_id,
            event.event_id,
            prediction_ordinal,
        ),
        raw_text=event.text,
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
                source_kind="extractor",
                source_id="extractor::{}::{}".format(scenario.scenario_id, event.event_id),
                trust_score=verification_score,
                observed_at=observed_at,
            )
        ],
        verification_score=verification_score,
        contradicts=[],
        supports=[],
    )
    return candidate, None


def _required_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _apply_contradictions(
    candidates: Sequence[CandidateUpdate],
    pending_contradiction_targets: Mapping[str, Sequence[str]],
    emitted_ids_by_event: Mapping[str, Sequence[str]],
) -> None:
    for candidate in candidates:
        targets = []
        seen = set()
        for target_event_id in pending_contradiction_targets.get(candidate.candidate_id, []):
            for target_candidate_id in emitted_ids_by_event.get(target_event_id, []):
                if target_candidate_id not in seen:
                    targets.append(target_candidate_id)
                    seen.add(target_candidate_id)
        candidate.contradicts = targets


def _apply_supports(
    candidates: Sequence[CandidateUpdate],
    event_by_id: Mapping[str, ScenarioEvent],
) -> None:
    previous_by_cluster: Dict[Tuple[str, str, str, str], List[str]] = {}
    for candidate in sorted(
        candidates,
        key=lambda item: (
            event_by_id[_event_id_from_rewritten_candidate_id(item.candidate_id)].turn_index,
            _ordinal_from_rewritten_candidate_id(item.candidate_id),
        ),
    ):
        event_id = _event_id_from_rewritten_candidate_id(candidate.candidate_id)
        event = event_by_id[event_id]
        key = (
            candidate.canonical_id or "",
            candidate.claim_type.value,
            candidate.scope_level.value,
            candidate.scope_key,
        )
        supports = []
        for support_id in previous_by_cluster.get(key, []):
            support_event_id = _event_id_from_rewritten_candidate_id(support_id)
            support_event = event_by_id[support_event_id]
            if support_event.turn_index < event.turn_index:
                supports.append(support_id)
        candidate.supports = supports
        previous_by_cluster.setdefault(key, []).append(candidate.candidate_id)


def _candidate_ids_by_oracle_candidate_id(
    scenario: Scenario,
    emitted_ids_by_event: Mapping[str, Sequence[str]],
) -> Dict[str, List[str]]:
    mapping = {}
    for event in scenario.sorted_events():
        if event.kind != EventKind.OBSERVATION or event.candidate is None:
            continue
        mapping[event.candidate.candidate_id] = list(emitted_ids_by_event.get(event.event_id, []))
    return mapping


def _map_question_ids(
    question: QuestionSpec,
    candidate_ids_by_oracle_candidate_id: Mapping[str, Sequence[str]],
) -> QuestionSpec:
    return replace(
        question,
        gold_candidate_ids=_map_candidate_id_list(
            question.gold_candidate_ids,
            candidate_ids_by_oracle_candidate_id,
        ),
        forbidden_candidate_ids=_map_candidate_id_list(
            question.forbidden_candidate_ids,
            candidate_ids_by_oracle_candidate_id,
        ),
    )


def _map_expected_lifecycle_ids(
    scenario: Scenario,
    candidate_ids_by_oracle_candidate_id: Mapping[str, Sequence[str]],
) -> Dict[str, object]:
    mapped = {}
    for key, value in scenario.expected_lifecycle.items():
        if key == "contradiction_timestamp" and isinstance(value, str):
            mapped[key] = _mapped_contradiction_timestamp(scenario)
        elif key.endswith("_candidate_ids") and isinstance(value, list):
            mapped[key] = _map_candidate_id_list(value, candidate_ids_by_oracle_candidate_id)
        elif key.endswith("_candidate_id") and isinstance(value, str):
            mapped[key] = _map_candidate_id_scalar(value, candidate_ids_by_oracle_candidate_id)
        else:
            mapped[key] = value
    return mapped


def _map_candidate_id_list(
    candidate_ids: Sequence[str],
    candidate_ids_by_oracle_candidate_id: Mapping[str, Sequence[str]],
) -> List[str]:
    mapped = []
    for candidate_id in candidate_ids:
        mapped.extend(candidate_ids_by_oracle_candidate_id.get(candidate_id, []))
    return mapped


def _map_candidate_id_scalar(
    candidate_id: str,
    candidate_ids_by_oracle_candidate_id: Mapping[str, Sequence[str]],
) -> str:
    mapped = list(candidate_ids_by_oracle_candidate_id.get(candidate_id, []))
    return mapped[0] if mapped else ""


def _mapped_contradiction_timestamp(scenario: Scenario) -> str:
    old_candidate_ids = {
        value
        for key, value in scenario.expected_lifecycle.items()
        if key.endswith("_candidate_id") and key.startswith("old") and isinstance(value, str)
    }
    for event in scenario.sorted_events():
        if event.kind != EventKind.OBSERVATION or event.candidate is None:
            continue
        if old_candidate_ids.intersection(event.candidate.contradicts):
            return (LOCKED_EPOCH + timedelta(seconds=event.turn_index)).isoformat()
    return scenario.expected_lifecycle.get("contradiction_timestamp", "")


def _question_by_id(scenario: Scenario, question_id: str) -> QuestionSpec:
    for event in scenario.sorted_events():
        if event.question is not None and event.question.question_id == question_id:
            return event.question
    raise ValueError("Question '{}' not found in scenario '{}'".format(question_id, scenario.scenario_id))


def _event_id_from_rewritten_candidate_id(candidate_id: str) -> str:
    parts = candidate_id.rsplit("::", 2)
    if len(parts) != 3:
        raise ValueError("Malformed rewritten candidate id: {}".format(candidate_id))
    return parts[1]


def _ordinal_from_rewritten_candidate_id(candidate_id: str) -> int:
    return int(candidate_id.rsplit("::", 1)[1])


def _drop(
    *,
    event_id: str,
    prediction_index: int,
    reason: str,
    value: object = None,
    canonical_id: str = "",
) -> Dict[str, object]:
    payload = {
        "event_id": event_id,
        "prediction_index": prediction_index,
        "reason": reason,
    }
    if value is not None:
        payload["value"] = value
    if canonical_id:
        payload["canonical_id"] = canonical_id
    return payload


def _summaries_by_field(run_records: List[dict], field_name: str) -> Dict[str, dict]:
    grouped = {}
    for record in run_records:
        field_value = record["scenario"].get(field_name, "")
        grouped.setdefault(field_value, []).append(record)
    return {
        field_value: jsonable(summarize_runs(group_records))
        for field_value, group_records in sorted(grouped.items())
        if field_value
    }


def _validate_gate_summary(
    summary: Mapping[str, object],
    *,
    schema_profile: str,
    summary_path: Path,
) -> None:
    checks = [
        ("policy_comparison_unlocked", summary.get("policy_comparison_unlocked"), True),
        ("primary_model_tag", summary.get("primary_model_tag"), LOCKED_MODEL_TAG),
        ("primary_model_digest", summary.get("primary_model_digest"), LOCKED_MODEL_DIGEST),
        ("expected_primary_model_digest", summary.get("expected_primary_model_digest"), LOCKED_MODEL_DIGEST),
        ("general_prompt_sha256", summary.get("general_prompt_sha256"), LOCKED_PROMPT_SHA256),
        ("schema_profile", summary.get("schema_profile"), schema_profile),
    ]
    for field_name, observed, expected in checks:
        if observed != expected:
            raise NoisyPolicyComparisonError(
                "Gate summary {} mismatch in {}: observed {!r}, expected {!r}".format(
                    field_name,
                    summary_path,
                    observed,
                    expected,
                )
            )


def _validate_gate_manifest(manifest_path: Path, summary_path: Path) -> None:
    manifest = _read_json(manifest_path)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise NoisyPolicyComparisonError("Manifest has no artifacts: {}".format(manifest_path))
    summary_sha = sha256_file(summary_path)
    artifact = artifacts[0]
    observed = artifact.get("summary_json_sha256") if isinstance(artifact, dict) else None
    if observed != summary_sha:
        raise NoisyPolicyComparisonError(
            "Manifest summary SHA mismatch: observed {}, expected {}".format(observed, summary_sha)
        )


def _repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _read_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
