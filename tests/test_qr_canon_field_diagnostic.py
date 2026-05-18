"""Tests for the PFLC / QR-canon field-diagnostic synthetic counterexamples.

These tests enforce the locked contract from
``docs/policy_facing_lookup_contract_registration.md`` §8:

- Per-benchmark synthetic counterexample structure for every anchor.
- CSV and manifest byte-stable reproduction.
- Manifest does not embed live git/Python/status fields.
- Generator runs without gitignored inputs.
- Alias function SHA pin: the CQR alias function source matches the
  byte-locked SHA in ``docs/canonical_id_resolution_audit_preregistration.md`` §6.
- Proposition 1 reproducibility: the renaming construction satisfies
  ``rho(g*) != g*`` and ``g* not in image(rho)`` and yields
  ``M_cluster = 1.00`` and ``M_lookup = 0.00`` by hand-computation.
"""

import csv
import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = _load(
    "build_qr_canon_field_diagnostic_metrics",
    REPO_ROOT / "scripts" / "build_qr_canon_field_diagnostic_metrics.py",
)
CQR = _load(
    "run_canonical_id_resolution_audit",
    REPO_ROOT / "scripts" / "run_canonical_id_resolution_audit.py",
)


class PerBenchmarkSyntheticStructureTests(unittest.TestCase):
    """Each anchor benchmark ships exactly one synthetic counterexample row
    with the structural properties locked by the registration.
    """

    EXPECTED_BENCHMARKS = ("longmemeval", "mem0_locomo", "memoryagentbench", "membench")
    EXPECTED_INSTANCE = {
        "longmemeval": "answer-handle",
        "mem0_locomo": "dialog-evidence-id",
        "memoryagentbench": "conflict-resolution-id",
        "membench": "fact-id",
    }
    EXPECTED_LEMMA = {
        "longmemeval": "Lemma 2",
        "mem0_locomo": "Lemma 1",
        "memoryagentbench": "Lemma 2",
        "membench": "Lemma 1",
    }
    EXPECTED_HEADLINE_METRIC = {
        "longmemeval": "overall_accuracy",
        "mem0_locomo": "recall_at_k",
        "memoryagentbench": "task_accuracy",
        "membench": "factual_recall",
    }

    def test_generator_builds_exactly_four_rows(self) -> None:
        rows = GENERATOR._build_synthetic_rows()
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["benchmark"] for r in rows], list(self.EXPECTED_BENCHMARKS))

    def test_every_row_has_pflc_zero_and_headline_one_by_construction(self) -> None:
        rows = GENERATOR._build_synthetic_rows()
        for row in rows:
            self.assertEqual(
                row["pflc_exact_rate"],
                "0.000000",
                f"benchmark {row['benchmark']} must have PFLC exact rate 0 by construction",
            )
            self.assertEqual(
                row["paired_headline_metric_value"],
                "1.000000",
                f"benchmark {row['benchmark']} must have paired headline value 1 by construction",
            )
            self.assertTrue(
                row["joint_passes_headline_but_not_lookup"],
                f"benchmark {row['benchmark']} must flag the joint gap",
            )
            self.assertEqual(row["denominator"], 1)
            self.assertEqual(row["pflc_exact_hits"], 0)
            self.assertEqual(row["pflc_exact_wilson_lcb"], "0.000000")

    def test_pflc_instance_and_lemma_ref_match_feasibility_memos(self) -> None:
        rows = {row["benchmark"]: row for row in GENERATOR._build_synthetic_rows()}
        for benchmark in self.EXPECTED_BENCHMARKS:
            self.assertEqual(
                rows[benchmark]["pflc_instance"],
                self.EXPECTED_INSTANCE[benchmark],
                f"{benchmark} PFLC instance must match its feasibility memo",
            )
            self.assertEqual(
                rows[benchmark]["proposition_or_lemma_ref"],
                self.EXPECTED_LEMMA[benchmark],
                f"{benchmark} proposition/lemma ref must match its feasibility memo",
            )
            self.assertEqual(
                rows[benchmark]["paired_headline_metric_name"],
                self.EXPECTED_HEADLINE_METRIC[benchmark],
            )

    def test_committed_csv_has_exactly_one_row_per_benchmark(self) -> None:
        committed = (
            REPO_ROOT / "data" / "results" / "qr_canon_field_diagnostic_metrics.csv"
        )
        with committed.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 4)
        seen = {row["benchmark"] for row in rows}
        self.assertEqual(seen, set(self.EXPECTED_BENCHMARKS))
        for row in rows:
            self.assertEqual(
                row["row_kind"], f"synthetic_{row['benchmark']}_counterexample"
            )


