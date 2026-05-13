from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PairedBootstrapResult:
    point_estimate: float
    lower_confidence_bound: float
    confidence_level: float
    resamples: int
    seed: int


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean requires at least one value")
    return sum(values) / len(values)


def paired_delta_point_estimate(deltas: Sequence[float]) -> float:
    if not deltas:
        raise ValueError("paired_delta_point_estimate requires at least one delta")
    return mean(deltas)


def paired_bootstrap_sample_means(
    deltas: Sequence[float],
    *,
    resamples: int = 10_000,
    seed: int = 0,
) -> list[float]:
    if not deltas:
        raise ValueError("paired_bootstrap_sample_means requires at least one delta")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    rng = random.Random(seed)
    count = len(deltas)
    samples = []
    for _ in range(resamples):
        sample = [deltas[rng.randrange(count)] for _ in range(count)]
        samples.append(mean(sample))
    samples.sort()
    return samples


def stratified_paired_bootstrap_sample_means(
    strata: Sequence[Sequence[float]],
    *,
    resamples: int = 10_000,
    seed: int = 0,
) -> list[float]:
    if not strata:
        raise ValueError("stratified_paired_bootstrap_sample_means requires at least one stratum")
    if any(not stratum for stratum in strata):
        raise ValueError("stratified_paired_bootstrap_sample_means requires non-empty strata")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    rng = random.Random(seed)
    samples = []
    for _ in range(resamples):
        stratum_means = []
        for deltas in strata:
            count = len(deltas)
            sample = [deltas[rng.randrange(count)] for _ in range(count)]
            stratum_means.append(mean(sample))
        samples.append(mean(stratum_means))
    samples.sort()
    return samples


def one_sided_lower_confidence_bound(
    bootstrap_samples: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> float:
    if not bootstrap_samples:
        raise ValueError("one_sided_lower_confidence_bound requires at least one sample")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1")
    alpha = 1.0 - confidence_level
    index = max(0, min(len(bootstrap_samples) - 1, math.ceil(alpha * len(bootstrap_samples))))
    return bootstrap_samples[index]


def one_sided_upper_confidence_bound(
    bootstrap_samples: Sequence[float],
    *,
    confidence_level: float = 0.95,
) -> float:
    if not bootstrap_samples:
        raise ValueError("one_sided_upper_confidence_bound requires at least one sample")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1")
    index = max(0, min(len(bootstrap_samples) - 1, math.ceil(confidence_level * len(bootstrap_samples)) - 1))
    return bootstrap_samples[index]


def paired_bootstrap_confidence_result(
    deltas: Sequence[float],
    *,
    resamples: int = 10_000,
    confidence_level: float = 0.95,
    seed: int = 0,
) -> PairedBootstrapResult:
    samples = paired_bootstrap_sample_means(
        deltas,
        resamples=resamples,
        seed=seed,
    )
    return PairedBootstrapResult(
        point_estimate=paired_delta_point_estimate(deltas),
        lower_confidence_bound=one_sided_lower_confidence_bound(
            samples,
            confidence_level=confidence_level,
        ),
        confidence_level=confidence_level,
        resamples=resamples,
        seed=seed,
    )
