import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from cq.eval.component_eval import (
    CandidateComponentPrediction,
    build_oracle_component_eval_artifact,
    evaluate_component_predictions,
    load_predictions_by_scenario,
    main,
    oracle_component_predictions,
)
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


class ComponentEvalTests(unittest.TestCase):
    def test_oracle_predictions_pass_quality_gates(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(3, template_mix="mixed")
        predictions = {
            scenario.scenario_id: oracle_component_predictions(scenario)
            for scenario in scenarios
        }

        result = evaluate_component_predictions(scenarios, predictions)

        for gate in result["quality_gates"].values():
            self.assertTrue(gate["passed"])
            self.assertEqual(gate["value"], 1.0)

    def test_candidate_detection_counts_false_positives_and_false_negatives(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        oracle_predictions = oracle_component_predictions(scenario)
        predictions = [
            oracle_predictions[0],
            CandidateComponentPrediction(
                event_id="not-an-observation-event",
                candidate_id="extra-candidate",
                canonical_id="extra-canonical",
                claim_type="world_fact",
                scope_level="world_global",
                scope_key="global",
            ),
        ]

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["candidate_detection_tp"], 1)
        self.assertEqual(metrics["candidate_detection_fp"], 1)
        self.assertEqual(metrics["candidate_detection_fn"], 1)
        self.assertEqual(metrics["candidate_detection_f1"], 0.5)

    def test_component_errors_affect_targeted_metrics(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        predictions = oracle_component_predictions(scenario)
        predictions[0] = CandidateComponentPrediction(
            event_id=predictions[0].event_id,
            candidate_id=predictions[0].candidate_id,
            canonical_id="wrong-canonical-cluster",
            claim_type="tooling_preference",
            scope_level="session",
            scope_key="wrong-scope",
            contradicts=[],
        )
        predictions[1].contradicts = []

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertLess(metrics["claim_type_accuracy"], 1.0)
        self.assertLess(metrics["scope_level_accuracy"], 1.0)
        self.assertLess(metrics["scope_key_accuracy"], 1.0)
        self.assertLess(metrics["canonicalization_b_cubed_f1"], 1.0)
        self.assertLess(metrics["contradiction_recall"], 1.0)

    def test_cli_writes_oracle_upper_bound_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "component_eval.json"

            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "--family",
                        "forced_contradiction",
                        "--scenarios",
                        "2",
                        "--template-mix",
                        "dirty",
                        "--output-json",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["mode"], "oracle_component_upper_bound")
            self.assertEqual(artifact["scenario_count"], 2)
            self.assertEqual(artifact["metrics"]["candidate_detection_f1"], 1.0)

    def test_cli_scores_prediction_json(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        with tempfile.TemporaryDirectory() as tmpdir:
            predictions_path = Path(tmpdir) / "predictions.json"
            output_path = Path(tmpdir) / "component_eval.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "scenario_predictions": {
                            scenario.scenario_id: [
                                prediction.__dict__
                                for prediction in oracle_component_predictions(scenario)
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "--family",
                        "forced_contradiction",
                        "--scenarios",
                        "1",
                        "--template-mix",
                        "dirty",
                        "--predictions-json",
                        str(predictions_path),
                        "--output-json",
                        str(output_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["mode"], "component_predictions")
            self.assertEqual(artifact["metrics"]["candidate_detection_f1"], 1.0)

    def test_load_predictions_by_scenario_accepts_missing_contradicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            predictions_path = Path(tmpdir) / "predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "scenario_predictions": {
                            "scenario-1": [
                                {
                                    "event_id": "event-1",
                                    "candidate_id": "candidate-1",
                                    "canonical_id": "canonical-1",
                                    "claim_type": "world_fact",
                                    "scope_level": "world_global",
                                    "scope_key": "global",
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            predictions = load_predictions_by_scenario(predictions_path)

            self.assertEqual(predictions["scenario-1"][0].contradicts, [])

    def test_oracle_artifact_exposes_quality_gate_thresholds(self) -> None:
        artifact = build_oracle_component_eval_artifact(
            family="forced_contradiction",
            scenario_count=1,
            template_mix="dirty",
        )

        self.assertIn("candidate_detection_f1", artifact["quality_gate_thresholds"])
        self.assertTrue(artifact["quality_gates"]["candidate_detection_f1"]["passed"])


if __name__ == "__main__":
    unittest.main()
