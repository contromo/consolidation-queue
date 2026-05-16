import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_classify_bucket_c_when_false_positive_cap_fails(self) -> None:
        families = {
            "useful_pending_memory": {
                "predictions": {
                    "alias_prediction_pass": True,
                    "false_positive_cap_pass": False,
                    "cq_cross_tab_pass": True,
                }
            },
            "memory_poisoning": {
                "predictions": {
                    "alias_prediction_pass": True,
                    "false_positive_cap_pass": True,
                    "cq_cross_tab_pass": True,
                }
            },
        }

        self.assertEqual(audit.classify_bucket(families)["bucket"], "C")

    def test_mechanism_diverse_union_counts_premature_promotion(self) -> None:
        scenario = {
            "scenario_id": "frozen_x",
            "question_traces": [
                {
                    "question_id": "q1",
                    "relevant_canonical_id": "slot-a",
                    "scope_level": "project",
                    "scope_key": "p1",
                }
            ],
            "failure_examples": [
                {
                    "failure_type": "premature_promotion",
                    "reason": "false_corroboration_stack_promoted",
                    "question_id": "q1",
                }
            ],
        }
        policy = {"policy_name": audit.CQ_POLICY, "scenarios": [scenario]}

        failures = audit.policy_primary_metric_failures(
            policy,
            "mechanism_diverse_heldout",
        )

        self.assertEqual(failures, {"frozen_x": {"q1"}})

    def test_mechanism_diverse_union_ignores_unmapped_failure_type(self) -> None:
        scenario = {
            "scenario_id": "frozen_x",
            "question_traces": [
                {
                    "question_id": "q1",
                    "relevant_canonical_id": "slot-a",
                    "scope_level": "project",
                    "scope_key": "p1",
                }
            ],
            "failure_examples": [
                {
                    "failure_type": "clean_durable_displacement",
                    "reason": "clean_durable_demoted_by_poison",
                    "question_id": "q1",
                }
            ],
        }
        policy = {"policy_name": audit.CQ_POLICY, "scenarios": [scenario]}

        failures = audit.policy_primary_metric_failures(
            policy,
            "mechanism_diverse_heldout",
        )

        self.assertEqual(failures, {})

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

    def test_strict_mode_aborts_on_raw_manifest_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifact = root / "noisy_policy_comparison_forced_contradiction_default.json"
            artifact.write_text(json.dumps({"key": "value"}), encoding="utf-8")
            manifest = root / "noisy_policy_comparison_forced_contradiction_default_manifest.json"
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

            context = audit.AuditContext(
                replay_root=Path("/"),
                output_root=Path("/"),
                equivalence_mode=audit.EQUIVALENCE_MODE_STRICT,
            )
            with self.assertRaises(audit.AuditAbort) as cm:
                audit.verify_manifested_artifacts(manifest, context=context)

        self.assertEqual(cm.exception.reason, "manifest_sha_mismatch")

    def test_path_normalized_accepts_only_predictions_path_drift(self) -> None:
        expected_payload = {
            "experiment": "noisy_policy_comparison_forced_contradiction_default",
            "predictions_path": "data/results/locked_predictions.json",
            "candidate_adapter_sha256": "abc",
        }
        observed_payload = {
            "experiment": "noisy_policy_comparison_forced_contradiction_default",
            "predictions_path": "/tmp/replay-root/data/results/locked_predictions.json",
            "candidate_adapter_sha256": "abc",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            replay_root = Path(tmpdir) / "replay"
            output_root = Path(tmpdir) / "output"
            replay_root.mkdir()
            output_root.mkdir()
            observed_path = replay_root / "observed_run.json"
            observed_path.write_text(json.dumps(observed_payload), encoding="utf-8")
            manifest_path = replay_root / "fake_manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            context = audit.AuditContext(
                replay_root=replay_root,
                output_root=output_root,
                equivalence_mode=audit.EQUIVALENCE_MODE_PATH_NORMALIZED,
            )

            observed_sha = audit.compare_run_json_path_normalized(
                observed_path=observed_path,
                expected_payload=expected_payload,
                expected_sha="ignored-byte-stable-sha",
                manifest_path=manifest_path,
                context=context,
            )

        self.assertTrue(observed_sha)

    def test_path_normalized_aborts_on_unapproved_path_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            replay_root = Path(tmpdir) / "replay-root"
            output_root = Path(tmpdir) / "output-root"
            replay_root.mkdir()
            output_root.mkdir()
            expected_payload = {
                "experiment": "noisy_policy_comparison_forced_contradiction_default",
                "predictions_path": "data/results/locked_predictions.json",
                "runner_command": "python3 scripts/run.py --input data/results/foo",
            }
            observed_payload = {
                "experiment": "noisy_policy_comparison_forced_contradiction_default",
                "predictions_path": f"{replay_root}/data/results/locked_predictions.json",
                # Drift in a non-approved field that contains a path-shaped
                # value referencing the replay root.
                "runner_command": (
                    f"python3 scripts/run.py --input {replay_root}/data/results/foo"
                ),
            }
            observed_path = replay_root / "observed_run.json"
            observed_path.write_text(json.dumps(observed_payload), encoding="utf-8")
            manifest_path = replay_root / "fake_manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            context = audit.AuditContext(
                replay_root=replay_root,
                output_root=output_root,
                equivalence_mode=audit.EQUIVALENCE_MODE_PATH_NORMALIZED,
            )

            with self.assertRaises(audit.AuditAbort) as cm:
                audit.compare_run_json_path_normalized(
                    observed_path=observed_path,
                    expected_payload=expected_payload,
                    expected_sha="ignored-byte-stable-sha",
                    manifest_path=manifest_path,
                    context=context,
                )

        self.assertEqual(cm.exception.reason, "run_json_unapproved_path_field_drift")
        leaks = cm.exception.details["leaks"]
        self.assertTrue(any("runner_command" in leak["json_pointer"] for leak in leaks))

    def test_path_normalized_no_expected_payload_still_blocks_path_leak(self) -> None:
        # Production fallback: no locked run JSON snapshot is available, so
        # only the observed payload is loaded. A path leak in a non-approved
        # field of the observed payload must still abort.
        with tempfile.TemporaryDirectory() as tmpdir:
            replay_root = Path(tmpdir) / "replay-root"
            output_root = Path(tmpdir) / "output-root"
            replay_root.mkdir()
            output_root.mkdir()
            observed_payload = {
                "experiment": "noisy_policy_comparison_forced_contradiction_default",
                "predictions_path": f"{replay_root}/predictions.json",
                "runner_command": f"python3 scripts/run.py --input {replay_root}/foo",
            }
            observed_path = replay_root / "observed_run.json"
            observed_path.write_text(json.dumps(observed_payload), encoding="utf-8")
            manifest_path = replay_root / "fake_manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")
            context = audit.AuditContext(
                replay_root=replay_root,
                output_root=output_root,
                equivalence_mode=audit.EQUIVALENCE_MODE_PATH_NORMALIZED,
            )
            with self.assertRaises(audit.AuditAbort) as cm:
                audit.compare_run_json_path_normalized(
                    observed_path=observed_path,
                    expected_payload=None,
                    expected_sha="ignored",
                    manifest_path=manifest_path,
                    context=context,
                )
        self.assertEqual(cm.exception.reason, "run_json_unapproved_path_field_drift")

    def test_path_normalized_aborts_on_metrics_csv_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            replay_root = Path(tmpdir) / "replay-root"
            output_root = Path(tmpdir) / "output-root"
            replay_root.mkdir()
            output_root.mkdir()
            metrics_path = replay_root / "noisy_policy_comparison_forced_contradiction_default_metrics.csv"
            metrics_path.write_text("family,value\nforced_contradiction,1.0\n", encoding="utf-8")
            manifest_path = replay_root / "noisy_policy_comparison_forced_contradiction_default_manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "path": str(metrics_path.relative_to(replay_root)),
                                "sha256": "0" * 64,
                                "bytes": metrics_path.stat().st_size,
                            }
                        ],
                        "candidate_stream_sha256": [],
                        "candidate_adapter_sha256": "x",
                        "primary_model_digest": "y",
                        "prompt_sha256": "z",
                        "schema_profile": "default",
                        "preregistration_lock_sha256": "w",
                        "predictions_sha256": "v",
                    }
                ),
                encoding="utf-8",
            )
            context = audit.AuditContext(
                replay_root=replay_root,
                output_root=output_root,
                equivalence_mode=audit.EQUIVALENCE_MODE_PATH_NORMALIZED,
            )

            with self.assertRaises(audit.AuditAbort) as cm:
                audit.verify_manifested_artifacts(
                    manifest_path,
                    context=context,
                    expected_manifest_path=None,
                )

        self.assertEqual(cm.exception.reason, "manifest_sha_mismatch")

    def test_path_normalized_aborts_on_stable_manifest_field_drift(self) -> None:
        for field, expected_value, observed_value in [
            (
                "candidate_stream_sha256",
                [{"scenario_id": "x", "candidate_stream_sha256": "expected"}],
                [{"scenario_id": "x", "candidate_stream_sha256": "observed"}],
            ),
            ("candidate_adapter_sha256", "expected-adapter", "observed-adapter"),
            ("primary_model_digest", "sha256:expected", "sha256:observed"),
            ("prompt_sha256", "expected-prompt", "observed-prompt"),
            ("schema_profile", "default", "scenario_conditioned"),
            ("preregistration_lock_sha256", "expected-lock", "observed-lock"),
            ("predictions_sha256", "expected-pred", "observed-pred"),
        ]:
            with self.subTest(field=field):
                self._assert_stable_manifest_field_drift(
                    field, expected_value, observed_value
                )

    def _assert_stable_manifest_field_drift(self, field, expected_value, observed_value):
        with tempfile.TemporaryDirectory() as tmpdir:
            replay_root = Path(tmpdir) / "replay-root"
            output_root = Path(tmpdir) / "output-root"
            replay_root.mkdir()
            output_root.mkdir()
            (replay_root / "data" / "runs").mkdir(parents=True)
            base_manifest = {
                "artifacts": [],
                "candidate_stream_sha256": [],
                "candidate_adapter_sha256": "default-adapter",
                "primary_model_digest": "sha256:default",
                "prompt_sha256": "default-prompt",
                "schema_profile": "default",
                "preregistration_lock_sha256": "default-lock",
                "predictions_sha256": "default-pred",
            }
            expected_manifest_payload = dict(base_manifest, **{field: expected_value})
            observed_manifest_payload = dict(base_manifest, **{field: observed_value})
            expected_path = output_root / "expected_manifest.json"
            expected_path.write_text(
                json.dumps(expected_manifest_payload), encoding="utf-8"
            )
            observed_path = replay_root / "data" / "runs" / "noisy_policy_comparison_forced_contradiction_default_manifest.json"
            observed_path.write_text(
                json.dumps(observed_manifest_payload), encoding="utf-8"
            )
            context = audit.AuditContext(
                replay_root=replay_root,
                output_root=output_root,
                equivalence_mode=audit.EQUIVALENCE_MODE_PATH_NORMALIZED,
            )
            with self.assertRaises(audit.AuditAbort) as cm:
                audit.verify_manifested_artifacts(
                    observed_path,
                    context=context,
                    expected_manifest_path=expected_path,
                )
            self.assertEqual(cm.exception.reason, "manifest_stable_field_drift")
            drifts = cm.exception.details["drifts"]
            self.assertEqual(len(drifts), 1)
            self.assertEqual(drifts[0]["field"], field)

    def test_path_normalized_aborts_on_candidate_stream_hash_drift(self) -> None:
        self._assert_stable_manifest_field_drift(
            "candidate_stream_sha256",
            [
                {
                    "scenario_id": "forced_contradiction_001",
                    "candidate_stream_sha256": "expected-hash",
                    "adapter_drop_count": 0,
                    "adapter_drop_rate": 0.0,
                }
            ],
            [
                {
                    "scenario_id": "forced_contradiction_001",
                    "candidate_stream_sha256": "observed-hash",
                    "adapter_drop_count": 0,
                    "adapter_drop_rate": 0.0,
                }
            ],
        )

    def test_path_normalized_aborts_on_adapter_sha_drift(self) -> None:
        self._assert_stable_manifest_field_drift(
            "candidate_adapter_sha256", "expected-adapter-sha", "observed-adapter-sha"
        )

    def test_path_normalized_aborts_on_adapter_drop_count_or_rate_drift(self) -> None:
        # Adapter drop count and rate live inside per-scenario
        # candidate_stream_sha256 entries; drift in either should be caught.
        self._assert_stable_manifest_field_drift(
            "candidate_stream_sha256",
            [
                {
                    "scenario_id": "forced_contradiction_001",
                    "candidate_stream_sha256": "shared-hash",
                    "adapter_drop_count": 0,
                    "adapter_drop_rate": 0.0,
                }
            ],
            [
                {
                    "scenario_id": "forced_contradiction_001",
                    "candidate_stream_sha256": "shared-hash",
                    "adapter_drop_count": 1,
                    "adapter_drop_rate": 0.5,
                }
            ],
        )

    def test_path_normalized_requires_explicit_replay_root(self) -> None:
        # With default replay root (equal to output root), path_normalized
        # mode must raise an explicit AuditAbort with an explicit reason and
        # exit non-zero from main().
        recorded: dict = {}

        def fake_write_stop_report(exc):
            recorded["reason"] = exc.reason
            recorded["details"] = exc.details

        with patch.object(audit, "write_stop_report", side_effect=fake_write_stop_report):
            code = audit.main(
                [
                    "--primary-model-tag",
                    audit.PRIMARY_MODEL_TAG,
                    "--schema-profile",
                    audit.SCHEMA_PROFILE,
                    "--include-frozen-sentinel",
                    "--equivalence-mode",
                    audit.EQUIVALENCE_MODE_PATH_NORMALIZED,
                ]
            )
        self.assertEqual(code, 1)
        self.assertEqual(recorded["reason"], "path_normalized_requires_explicit_replay_root")

    def test_replay_root_resolves_artifact_reads_but_writes_to_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            replay_root = Path(tmpdir) / "replay-root"
            output_root = Path(tmpdir) / "output-root"
            replay_root.mkdir()
            output_root.mkdir()
            context = audit.AuditContext(
                replay_root=replay_root,
                output_root=output_root,
                equivalence_mode=audit.EQUIVALENCE_MODE_PATH_NORMALIZED,
            )
            self.assertTrue(context.is_split_root)
            run_path = context.run_path("forced_contradiction")
            metrics_path = context.metrics_path("forced_contradiction")
            replay_manifest_path = context.replay_manifest_path("forced_contradiction")
            component_eval_path = context.component_eval_path("forced_contradiction")
            for path in (run_path, metrics_path, replay_manifest_path, component_eval_path):
                self.assertTrue(
                    str(path).startswith(str(replay_root)),
                    f"{path} must read from replay_root",
                )
            # Output paths (summary, CSV, manifest, results doc) write under
            # output_root, which equals REPO_ROOT for the runner. Confirm the
            # module-level constants point under REPO_ROOT.
            for output_const in (
                audit.SUMMARY_PATH,
                audit.CSV_PATH,
                audit.MANIFEST_PATH,
                audit.RESULTS_DOC_PATH,
            ):
                self.assertTrue(
                    str(output_const).startswith(str(audit.REPO_ROOT)),
                    f"{output_const} must write under REPO_ROOT",
                )

    def test_strict_sha_default_with_split_root_still_byte_exact(self) -> None:
        # In strict_sha mode, even with a split replay/output root, byte-exact
        # comparison must still fire on raw SHA mismatch.
        with tempfile.TemporaryDirectory() as tmpdir:
            replay_root = Path(tmpdir) / "replay-root"
            output_root = Path(tmpdir) / "output-root"
            replay_root.mkdir()
            output_root.mkdir()
            artifact = replay_root / "noisy_policy_comparison_forced_contradiction_default.json"
            artifact.write_text("{}", encoding="utf-8")
            manifest = replay_root / "noisy_policy_comparison_forced_contradiction_default_manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "path": str(artifact.relative_to(replay_root)),
                                "sha256": "0" * 64,
                                "bytes": artifact.stat().st_size,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            context = audit.AuditContext(
                replay_root=replay_root,
                output_root=output_root,
                equivalence_mode=audit.EQUIVALENCE_MODE_STRICT,
            )
            with self.assertRaises(audit.AuditAbort) as cm:
                audit.verify_manifested_artifacts(manifest, context=context)
        self.assertEqual(cm.exception.reason, "manifest_sha_mismatch")

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
