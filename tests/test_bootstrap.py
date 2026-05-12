import unittest
import math
import random

from cq.eval.bootstrap import (
    one_sided_lower_confidence_bound,
    paired_bootstrap_confidence_result,
    paired_bootstrap_sample_means,
    paired_delta_point_estimate,
)


class BootstrapTests(unittest.TestCase):
    def test_point_estimate_matches_mean(self) -> None:
        self.assertAlmostEqual(paired_delta_point_estimate([1.0, 0.0, -1.0, 1.0]), 0.25)

    def test_bootstrap_is_seed_deterministic(self) -> None:
        samples_a = paired_bootstrap_sample_means([1.0, 0.0, 0.0, 1.0], resamples=200, seed=7)
        samples_b = paired_bootstrap_sample_means([1.0, 0.0, 0.0, 1.0], resamples=200, seed=7)

        self.assertEqual(samples_a, samples_b)

    def test_lower_confidence_bound_uses_one_sided_quantile(self) -> None:
        samples = [0.1, 0.2, 0.3, 0.4, 0.5]
        self.assertEqual(
            one_sided_lower_confidence_bound(samples, confidence_level=0.80),
            0.2,
        )

    def test_confidence_result_exposes_point_estimate_and_lcb(self) -> None:
        result = paired_bootstrap_confidence_result(
            [1.0, 1.0, 0.0, 1.0, 0.0],
            resamples=500,
            confidence_level=0.95,
            seed=3,
        )

        self.assertAlmostEqual(result.point_estimate, 0.6)
        self.assertLessEqual(result.lower_confidence_bound, result.point_estimate)
        self.assertEqual(result.resamples, 500)
        self.assertEqual(result.seed, 3)

    def test_production_scale_lcb_tracks_analytic_uniform_mean(self) -> None:
        rng = random.Random(17)
        deltas = [rng.uniform(-0.2, 0.4) for _ in range(1000)]

        result = paired_bootstrap_confidence_result(
            deltas,
            resamples=10_000,
            confidence_level=0.95,
            seed=11,
        )

        mean = 0.1
        sigma = 0.6 / math.sqrt(12)
        analytic_lcb = mean - 1.6448536269514722 * sigma / math.sqrt(1000)
        self.assertAlmostEqual(result.lower_confidence_bound, analytic_lcb, delta=0.01)


if __name__ == "__main__":
    unittest.main()
