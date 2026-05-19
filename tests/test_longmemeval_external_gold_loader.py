import importlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval.gold_loader import (
    GoldCase,
    gold_answers_by_case_id,
    gold_session_ids_by_case_id,
    load_gold_cases,
)


class LongMemEvalGoldLoaderTests(unittest.TestCase):
    def test_load_gold_cases_round_trip(self) -> None:
        payload = [
            {
                "question_id": "case-1",
                "question_type": "knowledge-update",
                "question": "How many bikes do I own?",
                "answer": "4",
                "answer_session_ids": ["s1", "s2"],
                "haystack_session_ids": ["s1", "s2"],
            },
            {
                "question_id": "case-2",
                "question_type": "temporal-reasoning",
                "question": "When did I move?",
                "answer": "March",
                "answer_session_ids": ["s3"],
                "haystack_session_ids": ["s3", "s4"],
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "oracle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            cases = load_gold_cases(path)

        self.assertEqual([case.case_id for case in cases], ["case-1", "case-2"])
        self.assertEqual(cases[0].answer_session_ids, ["s1", "s2"])
        self.assertEqual(cases[1].haystack_session_ids, ["s3", "s4"])

    def test_helpers_filter_by_restrict_to(self) -> None:
        cases = [
            GoldCase("c1", "q", "Q1", "A1", ["s1"], ["s1"]),
            GoldCase("c2", "q", "Q2", "A2", ["s2"], ["s2"]),
        ]
        ids = gold_session_ids_by_case_id(cases, restrict_to=["c1"])
        answers = gold_answers_by_case_id(cases, restrict_to=["c1"])
        self.assertEqual(set(ids), {"c1"})
        self.assertEqual(set(answers), {"c1"})

    def test_missing_question_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "oracle.json"
            path.write_text(json.dumps([{"question_type": "x"}]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_gold_cases(path)

    def test_gold_loader_is_not_imported_by_protected_modules(self) -> None:
        allowed_importers = {
            "cq.eval.external.longmemeval.scorer",
            "cq.eval.external.longmemeval.judge_stability",
        }
        package_dir = Path(__file__).resolve().parents[1] / "cq" / "eval" / "external" / "longmemeval"
        forbidden_importers = []
        for source_path in package_dir.glob("*.py"):
            if source_path.stem == "gold_loader":
                continue
            module_name = "cq.eval.external.longmemeval.{}".format(source_path.stem)
            if module_name in allowed_importers or module_name.endswith(".__init__"):
                continue
            forbidden_importers.append(module_name)
        for module_name in forbidden_importers:
            module = importlib.import_module(module_name)
            source = inspect.getsource(module)
            self.assertNotIn(
                "gold_loader",
                source,
                msg="{} must not import gold_loader (hidden-answer protocol)".format(
                    module_name
                ),
            )


if __name__ == "__main__":
    unittest.main()
