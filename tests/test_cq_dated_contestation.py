from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from cq.eval.end_to_end_eval import execute_scenario
from cq.eval.runner import (
    ADVERSARIAL_UPSTREAM_NOISE,
    FORCED_CONTRADICTION,
    POLICY_SET_FOLLOWUP,
    POLICY_SET_PHASE_2_5,
    SCOPE_CONTAMINATION,
    build_run_artifact,
)
from cq.memory.consolidation_queue import (
    CQDatedContestation,
    ConsolidationQueueLite,
)
from cq.schemas.memory import (
    CandidateUpdate,
    ClaimType,
    MemoryState,
    ProvenanceRecord,
    ScopeLevel,
)
from cq.simulator.adversarial_upstream_noise import (
    generate_adversarial_upstream_noise_scenarios,
)


def _scenario_by_template(scenarios, template_id):
    return [scenario for scenario in scenarios if scenario.template_id == template_id][0]


def _candidate_state(snapshot, candidate_id):
    return [
        candidate
        for candidate in snapshot["candidate_memories"]
        if candidate["candidate_id"] == candidate_id
    ][0]["state"]


def _active_durable_for(snapshot, canonical_id):
    return [
        durable
        for durable in snapshot["durable_memories"]
        if durable["canonical_id"] == canonical_id and durable["active"]
    ]


def _make_candidate(
    *,
    candidate_id: str,
    canonical_claim: str,
    base_time: datetime,
    observed_at: datetime | None = None,
    include_provenance: bool = True,
    source_id: str = "src",
    strength: float = 0.50,
    contradicts=None,
    claim_type: ClaimType = ClaimType.WORLD_FACT,
    scope_level: ScopeLevel = ScopeLevel.WORLD_GLOBAL,
    scope_key: str = "global",
    canonical_id: str = "shared-canonical",
) -> CandidateUpdate:
    provenance = []
    if include_provenance:
        provenance.append(
            ProvenanceRecord(
                source_kind="manual_test",
                source_id=source_id,
                trust_score=strength,
                observed_at=observed_at or base_time,
            )
        )
    return CandidateUpdate(
        candidate_id=candidate_id,
        canonical_id=canonical_id,
        raw_text=canonical_claim,
        raw_claim=canonical_claim,
        canonical_claim=canonical_claim,
        claim_type=claim_type,
        scope_level=scope_level,
        scope_key=scope_key,
        provenance=provenance,
        verification_score=strength,
        created_at=base_time,
        updated_at=base_time,
        contradicts=list(contradicts or []),
    )


class CQDatedContestationTemporalSkewTests(unittest.TestCase):
    """End-to-end test pinning behavior on the adversarial_temporal_skew_v1 scenario."""

    def test_stale_contradictor_is_contested_and_fresher_target_is_not_demoted(self) -> None:
        scenario = _scenario_by_template(
            generate_adversarial_upstream_noise_scenarios(5, template_mix="mixed"),
            "adversarial_temporal_skew_v1",
        )
        stale_id = scenario.expected_lifecycle["stale_candidate_ids"][0]
        current_id = [
            event.candidate.candidate_id
            for event in scenario.sorted_events()
            if event.candidate is not None and event.candidate.candidate_id != stale_id
            and "current" in event.candidate.candidate_id and "corroboration" not in event.candidate.candidate_id
        ][0]

        base_result = execute_scenario(ConsolidationQueueLite, scenario)
        dated_result = execute_scenario(CQDatedContestation, scenario)

        # Base CQ loses temporal_skew because the stale contradictor poisons the fresher truth.
        self.assertEqual(base_result["metrics"]["answer_correctness"], 0.0)
        # CQDatedContestation must answer correctly from the fresher pending candidate.
        self.assertEqual(dated_result["metrics"]["answer_correctness"], 1.0)

        snapshot = dated_result["store_snapshot"]
        self.assertEqual(_candidate_state(snapshot, stale_id), MemoryState.CONTESTED.value)
        # Fresher target was not demoted to CONTESTED by the stale contradictor.
        current_state = _candidate_state(snapshot, current_id)
        self.assertNotEqual(current_state, MemoryState.CONTESTED.value)
        # The stale candidate's stale_evidence_promotion_rate should also stay at zero.
        self.assertEqual(dated_result["metrics"]["stale_evidence_promotion_rate"], 0.0)


