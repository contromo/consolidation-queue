import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SUMMARY_PATH = REPO_ROOT / "data" / "external" / "longmemeval" / "smoke_summary.json"
SMOKE_MANIFEST_PATH = REPO_ROOT / "data" / "external" / "longmemeval" / "smoke_manifest.json"


class LongMemEvalSmokeArtifactTests(unittest.TestCase):
    def test_committed_smoke_artifacts_exist(self) -> None:
        self.assertTrue(SMOKE_SUMMARY_PATH.exists(), str(SMOKE_SUMMARY_PATH))
        self.assertTrue(SMOKE_MANIFEST_PATH.exists(), str(SMOKE_MANIFEST_PATH))

    def test_committed_smoke_manifest_has_expected_shape(self) -> None:
        manifest = json.loads(SMOKE_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifact"], "longmemeval_externalization_smoke")
        self.assertEqual(manifest["artifact_class"], "phase_x3_smoke")
        self.assertEqual(manifest["case_limit"], 6)
        self.assertTrue(manifest["candidate_stream_hash_invariant_passed"])
        self.assertTrue(manifest["policy_smoke_passed"])
        self.assertGreaterEqual(manifest["policy_count"], 3)
        self.assertIn("consolidation_queue_lite", manifest["policy_names"])
        self.assertIn("source_provenance", manifest)
        self.assertIn("git_commit_sha", manifest["source_provenance"])
        self.assertIn("dirty_worktree_check_passed", manifest["source_provenance"])
        self.assertEqual(manifest["scenario_count"], 6)
        for key in ("adapter_sha256", "preregistration_lock_sha256"):
            self.assertEqual(len(manifest[key]), 64)
        self.assertIn("annotations_json_repo_path", manifest["inputs"])
        self.assertIn("smoke_summary_repo_path", manifest["outputs"])

    def test_committed_smoke_summary_includes_policy_execution(self) -> None:
        summary = json.loads(SMOKE_SUMMARY_PATH.read_text(encoding="utf-8"))
        policy_smoke = summary["policy_smoke"]
        self.assertEqual(policy_smoke["scenario_count"], 6)
        self.assertTrue(policy_smoke["policy_smoke_passed"])
        self.assertIn("reflection_eager_write_lite", policy_smoke["policy_names"])
        for policy_run in policy_smoke["policies"]:
            self.assertEqual(policy_run["scenario_count"], 6)
            self.assertEqual(len(policy_run["per_scenario"]), 6)
            self.assertIn("summary", policy_run)

    def test_running_smoke_again_is_byte_stable(self) -> None:
        before_summary = SMOKE_SUMMARY_PATH.read_bytes()
        before_manifest = SMOKE_MANIFEST_PATH.read_bytes()
        with tempfile.TemporaryDirectory() as tmpdir:
            out_summary = Path(tmpdir) / "smoke_summary.json"
            out_manifest = Path(tmpdir) / "smoke_manifest.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "run_longmemeval_smoke.py"),
                    "--out-summary",
                    str(out_summary),
                    "--out-manifest",
                    str(out_manifest),
                    "--allow-dirty-worktree",
                ],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            generated_summary = out_summary.read_bytes()
            generated_manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(generated_summary, before_summary)
        committed_manifest = json.loads(before_manifest.decode("utf-8"))
        generated_outputs = generated_manifest.pop("outputs")
        committed_outputs = committed_manifest.pop("outputs")
        generated_manifest.pop("source_provenance")
        committed_manifest.pop("source_provenance")
        self.assertEqual(generated_manifest, committed_manifest)
        self.assertEqual(
            generated_outputs["smoke_summary_sha256"],
            committed_outputs["smoke_summary_sha256"],
        )
        self.assertEqual(
            generated_outputs["smoke_summary_bytes"],
            committed_outputs["smoke_summary_bytes"],
        )
        self.assertEqual(SMOKE_SUMMARY_PATH.read_bytes(), before_summary)
        self.assertEqual(SMOKE_MANIFEST_PATH.read_bytes(), before_manifest)


if __name__ == "__main__":
    unittest.main()