class PropositionOneReproducibilityTests(unittest.TestCase):
    """Proposition 1 from docs/policy_facing_lookup_contract_proposition.md
    is reproducible by hand-computation.

    Construction: a single-cluster partition with two items {e1, e2}
    labeled ``gold-X`` in gold and ``pred-Y`` in predicted. The renaming
    function rho: gold-X -> pred-Y satisfies:

    - rho(g*) != g* (the queried gold label is renamed), and
    - g* not in image(rho) (the renamed label space does not include g*).

    Under this construction:

    - Any cluster-partition metric scores 1.00 because the predicted
      partition equals the gold partition (label-renaming invariance).
    - Set-membership PFLC scores 0 because the queried gold canonical id
      ``gold-X`` is not in the predicted label set ``{pred-Y}``.
    """

    def test_construction_satisfies_both_renaming_conditions(self) -> None:
        c = GENERATOR.proposition_one_construction()
        self.assertTrue(c["rho_g_star_not_equal_g_star"])
        self.assertTrue(c["g_star_not_in_image_rho"])
        self.assertNotEqual(c["renaming_rho"]["gold-X"], "gold-X")
        self.assertNotIn(c["query_target_g_star"], c["renaming_image"])

    def test_b_cubed_f1_equals_one_on_identical_partitions(self) -> None:
        c = GENERATOR.proposition_one_construction()
        score = _b_cubed_f1(c["gold_partition"], c["pred_partition"])
        self.assertEqual(score, 1.0)

    def test_set_membership_pflc_equals_zero_under_construction(self) -> None:
        c = GENERATOR.proposition_one_construction()
        g_star = c["query_target_g_star"]
        predicted_labels = c["predicted_label_set"]
        m_lookup = 1 if g_star in predicted_labels else 0
        self.assertEqual(m_lookup, 0)
        self.assertEqual(m_lookup, c["m_lookup_set_membership_by_construction"])

    def test_label_renaming_invariance_holds_under_relabeling(self) -> None:
        """Renaming labels in a partition must not change the B-cubed F1
        of identical partitions. Validates the label-renaming-invariance
        hypothesis used by Proposition 1.
        """
        gold = ({1, 2, 3}, {4, 5})
        pred = ({1, 2, 3}, {4, 5})
        self.assertEqual(_b_cubed_f1(gold, pred), 1.0)
        relabeled_pred = ({1, 2, 3}, {4, 5})
        self.assertEqual(_b_cubed_f1(gold, relabeled_pred), 1.0)


class AliasFunctionShaPinTests(unittest.TestCase):
    """The CQR alias function source must remain byte-locked at the SHA
    fixed in docs/canonical_id_resolution_audit_preregistration.md §6.
    This workstream is forbidden from modifying the alias function.
    """

    EXPECTED_SHA = (
        "8176c5a93ffbdbfd99d48f73836b954aa27aee4ab08de567ca47ec63d7896de0"
    )

    def test_alias_function_source_matches_locked_sha(self) -> None:
        observed = hashlib.sha256(CQR.ALIAS_FUNCTION_SOURCE.encode("utf-8")).hexdigest()
        self.assertEqual(observed, self.EXPECTED_SHA)

    def test_generator_pin_matches_locked_sha(self) -> None:
        self.assertEqual(GENERATOR.ALIAS_SOURCE_SHA_EXPECTED, self.EXPECTED_SHA)

    def test_preregistration_doc_frontmatter_pin_matches_locked_sha(self) -> None:
        doc = (
            REPO_ROOT
            / "docs"
            / "canonical_id_resolution_audit_preregistration.md"
        ).read_text(encoding="utf-8")
        match = re.search(
            r"canonical_id_resolution_alias_source_sha256:\s*([0-9a-f]{64})",
            doc,
        )
        self.assertIsNotNone(match, "preregistration doc must record the alias SHA")
        self.assertEqual(match.group(1), self.EXPECTED_SHA)


