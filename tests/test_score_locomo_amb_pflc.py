"""Regression tests for ``scripts/score_locomo_amb_pflc.py``.

The scorer parses public Agent Memory Benchmark LoCoMo run gzips and
compares context-emitted ``dia_id`` values to gold ``qa[].evidence``.
These tests pin the corrected zero-gold semantics, the
``_assert_parse_sanity`` regex floor, and the dynamic
``created_utc_date`` behavior so future regenerations cannot silently
reintroduce the original bugs.

Inputs are tiny in-test fixtures; no AMB gzip or LoCoMo download is required.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "score_locomo_amb_pflc.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SCORER = _load_module("score_locomo_amb_pflc", SCRIPT_PATH)


def _memory_block(idx: int, dia_ids: list[str]) -> str:
    """Build a Memory N block that matches the AMB context format."""

    snippets = ",".join(f'{{"dia_id": "{did}"}}' for did in dia_ids)
    return f"## Memory {idx}\n{snippets}\n"


def _context(memory_dia_ids: list[list[str]]) -> str:
    return "".join(_memory_block(i + 1, ids) for i, ids in enumerate(memory_dia_ids))


def _make_run(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "run_name": "fixture-run",
        "memory_provider": "fixture",
        "mode": "rag",
        "split": "fixture-split",
        "total_queries": len(results),
        "accuracy": sum(r["correct"] for r in results) / len(results),
        "results": results,
    }


def _make_locomo(samples: list[tuple[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    return [{"sample_id": sid, "qa": qa} for sid, qa in samples]


class ZeroGoldRowSemanticsTests(unittest.TestCase):
    """Empty ``gold_evidence`` rows must score ``all_hit_*`` as vacuous True
    (``set() <= S`` for any ``S``) and ``any_hit_*`` as False (no element to
    intersect). They must be excluded from the summary's lookup-relevant
    denominator.
    """

    def _run(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        run = _make_run(
            [
                {
                    "query_id": "sample-a_q0",
                    "query": "Q0",
                    "gold_answers": ["yes"],
                    "correct": True,
                    "context": _context([["D1"], ["D2"], ["D3"]]),
                },
                {
                    "query_id": "sample-a_q1",
                    "query": "Q1",
                    "gold_answers": ["maybe"],
                    "correct": True,
                    "context": _context([["DX"], ["DY"], ["DZ"]]),
                },
                {
                    "query_id": "sample-a_q2",
                    "query": "Q2",
                    "gold_answers": ["no"],
                    "correct": False,
                    "context": _context([["D7"]]),
                },
            ]
        )
        locomo = _make_locomo(
            [
                (
                    "sample-a",
                    [
                        {"question": "Q0", "evidence": ["D1", "D2"], "category": "1"},
                        {"question": "Q1", "evidence": [], "category": "1"},
                        {"question": "Q2", "evidence": ["D7"], "category": "2"},
                    ],
                )
            ]
        )
        # ``_summarize_run`` always emits ``joint_counts_at_50``, so the
        # ks tuple must contain 50 even for the small fixture.
        ks = (1, 5, 10, 20, 50)
        rows, mismatches = SCORER._extract_rows(run, locomo, ks)
        summary = SCORER._summarize_run(
            run, rows, mismatches, ks, bootstrap_seed=0, bootstrap_samples=0
        )
        return rows, summary

    def test_zero_gold_all_hit_is_vacuous_true(self) -> None:
        rows, _ = self._run()
        empty_row = next(r for r in rows if r["query_id"] == "sample-a_q1")
        self.assertEqual(empty_row["gold_evidence_count"], 0)
        self.assertFalse(empty_row["lookup_relevant"])
        # set() <= S is True for any S; this is the correctness fix the
        # adversarial review caught (previously hard-coded to False).
        self.assertTrue(empty_row["all_hit_at_1"])
        self.assertTrue(empty_row["all_hit_at_5"])
        self.assertTrue(empty_row["all_hit_all_context"])

    def test_zero_gold_any_hit_is_false(self) -> None:
        rows, _ = self._run()
        empty_row = next(r for r in rows if r["query_id"] == "sample-a_q1")
        # bool(set() & S) is False for any S; this is correct and unchanged.
        self.assertFalse(empty_row["any_hit_at_1"])
        self.assertFalse(empty_row["any_hit_at_5"])
        self.assertFalse(empty_row["any_hit_all_context"])

    def test_lookup_relevant_flag(self) -> None:
        rows, _ = self._run()
        relevance = {r["query_id"]: r["lookup_relevant"] for r in rows}
        self.assertEqual(
            relevance,
            {"sample-a_q0": True, "sample-a_q1": False, "sample-a_q2": True},
        )

    def test_summary_excludes_zero_gold_from_lookup_denominator(self) -> None:
        _, summary = self._run()
        align = summary["alignment"]
        self.assertEqual(align["scored_rows"], 3)
        self.assertEqual(align["zero_gold_evidence_count"], 1)
        self.assertEqual(align["lookup_relevant_rows"], 2)
        self.assertEqual(align["metric_denominator"], "lookup_relevant")

    def test_summary_metrics_use_lookup_relevant_denominator(self) -> None:
        _, summary = self._run()
        metrics = summary["metrics"]
        # Only two lookup-relevant rows: Q0 (gold {D1,D2}) and Q2 (gold {D7}).
        # Q0 at k=1 retrieves {D1} ⊉ {D1,D2}: all_hit_at_1 = False;
        #    at k=5 retrieves {D1,D2,D3} ⊇ {D1,D2}: all_hit_at_1 (k=5) True.
        # Q2 at k=1 retrieves {D7} ⊇ {D7}: all_hit True at every k.
        # So all_hit_at_1 rate is 1/2 = 0.5, all_hit_at_5 rate is 2/2 = 1.0.
        self.assertAlmostEqual(metrics["all_hit_at_1"]["estimate"], 0.5)
        self.assertAlmostEqual(metrics["all_hit_at_5"]["estimate"], 1.0)
        # Q0 at k=1 any_hit (D1 in {D1,D2}) = True;
        # Q2 at k=1 any_hit = True. So any_hit_at_1 rate = 2/2 = 1.0.
        self.assertAlmostEqual(metrics["any_hit_at_1"]["estimate"], 1.0)

    def test_summary_records_full_row_answer_accuracy_alongside(self) -> None:
        _, summary = self._run()
        # answer_accuracy_all_rows matches AMB's full-denominator value
        # (here 2 correct / 3 rows), while answer_accuracy is restricted
        # to the lookup-relevant subset (here 1 correct / 2 lookup rows
        # because Q1 was the dropped correct-but-empty-gold row).
        self.assertAlmostEqual(
            summary["metrics"]["answer_accuracy_all_rows"]["estimate"], 2 / 3
        )
        self.assertAlmostEqual(
            summary["metrics"]["answer_accuracy"]["estimate"], 0.5
        )

    def test_joint_counts_use_lookup_relevant_subset(self) -> None:
        _, summary = self._run()
        joint = summary["metrics"]["joint_counts_all_context"]
        # Lookup-relevant rows: Q0 (correct=True, all_hit_all_context=True),
        # Q2 (correct=False, all_hit_all_context=True). Zero-gold Q1 is
        # excluded from joint counts entirely.
        self.assertEqual(joint["answer_correct_and_pflc_hit"], 1)
        self.assertEqual(joint["answer_correct_and_pflc_miss"], 0)
        self.assertEqual(joint["answer_wrong_and_pflc_hit"], 1)
        self.assertEqual(joint["answer_wrong_and_pflc_miss"], 0)


class AlignmentGuardTests(unittest.TestCase):
    """Bad AMB/LoCoMo pairings should fail with targeted alignment errors
    rather than raw KeyError or IndexError exceptions.
    """

    def test_unknown_sample_id_raises_clear_value_error(self) -> None:
        run = _make_run(
            [
                {
                    "query_id": "missing-sample_q0",
                    "query": "Q0",
                    "gold_answers": ["yes"],
                    "correct": True,
                    "context": _context([["D1"]]),
                }
            ]
        )
        locomo = _make_locomo(
            [("sample-a", [{"question": "Q0", "evidence": ["D1"], "category": "1"}])]
        )

        with self.assertRaises(ValueError) as ctx:
            SCORER._extract_rows(run, locomo, (1, 5, 10, 20, 50))

        msg = str(ctx.exception)
        self.assertIn("missing-sample_q0", msg)
        self.assertIn("sample_id 'missing-sample'", msg)
        self.assertIn("absent", msg)

    def test_out_of_range_qa_index_raises_clear_value_error(self) -> None:
        run = _make_run(
            [
                {
                    "query_id": "sample-a_q3",
                    "query": "Q3",
                    "gold_answers": ["yes"],
                    "correct": True,
                    "context": _context([["D1"]]),
                }
            ]
        )
        locomo = _make_locomo(
            [("sample-a", [{"question": "Q0", "evidence": ["D1"], "category": "1"}])]
        )

        with self.assertRaises(ValueError) as ctx:
            SCORER._extract_rows(run, locomo, (1, 5, 10, 20, 50))

        msg = str(ctx.exception)
        self.assertIn("sample-a_q3", msg)
        self.assertIn("qa_index 3", msg)
        self.assertIn("only 1 QA rows", msg)

    def test_missing_qa_field_raises_clear_value_error(self) -> None:
        run = _make_run(
            [
                {
                    "query_id": "sample-a_q0",
                    "query": "Q0",
                    "gold_answers": ["yes"],
                    "correct": True,
                    "context": _context([["D1"]]),
                }
            ]
        )
        locomo = [{"sample_id": "sample-a"}]

        with self.assertRaises(ValueError) as ctx:
            SCORER._extract_rows(run, locomo, (1, 5, 10, 20, 50))

        msg = str(ctx.exception)
        self.assertIn("sample-a_q0", msg)
        self.assertIn("no list-valued 'qa' field", msg)


class RegexSanityAssertTests(unittest.TestCase):
    """``_assert_parse_sanity`` must raise when MEMORY_BLOCK_RE or DIA_ID_RE
    produces parses below ``MIN_PARSE_RATIO`` of the input rows. This is the
    silent-failure guard the adversarial review flagged as the biggest live
    risk.
    """

    def test_memory_block_drift_raises(self) -> None:
        # All four rows have non-empty context but no ``## Memory N\n``
        # headers, so MEMORY_BLOCK_RE matches zero blocks per row. The
        # fallback in _memory_blocks returns the whole context as one
        # block, so retrieved_memory_blocks=1 per row, satisfying the
        # block floor — but if the regex regressed AND there were no
        # fallback rows, the assert would fire. Force the failure mode
        # directly: zero memory blocks AND zero dia_ids.
        run = _make_run(
            [
                {
                    "query_id": f"sample-a_q{i}",
                    "query": f"Q{i}",
                    "gold_answers": [f"a{i}"],
                    "correct": True,
                    "context": "",  # empty context → 0 memory blocks
                }
                for i in range(4)
            ]
        )
        locomo = _make_locomo(
            [
                (
                    "sample-a",
                    [
                        {"question": f"Q{i}", "evidence": [f"D{i}"], "category": "1"}
                        for i in range(4)
                    ],
                )
            ]
        )
        with self.assertRaises(ValueError) as ctx:
            SCORER._extract_rows(run, locomo, (1, 5, 10, 20, 50))
        # Both regex sanity errors are possible; the first that fires
        # determines the message. With empty context, blocks are zero
        # first, so MEMORY_BLOCK_RE is the named cause.
        self.assertIn("MEMORY_BLOCK_RE", str(ctx.exception))
        self.assertIn("fixture-run", str(ctx.exception))

    def test_dia_id_drift_raises(self) -> None:
        # Memory blocks parse but contain no dia_id JSON fragments.
        bad_block = "## Memory 1\n(no dia_id here)\n"
        run = _make_run(
            [
                {
                    "query_id": f"sample-a_q{i}",
                    "query": f"Q{i}",
                    "gold_answers": [f"a{i}"],
                    "correct": True,
                    "context": bad_block,
                }
                for i in range(4)
            ]
        )
        locomo = _make_locomo(
            [
                (
                    "sample-a",
                    [
                        {"question": f"Q{i}", "evidence": [f"D{i}"], "category": "1"}
                        for i in range(4)
                    ],
                )
            ]
        )
        with self.assertRaises(ValueError) as ctx:
            SCORER._extract_rows(run, locomo, (1, 5, 10, 20, 50))
        self.assertIn("DIA_ID_RE", str(ctx.exception))

    def test_no_memory_headers_returns_empty_blocks_not_fallback(self) -> None:
        # Header-format drift: AMB switches "## Memory 1\n" to something
        # MEMORY_BLOCK_RE no longer matches, but dia_id JSON is still in
        # the context. Previously the fallback returned [context], lumping
        # every emitted dia_id into a single rank-1 block and inflating
        # PFLC@1/@5/@10. Now the function returns [] so rank-sensitive
        # metrics fail closed via _assert_parse_sanity.
        context_without_headers = (
            'No headers here. {"dia_id": "D1"} '
            'and more text {"dia_id": "D2"}.'
        )
        self.assertEqual(SCORER._memory_blocks(context_without_headers), [])
        self.assertEqual(SCORER._memory_blocks(""), [])

    def test_header_drift_with_intact_dia_ids_still_fails_closed(self) -> None:
        # End-to-end: every row has dia_id JSON but no Memory N headers.
        # The dia_id regex still matches, but because dia_ids are
        # extracted per block (and there are no blocks), block_ids is
        # empty and retrieved_dia_id_count is zero. The sanity assert
        # fires on the block floor first; the rank inflation path is
        # unreachable.
        bad_context = 'some context {"dia_id": "D1"} text {"dia_id": "D2"}'
        run = _make_run(
            [
                {
                    "query_id": f"sample-a_q{i}",
                    "query": f"Q{i}",
                    "gold_answers": [f"a{i}"],
                    "correct": True,
                    "context": bad_context,
                }
                for i in range(4)
            ]
        )
        locomo = _make_locomo(
            [
                (
                    "sample-a",
                    [
                        {"question": f"Q{i}", "evidence": [f"D{i}"], "category": "1"}
                        for i in range(4)
                    ],
                )
            ]
        )
        with self.assertRaises(ValueError) as ctx:
            SCORER._extract_rows(run, locomo, (1, 5, 10, 20, 50))
        self.assertIn("MEMORY_BLOCK_RE", str(ctx.exception))

    def test_healthy_parse_does_not_raise(self) -> None:
        run = _make_run(
            [
                {
                    "query_id": f"sample-a_q{i}",
                    "query": f"Q{i}",
                    "gold_answers": [f"a{i}"],
                    "correct": True,
                    "context": _context([[f"D{i}a"], [f"D{i}b"]]),
                }
                for i in range(4)
            ]
        )
        locomo = _make_locomo(
            [
                (
                    "sample-a",
                    [
                        {"question": f"Q{i}", "evidence": [f"D{i}a"], "category": "1"}
                        for i in range(4)
                    ],
                )
            ]
        )
        # Should not raise.
        rows, _ = SCORER._extract_rows(run, locomo, (1, 5, 10, 20, 50))
        self.assertEqual(len(rows), 4)


class QuestionMismatchAbortTests(unittest.TestCase):
    """Validity of dialog-evidence-id PFLC depends on exact alignment between
    each AMB ``result["query"]`` and the resolved LoCoMo ``qa[qa_index].question``.
    A mismatch means evidence is being scored against the wrong gold row, so
    ``main`` must abort by default; ``--allow-question-mismatches`` is the
    explicit-override flag that surfaces the mismatch in the alignment block
    rather than silently scoring against the wrong gold.
    """

    def _build_fixture(
        self, tmp: Path, *, mismatch_query: str
    ) -> tuple[Path, Path, Path, Path]:
        locomo_path = tmp / "locomo.json"
        run_path = tmp / "run.json"
        out_csv = tmp / "rows.csv"
        out_summary = tmp / "summary.json"
        locomo_path.write_text(
            json.dumps(
                _make_locomo(
                    [
                        (
                            "sample-a",
                            [
                                {"question": "Q0", "evidence": ["D1"], "category": "1"},
                                {"question": "Q1", "evidence": ["D2"], "category": "1"},
                            ],
                        )
                    ]
                )
            )
        )
        run_path.write_text(
            json.dumps(
                _make_run(
                    [
                        {
                            "query_id": "sample-a_q0",
                            "query": "Q0",
                            "gold_answers": ["yes"],
                            "correct": True,
                            "context": _context([["D1"], ["D2"]]),
                        },
                        {
                            "query_id": "sample-a_q1",
                            "query": mismatch_query,
                            "gold_answers": ["no"],
                            "correct": True,
                            "context": _context([["D2"], ["D3"]]),
                        },
                    ]
                )
            )
        )
        return locomo_path, run_path, out_csv, out_summary

    def test_main_aborts_on_question_mismatch_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            locomo_path, run_path, out_csv, out_summary = self._build_fixture(
                Path(tmp_dir), mismatch_query="DIFFERENT QUESTION"
            )
            argv = [
                "score_locomo_amb_pflc.py",
                "--locomo-data",
                str(locomo_path),
                "--amb-run",
                str(run_path),
                "--out-csv",
                str(out_csv),
                "--out-summary",
                str(out_summary),
                "--bootstrap-samples",
                "0",
                "--created-utc-date",
                "1999-12-31",
            ]
            with mock.patch.object(sys, "argv", argv):
                with self.assertRaises(ValueError) as ctx:
                    SCORER.main()
            msg = str(ctx.exception)
            self.assertIn("query/LoCoMo question mismatches", msg)
            self.assertIn("sample-a_q1", msg)
            self.assertIn("--allow-question-mismatches", msg)
            # Summary must not have been written on abort.
            self.assertFalse(out_summary.exists())

    def test_main_proceeds_on_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            locomo_path, run_path, out_csv, out_summary = self._build_fixture(
                Path(tmp_dir), mismatch_query="DIFFERENT QUESTION"
            )
            argv = [
                "score_locomo_amb_pflc.py",
                "--locomo-data",
                str(locomo_path),
                "--amb-run",
                str(run_path),
                "--out-csv",
                str(out_csv),
                "--out-summary",
                str(out_summary),
                "--bootstrap-samples",
                "0",
                "--created-utc-date",
                "1999-12-31",
                "--allow-question-mismatches",
            ]
            with mock.patch.object(sys, "argv", argv):
                SCORER.main()
            summary = json.loads(out_summary.read_text())
            run_summary = summary["runs"][0]
            # The override does not hide the mismatch; it surfaces it
            # in the alignment block so reviewers see what was tolerated.
            self.assertEqual(run_summary["alignment"]["question_mismatch_count"], 1)
            self.assertIn("sample-a_q1", run_summary["alignment"]["question_mismatch_ids"])

    def test_main_no_mismatch_no_override_needed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            locomo_path, run_path, out_csv, out_summary = self._build_fixture(
                Path(tmp_dir), mismatch_query="Q1"
            )
            argv = [
                "score_locomo_amb_pflc.py",
                "--locomo-data",
                str(locomo_path),
                "--amb-run",
                str(run_path),
                "--out-csv",
                str(out_csv),
                "--out-summary",
                str(out_summary),
                "--bootstrap-samples",
                "0",
                "--created-utc-date",
                "1999-12-31",
            ]
            with mock.patch.object(sys, "argv", argv):
                SCORER.main()
            summary = json.loads(out_summary.read_text())
            self.assertEqual(summary["runs"][0]["alignment"]["question_mismatch_count"], 0)


class CreatedUtcDateTests(unittest.TestCase):
    """``--created-utc-date`` overrides the date stamp; the default is the
    current UTC date in ``YYYY-MM-DD`` form. The original hardcoded
    ``2026-05-18`` literal that silently survived any future regeneration is
    gone.
    """

    def test_no_hardcoded_date_literal_in_main(self) -> None:
        source = SCRIPT_PATH.read_text()
        # The only acceptable occurrences of the literal "2026-05-18" are
        # in docstrings or comments, not in executable string assignments
        # like ``"created_utc_date": "2026-05-18"``.
        self.assertNotIn('"created_utc_date": "2026-', source)
        self.assertNotIn("'created_utc_date': '2026-", source)

    def test_main_honors_cli_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            locomo_path = tmp / "locomo.json"
            run_path = tmp / "run.json"
            out_csv = tmp / "rows.csv"
            out_summary = tmp / "summary.json"

            locomo_path.write_text(
                json.dumps(
                    _make_locomo(
                        [
                            (
                                "sample-a",
                                [
                                    {
                                        "question": "Q0",
                                        "evidence": ["D1", "D2"],
                                        "category": "1",
                                    },
                                    {
                                        "question": "Q1",
                                        "evidence": ["D3"],
                                        "category": "1",
                                    },
                                ],
                            )
                        ]
                    )
                )
            )
            run_path.write_text(
                json.dumps(
                    _make_run(
                        [
                            {
                                "query_id": "sample-a_q0",
                                "query": "Q0",
                                "gold_answers": ["yes"],
                                "correct": True,
                                "context": _context([["D1"], ["D2"]]),
                            },
                            {
                                "query_id": "sample-a_q1",
                                "query": "Q1",
                                "gold_answers": ["no"],
                                "correct": False,
                                "context": _context([["DZ"], ["DY"]]),
                            },
                        ]
                    )
                )
            )

            argv = [
                "score_locomo_amb_pflc.py",
                "--locomo-data",
                str(locomo_path),
                "--amb-run",
                str(run_path),
                "--out-csv",
                str(out_csv),
                "--out-summary",
                str(out_summary),
                "--bootstrap-samples",
                "0",
                "--created-utc-date",
                "1999-12-31",
            ]
            with mock.patch.object(sys, "argv", argv):
                SCORER.main()

            summary = json.loads(out_summary.read_text())
            self.assertEqual(summary["created_utc_date"], "1999-12-31")

    def test_main_default_is_current_utc_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            locomo_path = tmp / "locomo.json"
            run_path = tmp / "run.json"
            out_csv = tmp / "rows.csv"
            out_summary = tmp / "summary.json"

            locomo_path.write_text(
                json.dumps(
                    _make_locomo(
                        [
                            (
                                "sample-a",
                                [
                                    {
                                        "question": "Q0",
                                        "evidence": ["D1"],
                                        "category": "1",
                                    },
                                    {
                                        "question": "Q1",
                                        "evidence": ["D2"],
                                        "category": "1",
                                    },
                                ],
                            )
                        ]
                    )
                )
            )
            run_path.write_text(
                json.dumps(
                    _make_run(
                        [
                            {
                                "query_id": "sample-a_q0",
                                "query": "Q0",
                                "gold_answers": ["yes"],
                                "correct": True,
                                "context": _context([["D1"], ["D2"]]),
                            },
                            {
                                "query_id": "sample-a_q1",
                                "query": "Q1",
                                "gold_answers": ["no"],
                                "correct": True,
                                "context": _context([["D2"], ["D3"]]),
                            },
                        ]
                    )
                )
            )

            argv = [
                "score_locomo_amb_pflc.py",
                "--locomo-data",
                str(locomo_path),
                "--amb-run",
                str(run_path),
                "--out-csv",
                str(out_csv),
                "--out-summary",
                str(out_summary),
                "--bootstrap-samples",
                "0",
            ]
            with mock.patch.object(sys, "argv", argv):
                SCORER.main()

            summary = json.loads(out_summary.read_text())
            self.assertRegex(summary["created_utc_date"], r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
