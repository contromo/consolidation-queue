from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def iso_to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def minutes_between(first: datetime, second: datetime) -> float:
    return (second - first).total_seconds() / 60.0


def first_non_none(values: Iterable[Optional[float]]) -> Optional[float]:
    for value in values:
        if value is not None:
            return value
    return None
