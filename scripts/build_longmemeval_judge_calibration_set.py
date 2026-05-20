#!/usr/bin/env python3
"""CLI wrapper for the LongMemEval judge calibration-set builder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cq.eval.external.longmemeval.judge_calibration_set import main


if __name__ == "__main__":
    raise SystemExit(main())
