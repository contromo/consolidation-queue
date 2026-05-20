import subprocess
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval.dirty_worktree_check import (
    DirtyWorktreeError,
    assert_clean_worktree,
    current_commit_sha,
)


class LongMemEvalDirtyWorktreeCheckTests(unittest.TestCase):
    def _init_repo(self, tmpdir: Path) -> Path:
        subprocess.run(["git", "init", "-q"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.email", "test@test"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=tmpdir, check=True)
        (tmpdir / "README").write_text("initial\n", encoding="utf-8")
        subprocess.run(["git", "add", "README"], cwd=tmpdir, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "init"],
            cwd=tmpdir,
            check=True,
        )
        return tmpdir

    def test_clean_worktree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._init_repo(Path(tmp))
            assert_clean_worktree(repo_root=repo)
            self.assertEqual(len(current_commit_sha(repo_root=repo)), 40)

    def test_dirty_worktree_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._init_repo(Path(tmp))
            (repo / "untracked.txt").write_text("hello\n", encoding="utf-8")
            with self.assertRaises(DirtyWorktreeError):
                assert_clean_worktree(repo_root=repo)


if __name__ == "__main__":
    unittest.main()
