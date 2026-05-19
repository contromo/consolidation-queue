import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval.transfer import (
    LongMemEvalTransferError,
    _bucket_verdict,
    _predicted_session_ids,
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

    def test_build_sensitivity_cells_applies_contract_variants(self) -> None:
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

        self.assertEqual([cell["cell_id"] for cell in cells[:3]], [
            "primary_contract",
            "alternate_canonicalizer",
            "flat_user_global_scope",
        ])
        primary = cells[0]["annotations"][0]
        alternate = cells[1]["annotations"][0]
        flat = cells[2]["annotations"][0]
        self.assertEqual(primary["relevant_canonical_id"], "slot-c1")
        self.assertEqual(alternate["relevant_canonical_id"], "alt-lme-c1")
        self.assertEqual(alternate["candidate_events"][0]["canonical_id"], "alt-lme-c1")
        self.assertEqual(flat["scope_level"], "user_global")
        self.assertEqual(flat["candidate_events"][0]["scope_key"], "longmemeval:user")

    def test_predicted_session_ids_preserve_unique_resolved_order(self) -> None:
        result = _predicted_session_ids(
            ["c2", "c1", "c2", "missing"],
            {"c1": "s1", "c2": "s2"},
        )

        self.assertEqual(result, ["s2", "s1"])

    def test_bucket_verdict_reports_sign_flip(self) -> None:
        pairwise = {
            "primary_contract": {
                "cq_vs_reflection": {"sign": "positive"},
            },
            "alternate_canonicalizer": {
                "cq_vs_reflection": {"sign": "negative"},
            },
        }

        bucket = _bucket_verdict(
            pairwise,
            judge_report={"support_count": 25},
            run_local_judge=True,
        )

        self.assertEqual(bucket["bucket"], "C")


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


if __name__ == "__main__":
    unittest.main()
