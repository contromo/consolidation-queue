import unittest

from cq.eval.external.longmemeval.judge_stability import (
    CORRECT_VERDICT,
    INCORRECT_VERDICT,
    INDETERMINATE_VERDICT,
    JUDGE_AGREEMENT_FLOOR,
    CalibrationCase,
    JudgeVerdict,
    parse_verdict,
    render_judge_prompt,
    stability_report,
)


class LongMemEvalJudgeStabilityTests(unittest.TestCase):
    def test_parse_verdict_handles_common_shapes(self) -> None:
        self.assertEqual(parse_verdict("correct"), CORRECT_VERDICT)
        self.assertEqual(parse_verdict("Correct\nbecause..."), CORRECT_VERDICT)
        self.assertEqual(parse_verdict("incorrect."), INCORRECT_VERDICT)
        self.assertEqual(parse_verdict(" INCORRECT  \nfollow-up"), INCORRECT_VERDICT)
        self.assertEqual(parse_verdict("maybe"), INDETERMINATE_VERDICT)
        self.assertEqual(parse_verdict(""), INDETERMINATE_VERDICT)

    def test_render_judge_prompt_includes_all_three_fields(self) -> None:
        case = CalibrationCase("c1", "Q?", "Gold.", "Cand.")
        prompt = render_judge_prompt(case)
        self.assertIn("Q?", prompt)
        self.assertIn("Gold.", prompt)
        self.assertIn("Cand.", prompt)
        self.assertIn("correct", prompt)

    def test_stability_report_local_cross_check_passes_threshold(self) -> None:
        primary = [
            JudgeVerdict("c1", "primary", CORRECT_VERDICT, "correct"),
            JudgeVerdict("c2", "primary", INCORRECT_VERDICT, "incorrect"),
            JudgeVerdict("c3", "primary", CORRECT_VERDICT, "correct"),
            JudgeVerdict("c4", "primary", CORRECT_VERDICT, "correct"),
            JudgeVerdict("c5", "primary", INCORRECT_VERDICT, "incorrect"),
        ]
        secondary = [
            JudgeVerdict("c1", "secondary", CORRECT_VERDICT, "correct"),
            JudgeVerdict("c2", "secondary", INCORRECT_VERDICT, "incorrect"),
            JudgeVerdict("c3", "secondary", CORRECT_VERDICT, "correct"),
            JudgeVerdict("c4", "secondary", CORRECT_VERDICT, "correct"),
            JudgeVerdict("c5", "secondary", CORRECT_VERDICT, "correct"),
        ]
        report = stability_report(
            primary,
            secondary,
            primary_model_id="primary",
            secondary_model_id="secondary",
        )
        self.assertEqual(report["paired_total"], 5)
        self.assertEqual(report["cross_judge_matches"], 4)
        self.assertAlmostEqual(report["cross_judge_agreement"], 0.8)
        self.assertEqual(report["calibration_path"], "judge_stability_local_cross_check")
        self.assertTrue(report["kill_criterion_10_triggered"])

    def test_stability_report_reference_calibration_path(self) -> None:
        primary = [JudgeVerdict("c1", "p", CORRECT_VERDICT, "correct")]
        secondary = [JudgeVerdict("c1", "s", INCORRECT_VERDICT, "incorrect")]
        report = stability_report(
            primary,
            secondary,
            primary_model_id="p",
            secondary_model_id="s",
            reference_verdicts={"c1": CORRECT_VERDICT},
        )
        self.assertEqual(report["calibration_path"], "reference_calibration")
        self.assertEqual(report["reference_verdicts_present"], 1)
        self.assertEqual(report["reference_matches"], 1)
        self.assertEqual(report["primary_agreement"], 1.0)
        self.assertFalse(report["kill_criterion_10_triggered"])

    def test_indeterminate_verdict_is_counted(self) -> None:
        primary = [JudgeVerdict("c1", "p", INDETERMINATE_VERDICT, "?")]
        secondary = [JudgeVerdict("c1", "s", CORRECT_VERDICT, "correct")]
        report = stability_report(
            primary,
            secondary,
            primary_model_id="p",
            secondary_model_id="s",
        )
        self.assertEqual(report["indeterminate_count"], 1)
        self.assertFalse(report["paired_rows"][0]["cross_judge_match"])

    def test_judge_agreement_floor_constant(self) -> None:
        self.assertEqual(JUDGE_AGREEMENT_FLOOR, 0.85)


if __name__ == "__main__":
    unittest.main()
