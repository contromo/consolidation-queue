import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from cq.eval.component_eval import evaluate_component_predictions, oracle_predictions_by_scenario
from cq.eval.runner import generate_scenarios


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

        paths = gate.gate_artifact_paths(rows[0], Path("/tmp/cq-results"))

        self.assertEqual(
            paths.predictions.name,
            "component_gate_decision_forced_contradiction_local_extractor_qwen2_5_7b_q4km_general_v1_heldout_n60_primary_floor_predictions.json",
        )
        self.assertIn("_n60_primary_floor_component_eval.json", paths.component_eval.name)

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
        self.assertEqual(len(plan["rows"]), 13)
        self.assertIn(
            'generate_scenarios(family, 60, "heldout")',
            plan["generation_contract"]["primary_rows"],
        )
        self.assertIn("template-rotation variants", plan["generation_contract"]["dependence_warning"])
        self.assertIn("run_prompt_regression", plan["phase_a_contract"]["source"])
        self.assertIn("run_determinism_check", plan["determinism_contract"]["source"])
        self.assertIn("_n60_primary_floor_predictions.json", plan["rows"][0]["paths"]["predictions"])

    def test_oracle_summary_unlocks_and_marks_b_cubed_observed_only(self) -> None:
        results = [_oracle_row_result(row) for row in gate.primary_gate_rows()]

        summary = gate.gate_summary_payload(
            primary_results=results,
            headroom_results=[],
            frozen_sentinel_results=[],
            general_prompt_path=gate.matrix.GENERAL_PROMPT_PATH,
            general_prompt_label=gate.matrix.DEFAULT_GENERAL_PROMPT_LABEL,
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertTrue(summary["policy_comparison_unlocked"])
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
            decoding_json=gate.matrix.DEFAULT_DECODING_JSON,
            per_scenario_timeout_seconds=gate.matrix.DEFAULT_TIMEOUT_SECONDS,
            phase_a_passed=True,
            determinism_passed=True,
        )

        self.assertFalse(summary["policy_comparison_unlocked"])
        blocker_types = {blocker["type"] for blocker in summary["blockers"]}
        self.assertIn("primary_scenario_errors", blocker_types)
        self.assertIn("per_family_observed_gate_failed", blocker_types)


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


if __name__ == "__main__":
    unittest.main()
