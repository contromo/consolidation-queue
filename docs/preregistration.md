# Phase 2.5 Preregistration

frozen_eval_lock_sha256: 7e506d540745d7409e2569b7bc5483aba566112e8077a8b709c1ed4e8a04569a

This file locks the Phase 2.5 mechanism-diverse held-out evaluation before any policy is run on that frozen set.

The lock hash covers:

- canonical JSON serialization of the frozen mechanism-diverse scenario contracts
- the exact predictions block delimited below

Existing-family `phase2_5` calibration may inform these commitments. Those are calibrated commitments, not blind predictions. Only the frozen mechanism-diverse held-out predictions below carry the disconfirmation weight for the CQ policy contribution.

<!-- FROZEN_EVAL_PREDICTIONS_START -->
## Frozen Set

Frozen scenario contracts:

- `false_corroboration_adversarial_mixed_source`
- `memory_poisoning_scope_laundered`
- `preference_drift_long_horizon_corrections`

Primary disconfirmation rule:

- If `Mem0Lite` is within 5 percentage points of CQ or exceeds CQ on the primary metric bundle across the frozen mechanism-diverse held-out set, CQ is not supported as a policy contribution.
- If that happens, the writeup will be reframed as a benchmark and failure-taxonomy contribution.

## Oracle-Mode Predictions

Metric deltas are expressed as `CQ - comparator`. Positive `answer_correctness` is better. Negative `false_assertion_rate`, `poison_promotion_rate`, `premature_promotion_rate`, `clean_durable_displacement_rate`, and `scope_leakage_rate` are better.

| Frozen family | Comparator | false_assertion_rate | answer_correctness | poison_promotion_rate | premature_promotion_rate | clean_durable_displacement_rate | scope_leakage_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| false_corroboration_adversarial_mixed_source | ReflectionEagerWriteLite | -1.00 | 0.00 | 0.00 | -1.00 | 0.00 | 0.00 |
| false_corroboration_adversarial_mixed_source | Mem0Lite | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| false_corroboration_adversarial_mixed_source | cq_no_contestation_demotion | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| false_corroboration_adversarial_mixed_source | cq_no_wider_scope_pending_override | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| false_corroboration_adversarial_mixed_source | cq_no_pending_lookup_use | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| false_corroboration_adversarial_mixed_source | cq_no_source_independence_gate | -1.00 | 0.00 | 0.00 | -0.20 | 0.00 | 0.00 |
| memory_poisoning_scope_laundered | ReflectionEagerWriteLite | -1.00 | +1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| memory_poisoning_scope_laundered | Mem0Lite | -1.00 | +1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| memory_poisoning_scope_laundered | cq_no_contestation_demotion | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| memory_poisoning_scope_laundered | cq_no_wider_scope_pending_override | -1.00 | +1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| memory_poisoning_scope_laundered | cq_no_pending_lookup_use | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| memory_poisoning_scope_laundered | cq_no_source_independence_gate | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| preference_drift_long_horizon_corrections | ReflectionEagerWriteLite | -1.00 | +1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| preference_drift_long_horizon_corrections | Mem0Lite | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| preference_drift_long_horizon_corrections | cq_no_contestation_demotion | -1.00 | +1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| preference_drift_long_horizon_corrections | cq_no_wider_scope_pending_override | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| preference_drift_long_horizon_corrections | cq_no_pending_lookup_use | -1.00 | +1.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| preference_drift_long_horizon_corrections | cq_no_source_independence_gate | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Source-Independence Ablation Interpretation

`cq_no_source_independence_gate` is intentionally more permissive than full CQ because `len(candidate.supports)` is always greater than or equal to independent-source `corroboration_count`. This is a small baseline shift on normal supported cases and a large shift on mirrored-source cases. Mirrored-source gaps are interpreted as the cost of removing the independence gate, not as a neutral baseline comparison.

## Noisy-Mode Expectations

Noisy-mode claims remain blocked until Phase 3 component evaluation and Phase 4 local extraction are implemented. Expected noisy-mode gaps are:

- CQ retains the same qualitative direction as oracle mode only if component quality gates are met.
- CQ vs Reflection and CQ vs `Mem0Lite` margins should shrink by 10 to 25 percentage points on families where scope inference, contradiction detection, or source canonicalization is required.
- On false corroboration, noisy source canonicalization errors are expected to create the largest oracle-to-noisy gap, with CQ false assertion increasing by 0.25 to 0.50 if mirrored sources are not clustered correctly.
- On scope-laundered poisoning, noisy scope-key errors are expected to reduce CQ's advantage by 0.25 to 0.50.
- On long-horizon preference corrections, noisy contradiction errors are expected to reduce CQ's answer-correctness advantage by 0.10 to 0.25.
- If any Phase 3 quality gate is missed, noisy-mode results will be reported as pipeline failure evidence rather than CQ policy evidence.
<!-- FROZEN_EVAL_PREDICTIONS_END -->
