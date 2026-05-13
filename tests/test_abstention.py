import csv
import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.abstention import (
    AbstentionDecision,
    _paired_deltas,
    _question_id_for_probe,
    abstained_from_trace,
    abstention_artifact_for_run,
    scenario_intent,
    stratified_bucket_comparison,
    summarize_decisions,
)
from cq.eval.runner import EVIDENCE_CONFLICT_SPECTRUM, POLICY_SET_PHASE_2_5, build_run_artifact, write_outputs
from scripts.run_abstention_replay import REPLAY_CSV_FIELDNAMES, run_replay


class AbstentionMetricTests(unittest.TestCase):
    def test_predicate_matches_runner_abstention_expression(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set=POLICY_SET_PHASE_2_5,
        )
        cq_policy = [
            policy for policy in artifact["policies"] if policy["policy_name"] == "consolidation_queue_lite"
        ][0]
        moderate = [
            record
            for record in cq_policy["scenarios"]
            if record["scenario"]["expected_lifecycle"]["mechanism"] == "conflict_moderate"
        ][0]
        trace = moderate["question_traces"][0]

        self.assertTrue(abstained_from_trace(trace, moderate["store_snapshot"]))
        self.assertEqual(moderate["metrics"]["useful_abstention"], 1.0)

    def test_denominator_aware_summary_excludes_gray_zone(self) -> None:
        decisions = [
            AbstentionDecision("s1", "p", "f", "m1", "moderate", True, False, True, 1.0, 1.0, 0.0, 0.0),
            AbstentionDecision("s2", "p", "f", "m2", "zero", False, True, True, 0.0, 0.0, 1.0, 1.0),
            AbstentionDecision("s3", "p", "f", "m3", "", False, False, True, 0.0, 0.0, 0.0, 0.0),
        ]

        summary = summarize_decisions(decisions)

        self.assertEqual(summary.gray_zone_count, 1)
        self.assertEqual(summary.useful_abstention_rate, 1.0)
        self.assertEqual(summary.harmful_abstention_rate, 1.0)

    def test_zero_denominator_summary_rates_are_zero(self) -> None:
        summary = summarize_decisions(
            [
                AbstentionDecision("s1", "p", "f", "m", "", False, False, True, 0.0, 0.0, 0.0, 0.0),
            ]
        )

        self.assertEqual(summary.useful_abstention_rate, 0.0)
        self.assertEqual(summary.harmful_abstention_rate, 0.0)

    def test_missing_intent_mapping_fails_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "No abstention intent mapping"):
            scenario_intent(
                family="new_family",
                template_id="template",
                expected_lifecycle={"mechanism": "new_mechanism"},
            )

    def test_unknown_mechanism_diverse_template_fails_fast(self) -> None:
        with self.assertRaisesRegex(ValueError, "No mechanism-diverse abstention intent mapping"):
            scenario_intent(
                family="mechanism_diverse_heldout",
                template_id="new_mechanism_diverse_template",
                expected_lifecycle={},
            )

    def test_empty_phase_probe_fallback_uses_last_question(self) -> None:
        scenario = {
            "scenario_id": "s",
            "expected_lifecycle": {},
            "oracle_events": [
                {"question": {"question_id": "q1", "phase": "first"}},
                {"question": {"question_id": "q2", "phase": "second"}},
            ],
        }

        self.assertEqual(_question_id_for_probe(scenario, "unknown_family"), "q2")

    def test_paired_deltas_requires_matching_scenario_sets(self) -> None:
        reference = [
            AbstentionDecision("s1", "cq", "f", "m", "", True, False, True, 1.0, 1.0, 0.0, 0.0),
        ]
        comparator = [
            AbstentionDecision("s2", "mem0", "f", "m", "", True, False, False, 0.0, 1.0, 0.0, 0.0),
        ]

        with self.assertRaisesRegex(ValueError, "Policy scenario sets differ"):
            _paired_deltas(reference, comparator, mechanism="m", metric_name="useful_abstention")

    def test_stratified_bucket_comparison_averages_mechanisms_not_pooled_counts(self) -> None:
        reference = [
            AbstentionDecision("a1", "cq", "f", "m1", "", False, True, False, 0.0, 0.0, 0.0, 1.0),
            AbstentionDecision("a2", "cq", "f", "m1", "", False, True, False, 0.0, 0.0, 0.0, 1.0),
            AbstentionDecision("b1", "cq", "f", "m2", "", False, True, True, 0.0, 0.0, 1.0, 1.0),
        ]
        comparator = [
            AbstentionDecision("a1", "mem0", "f", "m1", "", False, True, True, 0.0, 0.0, 1.0, 1.0),
            AbstentionDecision("a2", "mem0", "f", "m1", "", False, True, True, 0.0, 0.0, 1.0, 1.0),
            AbstentionDecision("b1", "mem0", "f", "m2", "", False, True, True, 0.0, 0.0, 1.0, 1.0),
        ]

        result = stratified_bucket_comparison(
            reference,
            comparator,
            mechanisms=("m1", "m2"),
            metric_name="harmful_abstention",
            resamples=100,
            seed=0,
        )

        self.assertEqual(result.point_estimate_delta, -0.5)
        self.assertEqual(result.scenario_count, 3)

    def test_replay_uses_tempfile_backed_runner_artifact(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set=POLICY_SET_PHASE_2_5,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            input_json = Path(tmpdir) / "tiny.json"
            input_csv = Path(tmpdir) / "tiny.csv"
            output_dir = Path(tmpdir) / "abstention"
            write_outputs(artifact, input_json, input_csv)

            written = run_replay([input_json], output_dir)

            self.assertEqual(len(written), 2)
            replay = json.loads((output_dir / "tiny_abstention.json").read_text(encoding="utf-8"))
            self.assertIn("consolidation_queue_vs_mem0_primary_abstention", replay["primary_comparisons"])
            with (output_dir / "tiny_abstention.csv").open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, REPLAY_CSV_FIELDNAMES)

    def test_runner_artifact_persists_primary_abstention_rows(self) -> None:
        artifact = build_run_artifact(
            10,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set=POLICY_SET_PHASE_2_5,
        )
        abstention = abstention_artifact_for_run(artifact)
        comparison = abstention["primary_comparisons"]["consolidation_queue_vs_mem0_primary_abstention"]

        self.assertIn("conflict_moderate", comparison["useful_mechanism_rows"])
        self.assertIn("conflict_witness", comparison["useful_mechanism_rows"])
        self.assertIsNotNone(comparison["harmful_bucket_row"]["one_sided_95_ucb"])

    def test_replay_emits_cq_ablation_pairwise_rows(self) -> None:
        artifact = build_run_artifact(
            10,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set=POLICY_SET_PHASE_2_5,
        )

        abstention = abstention_artifact_for_run(artifact)
        comparisons = abstention["pairwise_abstention_comparisons"]

        for comparator in (
            "cq_no_contestation_demotion",
            "cq_no_wider_scope_pending_override",
            "cq_no_pending_lookup_use",
            "cq_no_source_independence_gate",
        ):
            comparison_name = "consolidation_queue_vs_{}".format(comparator)
            self.assertIn(comparison_name, comparisons)
            comparison = comparisons[comparison_name]
            self.assertIn("conflict_moderate", comparison["useful_abstention_rows"])
            self.assertIn("one_sided_95_ucb", comparison["useful_abstention_rows"]["conflict_moderate"])
            self.assertIn("conflict_zero", comparison["harmful_abstention_rows"])
            self.assertIn("one_sided_95_ucb", comparison["harmful_abstention_rows"]["conflict_zero"])


if __name__ == "__main__":
    unittest.main()
