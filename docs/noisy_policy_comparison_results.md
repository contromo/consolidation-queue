# Noisy Policy Comparison Results

Bucket B fired in the preregistered Phase 4 noisy policy comparison.

Source summary: `data/results/noisy_policy_comparison_summary.json`.
Primary run artifacts are the `default` files under
`data/runs/noisy_policy_comparison_*_default.json`,
`data/runs/noisy_policy_comparison_*_default_manifest.json`, and
`data/results/noisy_policy_comparison_*_default_metrics.csv`. Robustness
replicate artifacts use the same paths with `scenario_conditioned`.

## Audit Trail

Source: `data/results/noisy_policy_comparison_summary.json` and
`data/runs/noisy_policy_comparison_*_manifest.json`.

| Field | Value |
| --- | --- |
| Preregistration lock SHA | `4bd2bbe64a542c6d8479c2c7c4b40b12c3c601fd35256a60b85bd1e30bfa9bff` |
| Adapter SHA | `4f1fc0f8f67ea6246268933f14fb0f20b514475b37153b4af0d29a8178c34de9` |
| Primary model digest | `sha256:9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368` |
| Prompt SHA | `ca9ec418156b4cc12bcf5457683844f023684bbc5cee2b7460a6c5030a475633` |
| Completed profiles | `default`, `scenario_conditioned` |
| Per-family manifests | `14` |
| Candidate-stream audit rows | `726` |
| Max scenario adapter drop rate | `0.00` |

No `data/results/noisy_policy_comparison_stop_*.json` report is present for
the completed artifact set.

## Bucket Readout

Source: `data/results/noisy_policy_comparison_summary.json`.

Bucket B applies because the completed result survived Bucket D and Bucket C,
but did not clear Bucket A. CQ won versus Reflection on two of five countable
families, not the four required for Bucket A. CQ was non-inferior to `Mem0Lite`
on the frozen sentinel metrics, but was not superior to `Mem0Lite` on any
frozen sentinel primary metric. The `scenario_conditioned` replicate
contradicted none of the primary wins.

## Headline Countable Families

Source: `data/results/noisy_policy_comparison_summary.json`,
`schema_profiles.default.primary_metric_comparisons`.

Positive deltas are sign-normalized improvements for CQ.

| Family | Metric | CQ vs Reflection delta | LCB | UCB | Win | CQ vs `Mem0Lite` delta |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| `forced_contradiction` | `false_assertion_rate` | +0.93 | +0.88 | +0.98 | yes | +0.00 |
| `scope_contamination` | `leakage_rate` | +0.00 | +0.00 | +0.00 | no | +0.00 |
| `preference_drift` | `answer_correctness` | +0.13 | +0.07 | +0.22 | yes | +0.00 |
| `useful_pending_memory` | `answer_correctness` | +0.00 | +0.00 | +0.00 | no | +0.00 |
| `memory_poisoning` | `poison_promotion_rate` | +0.00 | +0.00 | +0.00 | no | +0.00 |

## Descriptive-Only False Corroboration

Source: `data/results/noisy_policy_comparison_summary.json`,
`schema_profiles.default.primary_metric_comparisons.false_corroboration`.

`false_corroboration` is excluded from Bucket A and Bucket C because Phase 4
does not extract source identity; the adapter uses event ids as a symmetric
noisy source proxy.

| Metric | CQ vs Reflection delta | LCB | UCB | CQ vs `Mem0Lite` delta |
| --- | ---: | ---: | ---: | ---: |
| `false_assertion_rate` | +0.00 | +0.00 | +0.00 | +0.00 |

## Ablation Attribution

Source: `data/results/noisy_policy_comparison_summary.json`,
`schema_profiles.default.primary_metric_comparisons`.

Thresholds are the preregistered rules: drop `>= 0.15` means the ablated
component carries the mechanism; drop `<= 0.05` means inert.