class CQDatedContestationUnitTests(unittest.TestCase):
    """Unit-level construction to pin equal/fresher/missing-provenance behavior."""

    def setUp(self) -> None:
        self.base_time = datetime(2026, 6, 1, 9, 0, 0)

    def test_dated_variant_reuses_base_observe_candidate_pipeline(self) -> None:
        self.assertIs(CQDatedContestation.observe_candidate, ConsolidationQueueLite.observe_candidate)

    def _run_pair(self, source: CandidateUpdate, target: CandidateUpdate):
        base_policy = ConsolidationQueueLite()
        base_policy.observe_candidate(target)
        base_policy.observe_candidate(source)
        dated_policy = CQDatedContestation()
        dated_policy.observe_candidate(target)
        dated_policy.observe_candidate(source)
        return base_policy, dated_policy

    def test_equal_observed_at_falls_through_to_base_behavior(self) -> None:
        target = _make_candidate(
            candidate_id="target-eq",
            canonical_claim="claim-A",
            base_time=self.base_time,
            observed_at=self.base_time,
            source_id="src-target-eq",
            strength=0.60,
        )
        source = _make_candidate(
            candidate_id="source-eq",
            canonical_claim="claim-B",
            base_time=self.base_time + timedelta(minutes=1),
            observed_at=self.base_time,  # equal to target
            source_id="src-source-eq",
            strength=0.60,
            contradicts=[target.candidate_id],
        )
        base_policy, dated_policy = self._run_pair(source, target)

        base_target = base_policy.store.candidate_memories[target.candidate_id]
        dated_target = dated_policy.store.candidate_memories[target.candidate_id]
        base_source = base_policy.store.candidate_memories[source.candidate_id]
        dated_source = dated_policy.store.candidate_memories[source.candidate_id]

        self.assertEqual(dated_target.state, base_target.state)
        self.assertEqual(dated_target.contradiction_count, base_target.contradiction_count)
        self.assertEqual(dated_source.state, base_source.state)
        # Both should have actually contested the target since equal == not dated.
        self.assertEqual(dated_target.state, MemoryState.CONTESTED)

    def test_fresher_source_matches_base_behavior(self) -> None:
        target = _make_candidate(
            candidate_id="target-fresh",
            canonical_claim="claim-A",
            base_time=self.base_time,
            observed_at=self.base_time,
            source_id="src-target-fresh",
            strength=0.60,
        )
        source = _make_candidate(
            candidate_id="source-fresh",
            canonical_claim="claim-B",
            base_time=self.base_time + timedelta(minutes=1),
            observed_at=self.base_time + timedelta(hours=1),  # newer than target
            source_id="src-source-fresh",
            strength=0.60,
            contradicts=[target.candidate_id],
        )
        base_policy, dated_policy = self._run_pair(source, target)

        base_target = base_policy.store.candidate_memories[target.candidate_id]
        dated_target = dated_policy.store.candidate_memories[target.candidate_id]
        base_source = base_policy.store.candidate_memories[source.candidate_id]
        dated_source = dated_policy.store.candidate_memories[source.candidate_id]

        self.assertEqual(dated_target.state, base_target.state)
        self.assertEqual(dated_target.contradiction_count, base_target.contradiction_count)
        self.assertEqual(dated_source.state, base_source.state)
        self.assertEqual(dated_target.state, MemoryState.CONTESTED)

    def test_older_source_marks_source_contested_and_leaves_target(self) -> None:
        target = _make_candidate(
            candidate_id="target-older-src",
            canonical_claim="claim-A",
            base_time=self.base_time,
            observed_at=self.base_time,
            source_id="src-target-older",
            strength=0.60,
        )
        source = _make_candidate(
            candidate_id="source-older",
            canonical_claim="claim-B",
            base_time=self.base_time + timedelta(minutes=1),
            observed_at=self.base_time - timedelta(days=30),  # older than target
            source_id="src-source-older",
            strength=0.60,
            contradicts=[target.candidate_id],
        )
        _, dated_policy = self._run_pair(source, target)

        dated_target = dated_policy.store.candidate_memories[target.candidate_id]
        dated_source = dated_policy.store.candidate_memories[source.candidate_id]

        # Stale source is contested.
        self.assertEqual(dated_source.state, MemoryState.CONTESTED)
        # Fresher target is not penalized.
        self.assertNotEqual(dated_target.state, MemoryState.CONTESTED)
        self.assertEqual(dated_target.contradiction_count, 0)

    def test_missing_target_provenance_falls_back_to_target_updated_at(self) -> None:
        # Target has no provenance; its updated_at is the fallback. Source has
        # provenance with observed_at strictly older than target.updated_at.
        target = _make_candidate(
            candidate_id="target-no-prov",
            canonical_claim="claim-A",
            base_time=self.base_time,
            include_provenance=False,
            source_id="src-target-noprov",
            strength=0.60,
        )
        source = _make_candidate(
            candidate_id="source-with-prov",
            canonical_claim="claim-B",
            base_time=self.base_time + timedelta(minutes=1),
            observed_at=self.base_time - timedelta(days=10),
            source_id="src-source-withprov",
            strength=0.60,
            contradicts=[target.candidate_id],
        )
        _, dated_policy = self._run_pair(source, target)

        dated_target = dated_policy.store.candidate_memories[target.candidate_id]
        dated_source = dated_policy.store.candidate_memories[source.candidate_id]

        # Source's observed_at < target.updated_at -> dated branch fires.
        self.assertEqual(dated_source.state, MemoryState.CONTESTED)
        self.assertNotEqual(dated_target.state, MemoryState.CONTESTED)
        self.assertEqual(dated_target.contradiction_count, 0)

    def test_missing_source_provenance_falls_back_to_source_updated_at(self) -> None:
        # Source has no provenance; its updated_at is the fallback. Target has
        # provenance with observed_at strictly newer than source.updated_at.
        target = _make_candidate(
            candidate_id="target-with-prov",
            canonical_claim="claim-A",
            base_time=self.base_time,
            observed_at=self.base_time + timedelta(days=10),
            source_id="src-target-withprov",
            strength=0.60,
        )
        source = _make_candidate(
            candidate_id="source-no-prov",
            canonical_claim="claim-B",
            base_time=self.base_time + timedelta(minutes=1),
            include_provenance=False,
            source_id="src-source-noprov",
            strength=0.60,
            contradicts=[target.candidate_id],
        )
        _, dated_policy = self._run_pair(source, target)

        dated_target = dated_policy.store.candidate_memories[target.candidate_id]
        dated_source = dated_policy.store.candidate_memories[source.candidate_id]

        # Source.updated_at = base+1min; Target.observed_at = base+10d. Source older.
        self.assertEqual(dated_source.state, MemoryState.CONTESTED)
        self.assertNotEqual(dated_target.state, MemoryState.CONTESTED)
        self.assertEqual(dated_target.contradiction_count, 0)

    def test_both_sides_missing_provenance_equal_updated_at_falls_through_to_base(self) -> None:
        target = _make_candidate(
            candidate_id="target-no-prov-eq",
            canonical_claim="claim-A",
            base_time=self.base_time,
            include_provenance=False,
            source_id="src-target-noprov-eq",
            strength=0.60,
        )
        source = _make_candidate(
            candidate_id="source-no-prov-eq",
            canonical_claim="claim-B",
            base_time=self.base_time,  # same updated_at as target
            include_provenance=False,
            source_id="src-source-noprov-eq",
            strength=0.60,
            contradicts=[target.candidate_id],
        )
        base_policy, dated_policy = self._run_pair(source, target)

        base_target = base_policy.store.candidate_memories[target.candidate_id]
        dated_target = dated_policy.store.candidate_memories[target.candidate_id]
        # Equal updated_at -> not strictly older -> base behavior preserved.
        self.assertEqual(dated_target.state, base_target.state)
        self.assertEqual(dated_target.state, MemoryState.CONTESTED)

    def test_both_sides_missing_provenance_older_source_triggers_dated_branch(self) -> None:
        target = _make_candidate(
            candidate_id="target-no-prov-fresh",
            canonical_claim="claim-A",
            base_time=self.base_time,
            include_provenance=False,
            source_id="src-target-fresh-noprov",
            strength=0.60,
        )
        source = _make_candidate(
            candidate_id="source-no-prov-old",
            canonical_claim="claim-B",
            base_time=self.base_time - timedelta(days=5),  # older updated_at
            include_provenance=False,
            source_id="src-source-old-noprov",
            strength=0.60,
            contradicts=[target.candidate_id],
        )
        _, dated_policy = self._run_pair(source, target)

        dated_target = dated_policy.store.candidate_memories[target.candidate_id]
        dated_source = dated_policy.store.candidate_memories[source.candidate_id]
        self.assertEqual(dated_source.state, MemoryState.CONTESTED)
        self.assertNotEqual(dated_target.state, MemoryState.CONTESTED)
        self.assertEqual(dated_target.contradiction_count, 0)


