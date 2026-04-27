import unittest

from cq.eval.end_to_end_eval import execute_scenario
from cq.memory.consolidation_queue import ConsolidationQueueLite
from cq.simulator.scenario_generator import generate_forced_contradiction_scenarios


class ConsolidationQueueTests(unittest.TestCase):
    def test_pending_memory_is_used_before_promotion(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, seed=3)[0]
        result = execute_scenario(ConsolidationQueueLite, scenario)
        traces = result["question_traces"]
        before_trace = traces[0]

        self.assertTrue(before_trace["used_pending"])
        self.assertEqual(result["metrics"]["useful_recall_before_contradiction"], 1.0)

    def test_old_candidate_becomes_contested_after_stronger_contradiction(self) -> None:
        scenario = generate_forced_contradiction_scenarios(1, seed=4)[0]
        result = execute_scenario(ConsolidationQueueLite, scenario)
        snapshot = result["store_snapshot"]
        old_candidate_id = scenario.expected_lifecycle["old_candidate_id"]
        old_candidate = [
            candidate
            for candidate in snapshot["candidate_memories"]
            if candidate["candidate_id"] == old_candidate_id
        ][0]

        self.assertEqual(old_candidate["state"], "contested")
        self.assertEqual(result["metrics"]["false_assertion_after_contradiction"], 0.0)
        self.assertEqual(result["metrics"]["contradiction_recovery_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
