import json
import subprocess
import sys
import unittest
from pathlib import Path

from cq.pipeline.ollama_component_extractor import (
    OllamaCommandError,
    _normalize_digest,
    build_extraction_output,
    build_output_schema,
    normalize_model_payload,
)


class OllamaComponentExtractorTests(unittest.TestCase):
    def test_build_extraction_output_repairs_narrow_shape_and_records_diagnostics(self) -> None:
        client = _FakeOllamaClient(
            response_payload={
                "predictions": [
                    {
                        "event_id": "event-2",
                        "candidate_id": "hallucinated-candidate-id",
                        "canonical_id": "world-fact-alpha-beta-acquisition-status",
                        "claim_type": "world_fact",
                        "scope_level": "world_global",
                        "scope_key": "global",
                        "contradicts": ["event-1"],
                        "raw_claim": "Alpha did not acquire Beta.",
                        "confidence": 0.7,
                    }
                ],
                "notes": "drop this top-level field",
            }
        )

        output = build_extraction_output(_envelope(), client=client)

        self.assertEqual(client.generated_model_id, "qwen2.5:7b-instruct-q4_K_M")
        prediction = output["predictions"][0]
        self.assertEqual(prediction["candidate_id"], "")
        self.assertEqual(prediction["contradicts_event_ids"], ["event-1"])
        self.assertNotIn("contradicts", prediction)
        self.assertNotIn("notes", output)
        diagnostics = output["model_diagnostics"]
        self.assertEqual(diagnostics["ollama_server_version"], "0.0-test")
        self.assertEqual(diagnostics["wrapper_name"], "ollama_component_extractor")
        self.assertEqual(diagnostics["wrapper_version"], "v1")
        self.assertTrue(diagnostics["constrained_decoding"])
        self.assertEqual(diagnostics["model_digest"], "sha256:test-digest")
        repair_counts = diagnostics["scenarios"]["scenario-1"]["repair_counts"]
        self.assertEqual(repair_counts["candidate_id_cleared"], 1)
        self.assertEqual(repair_counts["contradicts_renamed"], 1)
        self.assertEqual(repair_counts["extra_top_level_dropped"], 1)

    def test_unknown_legacy_contradiction_target_is_not_repaired(self) -> None:
        output, repair_counts = normalize_model_payload(
            {
                "predictions": [
                    {
                        "event_id": "event-2",
                        "canonical_id": "canonical",
                        "claim_type": "world_fact",
                        "scope_level": "world_global",
                        "scope_key": "global",
                        "contradicts": ["missing-event"],
                        "raw_claim": "claim",
                        "confidence": 0.5,
                    }
                ]
            },
            ["event-1", "event-2"],
        )

        prediction = output["predictions"][0]
        self.assertEqual(prediction["contradicts"], ["missing-event"])
        self.assertNotIn("contradicts_event_ids", prediction)
        self.assertEqual(repair_counts["contradicts_renamed"], 0)

    def test_output_schema_uses_contract_enums(self) -> None:
        schema = build_output_schema(_envelope())
        item_schema = schema["properties"]["predictions"]["items"]

        self.assertEqual(
            item_schema["properties"]["claim_type"]["enum"],
            ["project_convention", "tooling_preference", "world_fact"],
        )
        self.assertEqual(
            item_schema["properties"]["scope_level"]["enum"],
            ["project", "session", "world_global"],
        )

    def test_missing_model_digest_is_command_error(self) -> None:
        client = _FakeOllamaClient(response_payload={"predictions": []}, digest_error=True)

        with self.assertRaisesRegex(OllamaCommandError, "not installed"):
            build_extraction_output(_envelope(), client=client)

    def test_digest_normalization_adds_sha256_prefix(self) -> None:
        self.assertEqual(_normalize_digest("abc123"), "sha256:abc123")
        self.assertEqual(_normalize_digest("sha256:abc123"), "sha256:abc123")

    def test_script_entrypoint_can_import_repo_package(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/ollama_component_extractor.py"],
            cwd=repo_root,
            input=b"",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("command_error", completed.stdout.decode("utf-8"))
        self.assertNotIn("ModuleNotFoundError", completed.stderr.decode("utf-8"))


class _FakeOllamaClient:
    def __init__(self, response_payload, digest_error=False):
        self.response_payload = response_payload
        self.digest_error = digest_error
        self.generated_model_id = ""

    def get_version(self):
        return "0.0-test"

    def get_model_digest(self, model_id):
        if self.digest_error:
            raise OllamaCommandError("Ollama model '{}' is not installed".format(model_id))
        return "sha256:test-digest"

    def generate(self, *, model_id, prompt, output_schema, decoding_params):
        self.generated_model_id = model_id
        self.prompt = prompt
        self.output_schema = output_schema
        self.decoding_params = decoding_params
        return json.dumps(self.response_payload)


def _envelope():
    return {
        "input_contract": "transcript_only",
        "model_id": "qwen2.5:7b-instruct-q4_K_M",
        "decoding_params": {"temperature": 0, "seed": 7, "top_p": 1},
        "prompt": "Extract transcript claims.",
        "scenario": {
            "scenario_id": "scenario-1",
            "events": [
                {
                    "event_id": "event-1",
                    "event_kind": "observation",
                    "turn_index": 1,
                    "text": "Alpha acquired Beta.",
                },
                {
                    "event_id": "event-2",
                    "event_kind": "observation",
                    "turn_index": 2,
                    "text": "Alpha did not acquire Beta.",
                },
            ],
        },
        "output_contract": {
            "stdout_json": {
                "predictions": [
                    {
                        "event_id": "event id from input",
                        "candidate_id": "",
                        "canonical_id": "stable cluster id",
                        "claim_type": [
                            "project_convention",
                            "tooling_preference",
                            "world_fact",
                        ],
                        "scope_level": ["project", "session", "world_global"],
                        "scope_key": "scope key string",
                        "contradicts_event_ids": ["event ids from input"],
                        "raw_claim": "short extracted claim",
                        "confidence": "number or null",
                    }
                ]
            }
        },
    }


if __name__ == "__main__":
    unittest.main()
