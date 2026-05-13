import importlib.util
import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from cq.eval.component_eval import evaluate_component_predictions, oracle_predictions_by_scenario
from cq.eval.runner import generate_scenarios
from cq.schemas.memory import jsonable


def _load_gate_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_component_gate_decision.py"
    spec = importlib.util.spec_from_file_location("run_component_gate_decision", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_gate_module()


class ComponentGateDecisionTests(unittest.TestCase):
    def test_primary_rows_and_artifact_names_are_fixed(self) -> None:
        rows = gate.primary_gate_rows()

        self.assertEqual(
            [row.family for row in rows],
            [
                gate.FORCED_CONTRADICTION,
                gate.SCOPE_CONTAMINATION,
                gate.PREFERENCE_DRIFT,
                gate.USEFUL_PENDING_MEMORY,
                gate.FALSE_CORROBORATION,
                gate.MEMORY_POISONING,
            ],
        )
        self.assertTrue(all(row.template_mix == "heldout" for row in rows))
        self.assertTrue(all(row.scenarios == 60 for row in rows))
        self.assertTrue(all(row.model == gate.matrix.QWEN_7B_Q4KM for row in rows))
        self.assertTrue(all(row.schema_profile == "default" for row in rows))

        paths = gate.gate_artifact_paths(rows[0], Path("/tmp/cq-results"))

        self.assertEqual(
            paths.predictions.name,
            "component_gate_decision_forced_contradiction_local_extractor_qwen2_5_7b_q4km_general_v1_default_heldout_n60_primary_floor_predictions.json",
        )
        self.assertIn("_n60_primary_floor_component_eval.json", paths.component_eval.name)

    def test_primary_rows_can_promote_32b_to_unlocking_role(self) -> None:
        rows = gate.primary_gate_rows(
            primary_model=gate.matrix.QWEN_32B_Q4KM,
            schema_profile="scenario_conditioned",
        )

        self.assertTrue(all(row.model == gate.matrix.QWEN_32B_Q4KM for row in rows))
        self.assertTrue(all(row.gate_role == "primary_unlock_probe" for row in rows))
        self.assertTrue(all(row.schema_profile == "scenario_conditioned" for row in rows))
        self.assertIn(
            "_general_v1_scenario_conditioned_heldout_n60_primary_unlock_probe_",
            gate.gate_artifact_paths(rows[0], Path("/tmp/cq-results")).predictions.name,
        )

    def test_headroom_rows_can_be_filtered_and_include_descriptive_frozen_sentinel(self) -> None:
        rows = gate.headroom_gate_rows(
            families=(gate.SCOPE_CONTAMINATION, gate.PREFERENCE_DRIFT),
        )
        self.assertEqual(
            [row.family for row in rows],
            [gate.SCOPE_CONTAMINATION, gate.PREFERENCE_DRIFT],
        )
        self.assertTrue(all(row.model == gate.matrix.QWEN_32B_Q4KM for row in rows))
        frozen = gate.frozen_sentinel_rows(
            model=gate.matrix.QWEN_32B_Q4KM,
            gate_role="descriptive_headroom_frozen_sentinel",
        )[0]
        self.assertEqual(frozen.model, gate.matrix.QWEN_32B_Q4KM)
        self.assertEqual(frozen.gate_role, "descriptive_headroom_frozen_sentinel")

    def test_expected_denominators_match_current_generator_contract(self) -> None:
        expected = {
            gate.FORCED_CONTRADICTION: (150, 90, 120),
            gate.SCOPE_CONTAMINATION: (105, 30, 45),
            gate.PREFERENCE_DRIFT: (120, 30, 90),
            gate.USEFUL_PENDING_MEMORY: (90, 30, 30),
            gate.FALSE_CORROBORATION: (300, 0, 600),
            gate.MEMORY_POISONING: (84, 24, 24),
        }

        for row in gate.primary_gate_rows():
            denominators = gate.expected_denominators_for_row(row)
            self.assertEqual(
                (
                    denominators["candidate_event_count"],
                    denominators["undirected_contradiction_edge_count"],
                    denominators["positive_canonical_pair_count"],
                ),
                expected[row.family],
            )

        aggregate = gate.expected_denominators_payload(gate.primary_gate_rows())["aggregate"]
        self.assertEqual(aggregate["candidate_event_count"], 849)
        self.assertEqual(aggregate["undirected_contradiction_edge_count"], 204)
        self.assertEqual(aggregate["positive_canonical_pair_count"], 909)

    def test_wilson_and_f1_composite_fields_do_not_overclaim(self) -> None:
        self.assertEqual(gate.minimum_successes_for_wilson_threshold(24, 0.75), 23)

        payload = gate.f1_composite_gate(
            metric_name="candidate_detection_f1",
            threshold=0.75,
            precision_successes=849,
            precision_total=849,
            recall_successes=849,
            recall_total=849,
        )

        self.assertIn("f1_conservative_composite_from_wilson_pr", payload)
        self.assertNotIn("f1_wilson_lower_bound", payload)
        self.assertIn("not a 95% lower bound on F1", payload["coverage_note"])
        self.assertEqual(
            payload["precision_support"]["interval_method"],
            "wilson_lower_bound_event_assumption",
        )
        self.assertGreaterEqual(
            payload["f1_conservative_composite_from_wilson_pr"],
            payload["threshold"],
        )

    def test_int_metric_rejects_fractional_rates_for_count_fields(self) -> None:
        self.assertEqual(gate._int_metric({"count": 3.0}, "count"), 3)
        self.assertEqual(gate._int_metric({}, "missing_count"), 0)

        with self.assertRaisesRegex(ValueError, "must be an integer count"):
            gate._int_metric({"candidate_detection_tp": 0.99}, "candidate_detection_tp")

        with self.assertRaisesRegex(ValueError, "not a boolean"):
            gate._int_metric({"candidate_detection_tp": True}, "candidate_detection_tp")

    def test_dry_run_records_generation_warning_and_paths_without_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = gate.dry_run_plan(
                output_dir=Path(tmpdir),
                model_command="python3 scripts/ollama_component_extractor.py",
                decoding_json='{"temperature": 0}',
                per_scenario_timeout_seconds=180.0,
                include_headroom=True,
                include_frozen_sentinel=True,
            )

        self.assertEqual(plan["mode"], "dry_run")
        self.assertEqual(plan["policy_comparison_unlocked"], "not_evaluated")
        self.assertEqual(plan["primary_model_tag"], gate.matrix.QWEN_7B_Q4KM.model_id)
        self.assertEqual(plan["schema_profile"], "default")
        self.assertEqual(len(plan["rows"]), 13)
        self.assertIn(
            'generate_scenarios(family, 60, "heldout")',
            plan["generation_contract"]["primary_rows"],
        )
        self.assertIn("template-rotation variants", plan["generation_contract"]["dependence_warning"])
        self.assertIn("run_prompt_regression", plan["phase_a_contract"]["source"])
        self.assertIn("run_determinism_check", plan["determinism_contract"]["source"])
        self.assertIn("_default_heldout_n60_primary_floor_predictions.json", plan["rows"][0]["paths"]["predictions"])

    def test_dry_run_supports_selected_headroom_families_and_headroom_frozen_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = gate.dry_run_plan(
                output_dir=Path(tmpdir),
                model_command="python3 scripts/ollama_component_extractor.py",
                decoding_json='{"temperature": 0}',
                per_scenario_timeout_seconds=180.0,
                primary_model_tag=gate.matrix.QWEN_32B_Q4KM.model_id,
                schema_profile="scenario_conditioned",
                include_headroom=True,
                headroom_families=(gate.SCOPE_CONTAMINATION, gate.PREFERENCE_DRIFT),
                include_headroom_frozen_sentinel=True,
            )

        rows = plan["rows"]
        self.assertEqual(len(rows), 9)
        primary_rows = [row for row in rows if row["gate_role"] == "primary_unlock_probe"]
        self.assertEqual(len(primary_rows), 6)
        self.assertTrue(all(row["model_id"] == gate.matrix.QWEN_32B_Q4KM.model_id for row in primary_rows))
        self.assertTrue(all(row["schema_profile"] == "scenario_conditioned" for row in rows))
        headroom_rows = [row for row in rows if row["gate_role"].startswith("descriptive_headroom")]
        self.assertEqual(
            {(row["family"], row["gate_role"]) for row in headroom_rows},
            {
                (gate.SCOPE_CONTAMINATION, "descriptive_headroom"),
                (gate.PREFERENCE_DRIFT, "descriptive_headroom"),
                (gate.MECHANISM_DIVERSE_HELDOUT, "descriptive_headroom_frozen_sentinel"),
            },
        )

    def test_oracle_summary_unlocks_and_marks_b_cubed_observed_only(self) -> None:
        results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]

        summary = gate.gate_summary_payload(
            primary_results=results,
            headroom_results=[],
            frozen_sentinel_results=[],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            summary_label=None,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertTrue(summary["policy_comparison_unlocked"])
        self.assertEqual(summary["primary_model_tag"], gate.matrix.QWEN_7B_Q4KM.model_id)
        self.assertEqual(summary["schema_profile"], "default")
        self.assertEqual(summary["unlock_rule"]["primary_model_tag"], gate.matrix.QWEN_7B_Q4KM.model_id)
        self.assertEqual(summary["blockers"], [])
        aggregate = summary["aggregate_primary"]
        self.assertEqual(
            aggregate["canonicalization_b_cubed_f1_interval_policy"]["status"],
            "observed_only",
        )
        self.assertEqual(
            aggregate["ci_supported_gates"]["canonicalization_pairwise_f1"][
                "supports_quality_gate"
            ],
            "canonicalization_b_cubed_f1",
        )
        self.assertEqual(
            aggregate["ci_supported_gates"]["canonicalization_pairwise_f1"][
                "interval_method"
            ],
            "conservative_composite_from_wilson_precision_recall",
        )
        self.assertEqual(
            aggregate["denominators"]["canonicalization_pairwise"]["gold_positive_pair_count"],
            909,
        )
        self.assertTrue(
            aggregate["canonicalization_b_cubed_f1_interval_policy"]["passed"]
        )
        self.assertIn(
            "Proxy threshold",
            aggregate["ci_supported_gates"]["canonicalization_pairwise_f1"]["threshold_note"],
        )

    def test_phase_a_and_determinism_failures_block_unlock(self) -> None:
        results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]

        summary = gate.gate_summary_payload(
            primary_results=results,
            headroom_results=[],
            frozen_sentinel_results=[],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            summary_label=None,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=False,
            determinism_passed=False,
        )

        self.assertFalse(summary["policy_comparison_unlocked"])
        blocker_types = {blocker["type"] for blocker in summary["blockers"]}
        self.assertIn("phase_a_failed", blocker_types)
        self.assertIn("determinism_failed", blocker_types)

    def test_scenario_errors_block_unlock_even_if_other_gates_pass(self) -> None:
        results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]
        first = results[0]
        artifact = dict(first.component_artifact)
        artifact["scenario_error_count"] = 1
        results[0] = gate.GateRowResult(
            row=first.row,
            paths=first.paths,
            component_artifact=artifact,
            predictions_by_scenario=first.predictions_by_scenario,
            scenario_errors=first.scenario_errors,
            reused=first.reused,
        )

        summary = gate.gate_summary_payload(
            primary_results=results,
            headroom_results=[],
            frozen_sentinel_results=[],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            summary_label=None,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertFalse(summary["policy_comparison_unlocked"])
        blocker_types = {blocker["type"] for blocker in summary["blockers"]}
        self.assertIn("primary_scenario_errors", blocker_types)
        self.assertNotIn("per_family_observed_gate_failed", blocker_types)

    def test_aggregate_ci_gate_failure_blocks_unlock(self) -> None:
        results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]
        first = results[0]
        # This pins aggregate evaluation as a fresh recompute from row predictions, not a per-row metric sum.
        results[0] = gate.GateRowResult(
            row=first.row,
            paths=first.paths,
            component_artifact=first.component_artifact,
            predictions_by_scenario={},
            scenario_errors=first.scenario_errors,
            reused=first.reused,
        )

        summary = gate.gate_summary_payload(
            primary_results=results,
            headroom_results=[],
            frozen_sentinel_results=[],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            summary_label=None,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertFalse(summary["policy_comparison_unlocked"])
        aggregate_blockers = [
            blocker
            for blocker in summary["blockers"]
            if blocker["type"] == "aggregate_ci_gate_failed"
        ]
        self.assertTrue(aggregate_blockers)

    def test_aggregate_observed_b_cubed_failure_blocks_unlock(self) -> None:
        results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]
        results = [
            gate.GateRowResult(
                row=result.row,
                paths=result.paths,
                component_artifact=result.component_artifact,
                predictions_by_scenario={
                    scenario_id: [
                        gate.CandidateComponentPrediction(
                            event_id=prediction.event_id,
                            candidate_id=prediction.candidate_id,
                            canonical_id="unique-{}".format(prediction.event_id),
                            claim_type=prediction.claim_type,
                            scope_level=prediction.scope_level,
                            scope_key=prediction.scope_key,
                            contradicts=list(prediction.contradicts),
                            contradicts_event_ids=list(prediction.contradicts_event_ids),
                            raw_claim=prediction.raw_claim,
                            confidence=prediction.confidence,
                        )
                        for prediction in predictions
                    ]
                    for scenario_id, predictions in result.predictions_by_scenario.items()
                },
                scenario_errors=result.scenario_errors,
                reused=result.reused,
            )
            for result in results
        ]

        summary = gate.gate_summary_payload(
            primary_results=results,
            headroom_results=[],
            frozen_sentinel_results=[],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            summary_label=None,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertFalse(summary["policy_comparison_unlocked"])
        observed_blockers = [
            blocker
            for blocker in summary["blockers"]
            if blocker["type"] == "aggregate_observed_gate_failed"
        ]
        self.assertEqual(
            [blocker["metric"] for blocker in observed_blockers],
            ["canonicalization_b_cubed_f1"],
        )

    def test_frozen_sentinel_observed_gate_failure_blocks_unlock(self) -> None:
        primary_results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]
        frozen = _oracle_row_result(gate.frozen_sentinel_rows()[0])
        artifact = dict(frozen.component_artifact)
        quality_gates = {
            name: dict(payload)
            for name, payload in artifact["quality_gates"].items()
        }
        quality_gates["candidate_detection_f1"]["passed"] = False
        quality_gates["candidate_detection_f1"]["value"] = 0.0
        artifact["quality_gates"] = quality_gates
        frozen = gate.GateRowResult(
            row=frozen.row,
            paths=frozen.paths,
            component_artifact=artifact,
            predictions_by_scenario=frozen.predictions_by_scenario,
            scenario_errors=frozen.scenario_errors,
            reused=frozen.reused,
        )

        summary = gate.gate_summary_payload(
            primary_results=primary_results,
            headroom_results=[],
            frozen_sentinel_results=[frozen],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            summary_label=None,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertFalse(summary["policy_comparison_unlocked"])
        blocker_types = {blocker["type"] for blocker in summary["blockers"]}
        self.assertIn("frozen_sentinel_observed_gate_failed", blocker_types)

    def test_descriptive_headroom_frozen_sentinel_does_not_block_unlock(self) -> None:
        primary_results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]
        headroom_frozen = _oracle_row_result(
            gate.frozen_sentinel_rows(
                model=gate.matrix.QWEN_32B_Q4KM,
                gate_role="descriptive_headroom_frozen_sentinel",
            )[0]
        )
        artifact = dict(headroom_frozen.component_artifact)
        quality_gates = {
            name: dict(payload)
            for name, payload in artifact["quality_gates"].items()
        }
        quality_gates["candidate_detection_f1"]["passed"] = False
        quality_gates["candidate_detection_f1"]["value"] = 0.0
        artifact["quality_gates"] = quality_gates
        headroom_frozen = gate.GateRowResult(
            row=headroom_frozen.row,
            paths=headroom_frozen.paths,
            component_artifact=artifact,
            predictions_by_scenario=headroom_frozen.predictions_by_scenario,
            scenario_errors=headroom_frozen.scenario_errors,
            reused=headroom_frozen.reused,
        )

        summary = gate.gate_summary_payload(
            primary_results=primary_results,
            headroom_results=[headroom_frozen],
            frozen_sentinel_results=[],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            summary_label=None,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertTrue(summary["policy_comparison_unlocked"])
        self.assertEqual(summary["unlock_checks"]["frozen_sentinel_observed_gate_failure_count"], 0)
        self.assertEqual(summary["blockers"], [])

    def test_run_or_reuse_gate_row_uses_matching_cached_artifacts(self) -> None:
        row = gate.GateRow(
            family=gate.FORCED_CONTRADICTION,
            template_mix=gate.TEMPLATE_MIX_HELDOUT,
            scenarios=1,
            model=gate.matrix.QWEN_7B_Q4KM,
            prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            gate_role="primary_floor",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            paths = gate.gate_artifact_paths(row, output_dir)
            script_path = _write_empty_prediction_model_script(output_dir)
            predictions_payload = gate.build_extractor_output(
                family=row.family,
                scenario_count=row.scenarios,
                template_mix=row.template_mix,
                mode=gate.MODEL_MODE,
                model_command=_fake_model_command(script_path),
                model_id=row.model.model_id,
                prompt_template_path=str(row.prompt_path),
                decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
                per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            )
            model_digest = gate.PREREGISTERED_MODEL_DIGESTS[row.model.model_id]
            predictions_payload["model_digest"] = model_digest
            predictions_payload["model_diagnostics"] = {
                "schema_profile": row.schema_profile,
                "model_digest": model_digest,
            }
            paths.predictions.write_text(
                json.dumps(jsonable(predictions_payload), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            loaded_predictions = gate.load_predictions_by_scenario(paths.predictions)
            component_artifact = gate._build_row_component_artifact(
                row,
                loaded_predictions,
                gate.load_scenario_errors(paths.predictions),
                model_digest=model_digest,
            )
            paths.component_eval.write_text(
                json.dumps(jsonable(component_artifact), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = gate.run_or_reuse_gate_row(
                row,
                output_dir=output_dir,
                model_command=_fake_model_command(script_path),
                decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
                per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            )

        self.assertTrue(result.reused)
        self.assertEqual(result.predictions_by_scenario, loaded_predictions)
        self.assertEqual(result.component_artifact["family"], row.family)

    def test_run_or_reuse_gate_row_flags_vacuous_placeholders_from_cached_predictions(self) -> None:
        row = gate.GateRow(
            family=gate.FORCED_CONTRADICTION,
            template_mix=gate.TEMPLATE_MIX_HELDOUT,
            scenarios=1,
            model=gate.matrix.QWEN_7B_Q4KM,
            prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            gate_role="primary_floor",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            paths = gate.gate_artifact_paths(row, output_dir)
            script_path = _write_empty_prediction_model_script(output_dir)
            predictions_payload = gate.build_extractor_output(
                family=row.family,
                scenario_count=row.scenarios,
                template_mix=row.template_mix,
                mode=gate.MODEL_MODE,
                model_command=_fake_model_command(script_path),
                model_id=row.model.model_id,
                prompt_template_path=str(row.prompt_path),
                decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
                per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            )
            model_digest = gate.PREREGISTERED_MODEL_DIGESTS[row.model.model_id]
            predictions_payload["model_digest"] = model_digest
            predictions_payload["model_diagnostics"] = {
                "schema_profile": row.schema_profile,
                "model_digest": model_digest,
            }
            scenario_id = next(iter(predictions_payload["scenario_predictions"]))
            predictions_payload["scenario_predictions"][scenario_id] = [
                {
                    "event_id": "{}-event-1".format(scenario_id),
                    "candidate_id": "",
                    "canonical_id": "unknown",
                    "claim_type": "world_fact",
                    "scope_level": "world_global",
                    "scope_key": "global",
                    "contradicts_event_ids": [],
                    "raw_claim": "claim",
                    "confidence": 1.0,
                }
            ]
            paths.predictions.write_text(
                json.dumps(jsonable(predictions_payload), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            component_artifact = gate._build_row_component_artifact(
                row,
                gate.load_predictions_by_scenario(paths.predictions),
                gate.load_scenario_errors(paths.predictions),
                model_digest=model_digest,
            )
            paths.component_eval.write_text(
                json.dumps(jsonable(component_artifact), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = gate.run_or_reuse_gate_row(
                row,
                output_dir=output_dir,
                model_command=_fake_model_command(script_path),
                decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
                per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            )

        self.assertTrue(result.reused)
        self.assertEqual(result.predictions_by_scenario[scenario_id], [])
        self.assertEqual(
            result.scenario_errors[scenario_id]["message"],
            "Prediction 0 must include non-vacuous string canonical_id",
        )
        self.assertEqual(result.component_artifact["scenario_error_count"], 1)
        self.assertEqual(
            result.component_artifact["scenario_errors"][scenario_id]["message"],
            "Prediction 0 must include non-vacuous string canonical_id",
        )

    def test_cached_artifact_provenance_rejects_stale_model_digest(self) -> None:
        row = gate.GateRow(
            family=gate.FORCED_CONTRADICTION,
            template_mix=gate.TEMPLATE_MIX_HELDOUT,
            scenarios=1,
            model=gate.matrix.QWEN_7B_Q4KM,
            prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            gate_role="primary_floor",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            paths = gate.gate_artifact_paths(row, output_dir)
            script_path = _write_empty_prediction_model_script(output_dir)
            predictions_payload = gate.build_extractor_output(
                family=row.family,
                scenario_count=row.scenarios,
                template_mix=row.template_mix,
                mode=gate.MODEL_MODE,
                model_command=_fake_model_command(script_path),
                model_id=row.model.model_id,
                prompt_template_path=str(row.prompt_path),
                decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
                per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            )
            predictions_payload["model_digest"] = "sha256:stale"
            predictions_payload["model_diagnostics"] = {
                "schema_profile": row.schema_profile,
                "model_digest": "sha256:stale",
            }
            paths.predictions.write_text(
                json.dumps(jsonable(predictions_payload), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            component_artifact = gate._build_row_component_artifact(
                row,
                gate.load_predictions_by_scenario(paths.predictions),
                gate.load_scenario_errors(paths.predictions),
                model_digest="sha256:stale",
            )
            paths.component_eval.write_text(
                json.dumps(jsonable(component_artifact), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            mismatches = gate.gate_cached_artifact_provenance_mismatches(
                row,
                paths,
                model_command=_fake_model_command(script_path),
            )

        fields = {item["field"] for item in mismatches}
        self.assertIn("predictions.model_digest", fields)
        self.assertIn("predictions.model_diagnostics.model_digest", fields)
        self.assertIn("component.model_digest", fields)

    def test_main_uses_summary_label_for_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_run_gate_decision = gate.run_gate_decision
            called = {}

            def fake_run_gate_decision(**kwargs):
                called.update(kwargs)
                return gate.gate_summary_path(
                    Path(kwargs["output_dir"]),
                    general_prompt_label=kwargs["summary_label"] or kwargs["general_prompt_label"],
                )

            try:
                gate.run_gate_decision = fake_run_gate_decision
                exit_code = gate.main(
                    [
                        "--output-dir",
                        tmpdir,
                        "--primary-model-tag",
                        gate.matrix.QWEN_7B_Q4KM.model_id,
                        "--schema-profile",
                        "default",
                        "--summary-label",
                        "custom_followup_label",
                    ]
                )
            finally:
                gate.run_gate_decision = original_run_gate_decision

        self.assertEqual(exit_code, 0)
        self.assertEqual(called["summary_label"], "custom_followup_label")
        self.assertEqual(called["primary_model_tag"], gate.matrix.QWEN_7B_Q4KM.model_id)
        self.assertEqual(called["schema_profile"], "default")

    def test_main_returns_one_and_writes_stop_report_on_stop_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original_run_gate_decision = gate.run_gate_decision

            def stop_gate_decision(**_kwargs):
                raise gate.matrix.StopConditionError(
                    "model_digest_mismatch",
                    {"expected_digest": "sha256:locked", "observed_digest": "sha256:new"},
                )

            try:
                gate.run_gate_decision = stop_gate_decision
                exit_code = gate.main(
                    [
                        "--output-dir",
                        tmpdir,
                        "--primary-model-tag",
                        gate.matrix.QWEN_7B_Q4KM.model_id,
                        "--schema-profile",
                        "default",
                    ]
                )
            finally:
                gate.run_gate_decision = original_run_gate_decision

            reports = list(Path(tmpdir).glob("component_gate_decision_stop_*.json"))
            report = json.loads(reports[0].read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 1)
        self.assertEqual(len(reports), 1)
        self.assertEqual(report["reason"], "model_digest_mismatch")
        self.assertEqual(report["details"]["observed_digest"], "sha256:new")

    def test_primary_model_digest_verification_records_backend(self) -> None:
        client = _FakeOllamaClient(
            version="0.23.1",
            digest=gate.PREREGISTERED_MODEL_DIGESTS[gate.matrix.QWEN_7B_Q4KM.model_id],
        )

        backend = gate.verify_primary_model_backend(
            gate.matrix.QWEN_7B_Q4KM.model_id,
            runner_command="python3 scripts/run_component_gate_decision.py",
            client=client,
        )

        self.assertEqual(backend.model_tag, gate.matrix.QWEN_7B_Q4KM.model_id)
        self.assertEqual(
            backend.resolved_digest,
            gate.PREREGISTERED_MODEL_DIGESTS[gate.matrix.QWEN_7B_Q4KM.model_id],
        )
        self.assertEqual(backend.ollama_server_version, "0.23.1")

    def test_primary_model_digest_mismatch_aborts_with_details(self) -> None:
        client = _FakeOllamaClient(version="0.23.1", digest="sha256:not-locked")

        with self.assertRaises(gate.matrix.StopConditionError) as context:
            gate.verify_primary_model_backend(
                gate.matrix.QWEN_7B_Q4KM.model_id,
                runner_command="python3 scripts/run_component_gate_decision.py --dry-run",
                client=client,
            )

        self.assertEqual(context.exception.reason, "model_digest_mismatch")
        self.assertEqual(
            context.exception.details["expected_digest"],
            gate.PREREGISTERED_MODEL_DIGESTS[gate.matrix.QWEN_7B_Q4KM.model_id],
        )
        self.assertEqual(context.exception.details["observed_digest"], "sha256:not-locked")
        self.assertEqual(context.exception.details["ollama_server_version"], "0.23.1")

    def test_model_command_schema_profile_is_runner_owned(self) -> None:
        command = gate.model_command_for_schema_profile(
            "python3 scripts/ollama_component_extractor.py",
            "scenario_conditioned",
        )

        self.assertTrue(command.endswith("--schema-profile scenario_conditioned"))
        with self.assertRaisesRegex(ValueError, "runner-level --schema-profile"):
            gate.model_command_for_schema_profile(
                "python3 scripts/ollama_component_extractor.py --schema-profile default",
                "scenario_conditioned",
            )

    def test_manifest_records_summary_sha_and_unlock_probe_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "component_gate_decision_qwen_default_summary.json"
            summary_payload = {
                "primary_model_tag": gate.matrix.QWEN_7B_Q4KM.model_id,
                "primary_model_digest": gate.PREREGISTERED_MODEL_DIGESTS[
                    gate.matrix.QWEN_7B_Q4KM.model_id
                ],
                "expected_primary_model_digest": gate.PREREGISTERED_MODEL_DIGESTS[
                    gate.matrix.QWEN_7B_Q4KM.model_id
                ],
                "ollama_server_version": "0.23.1",
                "general_prompt_sha256": "prompt-sha",
                "schema_profile": "default",
            }
            summary_path.write_text(json.dumps(summary_payload), encoding="utf-8")

            manifest_path = gate.write_gate_manifest(
                summary_path=summary_path,
                summary_payload=summary_payload,
                runner_command="python3 scripts/run_component_gate_decision.py",
                pre_run_working_tree_status="clean",
            )
            expected_sha = gate.sha256_file(summary_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        row = manifest["artifacts"][0]
        self.assertEqual(row["summary_json_sha256"], expected_sha)
        self.assertEqual(row["primary_model_tag"], gate.matrix.QWEN_7B_Q4KM.model_id)
        self.assertEqual(row["schema_profile"], "default")
        self.assertEqual(row["working_tree_status"], "clean")

    def test_locked_7b_anchor_summary_counts_are_pinned(self) -> None:
        self.assertTrue(gate.locked_baseline_anchor_matches())

    def test_anchor_verification_uses_pinned_counts_when_static_artifact_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "fresh_anchor_summary.json"
            summary_path.write_text(
                json.dumps({"unlock_checks": gate.LOCKED_BASELINE_UNLOCK_CHECKS}),
                encoding="utf-8",
            )

            error = gate.verify_anchor_against_locked_baseline(
                summary_path,
                locked_summary_path=Path(tmpdir) / "absent_locked_summary.json",
            )

        self.assertIsNone(error)

    def test_anchor_verification_rejects_count_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_path = Path(tmpdir) / "fresh_anchor_summary.json"
            payload = {"unlock_checks": dict(gate.LOCKED_BASELINE_UNLOCK_CHECKS)}
            payload["unlock_checks"]["primary_scenario_error_count"] = 44
            summary_path.write_text(json.dumps(payload), encoding="utf-8")

            error = gate.verify_anchor_against_locked_baseline(summary_path)

        self.assertIsNotNone(error)
        self.assertEqual(error.reason, "anchor_reproduction_mismatch")
        self.assertEqual(
            error.details["mismatches"][0]["field"],
            "unlock_checks.primary_scenario_error_count",
        )

    def test_32b_probe_requires_anchor_summary_before_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            error = gate.verify_required_anchor_before_probe(Path(tmpdir))

        self.assertIsNotNone(error)
        self.assertEqual(error.reason, "anchor_summary_missing")

    def test_32b_probe_rejects_anchor_ollama_server_version_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _write_anchor_summary(output_dir, ollama_server_version="0.23.1")

            error = gate.verify_required_anchor_before_probe(
                output_dir,
                live_ollama_server_version="0.24.0",
            )

        self.assertIsNotNone(error)
        self.assertEqual(error.reason, "anchor_ollama_server_version_mismatch")
        self.assertEqual(error.details["anchor_ollama_server_version"], "0.23.1")
        self.assertEqual(error.details["live_ollama_server_version"], "0.24.0")

    def test_run_gate_decision_writes_expected_32b_summary_path(self) -> None:
        """Wiring test: collaborators are mocked to isolate path and model handoff."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            _write_anchor_summary(output_dir, ollama_server_version="0.23.1")
            original_verify_backend = gate.verify_primary_model_backend
            original_prompt_regression = gate.matrix.run_prompt_regression
            original_determinism = gate.matrix.run_determinism_check
            original_run_or_reuse = gate.run_or_reuse_gate_row
            original_working_tree_status = gate.working_tree_status
            determinism_calls = []

            def fake_verify_backend(primary_model_tag, *, runner_command, client=None):
                return gate.PrimaryModelBackend(
                    model_tag=primary_model_tag,
                    expected_digest=gate.PREREGISTERED_MODEL_DIGESTS[primary_model_tag],
                    resolved_digest=gate.PREREGISTERED_MODEL_DIGESTS[primary_model_tag],
                    ollama_server_version="0.23.1",
                )

            def fake_prompt_regression(**_kwargs):
                return None

            def fake_determinism(**kwargs):
                determinism_calls.append(kwargs)

            def fake_run_or_reuse(row, **_kwargs):
                return _oracle_row_result(row)

            try:
                gate.verify_primary_model_backend = fake_verify_backend
                gate.matrix.run_prompt_regression = fake_prompt_regression
                gate.matrix.run_determinism_check = fake_determinism
                gate.run_or_reuse_gate_row = fake_run_or_reuse
                gate.working_tree_status = lambda: "clean"
                summary_path = gate.run_gate_decision(
                    output_dir=output_dir,
                    model_command="python3 scripts/ollama_component_extractor.py",
                    decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
                    per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
                    primary_model_tag=gate.matrix.QWEN_32B_Q4KM.model_id,
                    schema_profile="default",
                    include_frozen_sentinel=True,
                    runner_command="python3 scripts/run_component_gate_decision.py",
                )
            finally:
                gate.verify_primary_model_backend = original_verify_backend
                gate.matrix.run_prompt_regression = original_prompt_regression
                gate.matrix.run_determinism_check = original_determinism
                gate.run_or_reuse_gate_row = original_run_or_reuse
                gate.working_tree_status = original_working_tree_status

            self.assertEqual(
                summary_path.name,
                "component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_summary.json",
            )
            self.assertTrue(summary_path.exists())
            self.assertEqual(determinism_calls[0]["model"], gate.matrix.QWEN_32B_Q4KM)


def _oracle_row_result(row):
    scenarios = generate_scenarios(row.family, row.scenarios, row.template_mix)
    predictions = oracle_predictions_by_scenario(scenarios)
    evaluation = evaluate_component_predictions(scenarios, predictions)
    artifact = {
        "mode": "component_gate_decision_row",
        "family": row.family,
        "template_mix": row.template_mix,
        "requested_scenario_count": row.scenarios,
        "scenario_count": len(scenarios),
        "scenario_error_count": 0,
        "scenario_errors": {},
        "quality_gate_thresholds": gate.QUALITY_GATES,
        "metrics": evaluation["metrics"],
        "quality_gates": evaluation["quality_gates"],
        "failure_examples": evaluation["failure_examples"],
        "failure_example_count": evaluation["failure_example_count"],
        "failure_example_limits": evaluation["failure_example_limits"],
        "failure_example_overflow": evaluation["failure_example_overflow"],
    }
    paths = gate.GateArtifactPaths(
        predictions=Path("/tmp/predictions.json"),
        component_eval=Path("/tmp/component_eval.json"),
    )
    return gate.GateRowResult(
        row=row,
        paths=paths,
        component_artifact=artifact,
        predictions_by_scenario=predictions,
        scenario_errors={},
        reused=False,
    )


def _write_anchor_summary(output_dir: Path, *, ollama_server_version: str = "0.23.1") -> Path:
    path = gate.default_anchor_summary_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ollama_server_version": ollama_server_version,
                "unlock_checks": gate.LOCKED_BASELINE_UNLOCK_CHECKS,
            }
        ),
        encoding="utf-8",
    )
    return path


class _FakeOllamaClient:
    def __init__(self, *, version: str, digest: str) -> None:
        self.version = version
        self.digest = digest

    def get_version(self) -> str:
        return self.version

    def get_model_digest(self, _model_id: str) -> str:
        return self.digest


def _fake_model_command(script_path: Path) -> str:
    return "{} {}".format(shlex.quote(sys.executable), shlex.quote(str(script_path)))


def _write_empty_prediction_model_script(tmpdir: Path) -> Path:
    script_path = tmpdir / "empty_prediction_model.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "json.load(sys.stdin)",
                'json.dump({"predictions": []}, sys.stdout)',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return script_path


if __name__ == "__main__":
    unittest.main()
