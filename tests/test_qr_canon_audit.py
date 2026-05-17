import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load(
    "build_qr_canon_source_table",
    REPO_ROOT / "scripts" / "build_qr_canon_source_table.py",
)
AUDIT = _load(
    "run_qr_canon_audit",
    REPO_ROOT / "scripts" / "run_qr_canon_audit.py",
)


class WilsonIntervalTests(unittest.TestCase):
    def test_zero_trials_returns_zero(self) -> None:
        self.assertEqual(AUDIT._wilson_interval(0, 0), (0.0, 0.0))

    def test_perfect_rate_upper_bound_is_one(self) -> None:
        lcb, ucb = AUDIT._wilson_interval(60, 60)
        self.assertGreater(lcb, 0.93)
        self.assertAlmostEqual(ucb, 1.0, places=10)

    def test_zero_rate_lower_bound_is_zero(self) -> None:
        lcb, ucb = AUDIT._wilson_interval(0, 60)
        self.assertEqual(lcb, 0.0)
        self.assertLess(ucb, 0.10)

    def test_midpoint_rate_brackets_observed(self) -> None:
        lcb, ucb = AUDIT._wilson_interval(40, 120)
        observed = 40 / 120
        self.assertLess(lcb, observed)
        self.assertGreater(ucb, observed)
        self.assertAlmostEqual(lcb, 0.255317, places=4)
        self.assertAlmostEqual(ucb, 0.421689, places=4)


class JointDiagnosticTests(unittest.TestCase):
    def test_clustering_pass_lookup_miss_true_for_perfect_b_cubed_zero_qr(self) -> None:
        self.assertTrue(AUDIT._is_clustering_pass_lookup_miss(1.0, 0.0))

    def test_clustering_pass_lookup_miss_false_for_perfect_qr(self) -> None:
        self.assertFalse(AUDIT._is_clustering_pass_lookup_miss(1.0, 0.93))

    def test_clustering_pass_lookup_miss_false_when_clustering_below_gate(self) -> None:
        self.assertFalse(AUDIT._is_clustering_pass_lookup_miss(0.50, 0.0))

    def test_clustering_pass_lookup_miss_false_when_b_cubed_missing(self) -> None:
        self.assertFalse(AUDIT._is_clustering_pass_lookup_miss(None, 0.0))


class SyntheticCounterexampleTests(unittest.TestCase):
    def test_synthetic_row_is_b_cubed_one_with_qr_canon_zero(self) -> None:
        row = AUDIT._synthetic_counterexample()
        self.assertEqual(row["family"], "synthetic_counterexample")
        self.assertEqual(float(row["canonicalization_b_cubed_f1"]), 1.0)
        self.assertEqual(float(row["qr_canon_exact_rate"]), 0.0)
        self.assertEqual(float(row["qr_canon_normalized_rate"]), 0.0)
        self.assertTrue(row["joint_passes_clustering_floor_but_not_lookup"])
        self.assertEqual(row["row_kind"], "synthetic_counterexample")

    def test_synthetic_row_ships_in_metrics_csv(self) -> None:
        metrics_path = REPO_ROOT / "data" / "results" / "qr_canon_audit_metrics.csv"
        with metrics_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        synthetic_rows = [r for r in rows if r["row_kind"] == "synthetic_counterexample"]
        self.assertEqual(len(synthetic_rows), 1)
        synthetic = synthetic_rows[0]
        self.assertEqual(synthetic["canonicalization_b_cubed_f1"], "1.000000")
        self.assertEqual(synthetic["qr_canon_exact_rate"], "0.000000")


class AggregateFamilyRowsTests(unittest.TestCase):
    def test_aggregate_handles_per_question_rows(self) -> None:
        source_rows: List[Dict[str, str]] = [
            {
                "family": "forced_contradiction",
                "scenario_id": "s1",
                "question_id": "q1",
                "relevant_canonical_id": "x",
                "extracted_canonical_ids": "x",
                "qr_canon_exact_hit": "1",
                "qr_canon_normalized_hit": "1",
                "row_canonicalization_b_cubed_f1": "1.0",
            },
            {
                "family": "forced_contradiction",
                "scenario_id": "s2",
                "question_id": "q1",
                "relevant_canonical_id": "x",
                "extracted_canonical_ids": "y",
                "qr_canon_exact_hit": "0",
                "qr_canon_normalized_hit": "1",
                "row_canonicalization_b_cubed_f1": "1.0",
            },
            {
                "family": "useful_pending_memory",
                "scenario_id": "s1",
                "question_id": "q1",
                "relevant_canonical_id": "p",
                "extracted_canonical_ids": "z",
                "qr_canon_exact_hit": "0",
                "qr_canon_normalized_hit": "0",
                "row_canonicalization_b_cubed_f1": "1.0",
            },
        ]
        aggregated = AUDIT._aggregate_family_rows(source_rows)
        by_family = {row["family"]: row for row in aggregated}
        self.assertEqual(by_family["forced_contradiction"]["denominator"], 2)
        self.assertEqual(by_family["forced_contradiction"]["qr_canon_exact_hits"], 1)
        self.assertEqual(by_family["forced_contradiction"]["qr_canon_normalized_hits"], 2)
        self.assertEqual(by_family["useful_pending_memory"]["denominator"], 1)
        self.assertEqual(
            by_family["useful_pending_memory"]["qr_canon_exact_hits"], 0
        )
        self.assertTrue(
            by_family["useful_pending_memory"][
                "joint_passes_clustering_floor_but_not_lookup"
            ]
        )
        self.assertFalse(
            by_family["forced_contradiction"][
                "joint_passes_clustering_floor_but_not_lookup"
            ]
        )


