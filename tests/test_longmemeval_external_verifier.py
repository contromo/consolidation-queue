import unittest

from cq.eval.external.longmemeval import verifier


class LongMemEvalVerifierTests(unittest.TestCase):
    def test_binomial_upper_tail(self) -> None:
        self.assertAlmostEqual(verifier.binomial_upper_tail(4, 4, 0.5), 0.0625)
        self.assertAlmostEqual(verifier.binomial_upper_tail(3, 4, 0.5), 0.3125)

    def test_forbidden_answer_key_paths_are_recursive(self) -> None:
        payload = [{"case_id": "c1", "nested": {"answer": "secret"}}]
        self.assertEqual(
            verifier.forbidden_answer_key_paths(payload),
            ["[0].nested.answer"],
        )

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


if __name__ == "__main__":
    unittest.main()

