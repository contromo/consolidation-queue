from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from cq.memory.substrate import MemoryStore
from cq.schemas.memory import CandidateUpdate, ClaimType, MemoryState, ProvenanceRecord, ScopeLevel


def _candidate(candidate_id: str, *, strength: float, minutes: int = 0) -> CandidateUpdate:
    timestamp = datetime(2026, 5, 20, 9, 0, 0) + timedelta(minutes=minutes)
    return CandidateUpdate(
        candidate_id=candidate_id,
        raw_text="Use command {}".format(candidate_id),
        raw_claim="Use command {}".format(candidate_id),
        canonical_claim="Use the local test command",
        canonical_id="slot-shared",
        claim_type=ClaimType.PROCEDURAL_KNOWLEDGE,
        scope_level=ScopeLevel.PROJECT,
        scope_key="project:alpha",
        provenance=[
            ProvenanceRecord(
                source_kind="unit_test",
                source_id="source-{}".format(candidate_id),
                trust_score=strength,
                observed_at=timestamp,
            )
        ],
        verification_score=strength,
        created_at=timestamp,
        updated_at=timestamp,
    )


class SubstratePendingLookupTests(unittest.TestCase):
    def test_plural_lookup_matches_singular_order_and_exclusion_filter(self) -> None:
        store = MemoryStore("unit")
        for candidate in [
            _candidate("low", strength=0.45, minutes=0),
            _candidate("high", strength=0.65, minutes=1),
            _candidate("contested", strength=0.90, minutes=2),
            _candidate("demoted", strength=0.85, minutes=3),
        ]:
            store.add_candidate(candidate)
        store.update_candidate_state("contested", MemoryState.CONTESTED, "test", datetime(2026, 5, 20, 9, 5, 0))
        store.update_candidate_state("demoted", MemoryState.DEMOTED, "test", datetime(2026, 5, 20, 9, 6, 0))

        singular = store.strongest_pending_candidate(
            "slot-shared",
            ScopeLevel.PROJECT,
            "project:alpha",
        )
        plural = store.strongest_pending_candidates(
            "slot-shared",
            ScopeLevel.PROJECT,
            "project:alpha",
        )

        self.assertEqual(singular.candidate_id, "high")
        self.assertEqual([candidate.candidate_id for candidate in plural], ["high", "low"])

    def test_plural_lookup_returns_empty_list_when_no_candidate_matches(self) -> None:
        store = MemoryStore("unit")
        store.add_candidate(_candidate("other", strength=0.60))

        self.assertEqual(
            store.strongest_pending_candidates(
                "slot-shared",
                ScopeLevel.PROJECT,
                "project:beta",
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
