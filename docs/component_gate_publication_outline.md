# Component Gate Publication Outline

Date: 2026-05-11

This outline defines the smallest publishable package that honestly combines the
existing oracle-mode benchmark evidence with the locked noisy-mode component
gate result.

## Target Framing

Preferred format:

- workshop paper or technical report

Primary claim:

- the repository contributes a preregistered memory-governance benchmark with a
  narrow oracle-mode CQ policy result and an inspectable failure taxonomy for
  why a local noisy extractor cannot yet support publishable noisy-mode policy
  comparisons

Non-claim:

- do not claim noisy-mode CQ policy superiority
- do not claim extractor generalization across model families from the current
  7B result alone

## Section Structure

| Section | Purpose | Existing evidence | Still needed |
| --- | --- | --- | --- |
| 1. Benchmark question and design | Define the memory-governance question, six scenario families, frozen mechanism-diverse contracts, and fairness constraints across policies | `README.md`, `PROJECT_PLAN.md`, `docs/preregistration.md` | none |
| 2. Preregistration discipline | Show that predictions were committed before frozen policy execution and that the benchmark can yield negative or mixed results without changing the contract | `docs/preregistration.md`, `PROJECT_PLAN.md` | none |
| 3. Oracle-mode policy results | Report the frozen oracle sweep and the narrow CQ-vs-`Mem0Lite` support | `docs/predictions_vs_results.md`, `docs/product_progress.md`, frozen oracle artifact paths cited in `docs/predictions_vs_results.md` | none |
| 4. Component-quality gate methodology | Explain Phase A, determinism, aggregate CI gates, per-family observed gates, and frozen-sentinel observed gates | `PROJECT_PLAN.md`, `docs/product_progress.md`, `scripts/run_component_gate_decision.py` | none |
| 5. Locked noisy-mode result and failure taxonomy | Explain why the 7B `general_v1` path remained locked, where failures concentrate, and what mode-level patterns they form | `docs/product_progress.md`, `docs/component_diagnostic_matrix.md` | dedicated repo-tracked taxonomy note |
| 6. Discussion and publication boundary | State what is supported now, what remains blocked, and why the contribution is benchmark + failure taxonomy rather than noisy-policy evidence | `PROJECT_PLAN.md`, `docs/product_progress.md` | publication outline wording |
| 7. External positioning | Place LongMemEval and any future noisy transfer result as external validation rather than a current claim | `PROJECT_PLAN.md` | none for the current draft |

## Existing Evidence To Lead With

### Oracle-mode result

- all 108 preregistered oracle-mode deltas matched observed deltas on the frozen
  mechanism-diverse sweep
- CQ does not show broad answer-quality superiority over `Mem0Lite` on the
  frozen aggregate
- the narrow oracle-mode support is lower premature durable promotion versus
  `Mem0Lite`, with CQ and `Mem0Lite` tied on the main answer-correctness and
  false-assertion aggregate metrics

Primary sources:

- `docs/preregistration.md`
- `docs/predictions_vs_results.md`

### Locked noisy-mode result

- the authoritative 7B `general_v1` gate passed Phase A and determinism but
  still stayed locked
- aggregate gates passed, but per-family and frozen-sentinel checks blocked
  unlock
- the failure pattern is concentrated in invalid structured outputs and
  contradiction-linking defects, not aggregate CI arithmetic

Primary sources:

- `docs/product_progress.md`
- `PROJECT_PLAN.md`

## Minimum Additional Evidence Decision

For a workshop paper or technical report, the minimum additional evidence is:

1. one descriptive 32B `scope_contamination` row

Rationale:

- the current 7B taxonomy is already resolved enough to support the lock
  decision
- one 32B row adds the smallest size-scaling check on the family that most
  clearly exhibits schema-sensitive failures, especially `scope_key`
  omission and `contradicts_event_ids` namespace confusion
- this lets the paper say whether the taxonomy looks like a pure 7B capacity
  ceiling or whether the same failure pattern survives a larger model on the
  most diagnostic family

Not required for the first publication draft:

- a second model-family row

Condition:

- only add a second model family if the target paper starts making a
  cross-family or cross-model generalization claim that one 32B row cannot
  honestly support

## Execution Order

1. draft the locked-gate failure-taxonomy note in
   `docs/component_gate_failure_taxonomy.md`
2. keep the 7B gate verdict fixed while drafting
3. if the publication draft still needs size-scaling evidence, run one
   descriptive 32B `scope_contamination` row as a separate follow-up
4. integrate the taxonomy note and oracle-mode results into a full draft

## LongMemEval Positioning

- keep LongMemEval as positioning and future work in the current draft
- do not present a noisy-mode LongMemEval transfer result while Phase 4 remains
  on hold
- frame future LongMemEval work as a transfer check on whether a later
  CQ-versus-baseline policy comparison survives outside the authored benchmark

## Boundaries

- do not reopen `general_v2`
- do not loosen validators or lower thresholds
- do not use any descriptive 32B result to reinterpret the locked 7B gate
- do not start noisy-mode policy comparisons while
  `policy_comparison_unlocked=false`