class CQDatedContestationDirectionPreservationTests(unittest.TestCase):
    """Confirm the four originally won mechanisms do not reverse direction."""

    def test_retraction_witness_scope_pending_directions_preserved(self) -> None:
        scenarios = generate_adversarial_upstream_noise_scenarios(10, template_mix="mixed")
        targets = [
            "adversarial_retraction_v1",
            "adversarial_witness_conflict_v1",
            "adversarial_scope_narrowing_v1",
            "adversarial_pending_competition_v1",
        ]
        for template_id in targets:
            with self.subTest(template_id=template_id):
                template_scenarios = [s for s in scenarios if s.template_id == template_id]
                self.assertTrue(template_scenarios, "expected scenarios for " + template_id)
                for scenario in template_scenarios:
                    base = execute_scenario(ConsolidationQueueLite, scenario)
                    dated = execute_scenario(CQDatedContestation, scenario)
                    base_score = base["metrics"]["answer_correctness"]
                    dated_score = dated["metrics"]["answer_correctness"]
                    # Direction preservation: where base CQ wins, dated CQ must not lose.
                    self.assertGreaterEqual(
                        dated_score,
                        base_score,
                        msg="{} regressed on {}: base={} dated={}".format(
                            template_id, scenario.scenario_id, base_score, dated_score
                        ),
                    )


