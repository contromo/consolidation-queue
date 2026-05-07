import json
import shlex
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from cq.eval.component_eval import (
    evaluate_component_predictions,
    load_predictions_by_scenario,
    load_scenario_errors,
)
from cq.pipeline.local_extractor import (
    MAX_MODEL_STDOUT_BYTES,
    MODEL_MODE,
    POSITIVE_CONTROL_MODE,
    WEAK_MODE,
    _build_model_config,
    _model_stdin_bytes,
    _sha256_bytes,
    build_extractor_output,
    extract_predictions_for_scenario,
    main,
    sanitize_scenario_for_extraction,
)
from cq.schemas.memory import jsonable
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


class LocalExtractorTests(unittest.TestCase):
    def test_sanitized_input_excludes_oracle_and_policy_fields(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="mixed")[0]

        sanitized = sanitize_scenario_for_extraction(scenario)
        payload_text = json.dumps(jsonable(sanitized), sort_keys=True)

        for forbidden in (
            "candidate",
            "gold_candidate_ids",
            "forbidden_candidate_ids",
            "expected_lifecycle",
            "latent_truth_graph",
            "metrics",
            "question_traces",
            "store_snapshot",
        ):
            self.assertNotIn(forbidden, payload_text)
        self.assertIn("event_id", payload_text)
        self.assertIn("event_kind", payload_text)
        self.assertIn("turn_index", payload_text)
        self.assertIn("text", payload_text)

    def test_extractor_rejects_raw_scenario_input(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="mixed")[0]

        with self.assertRaises(TypeError):
            extract_predictions_for_scenario(scenario, WEAK_MODE)

    def test_model_mode_requires_model_config_for_single_scenario_api(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="mixed")[0]
        transcript_scenario = sanitize_scenario_for_extraction(scenario)

        with self.assertRaisesRegex(ValueError, "model_config is required"):
            extract_predictions_for_scenario(transcript_scenario, MODEL_MODE)

    def test_weak_extractor_fails_forced_contradiction_gates_for_measured_reasons(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(6, template_mix="mixed")
        transcript_scenarios = [sanitize_scenario_for_extraction(scenario) for scenario in scenarios]
        predictions = {
            transcript_scenario.scenario_id: extract_predictions_for_scenario(
                transcript_scenario,
                WEAK_MODE,
            )
            for transcript_scenario in transcript_scenarios
        }

        result = evaluate_component_predictions(scenarios, predictions)
        metrics = result["metrics"]
        gates = result["quality_gates"]

        self.assertEqual(metrics["contradiction_applicability"], "measured")
        self.assertEqual(metrics["candidate_detection_f1"], 0.0)
        self.assertIsNone(metrics["claim_type_accuracy"])
        self.assertEqual(metrics["contradiction_f1"], 0.0)
        self.assertFalse(gates["candidate_detection_f1"]["passed"])
        self.assertFalse(gates["claim_type_accuracy"]["passed"])
        self.assertFalse(gates["contradiction_f1"]["passed"])
        self.assertEqual(gates["contradiction_f1"]["status"], "measured")

    def test_positive_control_extractor_passes_forced_contradiction_mixed(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(6, template_mix="mixed")
        transcript_scenarios = [sanitize_scenario_for_extraction(scenario) for scenario in scenarios]
        predictions = {
            transcript_scenario.scenario_id: extract_predictions_for_scenario(
                transcript_scenario,
                POSITIVE_CONTROL_MODE,
            )
            for transcript_scenario in transcript_scenarios
        }

        result = evaluate_component_predictions(scenarios, predictions)

        for gate in result["quality_gates"].values():
            self.assertTrue(gate["passed"])
        self.assertEqual(result["metrics"]["contradiction_applicability"], "measured")
        self.assertEqual(result["metrics"]["candidate_detection_f1"], 1.0)
        self.assertEqual(result["metrics"]["contradiction_f1"], 1.0)

    def test_cli_writes_positive_control_predictions_that_component_eval_can_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "positive_control_predictions.json"
            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "--family",
                        "forced_contradiction",
                        "--scenarios",
                        "6",
                        "--template-mix",
                        "mixed",
                        "--mode",
                        "positive_control",
                        "--output-json",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            predictions = load_predictions_by_scenario(output_path)
            self.assertEqual(len(predictions), 6)

    def test_build_extractor_output_labels_transcript_only_contract(self) -> None:
        output = build_extractor_output(
            family="forced_contradiction",
            scenario_count=1,
            template_mix="mixed",
            mode=WEAK_MODE,
        )

        self.assertEqual(output["input_contract"], "transcript_only")
        self.assertIn("scenario_predictions", output)

    def test_model_command_writes_valid_output_with_reproducibility_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=1,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "valid"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                decoding_json='{"seed": 7, "temperature": 0}',
                per_scenario_timeout_seconds=5,
            )

            self.assertEqual(output["model_command"], _fake_model_command(script_path, "valid"))
            self.assertEqual(output["model_id"], "fake-local-model:q4")
            self.assertEqual(output["prompt_template_path"], str(prompt_path))
            self.assertEqual(output["prompt_template_text"], "Extract transcript claims.\n")
            self.assertIn("prompt_template_sha256", output)
            self.assertIn("scenario_input_sha256", output)
            self.assertEqual(len(output["scenario_input_sha256"]), 1)
            scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
            transcript_scenario = sanitize_scenario_for_extraction(scenario)
            model_config = _build_model_config(
                model_command=_fake_model_command(script_path, "valid"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                decoding_json='{"seed": 7, "temperature": 0}',
                per_scenario_timeout_seconds=5,
            )
            self.assertEqual(
                output["scenario_input_sha256"][transcript_scenario.scenario_id],
                _sha256_bytes(_model_stdin_bytes(transcript_scenario, model_config)),
            )
            self.assertEqual(output["decoding_params"]["temperature"], 0)
            self.assertEqual(output["attempted_scenario_count"], 1)
            self.assertEqual(output["successful_scenario_count"], 1)
            self.assertEqual(output["scenario_errors"], {})
            predictions = next(iter(output["scenario_predictions"].values()))
            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0]["candidate_id"], "")

    def test_cli_model_mode_writes_predictions_that_component_eval_can_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            output_path = Path(tmpdir) / "model_predictions.json"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "--family",
                        "forced_contradiction",
                        "--scenarios",
                        "1",
                        "--template-mix",
                        "dirty",
                        "--mode",
                        "model",
                        "--model-command",
                        _fake_model_command(script_path, "valid"),
                        "--model-id",
                        "fake-local-model:q4",
                        "--prompt-template-path",
                        str(prompt_path),
                        "--decoding-json",
                        '{"temperature": 0}',
                        "--output-json",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            predictions = load_predictions_by_scenario(output_path)
            self.assertEqual(len(predictions), 1)
            self.assertEqual(load_scenario_errors(output_path), {})

    def test_model_command_records_timeout_as_per_scenario_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=2,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "sleep"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=0.01,
            )

            self.assertEqual(output["attempted_scenario_count"], 2)
            self.assertEqual(output["successful_scenario_count"], 0)
            self.assertEqual(len(output["scenario_errors"]), 2)
            for error in output["scenario_errors"].values():
                self.assertEqual(error["error_type"], "timeout")

    def test_model_command_captures_stderr_on_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=1,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "sleep_stderr"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=0.05,
            )

            error = next(iter(output["scenario_errors"].values()))
            self.assertEqual(error["error_type"], "timeout")
            self.assertIn("stderr before timeout", error["stderr"])
            self.assertGreater(error["stderr_bytes"], 0)

    def test_model_command_records_command_and_json_failures_per_scenario(self) -> None:
        cases = (
            ("exit", "nonzero_exit", "exited with status"),
            ("nonjson", "malformed_json", "strict JSON"),
            ("bad_shape", "validation_error", "predictions list"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            for behavior, error_type, message in cases:
                with self.subTest(behavior=behavior):
                    output = build_extractor_output(
                        family="forced_contradiction",
                        scenario_count=1,
                        template_mix="dirty",
                        mode=MODEL_MODE,
                        model_command=_fake_model_command(script_path, behavior),
                        model_id="fake-local-model:q4",
                        prompt_template_path=str(prompt_path),
                        per_scenario_timeout_seconds=5,
                    )
                    error = next(iter(output["scenario_errors"].values()))
                    self.assertEqual(error["error_type"], error_type)
                    self.assertIn(message, error["message"])
                    self.assertEqual(output["successful_scenario_count"], 0)

    def test_model_command_records_missing_command_as_per_scenario_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=1,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command="definitely-not-a-real-local-extractor-command",
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=5,
            )

            error = next(iter(output["scenario_errors"].values()))
            self.assertEqual(error["error_type"], "command_error")
            self.assertEqual(output["successful_scenario_count"], 0)

    def test_model_command_maps_structured_backend_failure_to_command_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=1,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "command_error_payload"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=5,
            )

            error = next(iter(output["scenario_errors"].values()))
            self.assertEqual(error["error_type"], "command_error")
            self.assertIn("Ollama unavailable", error["message"])
            self.assertEqual(output["successful_scenario_count"], 0)

    def test_model_command_preserves_model_diagnostics_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=1,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "diagnostics"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=5,
            )

            scenario_id = next(iter(output["scenario_predictions"]))
            self.assertEqual(output["model_digest"], "sha256:fake-digest")
            diagnostics = output["model_diagnostics"]
            self.assertEqual(diagnostics["ollama_server_version"], "fake-ollama-1.0")
            self.assertEqual(diagnostics["wrapper_name"], "ollama_component_extractor")
            self.assertTrue(diagnostics["constrained_decoding"])
            repair_counts = diagnostics["scenarios"][scenario_id]["repair_counts"]
            self.assertEqual(repair_counts["candidate_id_cleared"], 1)
            self.assertEqual(repair_counts["contradicts_renamed"], 0)
            self.assertEqual(repair_counts["extra_top_level_dropped"], 0)

    def test_model_command_preserves_diagnostics_on_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=1,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "diagnostics_bad_confidence"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=5,
            )

            scenario_id = next(iter(output["scenario_errors"]))
            self.assertEqual(output["scenario_errors"][scenario_id]["error_type"], "validation_error")
            self.assertEqual(output["model_digest"], "sha256:fake-digest")
            repair_counts = output["model_diagnostics"]["scenarios"][scenario_id]["repair_counts"]
            self.assertEqual(repair_counts["candidate_id_cleared"], 1)

    def test_model_command_records_backend_drift_as_scenario_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=2,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "diagnostics_drift"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=5,
            )

            self.assertEqual(output["successful_scenario_count"], 1)
            self.assertEqual(output["model_digest"], "sha256:first-digest")
            error = output["scenario_errors"]["forced_contradiction_002"]
            self.assertEqual(error["error_type"], "backend_drift")
            self.assertEqual(error["mismatches"][0]["field"], "model_digest")
            self.assertEqual(error["mismatches"][0]["expected"], "sha256:first-digest")
            self.assertEqual(error["mismatches"][0]["observed"], "sha256:second-digest")
            self.assertIn(
                "forced_contradiction_002",
                output["model_diagnostics"]["scenarios"],
            )

    def test_model_command_records_oversized_stdout_as_per_scenario_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            output = build_extractor_output(
                family="forced_contradiction",
                scenario_count=1,
                template_mix="dirty",
                mode=MODEL_MODE,
                model_command=_fake_model_command(script_path, "large"),
                model_id="fake-local-model:q4",
                prompt_template_path=str(prompt_path),
                per_scenario_timeout_seconds=5,
            )

            error = next(iter(output["scenario_errors"].values()))
            self.assertEqual(error["error_type"], "output_too_large")
            self.assertIn(str(MAX_MODEL_STDOUT_BYTES), error["message"])
            self.assertGreater(error["stdout_bytes"], MAX_MODEL_STDOUT_BYTES)
            self.assertEqual(output["successful_scenario_count"], 0)

    def test_model_validation_errors_are_per_scenario_errors(self) -> None:
        cases = (
            ("candidate_id", "candidate_id"),
            ("unknown_event", "unknown event_id"),
            ("bad_claim_type", "invalid claim_type"),
            ("bad_scope_level", "invalid scope_level"),
            ("duplicate_pair", "duplicates event_id/canonical_id"),
            ("bad_edge", "unknown contradicts_event_id"),
            ("bad_confidence", "confidence must be numeric"),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = _write_fake_model_script(Path(tmpdir))
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")

            for behavior, message in cases:
                with self.subTest(behavior=behavior):
                    output = build_extractor_output(
                        family="forced_contradiction",
                        scenario_count=1,
                        template_mix="dirty",
                        mode=MODEL_MODE,
                        model_command=_fake_model_command(script_path, behavior),
                        model_id="fake-local-model:q4",
                        prompt_template_path=str(prompt_path),
                        per_scenario_timeout_seconds=5,
                    )
                    error = next(iter(output["scenario_errors"].values()))
                    self.assertEqual(error["error_type"], "validation_error")
                    self.assertIn(message, error["message"])
                    self.assertEqual(output["successful_scenario_count"], 0)

    def test_model_config_validation_errors_fail_before_sweep(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_path = Path(tmpdir) / "prompt.txt"
            prompt_path.write_text("Extract transcript claims.\n", encoding="utf-8")
            cases = (
                (
                    {"model_command": ""},
                    "--model-command is required",
                ),
                (
                    {"model_id": ""},
                    "--model-id is required",
                ),
                (
                    {"prompt_template_path": ""},
                    "--prompt-template-path is required",
                ),
                (
                    {"prompt_template_path": str(Path(tmpdir) / "missing.txt")},
                    "Could not read prompt template",
                ),
                (
                    {"decoding_json": "{not-json"},
                    "--decoding-json must be a JSON object",
                ),
                (
                    {"decoding_json": "[]"},
                    "--decoding-json must be a JSON object",
                ),
                (
                    {"per_scenario_timeout_seconds": 0},
                    "--per-scenario-timeout-seconds must be positive",
                ),
            )

            for overrides, message in cases:
                with self.subTest(overrides=overrides):
                    kwargs = {
                        "family": "forced_contradiction",
                        "scenario_count": 1,
                        "template_mix": "dirty",
                        "mode": MODEL_MODE,
                        "model_command": _fake_model_command(
                            _write_fake_model_script(Path(tmpdir)),
                            "valid",
                        ),
                        "model_id": "fake-local-model:q4",
                        "prompt_template_path": str(prompt_path),
                        "decoding_json": "{}",
                        "per_scenario_timeout_seconds": 5,
                    }
                    kwargs.update(overrides)
                    with self.assertRaisesRegex(ValueError, message):
                        build_extractor_output(**kwargs)


def _fake_model_command(script_path: Path, behavior: str) -> str:
    return "{} {} {}".format(
        shlex.quote(sys.executable),
        shlex.quote(str(script_path)),
        shlex.quote(behavior),
    )


def _write_fake_model_script(tmpdir: Path) -> Path:
    script_path = tmpdir / "fake_model.py"
    script_path.write_text(
        """
import json
import sys
import time

behavior = sys.argv[1]
if behavior == "sleep":
    time.sleep(5)
if behavior == "sleep_stderr":
    print("stderr before timeout", file=sys.stderr, flush=True)
    time.sleep(5)
if behavior == "exit":
    print("failed", file=sys.stderr)
    sys.exit(7)
if behavior == "nonjson":
    print("not json")
    sys.exit(0)
if behavior == "large":
    sys.stdout.write("x" * (__MAX_STDOUT__ + 1))
    sys.exit(0)
if behavior == "command_error_payload":
    json.dump({"error_type": "command_error", "message": "Ollama unavailable"}, sys.stdout)
    print("server offline", file=sys.stderr)
    sys.exit(2)

payload = json.load(sys.stdin)
scenario = payload["scenario"]
scenario_text = json.dumps(scenario, sort_keys=True)
for forbidden in (
    "gold_candidate_ids",
    "forbidden_candidate_ids",
    "expected_lifecycle",
    "latent_truth_graph",
    "question_traces",
    "store_snapshot",
):
    if forbidden in scenario_text:
        print("forbidden field leaked: " + forbidden, file=sys.stderr)
        sys.exit(9)
if payload["prompt"] != "Extract transcript claims.\\n":
    print("prompt did not round trip", file=sys.stderr)
    sys.exit(10)

events = scenario["events"]
observation = next(event for event in events if event["event_kind"] == "observation")
prediction = {
    "event_id": observation["event_id"],
    "candidate_id": "",
    "canonical_id": "fake-canonical",
    "claim_type": "world_fact",
    "scope_level": "world_global",
    "scope_key": "global",
    "contradicts_event_ids": [],
    "raw_claim": observation["text"],
    "confidence": 0.8,
}

if behavior == "valid":
    json.dump({"predictions": [prediction]}, sys.stdout)
elif behavior in ("diagnostics", "diagnostics_bad_confidence", "diagnostics_drift"):
    prediction["candidate_id"] = ""
    if behavior == "diagnostics_bad_confidence":
        prediction["confidence"] = "high"
    model_digest = "sha256:fake-digest"
    if behavior == "diagnostics_drift":
        model_digest = (
            "sha256:first-digest"
            if scenario["scenario_id"].endswith("_001")
            else "sha256:second-digest"
        )
    json.dump(
        {
            "predictions": [prediction],
            "model_diagnostics": {
                "ollama_server_version": "fake-ollama-1.0",
                "wrapper_name": "ollama_component_extractor",
                "wrapper_version": "v1",
                "constrained_decoding": True,
                "model_digest": model_digest,
                "scenarios": {
                    scenario["scenario_id"]: {
                        "repair_counts": {
                            "candidate_id_cleared": 1,
                            "contradicts_renamed": 0,
                            "extra_top_level_dropped": 0,
                        }
                    }
                },
            },
        },
        sys.stdout,
    )
elif behavior == "bad_shape":
    json.dump({"items": [prediction]}, sys.stdout)
elif behavior == "candidate_id":
    prediction["candidate_id"] = "oracle-candidate-1"
    json.dump({"predictions": [prediction]}, sys.stdout)
elif behavior == "unknown_event":
    prediction["event_id"] = "missing-event"
    json.dump({"predictions": [prediction]}, sys.stdout)
elif behavior == "bad_claim_type":
    prediction["claim_type"] = "not_a_claim"
    json.dump({"predictions": [prediction]}, sys.stdout)
elif behavior == "bad_scope_level":
    prediction["scope_level"] = "not_a_scope"
    json.dump({"predictions": [prediction]}, sys.stdout)
elif behavior == "duplicate_pair":
    json.dump({"predictions": [prediction, dict(prediction)]}, sys.stdout)
elif behavior == "bad_edge":
    prediction["contradicts_event_ids"] = ["missing-event"]
    json.dump({"predictions": [prediction]}, sys.stdout)
elif behavior == "bad_confidence":
    prediction["confidence"] = "high"
    json.dump({"predictions": [prediction]}, sys.stdout)
else:
    raise SystemExit("unknown behavior: " + behavior)
""".replace("__MAX_STDOUT__", str(MAX_MODEL_STDOUT_BYTES)).lstrip(),
        encoding="utf-8",
    )
    return script_path


if __name__ == "__main__":
    unittest.main()
