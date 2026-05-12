import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from cq.eval.component_eval import (
    CandidateComponentPrediction,
    _b_cubed,
    build_component_eval_artifact,
    build_oracle_component_eval_artifact,
    canonical_component_maps,
    evaluate_component_predictions,
    load_predictions_by_scenario,
    load_scenario_errors,
    main,
    oracle_component_predictions,
    oracle_predictions_by_scenario,
)
from cq.eval.runner import COMPONENT_EVAL_FAMILIES, TEMPLATE_MIXES_BY_FAMILY, generate_scenarios
from cq.schemas.scenario import EventKind
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


def _failure_types(result):
    return {example["failure_type"] for example in result["failure_examples"]}


def _failure_by_type(result, failure_type):
    for example in result["failure_examples"]:
        if example["failure_type"] == failure_type:
            return example
    raise AssertionError("Missing failure type {}".format(failure_type))


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

    def test_canonical_component_maps_returns_public_gold_and_prediction_maps(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(1, template_mix="mixed")
        predictions = oracle_predictions_by_scenario(scenarios)

        gold, predicted = canonical_component_maps(scenarios, predictions)

        self.assertEqual(set(gold), set(predicted))
        self.assertTrue(all(item_id.startswith(scenarios[0].scenario_id) for item_id in gold))
        self.assertEqual(gold, predicted)

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
        self.assertEqual(
            _failure_types(result),
            {"candidate_extra", "candidate_missing", "contradiction_missing"},
        )
        missing = _failure_by_type(result, "candidate_missing")
        self.assertEqual(missing["component"], "candidate_detection")
        self.assertIn("gold", missing)
        extra = _failure_by_type(result, "candidate_extra")
        self.assertEqual(extra["predicted"]["canonical_id"], "extra-canonical")

    def test_candidate_failure_examples_track_metric_classifications_before_cap(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        oracle_predictions = oracle_component_predictions(scenario)
        predictions = [
            oracle_predictions[0],
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
        candidate_failure_counts = {
            failure_type: sum(
                1
                for example in result["failure_examples"]
                if example["failure_type"] == failure_type
            )
            for failure_type in (
                "candidate_missing",
                "candidate_extra",
                "candidate_duplicate",
            )
        }

        self.assertEqual(
            candidate_failure_counts["candidate_missing"],
            metrics["candidate_detection_fn"],
        )
        self.assertEqual(
            candidate_failure_counts["candidate_extra"]
            + candidate_failure_counts["candidate_duplicate"],
            metrics["candidate_detection_fp"],
        )

    def test_zero_prediction_extractor_fails_no_data_quality_gates(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]

        result = evaluate_component_predictions([scenario], {scenario.scenario_id: []})
        metrics = result["metrics"]
        gates = result["quality_gates"]

        self.assertEqual(metrics["candidate_detection_recall"], 0.0)
        self.assertEqual(metrics["candidate_detection_f1"], 0.0)
        self.assertEqual(metrics["predicted_event_count"], 0)
        self.assertEqual(metrics["extra_same_event_prediction_count"], 0)
        self.assertIsNone(metrics["predictions_per_event_p50"])
        self.assertIsNone(metrics["predictions_per_event_p95"])
        self.assertEqual(metrics["predictions_per_event_max"], 0)
        self.assertIsNone(metrics["claim_type_accuracy"])
        self.assertIsNone(metrics["scope_level_accuracy"])
        self.assertIsNone(metrics["scope_key_accuracy"])
        self.assertIsNone(metrics["canonicalization_b_cubed_f1"])
        self.assertEqual(metrics["canonicalization_coverage"], 0.0)
        self.assertIsNone(metrics["contradiction_precision"])
        self.assertEqual(metrics["contradiction_recall"], 0.0)
        self.assertFalse(gates["claim_type_accuracy"]["passed"])
        self.assertFalse(gates["scope_level_accuracy"]["passed"])
        self.assertFalse(gates["scope_key_accuracy"]["passed"])
        self.assertFalse(gates["canonicalization_b_cubed_f1"]["passed"])
        self.assertFalse(gates["contradiction_precision"]["passed"])
        self.assertEqual(
            _failure_types(result),
            {"candidate_missing", "contradiction_missing"},
        )

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
        failure_types = _failure_types(result)
        self.assertIn("claim_type_mismatch", failure_types)
        self.assertIn("scope_level_mismatch", failure_types)
        self.assertIn("scope_key_mismatch", failure_types)
        mismatch = _failure_by_type(result, "claim_type_mismatch")
        self.assertEqual(mismatch["gold"]["claim_type"], "world_fact")
        self.assertEqual(mismatch["predicted"]["claim_type"], "tooling_preference")

    def test_contradiction_edges_match_when_prediction_direction_is_reversed(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        predictions = oracle_component_predictions(scenario)
        predictions[0].contradicts = [predictions[1].candidate_id]
        predictions[1].contradicts = []

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["contradiction_tp"], 1)
        self.assertEqual(metrics["contradiction_fp"], 0)
        self.assertEqual(metrics["contradiction_fn"], 0)
        self.assertEqual(metrics["contradiction_precision"], 1.0)
        self.assertEqual(metrics["contradiction_recall"], 1.0)

    def test_event_id_contradiction_edges_match_when_prediction_direction_is_reversed(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        observations = [
            event
            for event in scenario.sorted_events()
            if event.kind == EventKind.OBSERVATION and event.candidate is not None
        ]
        first_event = observations[0]
        second_event = observations[1]
        predictions = [
            CandidateComponentPrediction(
                event_id=first_event.event_id,
                candidate_id="",
                canonical_id=first_event.candidate.canonical_id,
                claim_type=first_event.candidate.claim_type.value,
                scope_level=first_event.candidate.scope_level.value,
                scope_key=first_event.candidate.scope_key,
                contradicts_event_ids=[second_event.event_id],
            ),
            CandidateComponentPrediction(
                event_id=second_event.event_id,
                candidate_id="",
                canonical_id=second_event.candidate.canonical_id,
                claim_type=second_event.candidate.claim_type.value,
                scope_level=second_event.candidate.scope_level.value,
                scope_key=second_event.candidate.scope_key,
            ),
        ]

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["contradiction_tp"], 1)
        self.assertEqual(metrics["contradiction_fp"], 0)
        self.assertEqual(metrics["contradiction_fn"], 0)
        self.assertEqual(metrics["contradiction_f1"], 1.0)

    def test_event_id_contradiction_self_edge_counts_as_false_positive(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        predictions = oracle_component_predictions(scenario)
        for prediction in predictions:
            prediction.contradicts = []
        predictions[0].contradicts_event_ids = [predictions[0].event_id]

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["contradiction_tp"], 0)
        self.assertEqual(metrics["contradiction_fp"], 1)
        self.assertEqual(metrics["contradiction_fn"], 1)
        self.assertFalse(result["quality_gates"]["contradiction_f1"]["passed"])

    def test_event_id_contradiction_unknown_event_counts_as_false_positive(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        predictions = oracle_component_predictions(scenario)
        for prediction in predictions:
            prediction.contradicts = []
        predictions[0].contradicts_event_ids = ["missing-event"]

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["contradiction_tp"], 0)
        self.assertEqual(metrics["contradiction_fp"], 1)
        self.assertEqual(metrics["contradiction_fn"], 1)

    def test_event_id_contradiction_question_event_counts_as_false_positive(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        question_event = next(
            event for event in scenario.sorted_events() if event.kind == EventKind.QUESTION
        )
        predictions = oracle_component_predictions(scenario)
        for prediction in predictions:
            prediction.contradicts = []
        predictions[0].contradicts_event_ids = [question_event.event_id]

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["contradiction_tp"], 0)
        self.assertEqual(metrics["contradiction_fp"], 1)
        self.assertEqual(metrics["contradiction_fn"], 1)

    def test_contradiction_gates_are_not_applicable_without_gold_or_predicted_edges(self) -> None:
        scenario = generate_scenarios("useful_pending_memory", 1, "clean")[0]
        predictions = {scenario.scenario_id: oracle_component_predictions(scenario)}

        result = evaluate_component_predictions([scenario], predictions)
        metrics = result["metrics"]
        gates = result["quality_gates"]

        self.assertEqual(metrics["contradiction_applicability"], "not_applicable")
        self.assertIsNone(metrics["contradiction_f1"])
        self.assertTrue(gates["contradiction_f1"]["passed"])
        self.assertEqual(gates["contradiction_f1"]["status"], "not_applicable")

    def test_contradiction_gates_fail_false_positive_edges_without_gold_edges(self) -> None:
        scenario = generate_scenarios("useful_pending_memory", 1, "clean")[0]
        observation = next(
            event
            for event in scenario.sorted_events()
            if event.kind == EventKind.OBSERVATION and event.candidate is not None
        )
        prediction = CandidateComponentPrediction(
            event_id=observation.event_id,
            candidate_id="",
            canonical_id=observation.candidate.canonical_id,
            claim_type=observation.candidate.claim_type.value,
            scope_level=observation.candidate.scope_level.value,
            scope_key=observation.candidate.scope_key,
            contradicts_event_ids=["missing-event"],
        )

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: [prediction]},
        )
        metrics = result["metrics"]
        gates = result["quality_gates"]

        self.assertEqual(metrics["contradiction_applicability"], "measured")
        self.assertEqual(metrics["contradiction_fp"], 1)
        self.assertFalse(gates["contradiction_f1"]["passed"])
        extra = _failure_by_type(result, "contradiction_extra")
        self.assertEqual(extra["component"], "contradiction")
        self.assertEqual(len(extra["endpoints"]), 2)

    def test_symmetric_gold_contradiction_edges_are_not_double_counted(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        predictions = oracle_component_predictions(scenario)
        predictions[0].contradicts = []
        predictions[1].contradicts = [predictions[0].candidate_id]
        candidates = [
            event.candidate
            for event in scenario.sorted_events()
            if event.candidate is not None
        ]
        first_candidate = candidates[0]
        second_candidate = candidates[1]
        first_candidate.contradicts = [second_candidate.candidate_id]

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["contradiction_tp"], 1)
        self.assertEqual(metrics["contradiction_fp"], 0)
        self.assertEqual(metrics["contradiction_fn"], 0)
        self.assertEqual(metrics["contradiction_recall"], 1.0)

    def test_duplicate_event_predictions_count_as_false_positives(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        predictions = oracle_component_predictions(scenario)
        predictions.append(predictions[0])

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["candidate_detection_tp"], 2)
        self.assertEqual(metrics["candidate_detection_fp"], 1)
        self.assertEqual(metrics["candidate_detection_fn"], 0)
        self.assertEqual(metrics["predicted_event_count"], 2)
        self.assertEqual(metrics["extra_same_event_prediction_count"], 1)
        self.assertEqual(metrics["predictions_per_event_p50"], 1.0)
        self.assertEqual(metrics["predictions_per_event_p95"], 2.0)
        self.assertEqual(metrics["predictions_per_event_max"], 2)
        self.assertAlmostEqual(metrics["candidate_detection_precision"], 2 / 3)
        self.assertEqual(metrics["candidate_detection_recall"], 1.0)
        duplicate = _failure_by_type(result, "candidate_duplicate")
        self.assertEqual(duplicate["component"], "candidate_detection")
        self.assertEqual(duplicate["event_id"], predictions[0].event_id)

    def test_extra_same_event_prediction_does_not_hide_valid_prediction(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        oracle_predictions = oracle_component_predictions(scenario)
        misleading_extra = CandidateComponentPrediction(
            event_id=oracle_predictions[0].event_id,
            candidate_id="",
            canonical_id="wrong-canonical-cluster",
            claim_type="tooling_preference",
            scope_level="session",
            scope_key="wrong-scope",
        )

        result = evaluate_component_predictions(
            [scenario],
            {
                scenario.scenario_id: [
                    misleading_extra,
                    oracle_predictions[0],
                    oracle_predictions[1],
                ]
            },
        )
        metrics = result["metrics"]

        self.assertEqual(metrics["candidate_detection_tp"], 2)
        self.assertEqual(metrics["candidate_detection_fp"], 1)
        self.assertEqual(metrics["candidate_detection_fn"], 0)
        self.assertEqual(metrics["predicted_event_count"], 2)
        self.assertEqual(metrics["extra_same_event_prediction_count"], 1)
        self.assertEqual(metrics["predictions_per_event_p50"], 1.0)
        self.assertEqual(metrics["predictions_per_event_p95"], 2.0)
        self.assertEqual(metrics["predictions_per_event_max"], 2)
        self.assertEqual(metrics["claim_type_accuracy"], 1.0)
        self.assertEqual(metrics["scope_level_accuracy"], 1.0)
        self.assertEqual(metrics["scope_key_accuracy"], 1.0)
        self.assertEqual(metrics["canonicalization_b_cubed_f1"], 1.0)
        self.assertIn("candidate_duplicate", _failure_types(result))

    def test_canonicalization_split_example_emits_below_score_coverage_threshold(self) -> None:
        scenario = generate_scenarios("false_corroboration", 1, "clean")[0]
        oracle_predictions = oracle_component_predictions(scenario)
        predictions = [
            oracle_predictions[0],
            CandidateComponentPrediction(
                event_id=oracle_predictions[1].event_id,
                candidate_id="",
                canonical_id="wrong-split-cluster",
                claim_type=oracle_predictions[1].claim_type,
                scope_level=oracle_predictions[1].scope_level,
                scope_key=oracle_predictions[1].scope_key,
            ),
        ]

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )

        self.assertLess(
            result["metrics"]["canonicalization_coverage"],
            result["metrics"]["canonicalization_coverage_threshold"],
        )
        self.assertIsNone(result["metrics"]["canonicalization_b_cubed_f1"])
        split = _failure_by_type(result, "canonicalization_split")
        self.assertEqual(split["component"], "canonicalization")
        self.assertEqual(len(split["gold"]), 2)
        self.assertEqual(len(split["predicted"]), 2)

    def test_canonicalization_merge_example_is_pair_based(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, template_mix="dirty")[0]
        observations = [
            event
            for event in scenario.sorted_events()
            if event.kind == EventKind.OBSERVATION and event.candidate is not None
        ]
        observations[1].candidate.canonical_id = "different-gold-cluster"
        predictions = oracle_component_predictions(scenario)
        predictions[1] = CandidateComponentPrediction(
            event_id=predictions[1].event_id,
            candidate_id="",
            canonical_id=predictions[0].canonical_id,
            claim_type=predictions[1].claim_type,
            scope_level=predictions[1].scope_level,
            scope_key=predictions[1].scope_key,
        )

        result = evaluate_component_predictions(
            [scenario],
            {scenario.scenario_id: predictions},
        )

        merge = _failure_by_type(result, "canonicalization_merge")
        self.assertEqual(merge["component"], "canonicalization")
        self.assertEqual(merge["event_id"], predictions[0].event_id)
        self.assertEqual(merge["other_event_id"], predictions[1].event_id)
        self.assertNotEqual(merge["gold"][0]["canonical_id"], merge["gold"][1]["canonical_id"])
        self.assertEqual(merge["predicted"][0]["canonical_id"], merge["predicted"][1]["canonical_id"])

    def test_b_cubed_matches_hand_computed_clustering_case(self) -> None:
        result = _b_cubed(
            {
                "item-1": "gold-a",
                "item-2": "gold-a",
                "item-3": "gold-b",
                "item-4": "gold-b",
            },
            {
                "item-1": "predicted-single",
                "item-2": "predicted-single",
                "item-3": "predicted-single",
                "item-4": "predicted-single",
            },
        )

        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 1.0)
        self.assertAlmostEqual(result["f1"], 2 / 3)
        self.assertEqual(result["coverage"], 1.0)

    def test_b_cubed_is_undefined_below_canonicalization_coverage_threshold(self) -> None:
        result = _b_cubed(
            {
                "item-1": "gold-a",
                "item-2": "gold-a",
                "item-3": "gold-b",
                "item-4": "gold-b",
            },
            {
                "item-1": "predicted-a",
                "item-2": "predicted-a",
            },
        )

        self.assertEqual(result["coverage"], 0.5)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])
        self.assertIsNone(result["f1"])

    def test_cli_writes_oracle_upper_bound_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "component_eval.json"

            stdout = StringIO()
            with redirect_stdout(stdout):
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
            self.assertEqual(artifact["failure_examples"], [])
            self.assertEqual(artifact["failure_example_count"], 0)
            self.assertEqual(artifact["failure_example_limits"], {"per_type": 20})
            self.assertIn("failure_examples=0", stdout.getvalue())

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

            stdout = StringIO()
            with redirect_stdout(stdout):
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
            self.assertEqual(artifact["failure_examples"], [])
            self.assertEqual(artifact["failure_example_count"], 0)
            self.assertIn("failure_examples=0", stdout.getvalue())

    def test_cli_reports_scenario_errors_as_zero_predictions(self) -> None:
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
                        },
                        "scenario_errors": {
                            scenario.scenario_id: {
                                "error_type": "validation_error",
                                "message": "bad enum",
                            }
                        },
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
            self.assertEqual(artifact["scenario_error_count"], 1)
            self.assertEqual(artifact["metrics"]["scenario_error_count"], 1)
            self.assertEqual(artifact["metrics"]["candidate_detection_tp"], 0)
            self.assertEqual(artifact["metrics"]["candidate_detection_fn"], 2)
            self.assertIn("scenario_error", _failure_types(artifact))
            scenario_error = _failure_by_type(artifact, "scenario_error")
            self.assertEqual(scenario_error["error"]["error_type"], "validation_error")

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

    def test_load_predictions_by_scenario_normalizes_null_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            predictions_path = Path(tmpdir) / "predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "scenario_predictions": {
                            "scenario-1": [
                                {
                                    "event_id": None,
                                    "candidate_id": None,
                                    "canonical_id": None,
                                    "claim_type": None,
                                    "scope_level": None,
                                    "scope_key": None,
                                    "contradicts": [None, "candidate-1"],
                                    "contradicts_event_ids": [None, "event-1"],
                                    "raw_claim": None,
                                    "confidence": None,
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            prediction = load_predictions_by_scenario(predictions_path)["scenario-1"][0]

            self.assertEqual(prediction.event_id, "")
            self.assertEqual(prediction.candidate_id, "")
            self.assertEqual(prediction.canonical_id, "")
            self.assertEqual(prediction.claim_type, "")
            self.assertEqual(prediction.scope_level, "")
            self.assertEqual(prediction.scope_key, "")
            self.assertEqual(prediction.contradicts, ["candidate-1"])
            self.assertEqual(prediction.contradicts_event_ids, ["event-1"])
            self.assertEqual(prediction.raw_claim, "")
            self.assertIsNone(prediction.confidence)

    def test_load_predictions_by_scenario_rejects_malformed_confidence(self) -> None:
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
                                    "confidence": "high",
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "confidence must be numeric or null"):
                load_predictions_by_scenario(predictions_path)

    def test_load_scenario_errors_requires_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            predictions_path = Path(tmpdir) / "predictions.json"
            predictions_path.write_text(
                json.dumps(
                    {
                        "scenario_predictions": {},
                        "scenario_errors": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "scenario_errors must be an object"):
                load_scenario_errors(predictions_path)

    def test_load_predictions_by_scenario_requires_wrapper_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            predictions_path = Path(tmpdir) / "predictions.json"
            predictions_path.write_text(
                json.dumps({"version": "1.0", "extracted_at": "2026-05-05T00:00:00"}),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_predictions_by_scenario(predictions_path)

    def test_oracle_artifact_exposes_quality_gate_thresholds(self) -> None:
        artifact = build_oracle_component_eval_artifact(
            family="forced_contradiction",
            scenario_count=1,
            template_mix="dirty",
        )

        self.assertIn("candidate_detection_f1", artifact["quality_gate_thresholds"])
        self.assertTrue(artifact["quality_gates"]["candidate_detection_f1"]["passed"])

    def test_component_artifact_without_predictions_is_labeled_oracle_upper_bound(self) -> None:
        artifact = build_component_eval_artifact(
            family="forced_contradiction",
            scenario_count=1,
            template_mix="dirty",
        )

        self.assertEqual(artifact["mode"], "oracle_component_upper_bound")
        self.assertEqual(artifact["failure_examples"], [])
        self.assertEqual(artifact["failure_example_count"], 0)

    def test_failure_examples_are_capped_per_type_with_overflow(self) -> None:
        scenarios = generate_forced_contradiction_scenarios(25, template_mix="dirty")

        result = evaluate_component_predictions(
            scenarios,
            {scenario.scenario_id: [] for scenario in scenarios},
        )

        candidate_missing_examples = [
            example
            for example in result["failure_examples"]
            if example["failure_type"] == "candidate_missing"
        ]
        self.assertEqual(len(candidate_missing_examples), 20)
        self.assertEqual(
            result["failure_example_overflow"]["candidate_missing"],
            {
                "emitted": 20,
                "omitted": result["metrics"]["candidate_detection_fn"] - 20,
                "truncated": True,
            },
        )

    def test_mechanism_diverse_heldout_oracle_artifact_uses_frozen_lock(self) -> None:
        artifact = build_oracle_component_eval_artifact(
            family="mechanism_diverse_heldout",
            scenario_count=25,
            template_mix="frozen",
        )

        self.assertEqual(artifact["scenario_count"], 3)
        for gate in artifact["quality_gates"].values():
            self.assertTrue(gate["passed"])

    def test_oracle_upper_bound_reference_matrix_still_scores_one_for_applicable_gates(self) -> None:
        for family in COMPONENT_EVAL_FAMILIES:
            template_mixes = TEMPLATE_MIXES_BY_FAMILY[family]
            scenario_count = 3 if family == "mechanism_diverse_heldout" else 6
            for template_mix in template_mixes:
                with self.subTest(family=family, template_mix=template_mix):
                    artifact = build_oracle_component_eval_artifact(
                        family=family,
                        scenario_count=scenario_count,
                        template_mix=template_mix,
                    )
                    self.assertEqual(artifact["scenario_error_count"], 0)
                    for gate in artifact["quality_gates"].values():
                        self.assertTrue(gate["passed"])
                        if gate["status"] == "measured":
                            self.assertEqual(gate["value"], 1.0)

    def test_generated_gold_contradiction_targets_resolve_to_unique_observation_events(self) -> None:
        for family in COMPONENT_EVAL_FAMILIES:
            template_mixes = TEMPLATE_MIXES_BY_FAMILY[family]
            scenario_count = 3 if family == "mechanism_diverse_heldout" else 12
            for template_mix in template_mixes:
                scenarios = generate_scenarios(family, scenario_count, template_mix)
                for scenario in scenarios:
                    candidate_id_to_event_id = {}
                    for event in scenario.sorted_events():
                        if event.kind != EventKind.OBSERVATION or event.candidate is None:
                            continue
                        candidate_id = event.candidate.candidate_id
                        self.assertNotIn(candidate_id, candidate_id_to_event_id)
                        candidate_id_to_event_id[candidate_id] = event.event_id
                    for event in scenario.sorted_events():
                        if event.kind != EventKind.OBSERVATION or event.candidate is None:
                            continue
                        for target_candidate_id in event.candidate.contradicts:
                            self.assertIn(target_candidate_id, candidate_id_to_event_id)

    def test_adversarial_upstream_noise_is_not_component_eval_eligible(self) -> None:
        with self.assertRaisesRegex(ValueError, "not component-eval eligible"):
            build_oracle_component_eval_artifact(
                family="adversarial_upstream_noise",
                scenario_count=5,
                template_mix="mixed",
            )


if __name__ == "__main__":
    unittest.main()
