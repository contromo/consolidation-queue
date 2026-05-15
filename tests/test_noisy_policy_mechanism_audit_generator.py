import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "generate_noisy_policy_mechanism_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_noisy_policy_mechanism_audit", SCRIPT_PATH
)
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)


class NoisyPolicyMechanismAuditGeneratorTests(unittest.TestCase):
    def test_missing_required_artifacts_reports_producer_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(generator, "REPO_ROOT", Path(tmpdir)):
                missing = generator.missing_required_artifacts()

        missing_paths = {str(path) for path, _ in missing}
        hints = "\n".join(hint for _, hint in missing)

        self.assertIn("data/results/noisy_policy_comparison_summary.json", missing_paths)
        self.assertIn("scripts/run_noisy_policy_comparison.py", hints)
        self.assertIn("cq.eval.runner --family forced_contradiction", hints)
        self.assertIn("scripts/run_component_gate_decision.py", hints)

    def test_build_family_row_computes_deltas_and_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._write_overall_csv(
                root / "data/results/noisy_policy_comparison_forced_contradiction_default_metrics.csv",
                "false_assertion_rate",
                {
                    "consolidation_queue_lite": "0.0",
                    "reflection_eager_write_lite": "0.5",
                },
            )
            self._write_overall_csv(
                root / "data/results/forced_contradiction_oracle_heldout_metrics.csv",
                "false_assertion_after_contradiction",
                {
                    "consolidation_queue_lite": "0.0",
                    "reflection_eager_write_lite": "1.0",
                },
            )
            self._write_json(
                root / "component_eval.json",
                {
                    "failure_example_count": 0,
                    "failure_examples": [],
                    "metrics": {
                        "candidate_detection_f1": 1.0,
                        "contradiction_f1": 1.0,
                    },
                    "scenario_error_count": 0,
                },
            )
            self._write_json(
                root / "run.json",
                {
                    "policies": [
                        {
                            "policy_name": "consolidation_queue_lite",
                            "scenarios": [
                                {
                                    "extracted_candidate_stream": [
                                        {"canonical_id": "slot-a"}
                                    ],
                                    "question_traces": [
                                        {"relevant_canonical_id": "slot-a"},
                                        {
                                            "answer_text": "No usable memory available.",
                                            "relevant_canonical_id": "slot-b",
                                        },
                                    ],
                                    "scenario_id": "s1",
                                }
                            ],
                        }
                    ]
                },
            )
            summary = {
                "schema_profiles": {
                    "default": {
                        "primary_metric_comparisons": {
                            "forced_contradiction": self._comparison_rows()
                        }
                    }
                }
            }

            with patch.object(generator, "REPO_ROOT", root), patch.dict(
                generator.ORACLE_METRICS_PATH_BY_FAMILY,
                {
                    "forced_contradiction": Path(
                        "data/results/forced_contradiction_oracle_heldout_metrics.csv"
                    )
                },
            ), patch.dict(
                generator.COMPONENT_EVAL_PATH_BY_FAMILY,
                {"forced_contradiction": Path("component_eval.json")},
            ), patch.dict(
                generator.NOISY_RUN_PATH_BY_FAMILY,
                {"forced_contradiction": Path("run.json")},
            ):
                row = generator.build_family_row("forced_contradiction", summary)

        self.assertEqual(row["oracle"]["improvement_delta"], 1.0)
        self.assertEqual(row["noisy_overall"]["improvement_delta"], 0.5)
        self.assertEqual(row["noisy_overall"]["cq_oracle_minus_noisy_gap"], 0.0)
        self.assertEqual(row["canonical_alignment"]["exact_matches"], 1)
        self.assertEqual(row["canonical_alignment"]["question_traces_with_relevant_id"], 2)
        self.assertEqual(row["component_32b_default"]["metrics"]["contradiction_f1"], 1.0)

    def _comparison_rows(self):
        row = {
            "comparator_policy_name": "reflection_eager_write_lite",
            "improvement_delta": 0.5,
            "loss": False,
            "metric_name": "false_assertion_rate",
            "one_sided_95_lcb": 0.0,
            "one_sided_95_ucb": 0.5,
            "reference_policy_name": "consolidation_queue_lite",
            "scenario_count": 2,
            "win": False,
        }
        rows = {
            "reflection_eager_write_lite": row,
            "mem0_lite": {**row, "comparator_policy_name": "mem0_lite"},
        }
        for name in [
            "cq_no_contestation_demotion",
            "cq_no_wider_scope_pending_override",
            "cq_no_pending_lookup_use",
            "cq_no_source_independence_gate",
        ]:
            rows[name] = {**row, "comparator_policy_name": name}
        return rows

    def _write_overall_csv(self, path: Path, metric_name: str, values) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["policy_name", "summary_scope", metric_name],
            )
            writer.writeheader()
            for policy_name, value in values.items():
                writer.writerow(
                    {
                        "policy_name": policy_name,
                        "summary_scope": "overall",
                        metric_name: value,
                    }
                )

    def _write_json(self, path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
