import unittest

from cq.eval.external.longmemeval.judge_stability import (
    CORRECT_VERDICT,
    INCORRECT_VERDICT,
    INDETERMINATE_VERDICT,
    JUDGE_AGREEMENT_FLOOR,
    CalibrationCase,
    JudgeVerdict,
    JudgeStabilityError,
    parse_verdict,
    render_judge_prompt,
    run_judge,
    stability_report,
    verdict_artifact_row,
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

    def test_render_judge_prompt_preserves_literal_braces(self) -> None:
        case = CalibrationCase(
            "c1",
            "What does {x} mean?",
            "Use {'answer': 4}.",
            "I think {\"answer\": 4}.",
        )
        prompt = render_judge_prompt(case)

        self.assertIn("What does {x} mean?", prompt)
        self.assertIn("Use {'answer': 4}.", prompt)
        self.assertIn('I think {"answer": 4}.', prompt)

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
        self.assertEqual(report["support_count"], 5)
        self.assertFalse(report["support_count_check_passed"])
        self.assertTrue(report["kill_criterion_10_triggered"])

    def test_stability_report_reference_calibration_path_fails_with_too_few_cases(self) -> None:
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
        self.assertFalse(report["support_count_check_passed"])
        self.assertTrue(report["kill_criterion_10_triggered"])

    def test_stability_report_reference_calibration_passes_with_locked_support(self) -> None:
        primary = [
            JudgeVerdict("c{}".format(index), "p", CORRECT_VERDICT, "correct")
            for index in range(20)
        ]
        secondary = [
            JudgeVerdict("c{}".format(index), "s", INCORRECT_VERDICT, "incorrect")
            for index in range(20)
        ]
        report = stability_report(
            primary,
            secondary,
            primary_model_id="p",
            secondary_model_id="s",
            reference_verdicts={"c{}".format(index): CORRECT_VERDICT for index in range(20)},
        )

        self.assertEqual(report["reference_verdicts_present"], 20)
        self.assertTrue(report["support_count_check_passed"])
        self.assertFalse(report["kill_criterion_10_triggered"])

    def test_stability_report_local_cross_check_passes_with_locked_support(self) -> None:
        primary = [
            JudgeVerdict("c{}".format(index), "p", CORRECT_VERDICT, "correct")
            for index in range(20)
        ]
        secondary = [
            JudgeVerdict("c{}".format(index), "s", CORRECT_VERDICT, "correct")
            for index in range(20)
        ]
        report = stability_report(
            primary,
            secondary,
            primary_model_id="p",
            secondary_model_id="s",
        )

        self.assertEqual(report["paired_total"], 20)
        self.assertTrue(report["support_count_check_passed"])
        self.assertFalse(report["kill_criterion_10_triggered"])

    def test_empty_reference_verdicts_uses_reference_path_and_fails_closed(self) -> None:
        primary = [JudgeVerdict("c1", "p", CORRECT_VERDICT, "correct")]
        secondary = [JudgeVerdict("c1", "s", CORRECT_VERDICT, "correct")]
        report = stability_report(
            primary,
            secondary,
            primary_model_id="p",
            secondary_model_id="s",
            reference_verdicts={},
        )

        self.assertEqual(report["calibration_path"], "reference_calibration")
        self.assertIsNone(report["primary_agreement"])
        self.assertTrue(report["kill_criterion_10_triggered"])

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

    def test_run_judge_rejects_non_loopback_base_url(self) -> None:
        with self.assertRaises(JudgeStabilityError):
            run_judge(
                [CalibrationCase("c1", "Q?", "Gold", "Candidate")],
                model_id="qwen2.5:7b-instruct-q4_K_M",
                base_url="https://example.com",
            )

    def test_verdict_artifact_row_hashes_raw_response_without_persisting_text(self) -> None:
        row = verdict_artifact_row(JudgeVerdict("c1", "p", CORRECT_VERDICT, "correct because gold"))

        self.assertEqual(row["case_id"], "c1")
        self.assertEqual(row["verdict"], CORRECT_VERDICT)
        self.assertEqual(row["raw_response_bytes"], len("correct because gold"))
        self.assertNotIn("raw_response", row)


if __name__ == "__main__":
    unittest.main()
