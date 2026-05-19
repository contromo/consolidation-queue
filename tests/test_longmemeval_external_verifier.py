import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval import verifier


class LongMemEvalVerifierTests(unittest.TestCase):
    def test_binomial_upper_tail(self) -> None:
        self.assertAlmostEqual(verifier.binomial_upper_tail(4, 4, 0.5), 0.0625)
        self.assertAlmostEqual(verifier.binomial_upper_tail(3, 4, 0.5), 0.3125)

    def test_forbidden_answer_key_paths_are_recursive(self) -> None:
        payload = [
            {
                "case_id": "c1",
                "nested": {
                    "answer": "secret",
                    "ground_truth": "secret",
                    "gold_slot": "secret",
                    "answer_redaction": {"sha256": "safe"},
                },
            }
        ]
        self.assertEqual(
            verifier.forbidden_answer_key_paths(payload),
            [
                "[0].nested.answer",
                "[0].nested.ground_truth",
                "[0].nested.gold_slot",
            ],
        )

    def test_report_fails_closed_without_audit_summary(self) -> None:
        annotations = [{"case_id": str(index)} for index in range(9)]
        report = verifier.build_verifier_report(annotations)

        self.assertFalse(report["audit_summary_present"])
        self.assertFalse(report["audit_summary_check_passed"])
        self.assertFalse(report["agreement_rate_check_passed"])
        self.assertFalse(report["binomial_check_passed"])
        self.assertFalse(report["verifier_passed"])

    def test_report_passes_with_high_agreement_and_no_answer_keys(self) -> None:
        annotations = [{"case_id": str(index)} for index in range(9)]
        report = verifier.build_verifier_report(
            annotations,
            audit_summary={
                "agreement_count": 9,
                "comparable_in_denominator_count": 10,
            },
        )

        self.assertTrue(report["hidden_answer_check_passed"])
        self.assertTrue(report["agreement_rate_check_passed"])
        self.assertTrue(report["binomial_check_passed"])
        self.assertTrue(report["verifier_passed"])

    def test_binomial_check_is_diagnostic_not_hard_gate(self) -> None:
        annotations = [{"case_id": str(index)} for index in range(8)]
        report = verifier.build_verifier_report(
            annotations,
            audit_summary={
                "agreement_count": 8,
                "comparable_in_denominator_count": 10,
            },
        )

        self.assertTrue(report["agreement_rate_check_passed"])
        self.assertFalse(report["binomial_check_passed"])
        self.assertTrue(report["verifier_passed"])

    def test_report_fails_if_answer_field_leaks(self) -> None:
        report = verifier.build_verifier_report(
            [{"case_id": "c1", "answer": "secret"}],
            audit_summary={
                "agreement_count": 9,
                "comparable_in_denominator_count": 10,
            },
        )

        self.assertFalse(report["hidden_answer_check_passed"])
        self.assertFalse(report["verifier_passed"])

    def test_report_fails_if_annotator_source_reads_answer_side_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "annotator.py"
            source.write_text("value = case.answer_redaction.sha256\n", encoding="utf-8")

            report = verifier.build_verifier_report(
                [{"case_id": "c1"}],
                audit_summary={
                    "agreement_count": 8,
                    "comparable_in_denominator_count": 10,
                },
                source_paths=[source],
            )

        self.assertFalse(report["hidden_answer_check_passed"])
        self.assertIn("answer_redaction_reference", report["forbidden_answer_source_references"][0])
        self.assertFalse(report["verifier_passed"])


if __name__ == "__main__":
    unittest.main()
