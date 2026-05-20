# CQ Pending Multi-Evidence Follow-Up Results

Date: 2026-05-20

## Verdict

Outcome A: preregistered interface repair confirmed.

`cq_pending_multi_evidence` closes the LongMemEval evidence-completeness gap
under the locked follow-up protocol. On the primary contract cell it moves
`all_hit_at_50` from base CQ's `0/71` to `71/71`, matching base Reflection and
`Mem0Lite`. The result is stable across the two denominator-sensitivity cells
(`72/72` on both).

The cardinality control is load-bearing and supports the mechanism
interpretation: `reflection_eager_write_cardinality_capped` writes normally but
returns one durable candidate id at answer time, and it falls from base
Reflection's `71/71` to `0/71` on the primary cell. The follow-up therefore
isolates readout cardinality as the X.4 evidence-completeness variable.

This does not change the original X.4 verdict. Base
`consolidation_queue_lite` still loses `all_hit_at_50` to Reflection and
`Mem0Lite` by `-1.0` in every cell. The follow-up is a separate preregistered
interface-repair result.

## Preregistration And Commits

- Preregistration:
  `docs/cq_pending_multi_evidence_preregistration.md`
- Lock SHA:
  `84b3c44148494c1b6f72e8201a8da886f8e1f48e49ce00197f535c7e08638840`
- Preregistration commit:
  `ee3ca19` (`Preregister pending multi-evidence follow-up`)
- Implementation / run commit:
  `c0befcc3162317896730838ca4a64e5218707c23`

## Artifacts

External follow-up:

- `data/external/longmemeval/transfer_followup_summary.json`
- `data/external/longmemeval/transfer_followup_per_case_rows.csv`
- `data/external/longmemeval/transfer_followup_manifest.json`
- `data/external/longmemeval/sensitivity_followup/primary_contract.json`
- `data/external/longmemeval/sensitivity_followup/path_a_only_denominator.json`
- `data/external/longmemeval/sensitivity_followup/path_b_only_denominator.json`

Internal regression metrics:

- `data/results/cq_pending_multi_evidence_forced_contradiction_mixed_metrics.csv`
- `data/results/cq_pending_multi_evidence_preference_drift_mixed_metrics.csv`
- `data/results/cq_pending_multi_evidence_mechanism_diverse_heldout_frozen_metrics.csv`
- `data/results/cq_pending_multi_evidence_adversarial_upstream_noise_mixed_metrics.csv`
- `data/results/cq_pending_multi_evidence_evidence_conflict_spectrum_mixed_metrics.csv`

The large internal per-scenario JSON artifacts were generated under
`data/runs/cq_pending_multi_evidence_*` and remain regeneratable-only per the
artifact policy.

## External Transfer Readout

Run shape:

- policy set: `phase2_5_followup`
- judge mode: `local_judge`
- headline metric: `all_hit_at_50`
- rows: `2,365` policy/cell/case rows plus CSV header
- candidate-stream hash invariant: passed in all three cells

Per-cell counts:

| Cell | Base CQ | `cq_pending_multi_evidence` | Reflection | Reflection capped | `Mem0Lite` |
| --- | ---: | ---: | ---: | ---: | ---: |
| `primary_contract` | `0/71` | `71/71` | `71/71` | `0/71` | `71/71` |
| `path_a_only_denominator` | `0/72` | `72/72` | `72/72` | `0/72` | `72/72` |
| `path_b_only_denominator` | `0/72` | `72/72` | `72/72` | `0/72` | `72/72` |

Pairwise headline deltas:

| Cell | Comparison | Delta | 95% bootstrap interval | Sign |
| --- | --- | ---: | --- | --- |
| `primary_contract` | follow-up CQ - base CQ | `+1.0` | `[+1.0, +1.0]` | positive |
| `primary_contract` | follow-up CQ - Reflection | `+0.0` | `[+0.0, +0.0]` | zero |
| `primary_contract` | Reflection capped - Reflection | `-1.0` | `[-1.0, -1.0]` | negative |
| `path_a_only_denominator` | follow-up CQ - base CQ | `+1.0` | `[+1.0, +1.0]` | positive |
| `path_a_only_denominator` | follow-up CQ - Reflection | `+0.0` | `[+0.0, +0.0]` | zero |
| `path_a_only_denominator` | Reflection capped - Reflection | `-1.0` | `[-1.0, -1.0]` | negative |
| `path_b_only_denominator` | follow-up CQ - base CQ | `+1.0` | `[+1.0, +1.0]` | positive |
| `path_b_only_denominator` | follow-up CQ - Reflection | `+0.0` | `[+0.0, +0.0]` | zero |
| `path_b_only_denominator` | Reflection capped - Reflection | `-1.0` | `[-1.0, -1.0]` | negative |

The summary's follow-up outcome field records:

- `bucket = "A"`
- `primary_improvement_points = 1.0`
- `reflection_capped_strict_subset_on_primary = true`
- `followup_success_all_cells = true`

## Internal Regression Gate

The follow-up variant matched base CQ exactly on every checked overall metric
across all internal regression cells. The maximum absolute delta was `0.0`.

| Family | Base CQ answer correctness | Variant answer correctness | Max checked overall delta |
| --- | ---: | ---: | ---: |
| `forced_contradiction` | `1.00` | `1.00` | `0.00` |
| `preference_drift` | `1.00` | `1.00` | `0.00` |
| `mechanism_diverse_heldout` | `0.67` | `0.67` | `0.00` |
| `adversarial_upstream_noise` | `0.80` | `0.80` | `0.00` |
| `evidence_conflict_spectrum` | `1.00` | `1.00` | `0.00` |

Focused negative-control unit tests also passed:

- below-floor poisoned sibling is not returned;
- contested sibling is not returned;
- wrong-scope sibling is not returned;
- weak mirrored-source siblings are not returned;
- demoted sibling is not returned.

## Mechanism Interpretation

The implementation makes one public query-API addition to the shared substrate:
`MemoryStore.strongest_pending_candidates` returns all candidates passing the
same eligibility filter used by the singular lookup, ordered by
`(strength, updated_at)` (`cq/memory/substrate.py:373`).

`CQPendingMultiEvidence.answer_question` changes only the no-durable pending
fallback branch: it calls the plural query and includes all candidates that
also pass `pending_use_allowed` in `resolved_candidate_ids`
(`cq/memory/cq_pending_multi_evidence.py:55`).

`ReflectionEagerWriteCardinalityCapped` preserves Reflection's write path and
changes only answer readout cardinality: it returns one candidate id from the
active durable memory (`cq/memory/reflection_eager_write_cardinality_capped.py:17`).

Because capped Reflection reproduces base CQ's LongMemEval failure while
follow-up CQ matches base Reflection, the X.4 gap is best attributed to
policy-facing readout cardinality. It is not evidence of a richer CQ substrate,
changed annotations, changed adapter, changed judge, or changed headline
metric.

## Boundaries

Supported:

- the fair-stream method produced a mechanism-local repair under locked
  constraints;
- current CQ's X.4 evidence-completeness loss is repairable by exposing all
  eligible same-slot pending evidence;
- cardinality capping a winning eager baseline reproduces the loss.

Unsupported:

- broad CQ external generalization;
- LongMemEval-S, LongMemEval-V2, or distractor-heavy retrieval claims;
- natural-language answer-quality claims;
- retroactive change to the X.4 result;
- treating `cq_pending_multi_evidence` as a new general memory system rather
  than a follow-up interface repair.
