import csv
import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval import annotator_path_a as path_a
from cq.eval.external.longmemeval.verifier import forbidden_answer_key_paths


class LongMemEvalAnnotatorPathATests(unittest.TestCase):
    def test_path_a_outputs_byte_stable_answer_blind_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            oracle = tmp / "oracle.json"
            feasibility = tmp / "feasibility.csv"
            out1 = tmp / "a1.json"
            out2 = tmp / "a2.json"
            oracle.write_text(json.dumps(_fixture_rows()), encoding="utf-8")
            _write_feasibility(feasibility)

            self.assertEqual(
                path_a.main(
                    [
                        "--oracle-json",
                        str(oracle),
                        "--feasibility-csv",
                        str(feasibility),
                        "--output-json",
                        str(out1),
                    ]
                ),
                0,
            )
            self.assertEqual(
                path_a.main(
                    [
                        "--oracle-json",
                        str(oracle),
                        "--feasibility-csv",
                        str(feasibility),
                        "--output-json",
                        str(out2),
                    ]
                ),
                0,
            )

            self.assertEqual(out1.read_bytes(), out2.read_bytes())
            payload = json.loads(out1.read_text(encoding="utf-8"))

        self.assertEqual(payload["method_id"], path_a.METHOD_ID)
        self.assertEqual(payload["summary"]["annotation_count"], 1)
        row = payload["annotations"][0]
        self.assertEqual(row["case_id"], "case-1")
        self.assertEqual(row["relevant_canonical_id"], "lme-personal-best-time-charity-5k-run")
        self.assertEqual(row["contradiction_edges"], [["obs_0", "obs_1"]])
        self.assertEqual(len(row["candidate_events"]), 2)
        self.assertEqual(forbidden_answer_key_paths(payload), [])


def _write_feasibility(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question_id", "label"])
        writer.writeheader()
        writer.writerow({"question_id": "case-1", "label": "contradiction_edge"})
        writer.writerow({"question_id": "case-2", "label": "out_of_scope"})


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
        },
        {
            "question_id": "case-2",
            "question_type": "single-session-user",
            "question": "What color is my bike?",
            "answer": "blue",
            "answer_session_ids": ["s3"],
            "haystack_session_ids": ["s3"],
            "haystack_dates": ["2023/05/28"],
            "haystack_sessions": [[{"role": "user", "content": "My bike is blue."}]],
        },
    ]


if __name__ == "__main__":
    unittest.main()
