import unittest

from cq.eval.runner import (
    ADVERSARIAL_UPSTREAM_NOISE,
    CQ_ABLATION_POLICIES,
    FALSE_CORROBORATION,
    FORCED_CONTRADICTION,
    MEMORY_POISONING,
    POLICY_SET_PHASE_2_5,
    PREFERENCE_DRIFT,
    SCOPE_CONTAMINATION,
    USEFUL_PENDING_MEMORY,
    build_run_artifact,
)


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

    def test_adversarial_family_rejects_clean_mix(self) -> None:
        with self.assertRaisesRegex(ValueError, "Template mix 'clean' is not supported"):
            build_run_artifact(
                1,
                template_mix="clean",
                family=ADVERSARIAL_UPSTREAM_NOISE,
                policy_set=POLICY_SET_PHASE_2_5,
            )


if __name__ == "__main__":
    unittest.main()
