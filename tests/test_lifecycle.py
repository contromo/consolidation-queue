from datetime import datetime
import unittest

from cq.memory.lifecycle import merge_thresholds, pending_use_allowed, should_promote_candidate
from cq.memory.substrate import scope_matches
from cq.schemas.memory import CandidateUpdate, ClaimType, ProvenanceRecord, ScopeLevel


def make_candidate_with_scores(
    candidate_id: str,
    claim: str,
    verification_score: float,
    trust_score: float,
) -> CandidateUpdate:
    observed_at = datetime(2026, 1, 1, 9, 0, 0)
    return CandidateUpdate(
        candidate_id=candidate_id,
        raw_text=claim,
        raw_claim=claim,
        canonical_claim=claim,
        claim_type=ClaimType.WORLD_FACT,
        scope_level=ScopeLevel.PROJECT,
        scope_key="repo-a",
        provenance=[
            ProvenanceRecord(
                source_kind="test",
                source_id="source-" + candidate_id,
                trust_score=trust_score,
                observed_at=observed_at,
            )
        ],
        verification_score=verification_score,
        created_at=observed_at,
        updated_at=observed_at,
    )


class LifecycleThresholdTests(unittest.TestCase):
    def test_world_fact_promotion_threshold_is_inclusive(self) -> None:
        thresholds = merge_thresholds()
        candidate = make_candidate_with_scores(
            candidate_id="promotion-edge",
            claim="Acme acquired Northstar",
            verification_score=0.85,
            trust_score=0.85,
        )

        self.assertEqual(candidate.promotion_score, 0.85)
        self.assertTrue(should_promote_candidate(candidate, thresholds))

    def test_world_fact_pending_use_threshold_is_inclusive(self) -> None:
        thresholds = merge_thresholds()
        candidate = make_candidate_with_scores(
            candidate_id="pending-edge",
            claim="Acme acquired Northstar",
            verification_score=0.40,
            trust_score=0.40,
        )

        self.assertEqual(candidate.strength, 0.40)
        self.assertTrue(pending_use_allowed(candidate, thresholds))


class ScopeMatchTests(unittest.TestCase):
    def test_world_global_scope_matches_any_query_scope(self) -> None:
        self.assertTrue(
            scope_matches(
                ScopeLevel.WORLD_GLOBAL,
                "global",
                ScopeLevel.PROJECT,
                "repo-a",
            )
        )

    def test_non_global_scope_requires_same_level_and_key(self) -> None:
        self.assertTrue(scope_matches(ScopeLevel.PROJECT, "repo-a", ScopeLevel.PROJECT, "repo-a"))
        self.assertFalse(scope_matches(ScopeLevel.PROJECT, "repo-a", ScopeLevel.PROJECT, "repo-b"))
        self.assertFalse(scope_matches(ScopeLevel.PROJECT, "repo-a", ScopeLevel.SESSION, "repo-a"))


if __name__ == "__main__":
    unittest.main()