| Family | `no_contestation_demotion` | `no_wider_scope_pending_override` | `no_pending_lookup_use` | `no_source_independence_gate` |
| --- | --- | --- | --- | --- |
| `forced_contradiction` | +0.17, carries | +0.00, inert | +0.00, inert | +0.00, inert |
| `scope_contamination` | +0.00, inert | +0.00, inert | +0.00, inert | +0.00, inert |
| `preference_drift` | +0.00, inert | +0.00, inert | +0.00, inert | +0.00, inert |
| `useful_pending_memory` | +0.00, inert | +0.00, inert | +0.00, inert | +0.00, inert |
| `memory_poisoning` | +0.00, inert | +0.00, inert | +0.00, inert | +0.00, inert |

## Replicate Direction Check

Source: `data/results/noisy_policy_comparison_summary.json`,
`schema_profiles.scenario_conditioned.primary_metric_comparisons`.

| Primary winning family | Primary delta | Replicate delta | Replicate UCB | Contradiction |
| --- | ---: | ---: | ---: | --- |
| `forced_contradiction` | +0.93 | +0.93 | +0.98 | no |
| `preference_drift` | +0.13 | +0.13 | +0.22 | no |

## Frozen Sentinel

Sources: `data/results/noisy_policy_comparison_summary.json` and
`data/results/noisy_policy_comparison_mechanism_diverse_heldout_default_metrics.csv`.

All three frozen contracts tie between CQ, Reflection, and `Mem0Lite` on the
three frozen primary metrics in the noisy run. Aggregate CQ-vs-`Mem0Lite`
non-inferiority passes because every LCB is `+0.00`; frozen superiority fails
because every CQ-vs-`Mem0Lite` point estimate is `+0.00`.

| Frozen contract | Metric | CQ vs Reflection | CQ vs `Mem0Lite` |
| --- | --- | ---: | ---: |
| `false_corroboration_adversarial_mixed_source` | `false_assertion_rate` | +0.00 | +0.00 |
| `false_corroboration_adversarial_mixed_source` | `poison_promotion_rate` | +0.00 | +0.00 |
| `false_corroboration_adversarial_mixed_source` | `premature_promotion_rate` | +0.00 | +0.00 |
| `memory_poisoning_scope_laundered` | `false_assertion_rate` | +0.00 | +0.00 |
| `memory_poisoning_scope_laundered` | `poison_promotion_rate` | +0.00 | +0.00 |
| `memory_poisoning_scope_laundered` | `premature_promotion_rate` | +0.00 | +0.00 |
| `preference_drift_long_horizon_corrections` | `false_assertion_rate` | +0.00 | +0.00 |
| `preference_drift_long_horizon_corrections` | `poison_promotion_rate` | +0.00 | +0.00 |
| `preference_drift_long_horizon_corrections` | `premature_promotion_rate` | +0.00 | +0.00 |

## Oracle-Vs-Noisy Gap

Sources:
`data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_metrics.csv`
and
`data/results/noisy_policy_comparison_mechanism_diverse_heldout_default_metrics.csv`.

The only saved Phase 2.5 oracle anchor in this repo for the Phase 4 frozen
policy set is the frozen sentinel aggregate, so this gap table is intentionally
limited to that anchor. Values are raw noisy metric minus raw oracle metric;
negative is better for false assertion, poison promotion, and premature
promotion, while positive is better for answer correctness.

| Policy | false assertion gap | poison promotion gap | premature promotion gap | answer correctness gap |
| --- | ---: | ---: | ---: | ---: |
| `reflection_eager_write_lite` | -1.00 | +0.00 | +0.00 | +0.00 |
| `consolidation_queue_lite` | -0.33 | +0.00 | +0.33 | -0.67 |
| `mem0_lite` | -0.33 | +0.00 | +0.00 | -0.67 |

## Writeup Direction

Bucket B fixes the noisy-mode interpretation as mixed, mechanism-local support:
the extracted-candidate path preserves CQ's forced-contradiction advantage and
a smaller preference-drift advantage, but it does not support broad noisy CQ
superiority and it does not separate CQ from `Mem0Lite` on the frozen sentinel.

The next research direction should be a focused Bucket B plan around the
surviving countable mechanisms, especially forced contradiction and preference
drift. `CQDatedContestation`, new mechanism families, and external transfer
checks remain out of scope until a separate plan preregisters them against this
Bucket B outcome.
