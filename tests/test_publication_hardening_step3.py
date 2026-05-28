import csv
import contextlib
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest import mock
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_publication_hardening_step3.py"

SPEC = importlib.util.spec_from_file_location("run_publication_hardening_step3", SCRIPT_PATH)
step3 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = step3
SPEC.loader.exec_module(step3)


def make_run_data(family: str, alias_hits: int, alias_misses: int) -> dict:
    scenarios = []
    index = 0
    for _ in range(alias_hits):
        index += 1
        scenarios.append(make_scenario(index, alias_hit=True))
    for _ in range(alias_misses):
        index += 1
        scenarios.append(make_scenario(index, alias_hit=False))
    return {
        "family": family,
        "policies": [
            {
                "policy_name": step3.CQ_POLICY,
                "scenarios": scenarios,
            }
        ],
    }


def make_scenario(index: int, *, alias_hit: bool) -> dict:
    scenario_id = f"scenario-{index}"
    question_id = f"question-{index}"
    relevant_id = f"slot-{index}"
    candidate_id = relevant_id if alias_hit else f"unrelated-{index}"
    return {
        "scenario_id": scenario_id,
        "question_traces": [
            {
                "question_id": question_id,
                "relevant_canonical_id": relevant_id,
                "answer_text": "answer",
            },
            {"question_id": f"ignored-{index}", "answer_text": "no relevant id"},
        ],
        "extracted_candidate_stream": [
            {
                "candidate_id": f"candidate-{index}",
                "canonical_id": candidate_id,
            }
        ],
        "failure_examples": [],
    }


def family_entry(hits: int, misses: int) -> dict:
    return {
        "cross_tab": {
            "alias_hit_total": hits,
            "alias_miss_total": misses,
            "hit_success": hits,
            "hit_failure": 0,
            "miss_success": misses,
            "miss_failure": 0,
            "answer_success_given_alias_hit": 1.0 if hits else 0.0,
            "answer_success_given_alias_miss": 1.0 if misses else 0.0,
            "lift": 0.0,
        },
        "min_n_passed": hits >= step3.MIN_ALIAS_HITS_PER_THESIS_FAMILY,
        "miss_partition_evaluable": misses > 0,
    }


class PublicationHardeningStep3ComputationTests(unittest.TestCase):
    def test_compute_family_step3_returns_expected_shape(self) -> None:
        result = step3.compute_family_step3(
            "useful_pending_memory",
            make_run_data("useful_pending_memory", alias_hits=6, alias_misses=2),
        )
        self.assertEqual(result["alias_hit_total"], 6)
        self.assertTrue(result["min_n_passed"])
        self.assertEqual(
            result["miss_partition_evaluable"],
            result["alias_miss_total"] > 0,
        )
        self.assertIn("alias_false_positive", result)

    def test_min_n_gate_fails_with_fewer_than_5_hits(self) -> None:
        result = step3.compute_family_step3(
            "useful_pending_memory",
            make_run_data("useful_pending_memory", alias_hits=4, alias_misses=2),
        )
        self.assertFalse(result["min_n_passed"])

    def test_classify_outcome_returns_bucket_a_when_both_thesis_families_pass_min_n_and_evaluable_miss(self) -> None:
        per_family = {
            "useful_pending_memory": family_entry(5, 1),
            "memory_poisoning": family_entry(6, 2),
        }
        self.assertEqual(step3.classify_outcome(per_family), "A_cross_tab_populated")

    def test_classify_outcome_returns_b_min_n_when_one_thesis_family_fails_min_n_with_nonzero_pool(self) -> None:
        per_family = {
            "useful_pending_memory": family_entry(3, 10),
            "memory_poisoning": family_entry(6, 2),
        }
        self.assertEqual(step3.classify_outcome(per_family), "B_inconclusive_min_n")

    def test_classify_outcome_returns_b_empty_partition_when_alias_totals_are_zero(self) -> None:
        per_family = {
            "useful_pending_memory": family_entry(0, 0),
            "memory_poisoning": family_entry(0, 0),
        }
        self.assertEqual(
            step3.classify_outcome(per_family),
            "B_inconclusive_empty_partition",
        )

    def test_classify_outcome_returns_b_unevaluable_miss_when_min_n_passes_but_miss_zero(self) -> None:
        per_family = {
            "useful_pending_memory": family_entry(5, 0),
            "memory_poisoning": family_entry(6, 1),
        }
        self.assertEqual(
            step3.classify_outcome(per_family),
            "B_inconclusive_unevaluable_miss",
        )


