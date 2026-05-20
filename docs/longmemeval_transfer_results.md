# LongMemEval Phase X.4 Transfer Results

Date: 2026-05-19

## Verdict

Bucket A-negative: the externalization methodology passed and the transfer
readout is directionally stable, but the stable direction is against
`consolidation_queue_lite` on the headline completeness metric
`all_hit_at_50`.

This is not evidence of CQ generalizing to LongMemEval. It is evidence that the
fair-stream externalization protocol can produce an inspectable transfer
readout, and that on the current LongMemEval v1 controlled-pilot adapter CQ
systematically loses the headline PFLC metric to immediate-write baselines.

The metric-interface nuance is load-bearing: CQ matches the eager baselines on
`any_hit_at_50` in every cell, meaning it exposes at least one gold evidence
session for every case, but loses `all_hit_at_50` in every cell because it
never exposes both gold evidence sessions. The X.4 bucket uses
`all_hit_at_50`, so the formal bucket is A-negative; the body below should be
read as "evidence exposure transfers, evidence completeness does not."

## Artifacts

- Summary: `data/external/longmemeval/transfer_summary.json`
- Per-case rows: `data/external/longmemeval/transfer_per_case_rows.csv`
- Manifest: `data/external/longmemeval/transfer_manifest.json`
- Sensitivity cells:
  - `data/external/longmemeval/sensitivity/primary_contract.json`
  - `data/external/longmemeval/sensitivity/path_a_only_denominator.json`
  - `data/external/longmemeval/sensitivity/path_b_only_denominator.json`

The manifest records a clean-worktree run at commit
`5e079b32192894d62f9855eb048e9d68a21d3fa4`, with
`dirty_worktree_check_passed = true` and `judge_mode = local_judge`.

## Run Shape

- Headline metric: `all_hit_at_50`
- Judge model: `qwen2.5:32b-instruct-q4_K_M`
- Policies: 9
- Cells: 3 meaningful sensitivity cells
- Scored policy/cell/case rows: 1,935
- CSV rows including header: 1,936

Cell denominators:

| Cell | Cases | Candidate-stream hash invariant |
|---|---:|---|
| `primary_contract` | 71 | pass |
| `path_a_only_denominator` | 72 | pass |
| `path_b_only_denominator` | 72 | pass |

## PFLC Pairwise Result

CQ loses the headline metric to both Reflection and Mem0 in every cell:

| Cell | Comparison | Delta on `all_hit_at_50` | 95% bootstrap interval | Sign |
|---|---|---:|---|---|
| `primary_contract` | CQ - Reflection | -1.0 | [-1.0, -1.0] | negative |
| `path_a_only_denominator` | CQ - Reflection | -1.0 | [-1.0, -1.0] | negative |
| `path_b_only_denominator` | CQ - Reflection | -1.0 | [-1.0, -1.0] | negative |
| `primary_contract` | CQ - Mem0 | -1.0 | [-1.0, -1.0] | negative |
| `path_a_only_denominator` | CQ - Mem0 | -1.0 | [-1.0, -1.0] | negative |
| `path_b_only_denominator` | CQ - Mem0 | -1.0 | [-1.0, -1.0] | negative |

The paired-bootstrap interval collapses to `[-1.0, -1.0]` because every paired
case delta is exactly `-1.0`: CQ fails `all_hit_at_50` on every case while the
comparator succeeds on every case. This is expected behavior for the fixed-seed
paired bootstrap, not a confidence-interval implementation bug.

The sibling evidence-exposure metric gives a different policy story:

| Cell | Comparison | Delta on `any_hit_at_50` | Sign |
|---|---|---:|---|
| `primary_contract` | CQ - Reflection | 0.0 | zero |
| `path_a_only_denominator` | CQ - Reflection | 0.0 | zero |
| `path_b_only_denominator` | CQ - Reflection | 0.0 | zero |
| `primary_contract` | CQ - Mem0 | 0.0 | zero |
| `path_a_only_denominator` | CQ - Mem0 | 0.0 | zero |
| `path_b_only_denominator` | CQ - Mem0 | 0.0 | zero |

The runner reports Bucket A because the contract-sensitivity sign is stable
across all three meaningful cells. The sign is negative, so this is a stable
transfer loss for CQ on evidence completeness, not a positive CQ result and not
a total evidence-exposure failure.

## Policy Pattern

Every selected LongMemEval case has two gold evidence sessions. CQ retrieves at
least one gold session in every case but never retrieves both, so it clears
`any_hit_at_50` and fails `all_hit_at_50`.

By contrast, `reflection_eager_write_lite`, `mem0_lite`, and
`naive_eager_write_lite` retrieve both gold evidence sessions for every case in
all three cells.

| Policy family | `all_hit_at_50` pattern | `any_hit_at_50` pattern |
|---|---|---|
| `consolidation_queue_lite` | 0/71, 0/72, 0/72 | 71/71, 72/72, 72/72 |
| `reflection_eager_write_lite` | 71/71, 72/72, 72/72 | 71/71, 72/72, 72/72 |
| `mem0_lite` | 71/71, 72/72, 72/72 | 71/71, 72/72, 72/72 |
| `naive_eager_write_lite` | 71/71, 72/72, 72/72 | 71/71, 72/72, 72/72 |
| `no_memory_lite` | 0/71, 0/72, 0/72 | 0/71, 0/72, 0/72 |

The CQ ablations that still use pending lookup match CQ on `any_hit_at_50` but
also fail `all_hit_at_50`; `cq_no_pending_lookup_use` behaves like no-memory on
this adapter.

The singleton CQ behavior is not a hidden judge artifact. In
`cq/memory/consolidation_queue.py`, `answer_question` falls back to
`self.store.strongest_pending_candidate(...)` when no durable memory exists.
`MemoryStore.strongest_pending_candidate` in `cq/memory/substrate.py` sorts
eligible pending candidates by `(strength, updated_at)` and returns only
`allowed[0]`. On this adapter, both gold evidence candidates share the queried
canonical id, but CQ's pending lookup exposes only the strongest/latest pending
candidate. `reflection_eager_write_lite`, `mem0_lite`, and
`naive_eager_write_lite` instead answer from a durable memory whose
`created_from_candidate_ids` has been reinforced with both supporting
candidates, so they expose both evidence sessions.

## Judge Diagnostic

`answer_correct` is diagnostic only in this X.4 result. It is 0/1,935 across
all judged policy rows. This confirms the pre-run smoke finding that policy
`answer_text` is currently a structured memory-trace surface, not a
natural-language answer suitable for headline QA scoring.

## Interpretation

The fair-stream adapter and judge gates held up:

- same candidate stream across policies;
- clean-worktree provenance;
- adapter pin validation;
- local judge calibration gate passed before transfer;
- three-cell sensitivity audit produced a stable sign.

But the scientific result is negative for CQ under the current LongMemEval
adapter on evidence completeness. The immediate-write baselines retain both
evidence sessions; CQ's pending-memory lookup exposes only one of the two
evidence sessions needed by the PFLC `all_hit_at_50` target. CQ does retain
evidence exposure under `any_hit_at_50`, so the result should be treated as a
policy-interface gap around pending multi-evidence retrieval rather than a
complete failure to find relevant evidence.

This should be written as an external-transfer failure of the current CQ policy
interface, not as a failure of the externalization methodology.
