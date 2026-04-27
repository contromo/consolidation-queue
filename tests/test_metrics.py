import unittest

from cq.schemas.metrics import PolicyScenarioMetrics, PolicySummaryMetrics


class PolicySummaryMetricsTests(unittest.TestCase):
    def test_empty_summary_returns_zeroes(self) -> None:
        summary = PolicySummaryMetrics.from_scenarios("test-policy", [])

        self.assertEqual(summary.policy_name, "test-policy")
        self.assertEqual(summary.scenario_count, 0)
        self.assertEqual(summary.useful_recall_before_contradiction, 0.0)
        self.assertEqual(summary.used_pending_before_contradiction, 0.0)
        self.assertEqual(summary.durable_commit_before_contradiction, 0.0)
        self.assertEqual(summary.false_assertion_after_contradiction, 0.0)
        self.assertEqual(summary.contradiction_recovery_rate, 0.0)
        self.assertEqual(summary.average_time_to_demotion, 0.0)

    def test_average_time_to_demotion_ignores_missing_values(self) -> None:
        metrics = [
            PolicyScenarioMetrics(
                scenario_id="scenario-1",
                policy_name="test-policy",
                useful_recall_before_contradiction=1.0,
                used_pending_before_contradiction=0.0,
                durable_commit_before_contradiction=1.0,
                false_assertion_after_contradiction=0.0,
                contradiction_recovery_rate=1.0,
                time_to_demotion=None,
            ),
            PolicyScenarioMetrics(
                scenario_id="scenario-2",
                policy_name="test-policy",
                useful_recall_before_contradiction=1.0,
                used_pending_before_contradiction=0.0,
                durable_commit_before_contradiction=1.0,
                false_assertion_after_contradiction=0.0,
                contradiction_recovery_rate=1.0,
                time_to_demotion=2.5,
            ),
        ]

        summary = PolicySummaryMetrics.from_scenarios("test-policy", metrics)
        self.assertEqual(summary.average_time_to_demotion, 2.5)


if __name__ == "__main__":
    unittest.main()
