# PFLC-Surface Audit Note

Date: 2026-05-25

## Verdict

Demote to design note.

The current local policies do not expose pre-existing, separable
policy-facing lookup surfaces that would support a deletion experiment without
refactoring. Proceeding to a deletion PFLC experiment would require
manufacturing new public query surfaces or a deletion-handler abstraction,
which this revision explicitly excludes.

## Files Inspected

- `cq/memory/consolidation_queue.py`
- `cq/memory/cq_pending_multi_evidence.py`
- `cq/memory/reflection_eager_write.py`
- `cq/memory/reflection_eager_write_cardinality_capped.py`
- `cq/memory/mem0_lite.py`
- `cq/memory/substrate.py`
- Runner/test references to `answer_question`, `active_durable`, and direct
  `store` inspection

## Findings

All primary local policies expose the same policy-level read method:
`answer_question(question: QuestionSpec)`. The method receives a
`relevant_canonical_id`, `scope_level`, and `scope_key`, then directly queries
the shared `MemoryStore`.

- `ConsolidationQueueLite` resolves durable memories through
  `MemoryStore.active_durable` and pending fallback through
  `MemoryStore.strongest_pending_candidate`.
- `CQPendingMultiEvidence` uses the same durable path and changes only the
  pending fallback to `MemoryStore.strongest_pending_candidates`.
- `ReflectionEagerWriteLite` and `Mem0Lite` resolve durable memories through
  `MemoryStore.active_durable`.
- `ReflectionEagerWriteCardinalityCapped` preserves Reflection's write path
  and changes only answer-time durable candidate cardinality.
- `MemoryStore` exposes substrate-level candidate, durable, lifecycle, and
  query helpers, but those helpers are not distinct public PFLC surfaces owned
  by each policy.

Runners execute policies through `answer_question` and then snapshot
`policy.store`. Many tests inspect `policy.store` directly for assertions, but
that is test instrumentation rather than a policy-facing query contract. The
schema also has no committed deletion event or deletion handler.

## Consequence

There is no "proceed directly" path for B3 in this revision. A deletion PFLC
experiment should be future work only after a separate design step defines
stable policy-facing surfaces and deletion semantics before any policy run.
