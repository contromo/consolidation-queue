from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from cq.eval.component_eval import CandidateComponentPrediction
from cq.eval.runner import (
    FORCED_CONTRADICTION,
    TEMPLATE_MIXES_BY_FAMILY,
    generate_scenarios,
)
from cq.schemas.memory import ClaimType, ScopeLevel, jsonable
from cq.schemas.scenario import EventKind, Scenario


WEAK_MODE = "weak"
POSITIVE_CONTROL_MODE = "positive_control"
MODEL_MODE = "model"
EXTRACTOR_MODES = (WEAK_MODE, POSITIVE_CONTROL_MODE, MODEL_MODE)
MAX_MODEL_STDOUT_BYTES = 1_000_000
MAX_MODEL_STDERR_BYTES = 200_000


@dataclass(frozen=True)
class TranscriptEventInput:
    event_id: str
    event_kind: str
    turn_index: int
    text: str


@dataclass(frozen=True)
class TranscriptScenarioInput:
    scenario_id: str
    events: List[TranscriptEventInput]


@dataclass(frozen=True)
class ModelExtractorConfig:
    model_command: str
    model_argv: List[str]
    model_id: str
    prompt_template_path: Path
    prompt_template_text: str
    decoding_params: Dict[str, object]
    per_scenario_timeout_seconds: float


