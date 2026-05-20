# CQ Pending Multi-Evidence Follow-Up Preregistration

Date: 2026-05-20

Status: locked before implementation of `cq_pending_multi_evidence`,
`reflection_eager_write_cardinality_capped`, or any follow-up policy run.

cq_pending_multi_evidence_lock_sha256: 84b3c44148494c1b6f72e8201a8da886f8e1f48e49ce00197f535c7e08638840

This follow-up advances the `PROJECT_PLAN.md` immediate next-task lane for a
separately preregistered pending multi-evidence retrieval experiment motivated
by the completed LongMemEval X.4 evidence-completeness loss.

The X.4 result is not changed by this document. The original `phase2_5`
policy set, adapter, annotations, judge calibration, sensitivity cells, and
headline metric remain locked. This follow-up asks whether the diagnosed CQ
failure is a readout-cardinality interface gap.

<!-- CQ_PENDING_MULTI_EVIDENCE_PROTOCOL_START -->
## 1. Research Question

LongMemEval X.4 found that current `consolidation_queue_lite` retrieves at
least one gold evidence session in every agreed case but never retrieves both
under `all_hit_at_50`. The diagnosed mechanism is that CQ pending lookup
returns one strongest/latest pending candidate, while eager durable baselines
return all reinforcing candidate ids attached to a durable memory.

This follow-up asks:

- can CQ expose all eligible same-slot pending evidence without changing the
  candidate stream, annotations, adapter, storage schema, judge, or headline
  metric?
- does a cardinality-capped Reflection control reproduce the original X.4
  evidence-completeness loss, isolating readout cardinality as the variable?

The intended contribution is a preregistered interface-repair test, not a new
memory-system claim and not a retroactive reinterpretation of X.4.

## 2. Invariants

The follow-up must preserve these invariants:

- same upstream `CandidateUpdate` stream for all policies;
- no new field on `CandidateUpdate`, `DurableMemory`, `QuestionSpec`, or
  `AnswerTrace`;
- no storage-level substrate change;
- at most one new public `MemoryStore` query method for plural pending lookup;
- no LongMemEval annotation, adapter, gold-loader, judge, or scoring-target
  changes;
- `all_hit_at_50` remains the headline follow-up metric;
- `answer_correct` remains diagnostic only;
- original X.4 and `phase2_5` artifacts remain unmodified as historical
  evidence.

## 3. Variants

### 3.1 `cq_pending_multi_evidence`

`cq_pending_multi_evidence` is a `ConsolidationQueueLite` follow-up variant.
It changes only the pending fallback branch of `answer_question`.

When no durable memory is active and pending lookup is enabled, it calls a new
public substrate method, `MemoryStore.strongest_pending_candidates`, which
returns all eligible pending candidates for the query's canonical id and scope,
ordered by `(strength, updated_at)` descending. Eligibility must match the
existing singular pending lookup filter:

- excludes `CONTESTED`;
- excludes `DEMOTED`;
- excludes `REJECTED`;
- excludes `EXPIRED`;
- applies normal scope matching;
- applies `pending_use_allowed` before returning candidate ids to the answer
  trace.

The variant must not return every same-slot pending candidate blindly.

### 3.2 `reflection_eager_write_cardinality_capped`

`reflection_eager_write_cardinality_capped` is a diagnostic control over
`ReflectionEagerWriteLite`. It preserves Reflection's write behavior and
durable storage. It changes only the answer readout: when a durable memory is
active, it returns one candidate id from `durable.created_from_candidate_ids`
instead of the full list.

The chosen candidate id is deterministic: the highest-strength candidate among
the durable's `created_from_candidate_ids`, tie-broken by `updated_at`, then
candidate id. This mirrors CQ's one-candidate readout shape without changing
Reflection's writes.

The control is load-bearing. If capping a winning eager baseline's readout
also breaks `all_hit_at_50`, the X.4 CQ loss is attributable to readout
cardinality rather than hidden storage or adapter asymmetry.

## 4. Negative Controls

Before any external follow-up run, tests must show that
`cq_pending_multi_evidence` filters bad sibling evidence.

Required negative controls:

1. Same-slot legitimate siblings plus a below-use-floor poisoned sibling:
   return only the legitimate pending candidates.
2. Same-slot candidate contested by a later contradiction: do not return the
   contested candidate.
3. Same canonical id across different scope keys: return only scope-matching
   candidates.
