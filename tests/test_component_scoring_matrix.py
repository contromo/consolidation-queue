import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from cq.eval.component_eval import oracle_predictions_by_scenario
from cq.schemas.memory import jsonable
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


def _load_matrix_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_component_scoring_matrix.py"
    spec = importlib.util.spec_from_file_location("run_component_scoring_matrix", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


matrix = _load_matrix_module()


class ComponentScoringMatrixTests(unittest.TestCase):
    def test_matrix_rows_and_artifact_names_are_fixed(self) -> None:
        floor_rows = matrix.floor_diagnostic_rows()
        headroom_rows = matrix.headroom_diagnostic_rows()

        self.assertEqual(len(floor_rows), 13)
        self.assertEqual(len(headroom_rows), 7)
        self.assertEqual(
            sum(row.family == matrix.MECHANISM_DIVERSE_HELDOUT for row in floor_rows),
            1,
        )
        self.assertTrue(all(row.model == matrix.QWEN_7B_Q4KM for row in floor_rows))
        self.assertTrue(all(row.model == matrix.QWEN_32B_Q4KM for row in headroom_rows))

        paths = matrix.artifact_paths(floor_rows[0], Path("/tmp/cq-results"))

        self.assertEqual(
            paths.predictions.name,
            "forced_contradiction_local_extractor_qwen2_5_7b_q4km_general_v1_mixed_floor_predictions.json",
        )
        self.assertEqual(
            paths.component_eval.name,
            "forced_contradiction_local_extractor_qwen2_5_7b_q4km_general_v1_mixed_floor_component_eval.json",
        )

    def test_dry_run_commands_use_existing_extractor_and_scorer_clis(self) -> None:
        row = matrix.floor_diagnostic_rows()[0]
        commands = matrix.equivalent_commands(
            row,
            output_dir=Path("/tmp/cq-results"),
            model_command="python3 scripts/ollama_component_extractor.py",
            decoding_json='{"temperature": 0}',
            per_scenario_timeout_seconds=180.0,
        )

        self.assertIn("-m cq.pipeline.local_extractor", commands["extract"])
        self.assertIn("--family forced_contradiction", commands["extract"])
        self.assertIn("--model-id qwen2.5:7b-instruct-q4_K_M", commands["extract"])
        self.assertIn("component_extractor_general_v1.txt", commands["extract"])
        self.assertIn("-m cq.eval.component_eval", commands["score"])
        self.assertIn("--predictions-json", commands["score"])

        plan = matrix.dry_run_plan(
            output_dir=Path("/tmp/cq-results"),
            model_command="python3 scripts/ollama_component_extractor.py",
            decoding_json='{"temperature": 0}',
            per_scenario_timeout_seconds=180.0,
        )

        self.assertEqual(plan["statistical_gate_verdicts"], "not_issued")
        self.assertGreater(len(plan["rows"]), len(matrix.floor_diagnostic_rows()))

    def test_metric_non_regression_checks_each_gate_metric(self) -> None:
        baseline = _component_artifact({metric: 1.0 for metric in matrix.GATE_METRICS})
        general = _component_artifact({metric: 1.0 for metric in matrix.GATE_METRICS})
        general["metrics"]["contradiction_recall"] = 0.92
        general["metrics"]["scope_key_accuracy"] = None

        violations = matrix.regression_violations(
            model=matrix.QWEN_7B_Q4KM,
            baseline_artifact=baseline,
            general_artifact=general,
            baseline_correctness={"scenario-1": False},
            general_correctness={"scenario-1": False},
        )

        violation_types = {(item["type"], item.get("metric")) for item in violations}
        self.assertIn(("metric_regression", "contradiction_recall"), violation_types)
        self.assertIn(("metric_became_undefined", "scope_key_accuracy"), violation_types)

    def test_scenario_regression_flags_correct_to_incorrect_flip(self) -> None:
        violations = matrix.scenario_regression_violations(
            model=matrix.QWEN_7B_Q4KM,
            baseline_correctness={
                "forced_contradiction_001": True,
                "forced_contradiction_002": False,
            },
            general_correctness={
                "forced_contradiction_001": False,
                "forced_contradiction_002": False,
            },
        )

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["type"], "scenario_correctness_regression")
        self.assertEqual(violations[0]["scenario_id"], "forced_contradiction_001")

    def test_scenario_correctness_uses_existing_component_evaluator(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(1, template_mix="mixed")
        oracle_predictions = oracle_predictions_by_scenario(scenarios)
        with tempfile.TemporaryDirectory() as tmpdir:
            predictions_path = Path(tmpdir) / "predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "scenario_predictions": jsonable(oracle_predictions),
                        "scenario_errors": {},
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            correctness = matrix.scenario_correctness_by_id(
                "forced_contradiction",
                1,
                "mixed",
                predictions_path,
            )

            self.assertEqual(correctness, {"forced_contradiction_001": True})

            bad_payload = jsonable(oracle_predictions)
            bad_payload["forced_contradiction_001"][0]["scope_key"] = "wrong"
            predictions_path.write_text(
                json.dumps(
                    {
                        "scenario_predictions": bad_payload,
                        "scenario_errors": {},
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            correctness = matrix.scenario_correctness_by_id(
                "forced_contradiction",
                1,
                "mixed",
                predictions_path,
            )

            self.assertEqual(correctness, {"forced_contradiction_001": False})

    def test_normalized_json_preserves_prediction_array_order(self) -> None:
        first = {
            "scenario_predictions": {
                "scenario-1": [
                    {"event_id": "event-1"},
                    {"event_id": "event-2"},
                ]
            }
        }
        same_with_different_key_order = {
            "scenario_predictions": {
                "scenario-1": [
                    {"event_id": "event-1"},
                    {"event_id": "event-2"},
                ]
            }
        }
        reordered_array = {
            "scenario_predictions": {
                "scenario-1": [
                    {"event_id": "event-2"},
                    {"event_id": "event-1"},
                ]
            }
        }

        self.assertEqual(
            matrix.normalized_json_bytes(first),
            matrix.normalized_json_bytes(same_with_different_key_order),
        )
        self.assertNotEqual(
            matrix.normalized_json_bytes(first),
            matrix.normalized_json_bytes(reordered_array),
        )


def _component_artifact(metrics):
    return {
        "metrics": metrics,
        "scenario_error_count": 0,
    }


if __name__ == "__main__":
    unittest.main()
