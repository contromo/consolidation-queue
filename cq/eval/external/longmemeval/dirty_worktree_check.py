"""Dirty pre-run worktree check for LongMemEval externalization runners.

Preregistration §10 requires a dirty-pre-run worktree check before any Phase
X.4 policy execution. This module provides the helper that runners call.

Mirrors the discipline used by ``scripts/run_noisy_policy_comparison.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class DirtyWorktreeError(RuntimeError):
    pass


def assert_clean_worktree(repo_root: Optional[Path] = None) -> None:
    """Raise ``DirtyWorktreeError`` if ``git status --porcelain`` is non-empty."""

    output = worktree_status_porcelain(repo_root)
    if output:
        raise DirtyWorktreeError(
            "Dirty worktree before run; the preregistration §10 contract "
            "requires a clean tree:\n{}".format(output)
        )


def worktree_status_porcelain(repo_root: Optional[Path] = None) -> str:
    repo = repo_root or detect_repo_root()
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise DirtyWorktreeError("git is not available on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise DirtyWorktreeError(
            "git status failed: {}".format(exc.stderr.strip() or exc.returncode)
        ) from exc
    return completed.stdout.strip()


def current_commit_sha(repo_root: Optional[Path] = None) -> str:
    repo = repo_root or detect_repo_root()
    completed = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def detect_repo_root(start_path: Optional[Path] = None) -> Path:
    """Return the git repository root containing ``start_path`` or cwd."""

    start = (start_path or Path.cwd()).resolve()
    if start.is_file():
        start = start.parent
    completed = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()).resolve()
