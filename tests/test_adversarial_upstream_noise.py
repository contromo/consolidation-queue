import unittest

from cq.simulator.adversarial_upstream_noise import generate_adversarial_upstream_noise_scenarios


def _scenario_by_template(scenarios, template_id):
    return [scenario for scenario in scenarios if scenario.template_id == template_id][0]


class AdversarialUpstreamNoiseScenarioTests(unittest.TestCase):
    def test_mixed_rotation_covers_all_five_mechanisms(self) -> None:
        scenarios = generate_adversarial_upstream_noise_scenarios(10, template_mix="mixed")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios[:5]],
            [
                "adversarial_retraction_v1",
                "adversarial_witness_conflict_v1",
                "adversarial_temporal_skew_v1",
                "adversarial_scope_narrowing_v1",
                "adversarial_pending_competition_v1",
            ],
        )
        self.assertEqual([event.question.phase for event in scenarios[0].sorted_events() if event.question], ["adversarial_probe"])

    def test_witness_conflict_marks_abstention_ok(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_witness_conflict_v1",
        )

        self.assertTrue(scenario.expected_lifecycle["abstention_ok"])
        question = [event.question for event in scenario.sorted_events() if event.question][0]
        self.assertEqual(question.gold_candidate_ids, [])
        self.assertGreaterEqual(len(question.forbidden_candidate_ids), 4)

    def test_retraction_scenario_carries_retracted_and_retraction_ids(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_retraction_v1",
        )

        self.assertEqual(len(scenario.expected_lifecycle["retracted_candidate_ids"]), 2)
        self.assertEqual(len(scenario.expected_lifecycle["retraction_candidate_ids"]), 1)
        question = [event.question for event in scenario.sorted_events() if event.question][0]
        self.assertEqual(question.gold_candidate_ids, scenario.expected_lifecycle["retraction_candidate_ids"])

    def test_temporal_skew_marks_stale_observed_at(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_temporal_skew_v1",
        )
        stale_id = scenario.expected_lifecycle["stale_candidate_ids"][0]
        events = [event for event in scenario.sorted_events() if event.candidate is not None]
        current_observed_at = events[0].candidate.provenance[0].observed_at
        stale_event = [event for event in events if event.candidate.candidate_id == stale_id][0]

        self.assertLess(stale_event.candidate.provenance[0].observed_at, current_observed_at)

    def test_scope_narrowing_has_wider_and_narrower_scope_structure(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_scope_narrowing_v1",
        )
        wider_event, narrower_event = [event for event in scenario.sorted_events() if event.candidate is not None]

        self.assertEqual(wider_event.candidate.scope_level.value, "workspace")
        self.assertEqual(narrower_event.candidate.scope_level.value, "project")
        self.assertIn(
            wider_event.candidate.candidate_id,
            narrower_event.candidate.contradicts,
        )

    def test_pending_competition_has_two_under_threshold_candidates(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_pending_competition_v1",
        )
        candidate_events = [event for event in scenario.sorted_events() if event.candidate is not None]
        candidate_ids = [event.candidate.candidate_id for event in candidate_events]

        self.assertEqual(
            candidate_ids,
            scenario.expected_lifecycle["pending_competition_candidate_ids"],
        )
        self.assertEqual(
            sorted(scenario.expected_lifecycle["should_not_promote_candidate_ids"]),
            sorted(candidate_ids),
        )

    def test_heldout_scope_narrowing_uses_distinct_project_key_shape(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="heldout"),
            "adversarial_scope_narrowing_v2",
        )
        narrower_event = [event for event in scenario.sorted_events() if event.candidate is not None][1]

        self.assertIn("/env-prod", narrower_event.candidate.scope_key)


if __name__ == "__main__":
    unittest.main()