class PublicationHardeningStep3PreconditionTests(unittest.TestCase):
    def test_validate_preconditions_fails_on_lock_sha_mismatch_and_main_writes_bucket_c(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with mock.patch.object(step3, "capture_worktree_status", return_value=""), mock.patch.object(
                step3,
                "validate_publication_hardening_lock",
                return_value="0" * 64,
            ):
                rc = step3.main(
                    [
                        "--output-dir",
                        str(tmp),
                        "--manifest-path",
                        str(tmp / "manifest.json"),
                        "--results-doc",
                        str(tmp / "results.md"),
                        "--skip-doc",
                        str(tmp / "skip.md"),
                    ]
                )
            self.assertEqual(rc, 1)
            summary = json.loads((tmp / step3.SUMMARY_FILENAME).read_text(encoding="utf-8"))
            self.assertEqual(summary["bucket"], "C_preconditions_fail")
            self.assertEqual(
                summary["failure_details"]["precondition"],
                "publication_hardening_lock_sha256",
            )

    def test_validate_preconditions_fails_on_dirty_worktree(self) -> None:
        with mock.patch.object(step3, "capture_worktree_status", return_value=" M file"):
            with self.assertRaises(step3.Step3PreconditionFail) as raised:
                step3.validate_preconditions()
        self.assertEqual(raised.exception.reason, "C_preconditions_fail")
        self.assertEqual(raised.exception.details["precondition"], "clean_worktree")

    def test_validate_preconditions_fails_on_missing_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skip_doc = Path(tmpdir) / "skip.md"
            skip_doc.write_text("skip", encoding="utf-8")

            def fake_prediction_paths(*, predictions_dir: Path, family: str, schema_profile: str):
                if family == "forced_contradiction":
                    raise step3.NoisyPolicyComparisonError("missing forced")
                return SimpleNamespace()

            with self._patched_successful_preconditions(skip_doc), mock.patch.object(
                step3,
                "prediction_cell_paths",
                side_effect=fake_prediction_paths,
            ):
                with self.assertRaises(step3.Step3PreconditionFail) as raised:
                    step3.validate_preconditions(skip_doc_path=skip_doc)
        self.assertEqual(raised.exception.reason, "C_missing_predictions")
        self.assertEqual(
            raised.exception.details["missing_families"][0]["family"],
            "forced_contradiction",
        )

    def test_validate_preconditions_checks_all_seven_regeneration_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skip_doc = Path(tmpdir) / "skip.md"
            skip_doc.write_text("skip", encoding="utf-8")
            calls = []

            def fake_prediction_paths(*, predictions_dir: Path, family: str, schema_profile: str):
                calls.append(family)
                return SimpleNamespace()

            with self._patched_successful_preconditions(skip_doc), mock.patch.object(
                step3,
                "prediction_cell_paths",
                side_effect=fake_prediction_paths,
            ):
                step3.validate_preconditions(skip_doc_path=skip_doc)
        self.assertEqual(calls, list(step3.REGENERATION_FAMILIES))

    def _patched_successful_preconditions(self, skip_doc: Path):
        return mock.patch.multiple(
            step3,
            capture_worktree_status=mock.Mock(return_value=""),
            validate_publication_hardening_lock=mock.Mock(
                return_value=step3.EXPECTED_PUBLICATION_HARDENING_LOCK_SHA
            ),
            alias_source_sha256=mock.Mock(return_value=step3.EXPECTED_ALIAS_SOURCE_SHA),
            validate_preregistration_lock=mock.Mock(return_value="cqr-lock"),
            validate_noisy_preregistration_lock=mock.Mock(return_value="noisy-lock"),
            git_commit=mock.Mock(return_value="abc123"),
        )


class PublicationHardeningStep3RegenerationFailureTests(unittest.TestCase):
    def test_regeneration_subprocess_failure_emits_bucket_c(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stop_path = tmp / "noisy_policy_comparison_stop_20260525T000000000000Z.json"
            stop_path.write_text('{"reason": "backend_down"}\n', encoding="utf-8")
            stdout = f"Noisy policy comparison stopped: backend_down. Report: {stop_path}\n"
            rc, manifest = self._run_failed_regeneration(tmp, stdout=stdout)
        self.assertEqual(rc, 1)
        self.assertEqual(manifest["bucket"], "C_regeneration_fail")
        self.assertEqual(manifest["stop_report"], str(stop_path.resolve()))

    def test_regeneration_subprocess_failure_normalizes_relative_stop_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            rel_path = "data/results/noisy_policy_comparison_stop_20260525T000000000001Z.json"
            stdout = f"Noisy policy comparison stopped: backend_down. Report: {rel_path}\n"
            rc, manifest = self._run_failed_regeneration(tmp, stdout=stdout)
        self.assertEqual(rc, 1)
        self.assertEqual(
            manifest["stop_report"],
            str((step3.REPO_ROOT / rel_path).resolve()),
        )

    def test_regeneration_subprocess_failure_falls_back_to_glob_when_stdout_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stop_dir = tmp / "stops"
            stop_dir.mkdir()
            stop_path = stop_dir / "noisy_policy_comparison_stop_20260525T000000000002Z.json"

            def fake_run(*args, **kwargs):
                stop_path.write_text('{"reason": "gate_failed"}\n', encoding="utf-8")
                return subprocess.CompletedProcess(args=args[0], returncode=1, stdout="", stderr="err")

            rc, manifest = self._run_failed_regeneration(
                tmp,
                run_side_effect=fake_run,
                stop_dir=stop_dir,
            )
        self.assertEqual(rc, 1)
        self.assertEqual(manifest["stop_report"], str(stop_path.resolve()))

    def test_regeneration_subprocess_failure_when_no_stop_report_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            stop_dir = tmp / "stops"
            stop_dir.mkdir()
            rc, manifest = self._run_failed_regeneration(tmp, stdout="", stop_dir=stop_dir)
        self.assertEqual(rc, 1)
        self.assertIsNone(manifest["stop_report"])
        self.assertIn("stderr_tail", manifest["failure_details"])

    def test_regeneration_subprocess_failure_does_not_attempt_cross_tab(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            with mock.patch.object(step3, "compute_family_step3") as compute:
                self._run_failed_regeneration(tmp, stdout="")
            compute.assert_not_called()

    def _run_failed_regeneration(
        self,
        tmp: Path,
        *,
        stdout: str = "",
        run_side_effect=None,
        stop_dir: Optional[Path] = None,
    ) -> tuple[int, dict]:
        manifest_path = tmp / "manifest.json"
        stop_dir = stop_dir or tmp
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=1,
            stdout=stdout,
            stderr="stderr text",
        )
        run_mock = mock.Mock(return_value=completed) if run_side_effect is None else mock.Mock(side_effect=run_side_effect)
        preconditions = {
            "publication_hardening_lock_sha256": step3.EXPECTED_PUBLICATION_HARDENING_LOCK_SHA,
            "alias_function_sha256": step3.EXPECTED_ALIAS_SOURCE_SHA,
            "cqr_audit_preregistration_lock_sha256": "cqr-lock",
            "noisy_comparison_preregistration_lock_sha256": "noisy-lock",
            "skip_doc_path": "docs/skip.md",
            "skip_doc_sha256": "a" * 64,
            "git_commit": "abc123",
            "pre_run_worktree_status": "",
        }
        with mock.patch.object(step3, "validate_preconditions", return_value=preconditions), mock.patch.object(
            step3,
            "capture_worktree_status",
            return_value=" M generated",
        ), mock.patch.object(step3, "CANONICAL_OUTPUT_DIR", stop_dir), mock.patch.object(
            step3.subprocess,
            "run",
            run_mock,
        ):
            rc = step3.main(
                [
                    "--output-dir",
                    str(tmp),
                    "--manifest-path",
                    str(manifest_path),
                    "--results-doc",
                    str(tmp / "results.md"),
                    "--skip-doc",
                    str(tmp / "skip.md"),
                ]
            )
        return rc, json.loads(manifest_path.read_text(encoding="utf-8"))


class PublicationHardeningStep3OutputTests(unittest.TestCase):
    def test_no_regenerate_with_canonical_paths_is_rejected_by_argparser(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                step3.parse_args(["--no-regenerate-noisy-comparison"])

    def test_summary_json_shape_matches_prereg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "summary.json"
            step3.write_summary_json(
                {},
                "A_cross_tab_populated",
                {"pre_run_worktree_status": ""},
                {"regeneration_skipped": False},
                path,
                command="python3 scripts/run_publication_hardening_step3.py",
                limitation_text="none",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
        for key in (
            "bucket",
            "per_family",
            "preconditions",
            "min_n_threshold",
            "runner_command",
            "generated_at",
            "regeneration_metadata",
        ):
            self.assertIn(key, payload)
        self.assertIn("pre_run_worktree_status", payload["preconditions"])
        self.assertNotIn("post_output_worktree_status", payload)

    def test_manifest_includes_both_worktree_states(self) -> None:
        payload = self._write_manifest_payload()
        self.assertEqual(payload["pre_run_worktree_status"], "")
        self.assertEqual(payload["working_tree_status"], " M generated")
        self.assertEqual(payload["working_tree_status_context"], "step3_after_outputs")

    def test_family_rows_csv_columns_match_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rows.csv"
            step3.write_family_rows_csv({}, path)
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader)
        self.assertEqual(header, step3.CSV_COLUMNS)

    def test_results_doc_table_header_has_no_unescaped_pipes_in_cells(self) -> None:
        # Regression: an earlier version emitted "| P(success | hit) |" which
        # broke Markdown table parsing because the literal "|" inside the cell
        # is read as a column delimiter. Use Bucket B (which doesn't iterate
        # per_family in the outcome section) so we can pass an empty fixture.
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.md"
            step3.write_results_doc(
                {},
                "B_inconclusive_min_n",
                "no limitation",
                path,
                preconditions={
                    "publication_hardening_lock_sha256": "0" * 64,
                    "alias_function_sha256": "0" * 64,
                    "cqr_audit_preregistration_lock_sha256": "0" * 64,
                    "noisy_comparison_preregistration_lock_sha256": "0" * 64,
                    "skip_doc_path": "docs/skip.md",
                    "skip_doc_sha256": "0" * 64,
                    "git_commit": "abc",
                    "pre_run_worktree_status": "",
                },
                regeneration_metadata={"regeneration_skipped": False, "ollama_server_version": "x"},
            )
            text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        # The doc has two tables starting with "| Family |": the Scope table
        # (two columns) and the Per-Family Cross-Tab table. The bug being
        # regressed is in the SECOND one, so anchor on its section heading
        # first to avoid silently validating the wrong table.
        cross_tab_section = next(
            i for i, line in enumerate(lines) if line.strip() == "## Per-Family Cross-Tab"
        )
        header_index = next(
            i
            for i, line in enumerate(lines[cross_tab_section:], start=cross_tab_section)
            if line.startswith("| Family |")
        )
        header_line = lines[header_index]
        separator_line = lines[header_index + 1]
        # Sanity: the separator row must look like a Markdown table separator.
        self.assertTrue(
            set(separator_line.replace("|", "").strip()) <= set("- :")
            and "|" in separator_line,
            f"Line after header should be a Markdown table separator, got: {separator_line!r}",
        )
        # Sanity: the header should have the wider cross-tab column count
        # (at least 10 columns: Family, Role, Hits, Misses, P(hit), P(miss),
        # Lift, Alias FPR, Min N, Miss evaluable) — not the 2-column Scope
        # header. This guards against the anchor regressing onto the wrong table.
        self.assertGreaterEqual(
            header_line.count("|"),
            11,
            f"Cross-tab header should have >=11 pipes, got: {header_line!r}",
        )
        self.assertEqual(
            header_line.count("|"),
            separator_line.count("|"),
            "Markdown table header pipe count must match the separator row "
            "(literal pipes inside cells like 'P(success | hit)' break parsing)",
        )

    def test_manifest_lists_source_run_artifacts(self) -> None:
        payload = self._write_manifest_payload()
        self.assertIn("useful_pending_memory", payload["source_run_artifacts"])
        source = payload["source_run_artifacts"]["useful_pending_memory"]
        for key in (
            "run_json_sha256",
            "run_manifest_sha256",
            "metrics_csv_sha256",
            "predictions_sha256",
            "component_eval_sha256",
        ):
            self.assertIn(key, source)

    def _write_manifest_payload(self) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            summary = tmp / "summary.json"
            rows = tmp / "rows.csv"
            doc = tmp / "results.md"
            for path in (summary, rows, doc):
                path.write_text(path.name, encoding="utf-8")
            manifest = tmp / "manifest.json"
            step3.write_manifest(
                {},
                {
                    "pre_run_worktree_status": "",
                    "publication_hardening_lock_sha256": "pub",
                    "alias_function_sha256": "alias",
                    "cqr_audit_preregistration_lock_sha256": "cqr",
                    "noisy_comparison_preregistration_lock_sha256": "noisy",
                    "skip_doc_path": "docs/skip.md",
                    "skip_doc_sha256": "skip",
                    "git_commit": "abc123",
                },
                {"regeneration_skipped": False},
                "A_cross_tab_populated",
                " M generated",
                {
                    "useful_pending_memory": {
                        "run_json_sha256": "a",
                        "run_manifest_sha256": "b",
                        "metrics_csv_sha256": "c",
                        "predictions_sha256": "d",
                        "component_eval_sha256": "e",
                    }
                },
                [summary, rows, doc],
                manifest,
                command="cmd",
            )
            return json.loads(manifest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
