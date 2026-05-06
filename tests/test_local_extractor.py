import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from cq.eval.component_eval import evaluate_component_predictions, load_predictions_by_scenario
from cq.pipeline.local_extractor import (
    POSITIVE_CONTROL_MODE,
    WEAK_MODE,
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


if __name__ == "__main__":
    unittest.main()