class CommittedArtifactsTests(unittest.TestCase):
    """These tie the audit to the committed evidence so it cannot silently drift."""

    def test_committed_source_table_matches_mechanism_audit_evidence(self) -> None:
        source_path = REPO_ROOT / "data" / "results" / "qr_canon_source_table.csv"
        evidence_path = (
            REPO_ROOT / "data" / "results" / "noisy_policy_mechanism_audit_evidence.json"
        )
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        with source_path.open("r", encoding="utf-8", newline="") as handle:
            source_rows = list(csv.DictReader(handle))
        for family in [
            "forced_contradiction",
            "preference_drift",
            "scope_contamination",
            "useful_pending_memory",
            "memory_poisoning",
            "false_corroboration",
            "mechanism_diverse_heldout",
        ]:
            family_rows = [r for r in source_rows if r["family"] == family]
            evidence_alignment = evidence["rows"][family]["canonical_alignment"]
            self.assertEqual(
                len(family_rows),
                evidence_alignment["question_traces_with_relevant_id"],
                f"denominator mismatch on {family}",
            )
            self.assertEqual(
                sum(int(r["qr_canon_exact_hit"]) for r in family_rows),
                evidence_alignment["exact_matches"],
                f"exact-hit mismatch on {family}",
            )

    def test_committed_audit_metrics_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_repo = Path(tmpdir)
            (tmp_repo / "data" / "results").mkdir(parents=True)
            source = (
                REPO_ROOT / "data" / "results" / "qr_canon_source_table.csv"
            ).read_bytes()
            (tmp_repo / "data" / "results" / "qr_canon_source_table.csv").write_bytes(source)

            rc = AUDIT.main(["--repo-root", str(tmp_repo)])
            self.assertEqual(rc, 0)

            committed = (
                REPO_ROOT / "data" / "results" / "qr_canon_audit_metrics.csv"
            ).read_bytes()
            regenerated = (
                tmp_repo / "data" / "results" / "qr_canon_audit_metrics.csv"
            ).read_bytes()
            self.assertEqual(committed, regenerated)


class GeneratorRegressionCheckTests(unittest.TestCase):
    def test_regression_check_passes_when_counts_align(self) -> None:
        result = GENERATOR._check_regression(
            per_family_counts={
                "useful_pending_memory": {"row_count": 60, "exact_hits": 0, "normalized_hits": 0}
            },
            evidence={
                "rows": {
                    "useful_pending_memory": {
                        "canonical_alignment": {
                            "exact_matches": 0,
                            "question_traces_with_relevant_id": 60,
                        }
                    }
                }
            },
        )
        self.assertTrue(result["all_passed"])

    def test_regression_check_fails_on_denominator_drift(self) -> None:
        result = GENERATOR._check_regression(
            per_family_counts={
                "useful_pending_memory": {"row_count": 59, "exact_hits": 0, "normalized_hits": 0}
            },
            evidence={
                "rows": {
                    "useful_pending_memory": {
                        "canonical_alignment": {
                            "exact_matches": 0,
                            "question_traces_with_relevant_id": 60,
                        }
                    }
                }
            },
        )
        self.assertFalse(result["all_passed"])
        self.assertFalse(result["per_family"]["useful_pending_memory"]["passed"])

    def test_regression_check_fails_on_exact_hit_drift(self) -> None:
        result = GENERATOR._check_regression(
            per_family_counts={
                "forced_contradiction": {"row_count": 120, "exact_hits": 113, "normalized_hits": 120}
            },
            evidence={
                "rows": {
                    "forced_contradiction": {
                        "canonical_alignment": {
                            "exact_matches": 112,
                            "question_traces_with_relevant_id": 120,
                        }
                    }
                }
            },
        )
        self.assertFalse(result["all_passed"])


class AuditDoesNotImportRunJsonsTests(unittest.TestCase):
    def test_audit_runs_without_gitignored_run_jsons(self) -> None:
        """If only the committed source table is present, the audit must still run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_repo = Path(tmpdir)
            (tmp_repo / "data" / "results").mkdir(parents=True)
            source = (
                REPO_ROOT / "data" / "results" / "qr_canon_source_table.csv"
            ).read_bytes()
            (tmp_repo / "data" / "results" / "qr_canon_source_table.csv").write_bytes(source)
            self.assertFalse((tmp_repo / "data" / "runs").exists())

            rc = AUDIT.main(["--repo-root", str(tmp_repo)])
            self.assertEqual(rc, 0)
            self.assertTrue(
                (tmp_repo / "data" / "results" / "qr_canon_audit_metrics.csv").exists()
            )


if __name__ == "__main__":
    unittest.main()
