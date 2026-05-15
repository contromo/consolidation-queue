import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_noisy_runner_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_noisy_policy_comparison.py"
    spec = importlib.util.spec_from_file_location("run_noisy_policy_comparison", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


noisy = _load_noisy_runner_module()


def _comparison_row(
    *,
    win: bool = False,
    improvement_delta: float = 0.0,
    lcb: float = 0.0,
    ucb: float = 0.0,
):
    return {
        "win": win,
        "loss": improvement_delta <= -0.10 and ucb < 0.0,
        "improvement_delta": improvement_delta,
        "one_sided_95_lcb": lcb,
        "one_sided_95_ucb": ucb,
    }


def _policy_payload(policy_name: str, *, cq: bool = False):
    scenarios = []
    for index in range(3):
        metrics = {}
        for metric_name in noisy.DESCRIPTIVE_METRICS:
            if metric_name in noisy.HIGHER_IS_BETTER:
                metrics[metric_name] = 1.0 if cq else 0.8
            else:
                metrics[metric_name] = 0.0 if cq else 0.2
        scenarios.append({"scenario_id": "scenario-{}".format(index), "metrics": metrics})
    return {"policy_name": policy_name, "scenarios": scenarios}


class NoisyPolicyComparisonRunnerTests(unittest.TestCase):
    def test_bucket_decision_accepts_synthetic_bucket_a(self) -> None:
        primary = {
            family: {
                noisy.REFLECTION_POLICY: _comparison_row(
                    win=family
                    in {
                        noisy.FORCED_CONTRADICTION,
                        noisy.SCOPE_CONTAMINATION,
                        noisy.PREFERENCE_DRIFT,
                        noisy.USEFUL_PENDING_MEMORY,
                    },
                    improvement_delta=0.12,
                    lcb=0.01,
                    ucb=0.20,
                )
            }
            for family in noisy.COMPONENT_FAMILIES
        }
        frozen = {
            metric: {
                noisy.MEM0_POLICY: _comparison_row(
                    improvement_delta=0.05 if metric == "false_assertion_rate" else 0.00,
                    lcb=0.01 if metric == "false_assertion_rate" else 0.00,
                    ucb=0.10,
                )
            }
            for metric in noisy.FROZEN_PRIMARY_METRICS
        }
        replicate = {
            family: {
                noisy.REFLECTION_POLICY: _comparison_row(
                    win=False,
                    improvement_delta=0.00,
                    lcb=-0.01,
                    ucb=0.01,
                )
            }
            for family in noisy.COMPONENT_FAMILIES
        }

        decision = noisy._bucket_decision(
            {
                "default": {
                    "primary_metric_comparisons": primary,
                    "frozen_primary_comparisons": frozen,
                },
                "scenario_conditioned": {
                    "primary_metric_comparisons": replicate,
                    "frozen_primary_comparisons": frozen,
                },
            }
        )

        self.assertEqual(decision["bucket"], "A")
        self.assertEqual(len(decision["primary_reflection_wins"]), 4)

    def test_bucket_decision_records_directional_loss_asymmetry(self) -> None:
        loss_families = {
            noisy.FORCED_CONTRADICTION,
            noisy.SCOPE_CONTAMINATION,
            noisy.PREFERENCE_DRIFT,
        }
        primary = {
            family: {
                noisy.REFLECTION_POLICY: _comparison_row(
                    improvement_delta=-0.01 if family in loss_families else 0.0,
                    lcb=-0.02,
                    ucb=0.01,
                )
            }
            for family in noisy.COMPONENT_FAMILIES
        }

        decision = noisy._bucket_decision(
            {
                "default": {
                    "primary_metric_comparisons": primary,
                    "frozen_primary_comparisons": {},
                }
            }
        )

        self.assertEqual(decision["bucket"], "C")
        self.assertIn("directional", decision["directional_loss_note"])
        self.assertEqual(set(decision["reflection_directional_losses"]), loss_families)

    def test_profile_comparisons_emit_descriptive_grid_with_bounds(self) -> None:
        artifact = {
            "family": noisy.FORCED_CONTRADICTION,
            "policies": [
                _policy_payload(noisy.CQ_POLICY, cq=True),
                *[_policy_payload(comparator) for comparator in noisy.COMPARATORS],
            ],
        }

        comparisons = noisy._profile_comparisons({noisy.FORCED_CONTRADICTION: artifact})
        descriptive = comparisons["descriptive_metric_comparisons"][noisy.FORCED_CONTRADICTION]

        self.assertEqual(set(descriptive), set(noisy.DESCRIPTIVE_METRICS))
        row = descriptive["leakage_rate"][noisy.REFLECTION_POLICY]
        self.assertEqual(row["metric_name"], "leakage_rate")
        self.assertEqual(row["scenario_count"], 3)
        self.assertIn("one_sided_95_lcb", row)
        self.assertIn("one_sided_95_ucb", row)
        self.assertTrue(row["win"])

    def test_adapter_drop_rate_ceiling_stops_policy_scoring(self) -> None:
        run_artifact = {
            "candidate_stream_audit": [
                {
                    "scenario_id": "s1",
                    "input_prediction_count": 10,
                    "candidate_count": 9,
                    "adapter_drop_count": 1,
                    "adapter_drop_rate": 0.1,
                    "drops": [{"reason": "invalid_confidence"}],
                }
            ]
        }

        with self.assertRaises(noisy.StopConditionError) as context:
            noisy.assert_adapter_drop_rate_within_limit(
                run_artifact,
                family=noisy.FORCED_CONTRADICTION,
                max_drop_rate=0.05,
            )

        self.assertEqual(context.exception.reason, "adapter_drop_rate_exceeded")
        self.assertEqual(context.exception.details["adapter_drop_count"], 1)

    def test_dirty_pre_run_status_uses_hardened_git_helper(self) -> None:
        original = noisy.working_tree_status_short
        noisy.working_tree_status_short = lambda: " M changed.py\n"
        try:
            with self.assertRaises(noisy.StopConditionError) as context:
                noisy.run_noisy_policy_comparison(
                    output_dir=Path("/tmp/cq-results"),
                    run_dir=Path("/tmp/cq-runs"),
                    predictions_dir=Path("/tmp/cq-predictions"),
                    primary_model_tag=noisy.LOCKED_MODEL_TAG,
                    schema_profile="default",
                    include_frozen_sentinel=True,
                    policy_set="phase2_5",
                    runner_command="python3 scripts/run_noisy_policy_comparison.py",
                )
        finally:
            noisy.working_tree_status_short = original

        self.assertEqual(context.exception.reason, "dirty_pre_run_working_tree")
        self.assertEqual(context.exception.details["working_tree_status"], " M changed.py\n")

    def test_component_gate_recheck_stops_on_quality_regression(self) -> None:
        originals = (
            noisy.load_extracted_predictions,
            noisy.generate_scenarios,
            noisy.evaluate_component_predictions,
        )
        noisy.load_extracted_predictions = lambda _path: ({}, {})
        noisy.generate_scenarios = lambda _family, _count, _mix: []
        noisy.evaluate_component_predictions = lambda _scenarios, _predictions, scenario_errors: {
            "quality_gates": {
                "candidate_detection_f1": {
                    "passed": False,
                    "value": 0.5,
                    "threshold": 0.75,
                }
            }
        }
        try:
            with self.assertRaises(noisy.StopConditionError) as context:
                noisy._assert_component_gate_still_passes(
                    family=noisy.FORCED_CONTRADICTION,
                    scenario_count=60,
                    template_mix="heldout",
                    predictions_path=Path("/tmp/predictions.json"),
                )
        finally:
            (
                noisy.load_extracted_predictions,
                noisy.generate_scenarios,
                noisy.evaluate_component_predictions,
            ) = originals

        self.assertEqual(context.exception.reason, "component_quality_drift_gate_failure")
        self.assertEqual(
            context.exception.details["failures"][0]["metric"],
            "candidate_detection_f1",
        )

    def test_write_run_manifest_records_expected_shape(self) -> None:
        originals = (noisy.git_commit, noisy.working_tree_status)
        noisy.git_commit = lambda: "abc123"
        noisy.working_tree_status = lambda: "dirty"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                output_json = tmp / "run.json"
                output_csv = tmp / "metrics.csv"
                output_json.write_text('{"ok": true}\n', encoding="utf-8")
                output_csv.write_text("policy,metric\n", encoding="utf-8")
                backend = type(
                    "Backend",
                    (),
                    {
                        "model_tag": noisy.LOCKED_MODEL_TAG,
                        "expected_digest": noisy.LOCKED_MODEL_DIGEST,
                        "resolved_digest": noisy.LOCKED_MODEL_DIGEST,
                        "ollama_server_version": "0.1.0",
                    },
                )()

                manifest_path = noisy.write_run_manifest(
                    run_artifact={
                        "predictions_path": "predictions.json",
                        "predictions_sha256": "1" * 64,
                        "candidate_stream_audit": [
                            {
                                "scenario_id": "s1",
                                "candidate_stream_sha256": "2" * 64,
                                "input_prediction_count": 2,
                                "candidate_count": 1,
                                "adapter_drop_count": 1,
                                "adapter_drop_rate": 0.5,
                            }
                        ],
                    },
                    output_json=output_json,
                    output_csv=output_csv,
                    runner_command="python3 scripts/run_noisy_policy_comparison.py",
                    schema_profile="default",
                    model_backend=backend,
                    preregistration_lock_sha="3" * 64,
                    adapter_sha="4" * 64,
                )
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        finally:
            noisy.git_commit, noisy.working_tree_status = originals

        self.assertEqual(manifest["manifest_version"], 1)
        self.assertEqual(manifest["git_commit"], "abc123")
        self.assertEqual(manifest["working_tree_status"], "dirty")
        self.assertEqual(manifest["candidate_stream_sha256"][0]["adapter_drop_count"], 1)

    def test_completed_cell_run_rows_include_each_finished_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            run_dir = tmp / "runs"
            output_dir = tmp / "results"
            run_dir.mkdir()
            output_dir.mkdir()
            for profile in ("default", "scenario_conditioned"):
                stem = "noisy_policy_comparison_forced_contradiction_{}".format(profile)
                (run_dir / "{}.json".format(stem)).write_text("{}\n", encoding="utf-8")
                (run_dir / "{}_manifest.json".format(stem)).write_text("{}\n", encoding="utf-8")
                (output_dir / "{}_metrics.csv".format(stem)).write_text(
                    "policy_name,summary_scope\n",
                    encoding="utf-8",
                )

            rows = noisy.completed_cell_run_rows(
                run_dir=run_dir,
                output_dir=output_dir,
                schema_profiles=("default", "scenario_conditioned"),
                include_frozen_sentinel=True,
            )

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["schema_profile"] for row in rows},
            {"default", "scenario_conditioned"},
        )
        self.assertTrue(all(row["family"] == noisy.FORCED_CONTRADICTION for row in rows))


if __name__ == "__main__":
    unittest.main()