class CQDatedContestationRunnerTests(unittest.TestCase):
    def test_followup_policy_set_rejected_for_non_adversarial_family(self) -> None:
        with self.assertRaises(ValueError):
            build_run_artifact(
                1,
                template_mix="mixed",
                family=FORCED_CONTRADICTION,
                policy_set=POLICY_SET_FOLLOWUP,
            )
        with self.assertRaises(ValueError):
            build_run_artifact(
                1,
                template_mix="mixed",
                family=SCOPE_CONTAMINATION,
                policy_set=POLICY_SET_FOLLOWUP,
            )

    def test_followup_includes_dated_contestation_on_adversarial_family(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=ADVERSARIAL_UPSTREAM_NOISE,
            policy_set=POLICY_SET_FOLLOWUP,
        )
        policy_names = [policy["policy_name"] for policy in artifact["policies"]]
        self.assertIn(CQDatedContestation.policy_name, policy_names)
        self.assertIn(ConsolidationQueueLite.policy_name, policy_names)
        # Followup also keeps phase2_5 contents.
        self.assertIn("mem0_lite", policy_names)
        # ablation_notes mentions CQDatedContestation only under followup.
        self.assertIn(CQDatedContestation.policy_name, artifact["ablation_notes"])
        self.assertEqual(artifact["policy_set"], POLICY_SET_FOLLOWUP)

    def test_phase2_5_does_not_include_dated_contestation(self) -> None:
        artifact = build_run_artifact(
            5,
            template_mix="mixed",
            family=ADVERSARIAL_UPSTREAM_NOISE,
            policy_set=POLICY_SET_PHASE_2_5,
        )
        policy_names = [policy["policy_name"] for policy in artifact["policies"]]
        self.assertNotIn(CQDatedContestation.policy_name, policy_names)
        self.assertNotIn(CQDatedContestation.policy_name, artifact["ablation_notes"])
        self.assertNotIn(CQDatedContestation.policy_name, artifact["baseline_notes"])


if __name__ == "__main__":
    unittest.main()
