import csv
import tempfile
from pathlib import Path
import unittest

from cq.eval.runner import (
    ADVERSARIAL_UPSTREAM_NOISE,
    CQ_ABLATION_POLICIES,
    EVIDENCE_CONFLICT_SPECTRUM,
    FALSE_CORROBORATION,
    FORCED_CONTRADICTION,
    MEMORY_POISONING,
    POLICY_SET_FOLLOWUP,
    POLICY_SET_PHASE_2_5,
    PREFERENCE_DRIFT,
    SCOPE_CONTAMINATION,
    USEFUL_PENDING_MEMORY,
    build_run_artifact,
    write_outputs,
)
from cq.memory.consolidation_queue import CQDatedContestation


class RunnerPolicySetTests(unittest.TestCase):
    def test_default_policy_membership_is_unchanged(self) -> None:
        for family in [
            FORCED_CONTRADICTION,
            SCOPE_CONTAMINATION,
            PREFERENCE_DRIFT,
            USEFUL_PENDING_MEMORY,
            FALSE_CORROBORATION,
            MEMORY_POISONING,
            ADVERSARIAL_UPSTREAM_NOISE,
            EVIDENCE_CONFLICT_SPECTRUM,
        ]:
            with self.subTest(family=family):
                artifact = build_run_artifact(1, template_mix="mixed", family=family)
                policy_names = [policy["policy_name"] for policy in artifact["policies"]]

                self.assertNotIn("mem0_lite", policy_names)
                self.assertEqual(artifact["policy_set"], "default")
                self.assertEqual(artifact["baseline_notes"], {})
                self.assertEqual(artifact["ablation_notes"], {})

    def test_phase2_5_policy_set_includes_mem0_on_all_existing_families(self) -> None:
        for family in [
            FORCED_CONTRADICTION,
            SCOPE_CONTAMINATION,
            PREFERENCE_DRIFT,
            USEFUL_PENDING_MEMORY,
            FALSE_CORROBORATION,
            MEMORY_POISONING,
            ADVERSARIAL_UPSTREAM_NOISE,
            EVIDENCE_CONFLICT_SPECTRUM,
        ]:
            with self.subTest(family=family):
                artifact = build_run_artifact(
                    1,
                    template_mix="mixed",
                    family=family,
                    policy_set=POLICY_SET_PHASE_2_5,
                )
                policy_names = [policy["policy_name"] for policy in artifact["policies"]]

                self.assertIn("mem0_lite", policy_names)
                for ablation in CQ_ABLATION_POLICIES:
                    self.assertIn(ablation.policy_name, policy_names)
                self.assertEqual(artifact["policy_set"], POLICY_SET_PHASE_2_5)
                self.assertIn("mem0_lite", artifact["baseline_notes"])
                for ablation in CQ_ABLATION_POLICIES:
                    self.assertIn(ablation.policy_name, artifact["ablation_notes"])

    def test_phase2_5_preserves_scope_blind_rag_family_gating(self) -> None:
        forced = build_run_artifact(
            1,
            template_mix="mixed",
            family=FORCED_CONTRADICTION,
            policy_set=POLICY_SET_PHASE_2_5,
        )
        scoped = build_run_artifact(
            1,
            template_mix="mixed",
            family=SCOPE_CONTAMINATION,
            policy_set=POLICY_SET_PHASE_2_5,
        )

        self.assertNotIn(
            "scope_blind_transcript_rag_lite",
            [policy["policy_name"] for policy in forced["policies"]],
        )
        self.assertIn(
            "scope_blind_transcript_rag_lite",
            [policy["policy_name"] for policy in scoped["policies"]],
        )

    def test_evidence_conflict_spectrum_is_runner_only_not_component_family(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=EVIDENCE_CONFLICT_SPECTRUM,
            policy_set=POLICY_SET_PHASE_2_5,
        )
        policy_names = [policy["policy_name"] for policy in artifact["policies"]]

        self.assertIn("mem0_lite", policy_names)
        self.assertIn("scope_blind_transcript_rag_lite", policy_names)
        self.assertIn("primary_abstention_comparisons", artifact)

    def test_adversarial_family_rejects_clean_mix(self) -> None:
        with self.assertRaisesRegex(ValueError, "Template mix 'clean' is not supported"):
            build_run_artifact(
                1,
                template_mix="clean",
                family=ADVERSARIAL_UPSTREAM_NOISE,
                policy_set=POLICY_SET_PHASE_2_5,
            )

    def test_followup_policy_set_rejected_outside_adversarial_upstream_noise(self) -> None:
        for family in [
            FORCED_CONTRADICTION,
            SCOPE_CONTAMINATION,
            PREFERENCE_DRIFT,
            USEFUL_PENDING_MEMORY,
            FALSE_CORROBORATION,
            MEMORY_POISONING,
            EVIDENCE_CONFLICT_SPECTRUM,
        ]:
            with self.subTest(family=family):
                with self.assertRaises(ValueError):
                    build_run_artifact(
                        1,
                        template_mix="mixed",
                        family=family,
                        policy_set=POLICY_SET_FOLLOWUP,
                    )

    def test_followup_includes_dated_contestation_and_phase2_5_policies(self) -> None:
        artifact = build_run_artifact(
            1,
            template_mix="mixed",
            family=ADVERSARIAL_UPSTREAM_NOISE,
            policy_set=POLICY_SET_FOLLOWUP,
        )
        policy_names = [policy["policy_name"] for policy in artifact["policies"]]
        self.assertIn(CQDatedContestation.policy_name, policy_names)
        self.assertIn("mem0_lite", policy_names)
        for ablation in CQ_ABLATION_POLICIES:
            self.assertIn(ablation.policy_name, policy_names)
        self.assertEqual(artifact["policy_set"], POLICY_SET_FOLLOWUP)
        self.assertIn(CQDatedContestation.policy_name, artifact["ablation_notes"])
        self.assertIn("mem0_lite", artifact["baseline_notes"])

    def test_phase2_5_csv_includes_mem0_bootstrap_comparison_rows(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=ADVERSARIAL_UPSTREAM_NOISE,
            policy_set=POLICY_SET_PHASE_2_5,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "adversarial.json"
            output_csv = Path(tmpdir) / "adversarial.csv"
            write_outputs(artifact, output_json, output_csv)
            with output_csv.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        mem0_rows = [
            row
            for row in rows
            if row["summary_scope"] == "template_id_comparison"
            and row["comparison_name"] == "mem0_vs_reflection_by_template_id"
        ]
        self.assertTrue(mem0_rows)
        self.assertTrue(all(row["comparison_one_sided_95_lcb"] for row in mem0_rows))


if __name__ == "__main__":
    unittest.main()
