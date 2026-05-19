#!/usr/bin/env python3
"""CLI wrapper for the LongMemEval Phase X.4 transfer runner."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cq.eval.external.longmemeval.transfer import main


if __name__ == "__main__":
    raise SystemExit(main())
