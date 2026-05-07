from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


WRAPPER_NAME = "ollama_component_extractor"
WRAPPER_VERSION = "v1"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
CONNECT_TIMEOUT_SECONDS = 5.0
MIN_OLLAMA_VERSION = (0, 23, 0)
REPAIR_COUNT_KEYS = (
    "candidate_id_cleared",
    "contradicts_renamed",
    "extra_top_level_dropped",
)


class OllamaCommandError(Exception):
    """Raised when the local Ollama backend is unavailable or unusable."""


class OllamaHttpClient:
    """Minimal Ollama client.

    OLLAMA_BASE_URL may route transcript text away from localhost when set
    to a non-loopback URL; the default is local-only.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).rstrip("/")

    def get_version(self) -> str:
        payload = self._request_json("GET", "/api/version", None, CONNECT_TIMEOUT_SECONDS)
        version = payload.get("version") if isinstance(payload, dict) else None
        if not isinstance(version, str) or not version:
            raise OllamaCommandError("Ollama version response did not include a version")
        return version

    def get_model_digest(self, model_id: str) -> str:
        payload = self._request_json("GET", "/api/tags", None, CONNECT_TIMEOUT_SECONDS)
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise OllamaCommandError("Ollama tags response did not include a models list")
        for model in models:
            if not isinstance(model, dict):
                continue
            names = {str(value) for value in (model.get("name"), model.get("model")) if value}
            if model_id in names:
                digest = model.get("digest")
                if not isinstance(digest, str) or not digest:
                    raise OllamaCommandError(
                        "Ollama model '{}' did not include a digest".format(model_id)
                    )
                return _normalize_digest(digest)
        raise OllamaCommandError(
            "Ollama model '{}' is not installed; install that exact tag before running this smoke test".format(
                model_id
            )
        )

    def generate(
        self,
        *,
        model_id: str,
        prompt: str,
        output_schema: Dict[str, object],
        decoding_params: Dict[str, object],
    ) -> str:
        payload = {
            "model": model_id,
            "prompt": prompt,
            "stream": False,
            "format": output_schema,
            "options": decoding_params,
        }
        response = self._request_json("POST", "/api/generate", payload, None)
        text = response.get("response") if isinstance(response, dict) else None
        if not isinstance(text, str):
            raise OllamaCommandError("Ollama generate response did not include text")
        return text

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, object]],
        timeout: Optional[float],
    ) -> object:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise OllamaCommandError(
                "Ollama HTTP {} for {}: {}".format(error.code, path, body)
            )
        except urllib.error.URLError as error:
            raise OllamaCommandError(
                "Cannot connect to Ollama at {}: {}".format(self.base_url, error.reason)
            )
        except TimeoutError as error:
            raise OllamaCommandError(
                "Timed out connecting to Ollama at {}: {}".format(self.base_url, error)
            )
        except json.JSONDecodeError as error:
            raise OllamaCommandError(
                "Ollama response for {} was not JSON: {}".format(path, error)
            )


def build_extraction_output(
    envelope: Dict[str, object],
    client: Optional[OllamaHttpClient] = None,
) -> Dict[str, object]:
    client = client or OllamaHttpClient()
    model_id = _required_string(envelope, "model_id")
    scenario = _required_mapping(envelope, "scenario")
    scenario_id = _required_string(scenario, "scenario_id")
    known_event_ids = _known_event_ids(scenario)
    decoding_params = envelope.get("decoding_params") or {}
    if not isinstance(decoding_params, dict):
        raise OllamaCommandError("decoding_params must be an object")

    ollama_server_version = client.get_version()
    _ensure_supported_ollama_version(ollama_server_version)
    model_digest = client.get_model_digest(model_id)
    model_text = client.generate(
        model_id=model_id,
        prompt=build_generation_prompt(envelope),
        output_schema=build_output_schema(envelope),
        decoding_params=decoding_params,
    )
    try:
        model_payload = json.loads(model_text)
    except json.JSONDecodeError as error:
        raise OllamaCommandError("Model response was not strict JSON: {}".format(error))
    if not isinstance(model_payload, dict):
        raise OllamaCommandError("Model response JSON was not an object")

    output, repair_counts = normalize_model_payload(model_payload, known_event_ids)
    output["model_diagnostics"] = build_model_diagnostics(
        ollama_server_version=ollama_server_version,
        model_digest=model_digest,
        scenario_id=scenario_id,
        repair_counts=repair_counts,
    )
    return output


def build_generation_prompt(envelope: Dict[str, object]) -> str:
    prompt = _required_string(envelope, "prompt").strip()
    scenario = _required_mapping(envelope, "scenario")
    output_contract = _required_mapping(envelope, "output_contract")
    return "\n\n".join(
        (
            prompt,
            "Transcript-only scenario JSON:",
            json.dumps(scenario, indent=2, sort_keys=True),
            "Output contract JSON:",
            json.dumps(output_contract, indent=2, sort_keys=True),
            "Return exactly one JSON object. Do not include prose or markdown.",
        )
    )


def build_output_schema(envelope: Dict[str, object]) -> Dict[str, object]:
    claim_types, scope_levels = _enum_values_from_output_contract(envelope)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["predictions"],
        "properties": {
            "predictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "event_id",
                        "canonical_id",
                        "claim_type",
                        "scope_level",
                        "scope_key",
                        "contradicts_event_ids",
                        "raw_claim",
                        "confidence",
                    ],
                    "properties": {
                        "event_id": {"type": "string"},
                        "candidate_id": {"type": "string", "enum": [""]},
                        "canonical_id": {"type": "string"},
                        "claim_type": {"type": "string", "enum": claim_types},
                        "scope_level": {"type": "string", "enum": scope_levels},
                        "scope_key": {"type": "string"},
                        "contradicts_event_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "raw_claim": {"type": "string"},
                        "confidence": {"type": ["number", "null"]},
                    },
                },
            }
        },
    }


def normalize_model_payload(
    payload: Dict[str, object],
    known_event_ids: Iterable[str],
) -> Tuple[Dict[str, object], Dict[str, int]]:
    known_event_id_set = set(known_event_ids)
    repair_counts = {key: 0 for key in REPAIR_COUNT_KEYS}
    extra_keys = sorted(set(payload) - {"predictions"})
    repair_counts["extra_top_level_dropped"] = len(extra_keys)
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        return {"predictions": predictions}, repair_counts

    repaired_predictions: List[object] = []
    for prediction in predictions:
        if not isinstance(prediction, dict):
            repaired_predictions.append(prediction)
            continue
        repaired = dict(prediction)
        if repaired.get("candidate_id") not in (None, ""):
            repaired["candidate_id"] = ""
            repair_counts["candidate_id_cleared"] += 1
        if "contradicts" in repaired and "contradicts_event_ids" not in repaired:
            legacy_targets = repaired.get("contradicts")
            if _known_event_id_list(legacy_targets, known_event_id_set):
                repaired["contradicts_event_ids"] = list(legacy_targets)  # type: ignore[arg-type]
                del repaired["contradicts"]
                repair_counts["contradicts_renamed"] += 1
        repaired_predictions.append(repaired)
    return {"predictions": repaired_predictions}, repair_counts


def build_model_diagnostics(
    *,
    ollama_server_version: str,
    model_digest: str,
    scenario_id: str,
    repair_counts: Dict[str, int],
) -> Dict[str, object]:
    return {
        "ollama_server_version": ollama_server_version,
        "wrapper_name": WRAPPER_NAME,
        "wrapper_version": WRAPPER_VERSION,
        "constrained_decoding": True,
        "model_digest": model_digest,
        "scenarios": {
            scenario_id: {
                "repair_counts": {
                    key: int(repair_counts.get(key, 0))
                    for key in REPAIR_COUNT_KEYS
                }
            }
        },
    }


def _normalize_digest(digest: str) -> str:
    if digest.startswith("sha256:"):
        return digest
    return "sha256:{}".format(digest)


def _ensure_supported_ollama_version(version: str) -> None:
    parsed = _parse_version_prefix(version)
    if parsed < MIN_OLLAMA_VERSION:
        minimum = ".".join(str(item) for item in MIN_OLLAMA_VERSION)
        raise OllamaCommandError(
            "Ollama {} is below the minimum supported version {} for JSON-schema constrained decoding".format(
                version,
                minimum,
            )
        )


def _parse_version_prefix(version: str) -> Tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise OllamaCommandError("Could not parse Ollama version '{}'".format(version))
    return tuple(int(item) for item in match.groups())  # type: ignore[return-value]


def _known_event_id_list(value: object, known_event_ids: Iterable[str]) -> bool:
    if not isinstance(value, list):
        return False
    return all(isinstance(item, str) and item in known_event_ids for item in value)


def _known_event_ids(scenario: Dict[str, object]) -> List[str]:
    events = scenario.get("events")
    if not isinstance(events, list):
        raise OllamaCommandError("scenario.events must be a list")
    event_ids = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise OllamaCommandError("scenario.events[{}] must be an object".format(index))
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise OllamaCommandError("scenario.events[{}].event_id must be a string".format(index))
        event_ids.append(event_id)
    return event_ids


def _enum_values_from_output_contract(envelope: Dict[str, object]) -> Tuple[List[str], List[str]]:
    output_contract = _required_mapping(envelope, "output_contract")
    stdout_json = _required_mapping(output_contract, "stdout_json")
    predictions = stdout_json.get("predictions")
    if not isinstance(predictions, list) or not predictions or not isinstance(predictions[0], dict):
        raise OllamaCommandError("output_contract.stdout_json.predictions must describe prediction objects")
    prediction_contract = predictions[0]
    claim_types = prediction_contract.get("claim_type")
    scope_levels = prediction_contract.get("scope_level")
    if not _string_list(claim_types):
        raise OllamaCommandError("output contract claim_type must be a string list")
    if not _string_list(scope_levels):
        raise OllamaCommandError("output contract scope_level must be a string list")
    return list(claim_types), list(scope_levels)  # type: ignore[arg-type]


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _required_mapping(mapping: Dict[str, object], key: str) -> Dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise OllamaCommandError("{} must be an object".format(key))
    return value


def _required_string(mapping: Dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise OllamaCommandError("{} must be a non-empty string".format(key))
    return value


def _write_command_error(error: Exception) -> int:
    message = str(error)
    json.dump({"error_type": "command_error", "message": message}, sys.stdout)
    print(message, file=sys.stderr)
    return 2


def main(argv: Optional[Sequence[str]] = None) -> int:
    _ = argv
    try:
        envelope = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        return _write_command_error(error)
    if not isinstance(envelope, dict):
        return _write_command_error(OllamaCommandError("stdin envelope must be a JSON object"))
    try:
        output = build_extraction_output(envelope)
    except OllamaCommandError as error:
        return _write_command_error(error)
    json.dump(output, sys.stdout, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
