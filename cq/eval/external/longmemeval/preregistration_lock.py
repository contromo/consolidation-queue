from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import List, Optional


REPO_ROOT = Path(__file__).resolve().parents[4]
PREREGISTRATION_PATH = REPO_ROOT / "docs" / "fair_stream_externalization_preregistration.md"
LOCK_FIELD = "fair_stream_externalization_lock_sha256"
PROTOCOL_BLOCK_START = "<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_START -->"
PROTOCOL_BLOCK_END = "<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_END -->"
LOCK_RE = re.compile(
    r"^fair_stream_externalization_lock_sha256:\s*([a-f0-9]{64})\s*$",
    re.MULTILINE,
)


class FairStreamExternalizationLockError(ValueError):
    pass


def extract_protocol_block(preregistration_text: str) -> str:
    start = preregistration_text.find(PROTOCOL_BLOCK_START)
    if start == -1:
        raise FairStreamExternalizationLockError("Missing {}".format(PROTOCOL_BLOCK_START))
    end = preregistration_text.find(PROTOCOL_BLOCK_END, start)
    if end == -1:
        raise FairStreamExternalizationLockError("Missing {}".format(PROTOCOL_BLOCK_END))
    block_start = preregistration_text.find("\n", start)
    if block_start == -1 or block_start > end:
        raise FairStreamExternalizationLockError("Protocol block is empty or malformed")
    return preregistration_text[block_start + 1 : end]


def declared_fair_stream_externalization_lock(preregistration_text: str) -> str:
    match = LOCK_RE.search(preregistration_text)
    if match is None:
        raise FairStreamExternalizationLockError("Missing {}".format(LOCK_FIELD))
    return match.group(1)


def compute_fair_stream_externalization_lock_sha256(preregistration_text: str) -> str:
    block = extract_protocol_block(preregistration_text)
    block = block.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    return hashlib.sha256(block.encode("utf-8")).hexdigest()


def validate_fair_stream_externalization_lock(
    preregistration_path: Path = PREREGISTRATION_PATH,
) -> str:
    if not preregistration_path.exists():
        raise FairStreamExternalizationLockError(
            "Missing preregistration file: {}".format(preregistration_path)
        )
    text = preregistration_path.read_text(encoding="utf-8")
    declared = declared_fair_stream_externalization_lock(text)
    actual = compute_fair_stream_externalization_lock_sha256(text)
    if declared != actual:
        raise FairStreamExternalizationLockError(
            "Fair-stream externalization lock mismatch: declared {}, computed {}".format(
                declared,
                actual,
            )
        )
    return declared


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect the fair-stream externalization preregistration lock."
    )
    parser.add_argument(
        "--preregistration",
        default=str(PREREGISTRATION_PATH),
        help="Path to fair-stream externalization preregistration markdown.",
    )
    parser.add_argument("--recompute", action="store_true", help="Print the current lock SHA.")
    parser.add_argument("--check", action="store_true", help="Validate the declared lock SHA.")
    args = parser.parse_args(argv)
    preregistration_path = Path(args.preregistration)
    if args.recompute:
        print(
            compute_fair_stream_externalization_lock_sha256(
                preregistration_path.read_text(encoding="utf-8")
            )
        )
        return 0
    if args.check:
        validate_fair_stream_externalization_lock(preregistration_path)
        print("fair-stream externalization lock OK")
        return 0
    parser.error("Choose --recompute or --check")


if __name__ == "__main__":
    raise SystemExit(main())
