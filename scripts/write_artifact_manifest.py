#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


LARGE_ARTIFACT_THRESHOLD_BYTES = 5 * 1024 * 1024
DEFAULT_INCLUDE_GLOBS = ("*.json",)
EXCLUDED_JSON_GLOBS = (
    "*_manifest.json",
    "*_structure*.json",
    "*_nondegeneracy*.json",
)


def _repo_relative_path(path: Path) -> str:
    resolved = path.resolve()
    repo_root = Path(_git_output(["rev-parse", "--show-toplevel"])).resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _git_output(args: Sequence[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def git_commit() -> str:
    return _git_output(["rev-parse", "HEAD"])


def working_tree_status() -> str:
    return "clean" if not _git_output(["status", "--short"]) else "dirty"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_excluded(path: Path) -> bool:
    return any(path.match(pattern) for pattern in EXCLUDED_JSON_GLOBS)


def eligible_artifacts(run_dir: Path, include_globs: Iterable[str], *, large_only: bool) -> List[Path]:
    matched = set()
    for include_glob in include_globs:
        matched.update(path for path in run_dir.glob(include_glob) if path.is_file())

    eligible = []
    for path in sorted(matched, key=lambda item: _repo_relative_path(item)):
        if _is_excluded(path):
            continue
        if large_only and path.stat().st_size < LARGE_ARTIFACT_THRESHOLD_BYTES:
            continue
        eligible.append(path)
    return eligible


def derive_run_name(paths: Sequence[Path]) -> str:
    if len(paths) != 1:
        raise ValueError("Provide --run-name when manifest input contains {} files".format(len(paths)))
    return paths[0].stem


def build_manifest(
    *,
    run_dir: Path,
    include_globs: Sequence[str],
    run_name: str | None,
    runner_command: str,
    archive_status: str,
    large_only: bool,
) -> tuple[Path, dict]:
    paths = eligible_artifacts(run_dir, include_globs, large_only=large_only)
    if not paths:
        raise ValueError("No eligible artifacts matched in {}".format(run_dir))
    resolved_run_name = run_name or derive_run_name(paths)
    commit = git_commit()
    status = working_tree_status()
    python_version = sys.version.split()[0]
    artifacts = [
        {
            "archive_status": archive_status,
            "bytes": path.stat().st_size,
            "git_commit": commit,
            "path": _repo_relative_path(path),
            "python_version": python_version,
            "runner_command": runner_command,
            "sha256": sha256_file(path),
            "working_tree_status": status,
            "working_tree_status_context": "manifest_write_time_after_runner_outputs",
        }
        for path in paths
    ]
    manifest = {
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "manifest_version": 1,
        "run_name": resolved_run_name,
    }
    return run_dir / "{}_manifest.json".format(resolved_run_name), manifest


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(".{}.tmp".format(path.name))
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(payload, encoding="utf-8")
    temporary_path.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a manifest for large generated experiment artifacts.")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--include", action="append", default=None)
    parser.add_argument("--run-name")
    parser.add_argument("--runner-command", required=True)
    parser.add_argument("--archive-status", default="regeneratable_only")
    parser.add_argument("--large-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest_path, manifest = build_manifest(
            run_dir=args.run_dir,
            include_globs=tuple(args.include or DEFAULT_INCLUDE_GLOBS),
            run_name=args.run_name,
            runner_command=args.runner_command,
            archive_status=args.archive_status,
            large_only=args.large_only,
        )
        write_manifest(manifest_path, manifest)
    except Exception as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
