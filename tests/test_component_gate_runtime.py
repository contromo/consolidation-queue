import subprocess
import unittest

from cq.eval import component_gate_runtime as runtime


class ComponentGateRuntimeTests(unittest.TestCase):
    def test_git_output_reports_missing_git(self) -> None:
        original_run = runtime.subprocess.run

        def missing_git(*_args, **_kwargs):
            raise FileNotFoundError("git")

        runtime.subprocess.run = missing_git
        try:
            with self.assertRaises(runtime.GateRuntimeError) as context:
                runtime._git_output(["status", "--short"])
        finally:
            runtime.subprocess.run = original_run

        self.assertEqual(context.exception.reason, "git_unavailable")
        self.assertEqual(context.exception.details["command"], ["git", "status", "--short"])

    def test_git_output_reports_non_repo_failure(self) -> None:
        original_run = runtime.subprocess.run

        def failed_git(command, **_kwargs):
            raise subprocess.CalledProcessError(
                128,
                command,
                output="",
                stderr="fatal: not a git repository",
            )

        runtime.subprocess.run = failed_git
        try:
            with self.assertRaises(runtime.GateRuntimeError) as context:
                runtime._git_output(["rev-parse", "HEAD"])
        finally:
            runtime.subprocess.run = original_run

        self.assertEqual(context.exception.reason, "git_command_failed")
        self.assertEqual(context.exception.details["returncode"], 128)
        self.assertIn("not a git repository", context.exception.details["stderr"])


if __name__ == "__main__":
    unittest.main()
