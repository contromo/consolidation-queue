from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import List

from cq.schemas.memory import jsonable
from cq.schemas.scenario import Scenario
from cq.simulator.scenario_generator import generate_frozen_mechanism_diverse_scenarios


PREREGISTRATION_PATH = Path("docs/preregistration.md")
FROZEN_EVAL_LOCK_FIELD = "frozen_eval_lock_sha256"
PREDICTIONS_BLOCK_START = "<!-- FROZEN_EVAL_PREDICTIONS_START -->"
PREDICTIONS_BLOCK_END = "<!-- FROZEN_EVAL_PREDICTIONS_END -->"
LOCK_RE = re.compile(r"^frozen_eval_lock_sha256:\s*([a-f0-9]{64})\s*$", re.MULTILINE)


class FrozenEvalLockError(ValueError):
    pass


def frozen_scenario_contracts() -> List[Scenario]:
    return generate_frozen_mechanism_diverse_scenarios()


def canonical_frozen_contracts_json() -> str:
    return json.dumps(
        jsonable(frozen_scenario_contracts()),
        sort_keys=True,
        separators=(",", ":"),
    )


def extract_predictions_block(preregistration_text: str) -> str:
    start = preregistration_text.find(PREDICTIONS_BLOCK_START)
    if start == -1:
        raise FrozenEvalLockError("Missing {}".format(PREDICTIONS_BLOCK_START))
    end = preregistration_text.find(PREDICTIONS_BLOCK_END, start)
    if end == -1:
        raise FrozenEvalLockError("Missing {}".format(PREDICTIONS_BLOCK_END))
    block_start = preregistration_text.find("\n", start)
    if block_start == -1 or block_start > end:
        raise FrozenEvalLockError("Predictions block is empty or malformed")
    return preregistration_text[block_start + 1 : end]


def declared_frozen_eval_lock(preregistration_text: str) -> str:
    match = LOCK_RE.search(preregistration_text)
    if match is None:
        raise FrozenEvalLockError("Missing {}".format(FROZEN_EVAL_LOCK_FIELD))
    return match.group(1)


def compute_frozen_eval_lock_sha256(preregistration_text: str) -> str:
    predictions_block = extract_predictions_block(preregistration_text)
    payload = canonical_frozen_contracts_json() + "\n" + predictions_block
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_frozen_eval_lock(preregistration_path: Path = PREREGISTRATION_PATH) -> None:
    if not preregistration_path.exists():
        raise FrozenEvalLockError("Missing preregistration file: {}".format(preregistration_path))
    preregistration_text = preregistration_path.read_text(encoding="utf-8")
    declared = declared_frozen_eval_lock(preregistration_text)
    actual = compute_frozen_eval_lock_sha256(preregistration_text)
    if declared != actual:
        raise FrozenEvalLockError(
            "Frozen eval lock mismatch: declared {}, computed {}".format(declared, actual)
        )


def main(argv: List[str] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect the frozen mechanism-diverse preregistration lock.")
    parser.add_argument(
        "--preregistration",
        default=str(PREREGISTRATION_PATH),
        help="Path to preregistration markdown file.",
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="Print the SHA-256 lock for the current contracts and predictions block.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that the declared lock matches the current contracts and predictions block.",
    )
    args = parser.parse_args(argv)
    preregistration_path = Path(args.preregistration)
    if args.recompute:
        text = preregistration_path.read_text(encoding="utf-8")
        print(compute_frozen_eval_lock_sha256(text))
        return 0
    if args.check:
        validate_frozen_eval_lock(preregistration_path)
        print("frozen eval lock OK")
        return 0
    parser.error("Choose --recompute or --check")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