4. Mirrored-source support below durable-promotion threshold: return only the
   candidate that clears pending-use threshold, not weak mirrored siblings.
5. Same-slot demoted sibling: do not return the demoted candidate.

Failure of any negative control triggers Outcome D.

## 5. Locked Policy Set

Add `phase2_5_followup` as a new policy set. It includes every policy in
`phase2_5` plus:

- `cq_pending_multi_evidence`;
- `reflection_eager_write_cardinality_capped`.

It must not replace or modify `phase2_5`.

## 6. Internal Regression Gate

Before LongMemEval retest, run the follow-up policy set on:

- `forced_contradiction`, `template_mix=mixed`;
- `preference_drift`, `template_mix=mixed`;
- `mechanism_diverse_heldout`, `template_mix=frozen`;
- `adversarial_upstream_noise`, `template_mix=mixed`.

`cq_pending_multi_evidence` must match base `consolidation_queue_lite` within
5 percentage points on every primary summary metric emitted for the overall
row in these internal runs. Any regression larger than 5 points triggers
Outcome D and stops before LongMemEval retest.

## 7. External Follow-Up Comparisons

Run `scripts/run_longmemeval_transfer.py` with `policy_set=phase2_5_followup`,
the same adapter pin, preregistration lock, judge stability report, and three
meaningful cells used by X.4:

- `primary_contract`;
- `path_a_only_denominator`;
- `path_b_only_denominator`.

Locked comparisons:

- `cq_pending_multi_evidence` vs base CQ on `all_hit_at_50`;
- `cq_pending_multi_evidence` vs base Reflection on `all_hit_at_50`;
- `reflection_eager_write_cardinality_capped` vs base Reflection on
  `all_hit_at_50`;
- `cq_pending_multi_evidence` vs
  `reflection_eager_write_cardinality_capped` on `all_hit_at_50`.

The cardinality control must be independently active: on LongMemEval cases
where base Reflection returns multiple candidate ids, capped Reflection must
return a strict subset.

## 8. Outcome Buckets

Outcome A: interface repair confirmed.

- `cq_pending_multi_evidence` reaches `all_hit_at_50 >= 70/71` on the primary
  contract cell;
- signs are stable across all three cells;
- `reflection_eager_write_cardinality_capped` fails `all_hit_at_50` at or near
  base-CQ level on the primary cell;
- internal regression gate passes;
- negative controls pass.

Outcome A-weak: variant succeeds but cardinality hypothesis fails.

- `cq_pending_multi_evidence` reaches `all_hit_at_50 >= 70/71`;
- `reflection_eager_write_cardinality_capped` still passes `all_hit_at_50`.

This does not support a positive interface-repair claim. It is written as a
falsified mechanism explanation.

Outcome B: partial repair.

- `cq_pending_multi_evidence` improves over base CQ on primary-cell
  `all_hit_at_50` by at least 50 percentage points but remains below `70/71`;
- internal regression and negative controls pass.

Outcome C: interface hypothesis falsified.

- `cq_pending_multi_evidence` improves over base CQ by less than 10 percentage
  points on primary-cell `all_hit_at_50`.

Outcome D: internal failure or abort.

- any new schema field is added;
- any storage-level substrate change is introduced;
- any negative control fails;
- any internal regression exceeds 5 percentage points;
- X.4 invariant checks fail;
- capped Reflection is not a strict readout subset where base Reflection
  returns multiple candidates.

## 9. Out Of Scope

- changing LongMemEval annotations;
- changing the adapter;
- changing the judge calibration report;
- changing `answer_session_ids` handling;
- changing `all_hit_at_50`;
- adding a natural-language QA generator;
- claiming LongMemEval-S, LongMemEval-V2, distractor-heavy retrieval, or broad
  external generalization;
- retroactively changing the X.4 bucket verdict.
<!-- CQ_PENDING_MULTI_EVIDENCE_PROTOCOL_END -->

## Lock Maintenance

The lock is computed over the block between
`CQ_PENDING_MULTI_EVIDENCE_PROTOCOL_START` and
`CQ_PENDING_MULTI_EVIDENCE_PROTOCOL_END`.

Check:

```bash
awk '/CQ_PENDING_MULTI_EVIDENCE_PROTOCOL_START/{flag=1; next} /CQ_PENDING_MULTI_EVIDENCE_PROTOCOL_END/{flag=0} flag' docs/cq_pending_multi_evidence_preregistration.md | shasum -a 256
```
