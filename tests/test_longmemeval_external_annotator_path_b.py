import csv
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval import annotator_path_a as path_a
from cq.eval.external.longmemeval import annotator_path_b as path_b
from cq.eval.external.longmemeval.dual_path_audit import audit_annotation_maps


class LongMemEvalAnnotatorPathBTests(unittest.TestCase):
    def test_path_b_reproduces_and_agrees_with_path_a_on_fixture_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            oracle = tmp / "oracle.json"
            feasibility = tmp / "feasibility.csv"
            out_a = tmp / "a.json"
            out_b = tmp / "b.json"
            out_b2 = tmp / "b2.json"
            oracle.write_text(json.dumps(_fixture_rows()), encoding="utf-8")
            _write_feasibility(feasibility)

            path_a.main(
                [
                    "--oracle-json",
                    str(oracle),
                    "--feasibility-csv",
                    str(feasibility),
                    "--output-json",
                    str(out_a),
                ]
            )
            path_b.main(
                [
                    "--oracle-json",
                    str(oracle),
                    "--feasibility-csv",
                    str(feasibility),
                    "--output-json",
                    str(out_b),
                ]
            )
            path_b.main(
                [
                    "--oracle-json",
                    str(oracle),
                    "--feasibility-csv",
                    str(feasibility),
                    "--output-json",
                    str(out_b2),
                ]
            )
            payload_a = json.loads(out_a.read_text(encoding="utf-8"))
            payload_b = json.loads(out_b.read_text(encoding="utf-8"))
            out_b_bytes = out_b.read_bytes()
            out_b2_bytes = out_b2.read_bytes()

        self.assertEqual(out_b_bytes, out_b2_bytes)
        self.assertEqual(payload_b["method_id"], path_b.METHOD_ID)
        report, agreed = audit_annotation_maps(
            {row["case_id"]: row for row in payload_a["annotations"]},
            {row["case_id"]: row for row in payload_b["annotations"]},
        )
        self.assertEqual(report["summary"]["agreement_rate"], 1.0)
        self.assertEqual(len(agreed), 1)
        self.assertEqual(
            agreed[0]["relevant_canonical_id"],
            "lme-personal-best-time-charity-5k-run",
        )

    def test_path_b_does_not_import_path_a_or_call_its_canonicalizer(self) -> None:
        source = inspect.getsource(path_b)
        self.assertNotIn("annotator_path_a", source)
        self.assertNotIn("derive_relevant_canonical_id", source)


def _write_feasibility(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question_id", "label"])
        writer.writeheader()
        writer.writerow({"question_id": "case-1", "label": "contradiction_edge"})


def _fixture_rows() -> list[dict]:
    return [
        {
            "question_id": "case-1",
            "question_type": "knowledge-update",
            "question": "What was my personal best time in the charity 5K run?",
            "answer": "25:50",
            "answer_session_ids": ["s1", "s2"],
            "haystack_session_ids": ["s1", "s2"],
            "haystack_dates": ["2023/05/25", "2023/05/27"],
            "haystack_sessions": [
                [{"role": "user", "content": "My personal best time in the charity 5K run is 27:12."}],
                [{"role": "user", "content": "I am hoping to beat my personal best time of 25:50."}],
            ],
        }
    ]


if __name__ == "__main__":
    unittest.main()
