import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval.gold_loader import GoldCase
from cq.eval.external.longmemeval.scorer import (
    DEFAULT_K,
    PolicyPrediction,
    _percentile_index,
    degeneracy_diagnostic,
    load_policy_predictions,
    score_predictions,
)


class LongMemEvalScorerTests(unittest.TestCase):
    def test_perfect_retrieval_scores_all_hit_one(self) -> None:
        gold = [GoldCase("c1", "q", "Q", "A", ["s1", "s2"], ["s1", "s2"])]
        predictions = [
            PolicyPrediction(
                case_id="c1",
                policy_name="cq",
                predicted_session_ids_ranked=["s1", "s2"],
                candidate_answer="A",
                answer_correct=True,
            )
        ]
        result = score_predictions(predictions, gold, ks=(1, 2, 5))
        row = result["rows"][0]
        self.assertTrue(row["all_hit_at_2"])
        self.assertTrue(row["all_hit_at_5"])
        self.assertFalse(row["all_hit_at_1"])
        self.assertTrue(row["any_hit_at_1"])
        self.assertEqual(row["first_gold_rank"], 1)

    def test_no_overlap_records_zero_any_hit(self) -> None:
        gold = [GoldCase("c1", "q", "Q", "A", ["s1", "s2"], ["s1", "s2"])]
        predictions = [
            PolicyPrediction(
                case_id="c1",
                policy_name="cq",
                predicted_session_ids_ranked=["s9", "s10"],
                candidate_answer="wrong",
                answer_correct=False,
            )
        ]
        result = score_predictions(predictions, gold)
        row = result["rows"][0]
        self.assertFalse(row["any_hit_all_context"])
        self.assertFalse(row["all_hit_all_context"])
        self.assertIsNone(row["first_gold_rank"])

    def test_lookup_relevant_excludes_empty_gold(self) -> None:
        gold = [
            GoldCase("c1", "q", "Q1", "A1", ["s1"], ["s1"]),
            GoldCase("c2", "q", "Q2", "A2", [], ["s2"]),
        ]
        predictions = [
            PolicyPrediction("c1", "cq", ["s1"], "A1", True),
            PolicyPrediction("c2", "cq", ["s2"], "A2", True),
        ]
        result = score_predictions(predictions, gold)
        summary = result["summary"]
        self.assertEqual(summary["scored_rows"], 2)
        self.assertEqual(summary["lookup_relevant_rows"], 1)

    def test_prediction_outside_denominator_fails_closed(self) -> None:
        gold = [GoldCase("c1", "q", "Q1", "A1", ["s1"], ["s1"])]
        predictions = [
            PolicyPrediction("c1", "cq", ["s1"], "A1", True),
            PolicyPrediction("c-missing", "cq", ["s2"], "A2", True),
        ]

        with self.assertRaisesRegex(ValueError, "denominator check failed"):
            score_predictions(predictions, gold)

    def test_missing_prediction_for_expected_case_fails_closed(self) -> None:
        gold = [
            GoldCase("c1", "q", "Q1", "A1", ["s1"], ["s1"]),
            GoldCase("c2", "q", "Q2", "A2", ["s2"], ["s2"]),
        ]
        predictions = [PolicyPrediction("c1", "cq", ["s1"], "A1", True)]

        with self.assertRaisesRegex(ValueError, "incomplete predictions"):
            score_predictions(predictions, gold)

    def test_expected_case_ids_allow_agreed_subset_of_gold(self) -> None:
        gold = [
            GoldCase("c1", "q", "Q1", "A1", ["s1"], ["s1"]),
            GoldCase("c2", "q", "Q2", "A2", ["s2"], ["s2"]),
        ]
        predictions = [PolicyPrediction("c1", "cq", ["s1"], "A1", True)]

        result = score_predictions(predictions, gold, expected_case_ids=["c1"])

        self.assertEqual(result["summary"]["expected_case_count"], 1)
        self.assertEqual(result["summary"]["scored_rows"], 1)

    def test_duplicate_policy_case_prediction_fails_closed(self) -> None:
        gold = [GoldCase("c1", "q", "Q1", "A1", ["s1"], ["s1"])]
        predictions = [
            PolicyPrediction("c1", "cq", ["s1"], "A1", True),
            PolicyPrediction("c1", "cq", ["s1"], "A1", True),
        ]

        with self.assertRaisesRegex(ValueError, "duplicate predictions"):
            score_predictions(predictions, gold)

    def test_joint_counts_match_row_categories(self) -> None:
        gold = [
            GoldCase("c1", "q", "Q1", "A1", ["s1"], ["s1"]),
            GoldCase("c2", "q", "Q2", "A2", ["s2"], ["s2"]),
            GoldCase("c3", "q", "Q3", "A3", ["s3"], ["s3"]),
            GoldCase("c4", "q", "Q4", "A4", ["s4"], ["s4"]),
        ]
        predictions = [
            PolicyPrediction("c1", "cq", ["s1"], "A1", True),
            PolicyPrediction("c2", "cq", ["x"], "A2", True),
            PolicyPrediction("c3", "cq", ["s3"], "wrong", False),
            PolicyPrediction("c4", "cq", ["x"], "wrong", False),
        ]
        result = score_predictions(predictions, gold, ks=(1,))
        joint = result["summary"]["metrics"]["joint_counts_all_context"]
        self.assertEqual(joint["answer_correct_and_pflc_hit"], 1)
        self.assertEqual(joint["answer_correct_and_pflc_miss"], 1)
        self.assertEqual(joint["answer_wrong_and_pflc_hit"], 1)
        self.assertEqual(joint["answer_wrong_and_pflc_miss"], 1)

    def test_degeneracy_diagnostic_reports_full_overlap(self) -> None:
        gold = [
            GoldCase("c1", "knowledge-update", "Q", "A", ["s1", "s2"], ["s1", "s2"]),
            GoldCase("c2", "knowledge-update", "Q", "A", ["s3"], ["s3", "s4"]),
            GoldCase("c3", "temporal-reasoning", "Q", "A", [], ["s5"]),
        ]
        diagnostic = degeneracy_diagnostic(gold)
        self.assertEqual(diagnostic["total_cases"], 3)
        self.assertEqual(diagnostic["answer_equals_haystack_case_count"], 1)
        self.assertEqual(
            diagnostic["by_question_type"]["knowledge-update"],
            {"total": 2, "answer_equals_haystack": 1},
        )

    def test_default_k_includes_locked_cutoffs(self) -> None:
        self.assertEqual(DEFAULT_K, (1, 5, 10, 20, 50))

    def test_bootstrap_percentile_index_uses_samples_minus_one_convention(self) -> None:
        self.assertEqual(_percentile_index(100, 0.025), 2)
        self.assertEqual(_percentile_index(100, 0.975), 96)
        self.assertEqual(_percentile_index(5000, 0.025), 124)
        self.assertEqual(_percentile_index(5000, 0.975), 4874)

    def test_load_policy_predictions_rejects_malformed_payloads(self) -> None:
        malformed_rows = [
            {
                "case_id": "",
                "policy_name": "cq",
                "predicted_session_ids_ranked": [],
                "answer_correct": True,
            },
            {
                "case_id": "c1",
                "policy_name": "cq",
                "predicted_session_ids_ranked": "s1",
                "answer_correct": True,
            },
            {
                "case_id": "c1",
                "policy_name": "cq",
                "predicted_session_ids_ranked": [1],
                "answer_correct": True,
            },
            {
                "case_id": "c1",
                "policy_name": "cq",
                "predicted_session_ids_ranked": [],
                "answer_correct": "false",
            },
            {
                "case_id": "c1",
                "policy_name": "cq",
                "predicted_session_ids_ranked": [],
                "candidate_answer": 42,
                "answer_correct": False,
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            for index, row in enumerate(malformed_rows):
                path = Path(tmpdir) / "prediction_{}.json".format(index)
                path.write_text(json.dumps({"predictions": [row]}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_policy_predictions(path)

    def test_load_policy_predictions_accepts_valid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "predictions.json"
            path.write_text(
                json.dumps(
                    {
                        "predictions": [
                            {
                                "case_id": "c1",
                                "policy_name": "cq",
                                "predicted_session_ids_ranked": ["s1"],
                                "candidate_answer": "A",
                                "answer_correct": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            predictions = load_policy_predictions(path)

        self.assertEqual(predictions, [PolicyPrediction("c1", "cq", ["s1"], "A", False)])


if __name__ == "__main__":
    unittest.main()
