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


if __name__ == "__main__":
    unittest.main()

