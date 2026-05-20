import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from cq.eval.external.longmemeval.adapter import adapt_annotations
from cq.eval.external.longmemeval.transfer import (
    DEV_OVERRIDE_ENV,
    FOLLOWUP_CQ_POLICY,
    HEADLINE_METRIC,
    HEADLINE_POLICY,
    LongMemEvalTransferError,
    REFLECTION_CAPPED_POLICY,
    REFLECTION_POLICY,
    _assert_candidate_stream_unchanged,
    _bucket_verdict,
    _followup_outcome,
    _load_gold_cases_for_transfer,
    _predicted_session_ids,
    _reflection_capped_is_strict_subset,
    _require_dev_override,
    _scenario_candidate_stream_sha256,
    build_sensitivity_cells,
    validate_judge_report,
)


class LongMemEvalTransferTests(unittest.TestCase):
    def test_validate_judge_report_requires_passed_kill_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "judge_report.json"
            path.write_text(
                json.dumps(
                    {
                        "kill_criterion_10_triggered": False,
                        "support_count": 25,
                        "synthetic_correctness_floor": {
                            "applicable": True,
                            "passed": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = validate_judge_report(path)

        self.assertFalse(report["kill_criterion_10_triggered"])

    def test_validate_judge_report_rejects_failed_synthetic_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "judge_report.json"
            path.write_text(
                json.dumps(
                    {
                        "kill_criterion_10_triggered": False,
                        "support_count": 25,
                        "synthetic_correctness_floor": {
                            "applicable": True,
                            "passed": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(LongMemEvalTransferError):
                validate_judge_report(path)

    def test_validate_judge_report_rejects_missing_synthetic_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "judge_report.json"
            path.write_text(
                json.dumps(
                    {
                        "kill_criterion_10_triggered": False,
                        "support_count": 25,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(LongMemEvalTransferError):
                validate_judge_report(path)

    def test_build_sensitivity_cells_keeps_only_meaningful_contract_variants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            annotations_path = Path(tmpdir) / "annotations.json"
            annotations_path.write_text(
                json.dumps({"annotations": [_annotation_row("c1")]}),
                encoding="utf-8",
            )

            cells = build_sensitivity_cells(
                include_sensitivity_cells=True,
                primary_annotations_path=annotations_path,
            )

        self.assertEqual([cell["cell_id"] for cell in cells], [
            "primary_contract",
            "path_a_only_denominator",
            "path_b_only_denominator",
        ])
        primary = cells[0]["annotations"][0]
        self.assertEqual(primary["relevant_canonical_id"], "slot-c1")

    def test_headline_metric_uses_pflc_side_metric(self) -> None:
        self.assertEqual(HEADLINE_METRIC, "all_hit_at_50")

    def test_predicted_session_ids_preserve_unique_resolved_order(self) -> None:
        result = _predicted_session_ids(
            ["c2", "c1", "c2", "missing"],
            {"c1": "s1", "c2": "s2"},
        )

        self.assertEqual(result, ["s2", "s1"])

    def test_missing_oracle_json_reports_setup_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing_oracle.json"

            with self.assertRaisesRegex(
                LongMemEvalTransferError,
                "LongMemEval oracle JSON is missing",
            ):
                _load_gold_cases_for_transfer(missing)

    def test_dev_override_required_for_runtime_escape_hatches(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(LongMemEvalTransferError, DEV_OVERRIDE_ENV):
                _require_dev_override("--skip-judge-validation")

        with mock.patch.dict("os.environ", {DEV_OVERRIDE_ENV: "1"}, clear=True):
            _require_dev_override("--skip-judge-validation")

    def test_candidate_stream_mutation_check_detects_policy_side_mutation(self) -> None:
        scenarios, _streams = adapt_annotations([_annotation_row("c1")])
        scenario = scenarios[0]
        expected_hash = _scenario_candidate_stream_sha256(scenario)
        scenario.oracle_events[0].candidate.raw_claim = "Mutated by policy"

        with self.assertRaisesRegex(LongMemEvalTransferError, "mutated the LongMemEval candidate stream"):
            _assert_candidate_stream_unchanged(
                scenario,
                expected_hash,
                policy_name="bad_policy",
                cell_id="primary_contract",
            )

    def test_bucket_verdict_reports_sign_flip(self) -> None:
        pairwise = {
            "primary_contract": {
                "cq_vs_reflection": {"sign": "positive"},
            },
            "path_a_only_denominator": {
                "cq_vs_reflection": {"sign": "negative"},
            },
        }

        bucket = _bucket_verdict(
            pairwise,
            judge_report={"support_count": 25},
            run_local_judge=True,
        )

        self.assertEqual(bucket["bucket"], "C")

    def test_reflection_capped_subset_helper_requires_strict_subset(self) -> None:
        rows = [
            _row("case-1", REFLECTION_POLICY, True, ["c1", "c2"]),
            _row("case-1", REFLECTION_CAPPED_POLICY, False, ["c2"]),
        ]

        self.assertTrue(_reflection_capped_is_strict_subset(rows))

    def test_followup_outcome_confirms_interface_repair_when_cardinality_control_fails(self) -> None:
        payloads = {
            cell_id: {
                "rows": [
                    _row("case-1", HEADLINE_POLICY, False, ["c1"]),
                    _row("case-1", FOLLOWUP_CQ_POLICY, True, ["c1", "c2"]),
                    _row("case-1", REFLECTION_POLICY, True, ["c1", "c2"]),
                    _row("case-1", REFLECTION_CAPPED_POLICY, False, ["c2"]),
                    _row("case-2", HEADLINE_POLICY, False, ["c3"]),
                    _row("case-2", FOLLOWUP_CQ_POLICY, True, ["c3", "c4"]),
                    _row("case-2", REFLECTION_POLICY, True, ["c3", "c4"]),
                    _row("case-2", REFLECTION_CAPPED_POLICY, False, ["c4"]),
                ]
            }
            for cell_id in [
                "primary_contract",
                "path_a_only_denominator",
                "path_b_only_denominator",
            ]
        }

        outcome = _followup_outcome(payloads)

        self.assertEqual(outcome["bucket"], "A")
        self.assertTrue(outcome["reflection_capped_strict_subset_on_primary"])


def _annotation_row(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "question_type": "knowledge-update",
        "question": "Question?",
        "in_denominator": True,
        "mechanism_code": "contradiction_edge",
        "relevant_canonical_id": "slot-{}".format(case_id),
        "scope_level": "project",
        "scope_key": "project:x",
        "claim_type": "world_fact",
        "contradiction_edges": [],
        "candidate_events": [
            {
                "event_id": "obs_0",
                "session_id": "s1",
                "raw_claim": "Claim",
                "canonical_id": "slot-{}".format(case_id),
                "claim_type": "world_fact",
                "scope_level": "project",
                "scope_key": "project:x",
                "confidence": 0.7,
                "contradicts_event_ids": [],
            }
        ],
    }


def _row(case_id: str, policy_name: str, all_hit: bool, resolved_candidate_ids: list[str]) -> dict:
    return {
        "case_id": case_id,
        "policy_name": policy_name,
        HEADLINE_METRIC: all_hit,
        "resolved_candidate_ids": resolved_candidate_ids,
    }


if __name__ == "__main__":
    unittest.main()
