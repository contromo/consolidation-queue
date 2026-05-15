import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_canonical_id_resolution_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_canonical_id_resolution_audit", SCRIPT_PATH
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class CanonicalIdResolutionAuditTests(unittest.TestCase):
    def test_prereg_lock_and_alias_source_are_byte_identical(self) -> None:
        prereg_text = audit.PREREGISTRATION_PATH.read_text(encoding="utf-8")

        self.assertEqual(
            audit.validate_preregistration_lock(),
            audit.declared_lock(prereg_text),
        )
        self.assertEqual(
            audit.extract_between(
                prereg_text,
                audit.ALIAS_SOURCE_START,
                audit.ALIAS_SOURCE_END,
            ),
            audit.ALIAS_FUNCTION_SOURCE,
        )
        self.assertEqual(
            audit.declared_alias_source_sha(prereg_text),
            audit.alias_source_sha256(),
        )

    def test_locked_alias_function_rejects_known_mismatch(self) -> None:
        self.assertFalse(
            audit.alias_match(
                "project-atlas-pre-merge-check-command",
                "useful-pending-project-command",
            )
        )
        self.assertTrue(
            audit.alias_match(
                "useful-pending-atlas-merge-check-command",
                "useful-pending-project-command",
            )
        )
        self.assertTrue(audit.alias_match("project-foo-bar", "foo-bar"))

    def test_family_metrics_cover_exact_scope_alias_and_cross_tab(self) -> None:
        run_data = {
            "family": "useful_pending_memory",
            "policies": [
                self._policy(
                    audit.CQ_POLICY,
                    [
                        self._scenario("s1", "slot-a", "slot-a", "project", "project-a"),
                        self._scenario(
                            "s2",
                            "slot-b",
                            "slot-b",
                            "workspace",
                            "project-a",
                            trace_scope_level="project",
                            failure=True,
                        ),
                        self._scenario(
                            "s3",
                            "useful-pending-atlas-merge-check-command",
                            "useful-pending-project-command",
                            "project",
                            "project-a",
                        ),
                        self._scenario(
                            "s4",
                            "alpha",
                            "omega-delta",
                            "project",
                            "project-a",
                            failure=True,
                        ),
                    ],
                )
            ],
        }

        metrics = audit.compute_family_metrics("useful_pending_memory", run_data)
        cq_tab = metrics["cross_tabs_by_policy"][audit.CQ_POLICY]

        self.assertEqual(metrics["question_traces_with_relevant_id"], 4)
        self.assertEqual(metrics["cqr_exact_matches"], 2)
        self.assertEqual(metrics["cqr_scope_matched_matches"], 1)
        self.assertEqual(metrics["cqr_alias_matches"], 3)
        self.assertAlmostEqual(metrics["cqr_set_membership"], 0.5)
        self.assertAlmostEqual(metrics["cqr_scope_matched"], 0.25)
        self.assertAlmostEqual(metrics["cqr_alias_set_membership"], 0.75)
        self.assertEqual(cq_tab["hit_success"], 2)
        self.assertEqual(cq_tab["hit_failure"], 1)
        self.assertEqual(cq_tab["miss_failure"], 1)
        self.assertAlmostEqual(cq_tab["lift"], 2 / 3)
        self.assertEqual(
            cq_tab["answer_success_definition"]["metric"],
            "answer_correctness",
        )

    def test_multi_candidate_set_membership_counts_one_question_hit(self) -> None:
        run_data = {
            "family": "preference_drift",
            "policies": [
                self._policy(
                    audit.CQ_POLICY,
                    [
                        self._scenario(
                            "s1",
                            ["other-slot", "target-slot"],
                            "target-slot",
                            "user",
                            "user-a",
                        )
                    ],
                )
            ],
        }

        metrics = audit.compute_family_metrics("preference_drift", run_data)

        self.assertEqual(metrics["question_traces_with_relevant_id"], 1)
        self.assertEqual(metrics["cqr_exact_matches"], 1)
        self.assertEqual(metrics["cqr_alias_matches"], 1)

    def test_primary_metric_failures_are_family_specific(self) -> None:
        scenario = self._scenario(
            "s1",
            "poison-alpha",
            "poison-alpha",
            "project",
            "project-a",
            failures=[
                {
                    "failure_type": "incorrect_answer",
                    "reason": "gold_candidate_not_resolved",
                },
                {
                    "failure_type": "premature_promotion",
                    "reason": "poison_candidate_promoted",
                },
            ],
        )
        policy = self._policy(audit.CQ_POLICY, [scenario])

        memory_failures = audit.policy_primary_metric_failures(
            policy,
            "memory_poisoning",
        )
        forced_failures = audit.policy_primary_metric_failures(
            policy,
            "forced_contradiction",
        )

        self.assertEqual(memory_failures, {"s1": {"s1-q"}})
        self.assertEqual(forced_failures, {})

    def test_cross_tab_aborts_on_policy_scenario_mismatch(self) -> None:
        cq_scenarios = {
            "cq-s1": self._scenario(
                "cq-s1",
                "slot-a",
                "slot-a",
                "project",
                "project-a",
            )
        }
        policy = self._policy(
            audit.CQ_POLICY,
            [
                self._scenario(
                    "other-s1",
                    "slot-a",
                    "slot-a",
                    "project",
                    "project-a",
                )
            ],
        )

        with self.assertRaises(audit.AuditAbort) as cm:
            audit.policy_cross_tab("useful_pending_memory", policy, cq_scenarios)

        self.assertEqual(cm.exception.reason, "policy_scenario_stream_mismatch")

    def test_prediction_outcome_operators_and_bucket_b_path(self) -> None:
        self.assertTrue(
            audit.prediction_passes(
                0.20,
                audit.ALIAS_CQR_PREDICTIONS["useful_pending_memory"],
            )
        )
        self.assertTrue(
            audit.prediction_passes(
                0.35,
                audit.ALIAS_CQR_PREDICTIONS["scope_contamination"],
            )
        )
        self.assertTrue(
            audit.prediction_passes(
                0.40,
                audit.ALIAS_CQR_PREDICTIONS["preference_drift"],
            )
        )

        families = {
            "useful_pending_memory": {
                "predictions": {
                    "alias_prediction_pass": True,
                    "false_positive_cap_pass": True,
                    "cq_cross_tab_pass": True,
                }
            },
            "memory_poisoning": {
                "predictions": {
                    "alias_prediction_pass": False,
                    "false_positive_cap_pass": True,
                    "cq_cross_tab_pass": True,
                }
            },
        }

        self.assertEqual(audit.classify_bucket(families)["bucket"], "B")

    def test_prediction_dict_matches_preregistration_table_rows(self) -> None:
        block = audit.extract_between(
            audit.PREREGISTRATION_PATH.read_text(encoding="utf-8"),
            audit.PREDICTIONS_BLOCK_START,
            audit.PREDICTIONS_BLOCK_END,
        )

        self.assertIn("| `useful_pending_memory` | `>= 0.40` | +/- 0.20 | `<= 0.05` |", block)
        self.assertIn("| `preference_drift` | `0.25-0.60` | inside band | `<= 0.10` |", block)

    def test_alias_false_positive_rate_uses_same_scenario_questions(self) -> None:
        scenarios = {
            "s1": {
                "scenario_id": "s1",
                "extracted_candidate_stream": [
                    {"canonical_id": "alpha-beta", "scope_level": "project", "scope_key": "p1"}
                ],
                "question_traces": [
                    {
                        "question_id": "q1",
                        "relevant_canonical_id": "alpha-beta",
                        "scope_level": "project",
                        "scope_key": "p1",
                    },
                    {
                        "question_id": "q2",
                        "relevant_canonical_id": "gamma-delta",
                        "scope_level": "project",
                        "scope_key": "p1",
                    },
                ],
            }
        }

        result = audit.alias_false_positive_summary(scenarios)

        self.assertEqual(result["alias_matched_pairs"], 2)
        self.assertEqual(result["false_positive_pairs"], 1)
        self.assertAlmostEqual(result["alias_false_positive_rate"], 0.5)

    def test_manifest_sha_mismatch_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact = root / "artifact.json"
            artifact.write_text("{}", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "path": str(artifact),
                                "sha256": "0" * 64,
                                "bytes": artifact.stat().st_size,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(audit.AuditAbort) as cm:
                audit.verify_manifested_artifacts(manifest)

        self.assertEqual(cm.exception.reason, "manifest_sha_mismatch")

    def test_check_lock_only_main_exits_zero(self) -> None:
        code = audit.main(
            [
                "--primary-model-tag",
                audit.PRIMARY_MODEL_TAG,
                "--schema-profile",
                audit.SCHEMA_PROFILE,
                "--include-frozen-sentinel",
                "--check-lock-only",
            ]
        )

        self.assertEqual(code, 0)

    def _policy(self, name, scenarios):
        return {"policy_name": name, "scenarios": scenarios}

    def _scenario(
        self,
        scenario_id,
        candidate_id,
        relevant_id,
        candidate_scope_level,
        candidate_scope_key,
        *,
        trace_scope_level=None,
        trace_scope_key=None,
        failure=False,
        failures=None,
    ):
        question_id = f"{scenario_id}-q"
        candidate_ids = candidate_id if isinstance(candidate_id, list) else [candidate_id]
        return {
            "scenario_id": scenario_id,
            "extracted_candidate_stream": [
                {
                    "canonical_id": item,
                    "scope_level": candidate_scope_level,
                    "scope_key": candidate_scope_key,
                }
                for item in candidate_ids
            ],
            "question_traces": [
                {
                    "question_id": question_id,
                    "relevant_canonical_id": relevant_id,
                    "scope_level": trace_scope_level or candidate_scope_level,
                    "scope_key": trace_scope_key or candidate_scope_key,
                }
            ],
            "failure_examples": (
                [
                    {
                        **failure_payload,
                        "question_id": question_id,
                    }
                    for failure_payload in failures
                ]
                if failures is not None
                else [
                    {
                        "failure_type": "incorrect_answer",
                        "reason": "gold_candidate_not_resolved",
                        "question_id": question_id,
                    }
                ]
                if failure
                else []
            ),
        }


if __name__ == "__main__":
    unittest.main()
