import ast
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
        package_dir = Path(__file__).resolve().parents[1] / "cq" / "eval" / "external" / "longmemeval"
        protected_sources = []
        for source_path in package_dir.glob("*.py"):
            if source_path.stem in {"gold_loader", "scorer"} or source_path.name == "__init__.py":
                continue
            protected_sources.append(source_path)

        scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
        for source_path in scripts_dir.glob("*longmemeval*.py"):
            if source_path.name == "score_longmemeval_pflc.py":
                continue
            protected_sources.append(source_path)

        for source_path in protected_sources:
            violations = _gold_boundary_violations(source_path)
            self.assertEqual(
                violations,
                [],
                "{} must not reference gold-loader symbols: {}".format(
                    source_path,
                    violations,
                ),
            )

    def test_gold_boundary_scan_catches_reexport_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.py"
            path.write_text(
                "from cq.eval.external.longmemeval.scorer import load_gold_cases\n",
                encoding="utf-8",
            )

            violations = _gold_boundary_violations(path)

        self.assertIn("import:load_gold_cases", violations)


FORBIDDEN_GOLD_SYMBOLS = {
    "GoldCase",
    "load_gold_cases",
    "gold_session_ids_by_case_id",
    "gold_answers_by_case_id",
}


def _gold_boundary_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cq.eval.external.longmemeval.gold_loader":
                    violations.append("import:gold_loader")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "cq.eval.external.longmemeval.gold_loader":
                violations.append("import_from:gold_loader")
            for alias in node.names:
                if alias.name in FORBIDDEN_GOLD_SYMBOLS:
                    violations.append("import:{}".format(alias.name))
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_GOLD_SYMBOLS:
            violations.append("name:{}".format(node.id))
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_GOLD_SYMBOLS:
            violations.append("attr:{}".format(node.attr))
    return sorted(set(violations))


if __name__ == "__main__":
    unittest.main()
