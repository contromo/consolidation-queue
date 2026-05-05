from __future__ import annotations

from typing import Dict, Optional

from cq.schemas.memory import CandidateUpdate, ClaimType


DEFAULT_THRESHOLDS = {
    "world_fact_promotion": 0.85,
    "non_world_promotion": 0.70,
    "world_fact_pending_use": 0.40,
    "overwrite_margin": 0.05,
    "minimum_write_confidence": 0.55,
}


def merge_thresholds(overrides: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    if overrides:
        thresholds.update(overrides)
    return thresholds


def should_promote_candidate(candidate: CandidateUpdate, thresholds: Dict[str, float]) -> bool:
    if candidate.claim_type == ClaimType.WORLD_FACT:
        return candidate.promotion_score >= thresholds["world_fact_promotion"]
    return candidate.promotion_score >= thresholds["non_world_promotion"]


def pending_use_allowed(candidate: CandidateUpdate, thresholds: Dict[str, float]) -> bool:
    if candidate.claim_type == ClaimType.WORLD_FACT:
        return candidate.strength >= thresholds["world_fact_pending_use"]
    return candidate.strength >= 0.35