_COMPANY = r"[A-Z][A-Za-z]+"
# Positive-control patterns mirror the forced-contradiction observation
# templates in cq/simulator/scenario_generator.py; update both when template
# wording changes.
_FORCED_CONTRADICTION_PATTERNS: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("positive", re.compile(r"^(?P<buyer>{c}) acquired (?P<target>{c})\.$".format(c=_COMPANY))),
    (
        "positive",
        re.compile(
            r"^(?P<buyer>{c}) completed the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "positive",
        re.compile(r"^(?P<target>{c}) was acquired by (?P<buyer>{c})\.$".format(c=_COMPANY)),
    ),
    (
        "positive",
        re.compile(
            r"^(?P<buyer>{c}) later confirmed the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "positive",
        re.compile(
            r"^A follow-up report repeats that (?P<buyer>{c}) completed the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A trusted filing says (?P<buyer>{c})'s acquisition talks with (?P<target>{c}) collapsed\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A regulator filing says (?P<buyer>{c}) did not acquire (?P<target>{c}); the talks ended\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^Later reporting says the (?P<buyer>{c})-(?P<target>{c}) acquisition did not happen\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A credible but not definitive filing suggests (?P<buyer>{c})'s acquisition of (?P<target>{c}) may have fallen through\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A follow-up report indicates (?P<buyer>{c}) likely did not complete the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^Later reporting casts substantial doubt on whether (?P<buyer>{c}) acquired (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
    (
        "negative",
        re.compile(
            r"^A later clarification confirms (?P<buyer>{c}) did not complete the acquisition of (?P<target>{c})\.$".format(
                c=_COMPANY
            )
        ),
    ),
)


def sanitize_scenario_for_extraction(scenario: Scenario) -> TranscriptScenarioInput:
    return TranscriptScenarioInput(
        scenario_id=scenario.scenario_id,
        events=[
            TranscriptEventInput(
                event_id=event.event_id,
                event_kind=event.kind.value,
                turn_index=event.turn_index,
                text=event.text,
            )
            for event in scenario.sorted_events()
        ],
    )


def extract_predictions_for_scenario(
    transcript_scenario: TranscriptScenarioInput,
    mode: str,
    model_config: Optional[ModelExtractorConfig] = None,
) -> List[CandidateComponentPrediction]:
    if not isinstance(transcript_scenario, TranscriptScenarioInput):
        raise TypeError("Extractor input must be TranscriptScenarioInput")
    if mode == WEAK_MODE:
        return []
    if mode == POSITIVE_CONTROL_MODE:
        return _positive_control_forced_contradiction(transcript_scenario)
    if mode == MODEL_MODE:
        if model_config is None:
            raise ValueError("model_config is required for model mode")
        # Keep this fail-fast single-scenario path in lockstep with the
        # batch adapter path; both send the same transcript-only envelope.
        predictions, error = _run_model_for_scenario(transcript_scenario, model_config)
        if error is not None:
            raise ValueError(str(error["message"]))
        return predictions
    raise ValueError("Unsupported extractor mode: {}".format(mode))


def extract_predictions_by_scenario(
    transcript_scenarios: Sequence[TranscriptScenarioInput],
    mode: str,
    model_config: Optional[ModelExtractorConfig] = None,
) -> Dict[str, List[CandidateComponentPrediction]]:
    return {
        transcript_scenario.scenario_id: extract_predictions_for_scenario(
            transcript_scenario,
            mode,
            model_config=model_config,
        )
        for transcript_scenario in transcript_scenarios
    }


def build_extractor_output(
    *,
    family: str,
    scenario_count: int,
    template_mix: str,
    mode: str,
    model_command: str = "",
    model_id: str = "",
    prompt_template_path: str = "",
    decoding_json: str = "{}",
    per_scenario_timeout_seconds: float = 120.0,
) -> Dict[str, object]:
    scenarios = generate_scenarios(family, scenario_count, template_mix)
    transcript_scenarios = [sanitize_scenario_for_extraction(scenario) for scenario in scenarios]
    if mode == POSITIVE_CONTROL_MODE and family != FORCED_CONTRADICTION:
        raise ValueError("positive_control mode is only defined for forced_contradiction")

    scenario_predictions: Dict[str, List[CandidateComponentPrediction]] = {}
    scenario_errors: Dict[str, object] = {}
    model_config = None
    model_metadata: Dict[str, object] = {}
    scenario_input_sha256: Dict[str, str] = {}
    if mode == MODEL_MODE:
        model_config = _build_model_config(
            model_command=model_command,
            model_id=model_id,
            prompt_template_path=prompt_template_path,
            decoding_json=decoding_json,
            per_scenario_timeout_seconds=per_scenario_timeout_seconds,
        )
        model_metadata = _model_metadata(model_config)
        for transcript_scenario in transcript_scenarios:
            scenario_input_sha256[transcript_scenario.scenario_id] = _model_stdin_sha256(
                transcript_scenario,
                model_config,
            )
            predictions, error = _run_model_for_scenario(transcript_scenario, model_config)
            if error is None:
                scenario_predictions[transcript_scenario.scenario_id] = predictions
            else:
                scenario_predictions[transcript_scenario.scenario_id] = []
                scenario_errors[transcript_scenario.scenario_id] = error
    else:
        scenario_predictions = extract_predictions_by_scenario(transcript_scenarios, mode)

    output = {
        "mode": mode,
        "family": family,
        "template_mix": template_mix,
        "requested_scenario_count": scenario_count,
        "scenario_count": len(transcript_scenarios),
        "attempted_scenario_count": len(transcript_scenarios),
        "successful_scenario_count": len(transcript_scenarios) - len(scenario_errors),
        "input_contract": "transcript_only",
        "scenario_errors": scenario_errors,
        "scenario_predictions": jsonable(scenario_predictions),
    }
    output.update(model_metadata)
    if scenario_input_sha256:
        output["scenario_input_sha256"] = scenario_input_sha256
    return output


def _build_model_config(
    *,
    model_command: str,
    model_id: str,
    prompt_template_path: str,
    decoding_json: str,
    per_scenario_timeout_seconds: float,
) -> ModelExtractorConfig:
    if not model_command.strip():
        raise ValueError("--model-command is required for model mode")
    if not model_id.strip():
        raise ValueError("--model-id is required for model mode")
    if not prompt_template_path.strip():
        raise ValueError("--prompt-template-path is required for model mode")
    if per_scenario_timeout_seconds <= 0:
        raise ValueError("--per-scenario-timeout-seconds must be positive")
    prompt_path = Path(prompt_template_path)
    try:
        prompt_template_text = prompt_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError("Could not read prompt template: {}".format(error))
    try:
        model_argv = shlex.split(model_command)
    except ValueError as error:
        raise ValueError("--model-command could not be parsed: {}".format(error))
    if not model_argv:
        raise ValueError("--model-command is required for model mode")
    return ModelExtractorConfig(
        model_command=model_command,
        model_argv=model_argv,
        model_id=model_id,
        prompt_template_path=prompt_path,
        prompt_template_text=prompt_template_text,
        decoding_params=_parse_decoding_json(decoding_json),
        per_scenario_timeout_seconds=per_scenario_timeout_seconds,
    )


def _parse_decoding_json(decoding_json: str) -> Dict[str, object]:
    try:
        payload = json.loads(decoding_json or "{}")
    except json.JSONDecodeError as error:
        raise ValueError("--decoding-json must be a JSON object: {}".format(error))
    if not isinstance(payload, dict):
        raise ValueError("--decoding-json must be a JSON object")
    return payload


def _model_metadata(config: ModelExtractorConfig) -> Dict[str, object]:
    prompt_text = config.prompt_template_text
    return {
        "model_command": config.model_command,
        "model_id": config.model_id,
        "prompt_template_path": str(config.prompt_template_path),
        "prompt_template_sha256": hashlib.sha256(
            prompt_text.encode("utf-8")
        ).hexdigest(),
        "prompt_template_text": prompt_text,
        "decoding_params": config.decoding_params,
        "per_scenario_timeout_seconds": config.per_scenario_timeout_seconds,
    }


def _model_stdin_sha256(
    transcript_scenario: TranscriptScenarioInput,
    config: ModelExtractorConfig,
) -> str:
    payload = _model_stdin_payload(transcript_scenario, config)
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _run_model_for_scenario(
    transcript_scenario: TranscriptScenarioInput,
    config: ModelExtractorConfig,
) -> Tuple[List[CandidateComponentPrediction], Optional[Dict[str, object]]]:
    stdin_payload = _model_stdin_payload(transcript_scenario, config)
    stdin_text = json.dumps(stdin_payload, indent=2, sort_keys=True)
    try:
        stdin_bytes = stdin_text.encode("utf-8")
    except UnicodeEncodeError as error:
        return [], _scenario_error("input_encoding_error", str(error))
    try:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                completed = subprocess.run(
                    config.model_argv,
                    input=stdin_bytes,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=config.per_scenario_timeout_seconds,
                )
            except subprocess.TimeoutExpired:
                stderr_status = _read_capped_tempfile(stderr_file, MAX_MODEL_STDERR_BYTES)
                return [], _scenario_error(
                    "timeout",
                    "Model command timed out after {} seconds".format(
                        config.per_scenario_timeout_seconds
                    ),
                    stderr=stderr_status["text"],
                    stderr_bytes=stderr_status["byte_count"],
                    stderr_truncated=stderr_status["truncated"],
                )
            stdout_status = _read_capped_tempfile(stdout_file, MAX_MODEL_STDOUT_BYTES)
            stderr_status = _read_capped_tempfile(stderr_file, MAX_MODEL_STDERR_BYTES)
    except OSError as error:
        return [], _scenario_error("command_error", str(error))

    if stdout_status["truncated"]:
        return [], _scenario_error(
            "output_too_large",
            "Model stdout exceeded {} bytes".format(MAX_MODEL_STDOUT_BYTES),
            stdout=stdout_status["text"],
            stdout_bytes=stdout_status["byte_count"],
            stderr=stderr_status["text"],
            stderr_bytes=stderr_status["byte_count"],
            stderr_truncated=stderr_status["truncated"],
        )
    if completed.returncode != 0:
        return [], _scenario_error(
            "nonzero_exit",
            "Model command exited with status {}".format(completed.returncode),
            returncode=completed.returncode,
            stderr=stderr_status["text"],
            stderr_bytes=stderr_status["byte_count"],
            stderr_truncated=stderr_status["truncated"],
        )
    try:
        payload = json.loads(stdout_status["text"])
    except json.JSONDecodeError as error:
        return [], _scenario_error(
            "malformed_json",
            "Model stdout was not strict JSON: {}".format(error),
            stdout=stdout_status["text"],
            stdout_bytes=stdout_status["byte_count"],
            stderr=stderr_status["text"],
            stderr_bytes=stderr_status["byte_count"],
            stderr_truncated=stderr_status["truncated"],
        )
    try:
        return _validate_model_output_payload(payload, transcript_scenario), None
    except ValueError as error:
        return [], _scenario_error(
            "validation_error",
            str(error),
            stdout=stdout_status["text"],
            stdout_bytes=stdout_status["byte_count"],
            stderr=stderr_status["text"],
            stderr_bytes=stderr_status["byte_count"],
            stderr_truncated=stderr_status["truncated"],
        )


def _model_stdin_payload(
    transcript_scenario: TranscriptScenarioInput,
    config: ModelExtractorConfig,
) -> Dict[str, object]:
    return {
        "input_contract": "transcript_only",
        "model_id": config.model_id,
        "decoding_params": config.decoding_params,
        "prompt": config.prompt_template_text,
        "scenario": jsonable(transcript_scenario),
        "output_contract": {
            "stdout_json": {
                "predictions": [
                    {
                        "event_id": "event id from input",
                        "candidate_id": "",
                        "canonical_id": "stable cluster id",
                        "claim_type": sorted(item.value for item in ClaimType),
                        "scope_level": sorted(item.value for item in ScopeLevel),
                        "scope_key": "scope key string",
                        "contradicts_event_ids": ["event ids from input"],
                        "raw_claim": "short extracted claim",
                        "confidence": "number or null",
                    }
                ]
            }
        },
    }


def _validate_model_output_payload(
    payload: object,
    transcript_scenario: TranscriptScenarioInput,
) -> List[CandidateComponentPrediction]:
    if not isinstance(payload, dict):
        raise ValueError("Model stdout must be a JSON object")
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise ValueError("Model stdout must contain a predictions list")

    known_event_ids = {event.event_id for event in transcript_scenario.events}
    valid_claim_types = {item.value for item in ClaimType}
    valid_scope_levels = {item.value for item in ScopeLevel}
    seen_pairs = set()
    validated = []
    for index, mapping in enumerate(predictions):
        if not isinstance(mapping, dict):
            raise ValueError("Prediction {} must be an object".format(index))
        event_id = _required_string(mapping, "event_id", index)
        if event_id not in known_event_ids:
            raise ValueError(
                "Prediction {} uses unknown event_id '{}'".format(index, event_id)
            )
        candidate_id = str(mapping.get("candidate_id") or "")
        if candidate_id:
            raise ValueError(
                "Prediction {} must leave candidate_id empty in model mode".format(index)
            )
        if mapping.get("contradicts"):
            raise ValueError(
                "Prediction {} must use contradicts_event_ids, not legacy candidate ids".format(
                    index
                )
            )
        canonical_id = _required_string(mapping, "canonical_id", index)
        claim_type = _required_string(mapping, "claim_type", index)
        if claim_type not in valid_claim_types:
            raise ValueError(
                "Prediction {} has invalid claim_type '{}'".format(index, claim_type)
            )
        scope_level = _required_string(mapping, "scope_level", index)
        if scope_level not in valid_scope_levels:
            raise ValueError(
                "Prediction {} has invalid scope_level '{}'".format(index, scope_level)
            )
        scope_key = _required_string(mapping, "scope_key", index)
        pair = (event_id, canonical_id)
        if pair in seen_pairs:
            raise ValueError(
                "Prediction {} duplicates event_id/canonical_id pair {}".format(
                    index,
                    pair,
                )
            )
        seen_pairs.add(pair)
        contradicts_event_ids = _event_id_list(
            mapping.get("contradicts_event_ids") or [],
            known_event_ids,
            index,
        )
        validated.append(
            CandidateComponentPrediction(
                event_id=event_id,
                candidate_id="",
                canonical_id=canonical_id,
                claim_type=claim_type,
                scope_level=scope_level,
                scope_key=scope_key,
                contradicts_event_ids=contradicts_event_ids,
                raw_claim=str(mapping.get("raw_claim") or ""),
                confidence=_optional_float(mapping.get("confidence")),
            )
        )
    return validated


def _required_string(mapping: Dict[str, object], field_name: str, index: int) -> str:
    value = mapping.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(
            "Prediction {} must include non-empty string {}".format(index, field_name)
        )
    return value


def _event_id_list(
    values: object,
    known_event_ids: set,
    index: int,
) -> List[str]:
    if not isinstance(values, list):
        raise ValueError(
            "Prediction {} contradicts_event_ids must be a list".format(index)
        )
    event_ids = []
    for value in values:
        if not isinstance(value, str) or not value:
            raise ValueError(
                "Prediction {} has malformed contradicts_event_ids item".format(index)
            )
        if value not in known_event_ids:
            raise ValueError(
                "Prediction {} uses unknown contradicts_event_id '{}'".format(
                    index,
                    value,
                )
            )
        event_ids.append(value)
    return event_ids


def _optional_float(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("confidence must be numeric or null")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        raise ValueError("confidence must be numeric or null")


def _scenario_error(error_type: str, message: str, **details: object) -> Dict[str, object]:
    error = {
        "error_type": error_type,
        "message": message,
    }
    error.update({key: value for key, value in details.items() if value not in (None, "")})
    return error


def _truncate(text: object, limit: int = 4000) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    return value[:limit] + "...<truncated>"


def _read_capped_tempfile(handle, max_bytes: int) -> Dict[str, object]:
    handle.seek(0, 2)
    byte_count = handle.tell()
    handle.seek(0)
    data = handle.read(max_bytes + 1)
    truncated = len(data) > max_bytes or byte_count > max_bytes
    if truncated:
        data = data[:max_bytes]
    return {
        "text": data.decode("utf-8", errors="replace"),
        "byte_count": byte_count,
        "truncated": truncated,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write transcript-only component predictions for local extractor smoke tests."
    )
    parser.add_argument("--family", default=FORCED_CONTRADICTION, choices=sorted(TEMPLATE_MIXES_BY_FAMILY))
    parser.add_argument("--scenarios", type=int, default=25)
    parser.add_argument("--template-mix", default="mixed")
    parser.add_argument("--mode", choices=EXTRACTOR_MODES, default=WEAK_MODE)
    parser.add_argument("--model-command", default="")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--prompt-template-path", default="")
    parser.add_argument("--decoding-json", default="{}")
    parser.add_argument("--per-scenario-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)

    try:
        output = build_extractor_output(
            family=args.family,
            scenario_count=args.scenarios,
            template_mix=args.template_mix,
            mode=args.mode,
            model_command=args.model_command,
            model_id=args.model_id,
            prompt_template_path=args.prompt_template_path,
            decoding_json=args.decoding_json,
            per_scenario_timeout_seconds=args.per_scenario_timeout_seconds,
        )
    except ValueError as error:
        parser.error(str(error))

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Wrote {}".format(output_path))
    return 0


def _positive_control_forced_contradiction(
    transcript_scenario: TranscriptScenarioInput,
) -> List[CandidateComponentPrediction]:
    predictions: List[CandidateComponentPrediction] = []
    positive_events_by_canonical: Dict[str, List[str]] = {}
    for event in sorted(transcript_scenario.events, key=lambda item: item.turn_index):
        if event.event_kind != EventKind.OBSERVATION.value:
            continue
        parsed = _parse_forced_contradiction_observation(event.text)
        if parsed is None:
            continue
        polarity, buyer, target = parsed
        canonical_id = _forced_contradiction_canonical_id(buyer, target)
        contradicts_event_ids = []
        if polarity == "negative":
            contradicts_event_ids = list(positive_events_by_canonical.get(canonical_id, []))
        prediction = CandidateComponentPrediction(
            event_id=event.event_id,
            candidate_id="",
            canonical_id=canonical_id,
            claim_type="world_fact",
            scope_level="world_global",
            scope_key="global",
            contradicts_event_ids=contradicts_event_ids,
            raw_claim=event.text,
            confidence=1.0,
        )
        predictions.append(prediction)
        if polarity == "positive":
            positive_events_by_canonical.setdefault(canonical_id, []).append(event.event_id)
    return predictions


def _parse_forced_contradiction_observation(
    text: str,
) -> Optional[Tuple[str, str, str]]:
    for polarity, pattern in _FORCED_CONTRADICTION_PATTERNS:
        match = pattern.match(text)
        if match:
            return polarity, match.group("buyer"), match.group("target")
    return None


def _forced_contradiction_canonical_id(buyer: str, target: str) -> str:
    return "world-fact-{}-{}-acquisition-status".format(
        buyer.lower(),
        target.lower(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