class CommittedArtifactsTests(unittest.TestCase):
    """The committed CSV and manifest must reproduce byte-identically
    from a fixed (empty) input set.
    """

    def test_committed_csv_reproduces_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_repo = Path(tmpdir)
            (tmp_repo / "data" / "results").mkdir(parents=True)

            rc = GENERATOR.main(["--repo-root", str(tmp_repo)])
            self.assertEqual(rc, 0)

            committed = (
                REPO_ROOT
                / "data"
                / "results"
                / "qr_canon_field_diagnostic_metrics.csv"
            ).read_bytes()
            regenerated = (
                tmp_repo
                / "data"
                / "results"
                / "qr_canon_field_diagnostic_metrics.csv"
            ).read_bytes()
            self.assertEqual(committed, regenerated)

    def test_committed_manifest_reproduces_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_repo = Path(tmpdir)
            (tmp_repo / "data" / "results").mkdir(parents=True)

            rc = GENERATOR.main(["--repo-root", str(tmp_repo)])
            self.assertEqual(rc, 0)

            committed = (
                REPO_ROOT
                / "data"
                / "results"
                / "qr_canon_field_diagnostic_metrics_manifest.json"
            ).read_bytes()
            regenerated = (
                tmp_repo
                / "data"
                / "results"
                / "qr_canon_field_diagnostic_metrics_manifest.json"
            ).read_bytes()
            self.assertEqual(committed, regenerated)

    def test_manifest_does_not_embed_live_fields(self) -> None:
        manifest_path = (
            REPO_ROOT
            / "data"
            / "results"
            / "qr_canon_field_diagnostic_metrics_manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for forbidden in ("git_commit", "python_version", "working_tree_status"):
            self.assertNotIn(
                forbidden,
                manifest,
                f"field-diagnostic manifest must not embed live {forbidden}",
            )

    def test_manifest_records_b3_outcome_bucket(self) -> None:
        manifest_path = (
            REPO_ROOT
            / "data"
            / "results"
            / "qr_canon_field_diagnostic_metrics_manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["workstream_outcome_bucket"], "B-3")

    def test_manifest_includes_alias_sha_pin(self) -> None:
        manifest_path = (
            REPO_ROOT
            / "data"
            / "results"
            / "qr_canon_field_diagnostic_metrics_manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["alias_function_sha256_pin"]["expected_sha256"],
            AliasFunctionShaPinTests.EXPECTED_SHA,
        )


class GeneratorDoesNotImportExternalInputsTests(unittest.TestCase):
    """The generator must run without any gitignored or external inputs.

    A clean temp directory with no data/runs, no Phase 4 JSONs, no
    external benchmark downloads, no policy state must still produce the
    committed CSV and manifest.
    """

    def test_generator_runs_in_empty_tempdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_repo = Path(tmpdir)
            self.assertFalse((tmp_repo / "data" / "runs").exists())
            self.assertFalse((tmp_repo / "data" / "results").exists())

            rc = GENERATOR.main(["--repo-root", str(tmp_repo)])
            self.assertEqual(rc, 0)
            self.assertTrue(
                (
                    tmp_repo
                    / "data"
                    / "results"
                    / "qr_canon_field_diagnostic_metrics.csv"
                ).exists()
            )
            self.assertTrue(
                (
                    tmp_repo
                    / "data"
                    / "results"
                    / "qr_canon_field_diagnostic_metrics_manifest.json"
                ).exists()
            )


def _b_cubed_f1(
    gold_partition: Iterable[Set[str]],
    pred_partition: Iterable[Set[str]],
) -> float:
    """Compute B-cubed F1 between two partitions over identical item sets.

    Implemented from scratch so the proposition reproducibility test does
    not depend on sklearn or any external clustering library. Treats
    clusters as sets of item ids; ignores labels entirely (which is the
    label-renaming-invariance property used by Proposition 1).
    """
    gold = [set(c) for c in gold_partition]
    pred = [set(c) for c in pred_partition]
    items: Set[str] = set()
    for cluster in gold:
        items.update(cluster)
    for cluster in pred:
        items.update(cluster)
    if not items:
        return 0.0

    item_to_gold: Dict[str, Set[str]] = {}
    for cluster in gold:
        for item in cluster:
            item_to_gold[item] = cluster
    item_to_pred: Dict[str, Set[str]] = {}
    for cluster in pred:
        for item in cluster:
            item_to_pred[item] = cluster

    precisions: List[float] = []
    recalls: List[float] = []
    for item in sorted(items, key=str):
        gold_c = item_to_gold[item]
        pred_c = item_to_pred[item]
        common = gold_c & pred_c
        precisions.append(len(common) / len(pred_c))
        recalls.append(len(common) / len(gold_c))
    precision = sum(precisions) / len(precisions)
    recall = sum(recalls) / len(recalls)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


if __name__ == "__main__":
    unittest.main()
