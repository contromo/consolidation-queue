import json
import subprocess
import sys
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
        self.assertEqual(manifest["scenario_count"], 6)
        for key in ("adapter_sha256", "preregistration_lock_sha256"):
            self.assertEqual(len(manifest[key]), 64)
        self.assertIn("annotations_json_repo_path", manifest["inputs"])
        self.assertIn("smoke_summary_repo_path", manifest["outputs"])

    def test_running_smoke_again_is_byte_stable(self) -> None:
        before_summary = SMOKE_SUMMARY_PATH.read_bytes()
        before_manifest = SMOKE_MANIFEST_PATH.read_bytes()
        completed = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "run_longmemeval_smoke.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(SMOKE_SUMMARY_PATH.read_bytes(), before_summary)
        self.assertEqual(SMOKE_MANIFEST_PATH.read_bytes(), before_manifest)


if __name__ == "__main__":
    unittest.main()
