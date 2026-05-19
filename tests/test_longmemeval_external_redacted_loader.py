import gzip
import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval.redacted_loader import (
    RedactionAccessError,
    load_redacted_cases,
    sha256_value,
)


class LongMemEvalRedactedLoaderTests(unittest.TestCase):
    def test_loader_hashes_answer_fields_and_removes_raw_values(self) -> None:
        payload = [
            {
                "question_id": "case-1",
                "question_type": "knowledge-update",
                "question": "Where did Rachel move?",
                "answer": "the suburbs",
                "answer_session_ids": ["s1", "s2"],
                "haystack_sessions": [["old"], ["new"]],
                "haystack_dates": ["2024-01-01", "2024-02-01"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "oracle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            cases = load_redacted_cases(path)

        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case.case_id, "case-1")
        self.assertEqual(case.answer_redaction.sha256, sha256_value("the suburbs"))
        self.assertEqual(
            case.answer_session_ids_redaction.sha256,
            sha256_value(["s1", "s2"]),
        )
        self.assertNotIn("answer", case.raw)
        self.assertNotIn("answer_session_ids", case.raw)
        self.assertIn("answer_redaction", case.raw)

    def test_raw_recursively_scrubs_nested_answer_material(self) -> None:
        payload = [
            {
                "question_id": "case-1",
                "question_type": "knowledge-update",
                "question": "q",
                "answer": "top-level",
                "answer_session_ids": ["s1"],
                "metadata": {
                    "gold": "nested gold",
                    "ground_truth_answer": "nested answer",
                    "safe_note": "keep me",
                },
                "haystack_sessions": [
                    {
                        "text": "annotation context is retained",
                        "reference_answer": "nested forbidden",
                    }
                ],
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "oracle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            case = load_redacted_cases(path)[0]

        self.assertNotIn("gold", case.raw["metadata"])
        self.assertIn("gold_redaction", case.raw["metadata"])
        self.assertNotIn("ground_truth_answer", case.raw["metadata"])
        self.assertIn("ground_truth_answer_redaction", case.raw["metadata"])
        self.assertEqual(case.raw["metadata"]["safe_note"], "keep me")
        self.assertEqual(
            case.raw["haystack_sessions"][0]["text"],
            "annotation context is retained",
        )
        self.assertNotIn("reference_answer", case.raw["haystack_sessions"][0])
        self.assertIn("reference_answer_redaction", case.raw["haystack_sessions"][0])

    def test_redactor_scrubs_sibling_gold_key_names(self) -> None:
        payload = [
            {
                "question_id": "case-1",
                "question_type": "knowledge-update",
                "question": "q",
                "answer": "top-level",
                "answer_session_ids": ["s1"],
                "metadata": {
                    "solution": "hidden",
                    "correct_answer": "hidden",
                    "evidence_session_ids": ["s1"],
                    "target_answer": "hidden",
                    "expected_output": "hidden",
                    "oracle_output": "hidden",
                    "truth_value": True,
                    "verdict": "correct",
                    "safe_note": "keep me",
                },
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "oracle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            case = load_redacted_cases(path)[0]

        for key in (
            "solution",
            "correct_answer",
            "evidence_session_ids",
            "target_answer",
            "expected_output",
            "oracle_output",
            "truth_value",
            "verdict",
        ):
            self.assertNotIn(key, case.raw["metadata"])
            self.assertIn("{}_redaction".format(key), case.raw["metadata"])
        self.assertEqual(case.raw["metadata"]["safe_note"], "keep me")

    def test_accessing_redacted_values_raises(self) -> None:
        payload = [
            {
                "question_id": "case-1",
                "question_type": "knowledge-update",
                "question": "q",
                "answer": "secret",
                "answer_session_ids": ["s1"],
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "oracle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            case = load_redacted_cases(path)[0]

        with self.assertRaises(RedactionAccessError):
            _ = case.answer
        with self.assertRaises(RedactionAccessError):
            _ = case.answer_session_ids
        with self.assertRaises(RedactionAccessError):
            str(case.answer_redaction)
        with self.assertRaises(RedactionAccessError):
            bool(case.answer_session_ids_redaction)

    def test_jsonl_questions_without_answer_session_ids_are_supported(self) -> None:
        row = {
            "id": "v2-1",
            "question_type": "static-environment",
            "question": "q",
            "answer": "a",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "questions.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            case = load_redacted_cases(path)[0]

        self.assertEqual(case.case_id, "v2-1")
        self.assertTrue(case.answer_redaction.present)
        self.assertFalse(case.answer_session_ids_redaction.present)

    def test_jsonl_gz_questions_are_line_split_after_decompression(self) -> None:
        rows = [
            {
                "id": "v2-1",
                "question_type": "static-environment",
                "question": "q1",
                "answer": "a1",
            },
            {
                "id": "v2-2",
                "question_type": "procedure",
                "question": "q2",
                "answer": "a2",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "questions.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
            cases = load_redacted_cases(path)

        self.assertEqual([case.case_id for case in cases], ["v2-1", "v2-2"])


if __name__ == "__main__":
    unittest.main()
