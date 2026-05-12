# Component Gate Follow-Up Benchmark Memo

Date: 2026-05-12

This memo records the completed follow-up evidence block from
`docs/component_gate_followup_preregistration.md` and decides whether the next
step is drafting or more benchmark expansion.

## Inputs

- locked 7B baseline summary:
  `data/results/component_gate_decision_general_v1_summary.json`
- descriptive 32B default-schema follow-up:
  `data/results/component_gate_decision_general_v1_followup_32b_default_summary.json`
- 7B schema-rescue follow-up:
  `data/results/component_gate_decision_general_v1_dynamic_schema_summary.json`
- schema smoke artifacts:
  `data/results/schema_smoke/`

## Gate-Level Read

- the 7B schema-rescue run completed with `phase_a_passed=true` and
  `determinism_passed=true`
- `policy_comparison_unlocked` remained `false`
- primary scenario errors moved from `45` in the locked 7B baseline to `0` in
  the 7B schema-rescue run
- primary observed gate failures moved from `8` to `5`
- frozen-sentinel observed gate failures moved from `3` to `2`
- aggregate CI and aggregate observed gate failure counts stayed `0`, so the
  per-family and frozen-sentinel checks again carried the decision

## Common-Surface Burden

The preregistered common-surface schema-shaped burden covers only:

- empty or vacuous `scope_key`
- empty or vacuous `canonical_id`
- invalid `contradicts_event_ids` target

on:

- `scope_contamination`
- `preference_drift`
- `memory_poisoning`
- frozen sentinel (`mechanism_diverse_heldout`, `frozen`)

Observed burden:

- locked 7B baseline: `26`
  - empty/vacuous `scope_key`: `13`
  - empty/vacuous `canonical_id`: `8`
  - invalid `contradicts_event_ids` target: `5`
- 7B schema rescue: `0`
- 32B default schema: `0`

Reduction relative to the locked 7B baseline:

- 7B schema rescue: `100%`
- 32B default schema: `100%`

The vacuous-content rule did real work here. The implemented Ollama-compatible
schema kept the event-id namespace constraints and `minLength: 1` for
`scope_key` and `canonical_id`; smoke probing showed Ollama still rejects the
regex `pattern` keyword in this path. The successful 7B schema-rescue artifacts
were therefore checked for preregistered vacuous placeholders, and none were
observed on the common blocker surface.

## Residual Measured Failures

Eliminating schema-shaped burden did not eliminate all 7B gate failures.

On the common blocker surface:

- locked 7B baseline observed gate failures: `10`
  - `scope_contamination`: `3`
  - `preference_drift`: `2`
  - `memory_poisoning`: `2`
  - frozen sentinel: `3`
- 7B schema rescue observed gate failures: `7`
  - `scope_contamination`: `1`
  - `preference_drift`: `3`
  - `memory_poisoning`: `1`
  - frozen sentinel: `2`
- 32B default schema observed gate failures: `0`

This split matters:

- the stronger structured interface removed the contract-shaped failures
- the remaining 7B misses are measured claim/scope problems, not invalid-output
  transport or namespace failures
- the descriptive 32B rows clear those remaining common-surface measured failures

Outside the common blocker surface, the 7B schema-rescue run also removed the
entire `false_corroboration` blocker pattern:

- locked 7B baseline: `17` scenario errors and `1` observed gate failure
- 7B schema rescue: `0` scenario errors and `0` observed gate failures

## Quadrant Decision

The preregistered symmetric trigger for the conditional `32B + schema`
quadrant did not fire.

Reason:

1. the 7B schema-rescue run reduced common-surface burden by at least `75%`
   relative to the locked baseline
2. the 32B default-schema run also reduced common-surface burden by at least
   `75%`
3. the trigger requires one main effect to be strong and the other to remain
   below `50%` reduction

Because both mandatory runs fully removed the common-surface schema-shaped
burden, the combined quadrant would not resolve the preregistered interaction
question and was not run.

## Interpretation

The follow-up evidence supports a stronger methodology result than the locked
7B baseline alone:

- the original locked taxonomy was not just "the task is impossible at 7B";
  a stricter structured interface removes the entire schema-shaped blocker class
  without replacing it with vacuous placeholder strings
- the 7B path still remains gate-locked after that rescue, which localizes the
  remaining problem to measured semantic extraction quality rather than JSON
  contract breakage
- the 32B default-schema sweep shows that capacity can remove the remaining
  common-surface measured failures on the selected blocker region
- the per-family plus frozen-sentinel gate design remains load-bearing because
  aggregate gates stayed green even when the policy-unlock decision stayed locked

## Decision

The methodology case is now strong enough to start the benchmark/methodology
draft without leaning on the single oracle `CQ`-versus-`Mem0Lite` delta from
`false_corroboration_adversarial_mixed_source`.

What the draft can now claim:

- a benchmark-plus-gate-methodology result
- a failure-taxonomy result for the locked 7B default path
- a follow-up decomposition showing that schema strictness removes structural
  failure modes while larger-model capacity removes the remaining common-surface
  measured failures

What it still cannot claim:

- a noisy-mode policy comparison result
- a reopened Phase 4 unlock path for the current 7B gate

Recommended next step:

- begin the integrated paper/report draft around the oracle benchmark result,
  the per-family gate methodology, the locked-taxonomy note, and this
  follow-up decomposition

Optional strengthening after draft start, if a target venue needs broader
empirical breadth:

- expand frozen held-out benchmark evidence with a separately preregistered
  benchmark-strengthening step
- add another model family only if the paper wants a broader architecture claim
