import unittest

from cq.eval.runner import EVIDENCE_CONFLICT_SPECTRUM, build_run_artifact
from cq.simulator.evidence_conflict_spectrum import generate_evidence_conflict_spectrum_scenarios
from scripts.run_abstention_nondegeneracy_probe import build_probe_artifact
from scripts.run_family_structure_summary import build_structure_summary


def _scenario_by_template(scenarios, template_id):
    return [scenario for scenario in scenarios if scenario.template_id == template_id][0]


class EvidenceConflictSpectrumTests(unittest.TestCase):
    def test_mixed_rotation_covers_all_five_mechanisms(self) -> None:
        scenarios = generate_evidence_conflict_spectrum_scenarios(10, template_mix="mixed")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios[:5]],
            [
                "conflict_zero_clean_v1",
                "conflict_mild_v1",
                "conflict_moderate_v1",
                "conflict_witness_v1",
                "conflict_polluted_v1",
            ],
        )
        self.assertEqual(
            [event.question.phase for event in scenarios[0].sorted_events() if event.question],
            ["evidence_conflict_probe"],
        )

    def test_lifecycle_intent_labels_match_preregistered_table(self) -> None:
        scenarios = generate_evidence_conflict_spectrum_scenarios(5, template_mix="mixed")
        expected = {
            "conflict_zero_clean_v1": (False, True, "zero"),
            "conflict_mild_v1": (False, True, "mild"),
            "conflict_moderate_v1": (True, False, "moderate"),
            "conflict_witness_v1": (True, False, "witness"),
            "conflict_polluted_v1": (False, True, "polluted"),
        }

        for template_id, (abstention_ok, commit_required, intensity) in expected.items():
            scenario = _scenario_by_template(scenarios, template_id)
            lifecycle = scenario.expected_lifecycle
            self.assertEqual(lifecycle["abstention_ok"], abstention_ok)
            self.assertEqual(lifecycle["commit_required"], commit_required)
            self.assertEqual(lifecycle["evidence_conflict_intensity"], intensity)
            self.assertIn("gold_candidate_ids", lifecycle)
            self.assertIn("should_not_promote_candidate_ids", lifecycle)

    def test_heldout_templates_are_distinct_v2_templates(self) -> None:
        scenarios = generate_evidence_conflict_spectrum_scenarios(5, template_mix="heldout")

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "conflict_zero_clean_v2",
                "conflict_mild_v2",
                "conflict_moderate_v2",
                "conflict_witness_v2",
                "conflict_polluted_v2",
            ],
        )
        self.assertTrue(all(scenario.template_split == "heldout" for scenario in scenarios))

    def test_structure_summary_variance_checks_pass(self) -> None:
        summary = build_structure_summary(EVIDENCE_CONFLICT_SPECTRUM, 30, "mixed")

        self.assertTrue(summary["variance_checks"]["conflict_moderate"]["passed"])
        self.assertTrue(summary["variance_checks"]["conflict_witness"]["passed"])
        self.assertTrue(summary["variance_checks"]["conflict_polluted"]["passed"])

    def test_nondegeneracy_probe_detects_abstain_required_policy_disagreement(self) -> None:
        artifact = build_probe_artifact(scenarios_per_mechanism=4, template_mix="mixed")

        self.assertTrue(artifact["summary_by_mechanism"]["conflict_moderate"]["has_disagreement"])
        self.assertTrue(artifact["summary_by_mechanism"]["conflict_witness"]["has_disagreement"])
        self.assertTrue(artifact["abstain_required_mechanisms_have_disagreement"])
        for mechanism in ("conflict_zero", "conflict_mild", "conflict_polluted"):
            self.assertTrue(artifact["summary_by_mechanism"][mechanism]["has_commit_agreement"])
        self.assertTrue(artifact["commit_required_mechanisms_have_commit_agreement"])

    def test_runner_computes_abstention_metrics_for_family(self) -> None:
        artifact = build_run_artifact(
            10,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set="phase2_5",
        )
        cq = [policy for policy in artifact["policies"] if policy["policy_name"] == "consolidation_queue_lite"][0]
        moderate = cq["summary_by_template_id"]["conflict_moderate_v1"]

        self.assertEqual(moderate["useful_abstention_rate"], 1.0)
        self.assertIn("primary_abstention_comparisons", artifact)

    def test_evidence_conflict_useful_recall_does_not_count_abstention_as_recall(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set="phase2_5",
        )
        cq = [policy for policy in artifact["policies"] if policy["policy_name"] == "consolidation_queue_lite"][0]
        moderate = [
            record
            for record in cq["scenarios"]
            if record["scenario"]["expected_lifecycle"]["mechanism"] == "conflict_moderate"
        ][0]

        self.assertEqual(moderate["metrics"]["answer_correctness"], 1.0)
        self.assertEqual(moderate["metrics"]["useful_abstention"], 1.0)
        self.assertEqual(moderate["metrics"]["useful_recall"], 0.0)

    def test_default_policy_set_records_missing_primary_comparison_warning(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set="default",
        )

        self.assertEqual(artifact["primary_abstention_comparisons"], {})
        self.assertTrue(artifact["primary_abstention_comparison_warnings"])


if __name__ == "__main__":
    unittest.main()
