import json
import tempfile
import unittest
from pathlib import Path

from scripts.write_artifact_manifest import build_manifest, write_manifest


class ArtifactManifestTests(unittest.TestCase):
    def test_empty_input_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "No eligible artifacts"):
                build_manifest(
                    run_dir=Path(tmpdir),
                    include_globs=("*.json",),
                    run_name="empty",
                    runner_command="python3 -m cq.eval.runner",
                    archive_status="regeneratable_only",
                    large_only=False,
                )

    def test_single_file_manifest_records_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            artifact = run_dir / "run.json"
            artifact.write_text('{"ok": true}\n', encoding="utf-8")

            manifest_path, manifest = build_manifest(
                run_dir=run_dir,
                include_globs=("*.json",),
                run_name=None,
                runner_command="python3 -m cq.eval.runner --family evidence_conflict_spectrum",
                archive_status="regeneratable_only",
                large_only=False,
            )

            self.assertEqual(manifest_path, run_dir / "run_manifest.json")
            self.assertEqual(manifest["run_name"], "run")
            self.assertEqual(manifest["artifact_count"], 1)
            row = manifest["artifacts"][0]
            self.assertEqual(row["bytes"], artifact.stat().st_size)
            self.assertEqual(row["archive_status"], "regeneratable_only")
            self.assertEqual(
                row["runner_command"],
                "python3 -m cq.eval.runner --family evidence_conflict_spectrum",
            )
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(row["working_tree_status"], {"clean", "dirty"})
            self.assertEqual(
                row["working_tree_status_context"],
                "manifest_write_time_after_runner_outputs",
            )
            self.assertRegex(row["python_version"], r"^\d+\.\d+\.\d+")

    def test_existing_manifest_is_excluded_on_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "run.json").write_text("{}", encoding="utf-8")
            manifest_path, manifest = build_manifest(
                run_dir=run_dir,
                include_globs=("*.json",),
                run_name=None,
                runner_command="cmd",
                archive_status="regeneratable_only",
                large_only=False,
            )
            write_manifest(manifest_path, manifest)

            rerun_path, rerun_manifest = build_manifest(
                run_dir=run_dir,
                include_globs=("*.json",),
                run_name=None,
                runner_command="cmd",
                archive_status="regeneratable_only",
                large_only=False,
            )

            self.assertEqual(rerun_path, manifest_path)
            self.assertEqual(rerun_manifest["artifact_count"], 1)
            self.assertTrue(rerun_manifest["artifacts"][0]["path"].endswith("run.json"))

    def test_stable_ordering_across_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "z.json").write_text("z", encoding="utf-8")
            (run_dir / "a.json").write_text("a", encoding="utf-8")

            _, first = build_manifest(
                run_dir=run_dir,
                include_globs=("*.json",),
                run_name="two",
                runner_command="cmd",
                archive_status="regeneratable_only",
                large_only=False,
            )
            _, second = build_manifest(
                run_dir=run_dir,
                include_globs=("*.json",),
                run_name="two",
                runner_command="cmd",
                archive_status="regeneratable_only",
                large_only=False,
            )

            first_paths = [row["path"] for row in first["artifacts"]]
            second_paths = [row["path"] for row in second["artifacts"]]
            self.assertEqual(first_paths, sorted(first_paths))
            self.assertEqual(first_paths, second_paths)

    def test_runner_command_and_archive_status_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            (run_dir / "run.json").write_text("{}", encoding="utf-8")
            manifest_path, manifest = build_manifest(
                run_dir=run_dir,
                include_globs=("*.json",),
                run_name="custom",
                runner_command="RUNNER_CMD",
                archive_status="uploaded:s3://bucket/key",
                large_only=False,
            )
            write_manifest(manifest_path, manifest)
            written = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(written["run_name"], "custom")
            self.assertEqual(written["artifacts"][0]["runner_command"], "RUNNER_CMD")
            self.assertEqual(written["artifacts"][0]["archive_status"], "uploaded:s3://bucket/key")


if __name__ == "__main__":
    unittest.main()
