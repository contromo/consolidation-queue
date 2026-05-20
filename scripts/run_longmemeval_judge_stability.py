#!/usr/bin/env python3
"""CLI thin wrapper for LongMemEval judge stability calibration."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cq.eval.external.longmemeval.judge_stability import main


if __name__ == "__main__":
    raise SystemExit(main())
