# Predictions vs Results

## 2026-05-15 - Canonical-Id Resolution Audit Preregistration

Artifacts:

- Preregistration: `docs/canonical_id_resolution_audit_preregistration.md`
- Runner: `scripts/run_canonical_id_resolution_audit.py`
- Target outputs after clean replay:
  `data/results/canonical_id_resolution_audit_summary.json`,
  `data/results/canonical_id_resolution_audit_family_metrics.csv`,
  `data/runs/canonical_id_resolution_audit_manifest.json`, and
  `docs/canonical_id_resolution_audit_results.md`

### Interpretation

The CQR audit is locked and implemented, but observed values are intentionally
pending. The full runner enforces the preregistered Bucket D abort on a dirty
pre-run worktree, so the replay and observed rows must be emitted after the
implementation is committed and the locked 32B local model cell is available.

### Section B Alias-CQR Predictions

| Family | Role | Predicted alias CQR | False-positive cap | Observed |
| --- | --- | --- | ---: | --- |
| `useful_pending_memory` | thesis | `>= 0.40` +/- 0.20 | `<= 0.05` | pending clean replay |
| `memory_poisoning` | thesis | `>= 0.40` +/- 0.20 | `<= 0.05` | pending clean replay |
| `false_corroboration` | descriptive | `0.10-0.60` | `<= 0.10` | pending clean replay |
| `scope_contamination` | descriptive | `<= 0.25` +/- 0.10 | `<= 0.05` | pending clean replay |
| `forced_contradiction` | descriptive | `>= 0.85` +/- 0.10 | `<= 0.05` | pending clean replay |
| `preference_drift` | descriptive | `0.25-0.60` | `<= 0.10` | pending clean replay |
| `mechanism_diverse_heldout` | descriptive | `<= 0.40` +/- 0.20 | `<= 0.10` | pending clean replay |

### Section C Cross-Tab Prediction

For CQ on both thesis families, the locked prediction is:

`P(policy_answer_success | alias_CQR_hit) - P(policy_answer_success | alias_CQR_miss) >= 0.30`

Each thesis family must also have at least 5 alias-CQR hits.

## 2026-05-15 - Phase 4 Noisy Policy Comparison

Artifacts:

- Summary JSON: `data/results/noisy_policy_comparison_summary.json`
- Primary metrics CSVs: `data/results/noisy_policy_comparison_*_default_metrics.csv`
- Robustness metrics CSVs:
  `data/results/noisy_policy_comparison_*_scenario_conditioned_metrics.csv`
- Manifests: `data/runs/noisy_policy_comparison_*_manifest.json`
- Result readout: `docs/noisy_policy_comparison_results.md`

### Interpretation

Bucket B fired. The completed noisy policy comparison survived all abort
conditions and recorded no Bucket C directional-loss pattern, but it did not
clear Bucket A. CQ won versus Reflection on two countable primary metrics:
`forced_contradiction` false assertion and `preference_drift` answer
correctness. It tied Reflection and `Mem0Lite` on the other countable primary
metrics, tied `Mem0Lite` on all frozen sentinel primary metrics, and the
`scenario_conditioned` replicate contradicted none of the primary wins.

All observed values below are sign-normalized `improvement_delta` values from
`data/results/noisy_policy_comparison_summary.json`; positive means CQ is
better on the named metric.

### Countable Primary-Family Predictions

| Family | Metric | Comparator | Predicted | Observed |
| --- | --- | --- | ---: | ---: |
| `forced_contradiction` | `false_assertion_rate` | `reflection_eager_write_lite` | +0.55 | +0.93 |
| `forced_contradiction` | `false_assertion_rate` | `mem0_lite` | +0.05 | +0.00 |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_contestation_demotion` | +0.45 | +0.17 |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_wider_scope_pending_override` | +0.00 | +0.00 |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_pending_lookup_use` | +0.00 | +0.00 |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_source_independence_gate` | +0.00 | +0.00 |
| `scope_contamination` | `leakage_rate` | `reflection_eager_write_lite` | +0.20 | +0.00 |
| `scope_contamination` | `leakage_rate` | `mem0_lite` | +0.05 | +0.00 |
| `scope_contamination` | `leakage_rate` | `cq_no_contestation_demotion` | +0.00 | +0.00 |
| `scope_contamination` | `leakage_rate` | `cq_no_wider_scope_pending_override` | +0.15 | +0.00 |
| `scope_contamination` | `leakage_rate` | `cq_no_pending_lookup_use` | +0.00 | +0.00 |
| `scope_contamination` | `leakage_rate` | `cq_no_source_independence_gate` | +0.00 | +0.00 |
| `preference_drift` | `answer_correctness` | `reflection_eager_write_lite` | +0.55 | +0.13 |
| `preference_drift` | `answer_correctness` | `mem0_lite` | +0.00 | +0.00 |
| `preference_drift` | `answer_correctness` | `cq_no_contestation_demotion` | +0.45 | +0.00 |
| `preference_drift` | `answer_correctness` | `cq_no_wider_scope_pending_override` | +0.00 | +0.00 |
| `preference_drift` | `answer_correctness` | `cq_no_pending_lookup_use` | +0.15 | +0.00 |
| `preference_drift` | `answer_correctness` | `cq_no_source_independence_gate` | +0.00 | +0.00 |
| `useful_pending_memory` | `answer_correctness` | `reflection_eager_write_lite` | +0.30 | +0.00 |
| `useful_pending_memory` | `answer_correctness` | `mem0_lite` | +0.30 | +0.00 |
| `useful_pending_memory` | `answer_correctness` | `cq_no_contestation_demotion` | +0.00 | +0.00 |
| `useful_pending_memory` | `answer_correctness` | `cq_no_wider_scope_pending_override` | +0.00 | +0.00 |
| `useful_pending_memory` | `answer_correctness` | `cq_no_pending_lookup_use` | +0.30 | +0.00 |
| `useful_pending_memory` | `answer_correctness` | `cq_no_source_independence_gate` | +0.00 | +0.00 |
| `memory_poisoning` | `poison_promotion_rate` | `reflection_eager_write_lite` | +0.45 | +0.00 |
| `memory_poisoning` | `poison_promotion_rate` | `mem0_lite` | +0.05 | +0.00 |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_contestation_demotion` | +0.10 | +0.00 |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_wider_scope_pending_override` | +0.15 | +0.00 |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_pending_lookup_use` | +0.00 | +0.00 |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_source_independence_gate` | +0.00 | +0.00 |

### Descriptive-Only False Corroboration Predictions

`false_corroboration` is excluded from bucket decisions because Phase 4 uses an
event-id source proxy rather than extracted source identity.

| Family | Metric | Comparator | Predicted | Observed |
| --- | --- | --- | ---: | ---: |
| `false_corroboration` | `false_assertion_rate` | `reflection_eager_write_lite` | -0.10 | +0.00 |
| `false_corroboration` | `false_assertion_rate` | `mem0_lite` | -0.10 | +0.00 |
| `false_corroboration` | `false_assertion_rate` | `cq_no_contestation_demotion` | +0.00 | +0.00 |
| `false_corroboration` | `false_assertion_rate` | `cq_no_wider_scope_pending_override` | +0.00 | +0.00 |
| `false_corroboration` | `false_assertion_rate` | `cq_no_pending_lookup_use` | +0.20 | +0.00 |
| `false_corroboration` | `false_assertion_rate` | `cq_no_source_independence_gate` | +0.00 | +0.00 |

### Frozen Sentinel Primary-Metric Predictions

| Frozen metric | Comparator | Predicted | Observed |
| --- | --- | ---: | ---: |
| `false_assertion_rate` | `reflection_eager_write_lite` | +0.45 | +0.00 |
| `false_assertion_rate` | `mem0_lite` | +0.00 | +0.00 |
| `false_assertion_rate` | `cq_no_contestation_demotion` | +0.30 | +0.00 |
| `false_assertion_rate` | `cq_no_wider_scope_pending_override` | +0.30 | +0.00 |
| `false_assertion_rate` | `cq_no_pending_lookup_use` | -0.15 | +0.00 |
| `false_assertion_rate` | `cq_no_source_independence_gate` | +0.00 | +0.00 |
| `poison_promotion_rate` | `reflection_eager_write_lite` | +0.00 | +0.00 |
| `poison_promotion_rate` | `mem0_lite` | +0.00 | +0.00 |
| `poison_promotion_rate` | `cq_no_contestation_demotion` | +0.00 | +0.00 |
| `poison_promotion_rate` | `cq_no_wider_scope_pending_override` | +0.00 | +0.00 |
| `poison_promotion_rate` | `cq_no_pending_lookup_use` | +0.00 | +0.00 |
| `poison_promotion_rate` | `cq_no_source_independence_gate` | +0.00 | +0.00 |
| `premature_promotion_rate` | `reflection_eager_write_lite` | +0.20 | +0.00 |
| `premature_promotion_rate` | `mem0_lite` | +0.15 | +0.00 |
| `premature_promotion_rate` | `cq_no_contestation_demotion` | +0.00 | +0.00 |
| `premature_promotion_rate` | `cq_no_wider_scope_pending_override` | +0.00 | +0.00 |
| `premature_promotion_rate` | `cq_no_pending_lookup_use` | +0.00 | +0.00 |
| `premature_promotion_rate` | `cq_no_source_independence_gate` | +0.10 | +0.00 |

## 2026-05-05 - Phase 2.5 Frozen Mechanism-Diverse Oracle Sweep

Artifacts:

- Run JSON: `data/runs/mechanism_diverse_heldout_oracle_frozen_phase2_5.json`
- Metrics CSV: `data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_metrics.csv`
- Static dashboard: `data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_dashboard.html`

Commands:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.preregistration_lock --check
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner --family mechanism_diverse_heldout --template-mix frozen --policy-set phase2_5 --output-json data/runs/mechanism_diverse_heldout_oracle_frozen_phase2_5.json --output-csv data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_metrics.csv
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.dashboard.app data/runs/mechanism_diverse_heldout_oracle_frozen_phase2_5.json --write-html data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_dashboard.html
```

### Interpretation

All 108 preregistered oracle-mode deltas matched the observed deltas.

The frozen aggregate does not show broad CQ answer-quality superiority over `Mem0Lite`: CQ and `Mem0Lite` tie on `false_assertion_rate`, `answer_correctness`, `poison_promotion_rate`, `clean_durable_displacement_rate`, and `scope_leakage_rate`. CQ does beat `Mem0Lite` on `premature_promotion_rate` by 33 percentage points in aggregate, driven by the adversarial mixed-source false-corroboration scenario.

Under the preregistered 5 percentage point rule, the CQ policy contribution is not disconfirmed in oracle mode: CQ beats `Mem0Lite` by more than 5 points on one primary metric and is not worse by more than 5 points on any primary metric in the frozen aggregate. This support is narrow. The frozen result supports staged promotion as a way to reduce premature durable promotion against the published-family rule-based baseline; it does not support a stronger claim that CQ improves answer correctness or false assertion over `Mem0Lite` on this frozen set.

The load-bearing mechanism-generalization signal remains CQ-vs-eager separation on scope-laundered poisoning and long-horizon preference corrections, plus the ablation gaps that isolate wider-scope pending override, pending lookup, contestation/demotion, and source-independence behavior.

### Observed Frozen Aggregate

| Policy | false_assertion_rate | answer_correctness | poison_promotion_rate | premature_promotion_rate | clean_durable_displacement_rate | scope_leakage_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `reflection_eager_write_lite` | 1.00 | 0.00 | 0.33 | 0.67 | 0.00 | 0.00 |
| `consolidation_queue_lite` | 0.33 | 0.67 | 0.33 | 0.33 | 0.00 | 0.00 |
| `cq_no_contestation_demotion` | 0.67 | 0.33 | 0.33 | 0.33 | 0.00 | 0.00 |
| `cq_no_wider_scope_pending_override` | 0.67 | 0.33 | 0.33 | 0.33 | 0.00 | 0.00 |
| `cq_no_pending_lookup_use` | 0.00 | 0.33 | 0.33 | 0.33 | 0.00 | 0.00 |
| `cq_no_source_independence_gate` | 0.33 | 0.67 | 0.33 | 0.53 | 0.00 | 0.00 |
| `naive_eager_write_lite` | 1.00 | 0.00 | 0.33 | 0.67 | 0.00 | 0.00 |
| `no_memory_lite` | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| `scope_blind_transcript_rag_lite` | 0.33 | 0.67 | 0.00 | 0.00 | 0.00 | 0.00 |
| `mem0_lite` | 0.33 | 0.67 | 0.33 | 0.67 | 0.00 | 0.00 |

### Preregistered Deltas vs Observed Deltas

Each cell is `predicted -> observed` for `CQ - comparator`. Positive `answer_correctness` is better. Negative `false_assertion_rate`, `poison_promotion_rate`, `premature_promotion_rate`, `clean_durable_displacement_rate`, and `scope_leakage_rate` is better.

| Frozen family | Comparator | false_assertion_rate | answer_correctness | poison_promotion_rate | premature_promotion_rate | clean_durable_displacement_rate | scope_leakage_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `false_corroboration_adversarial_mixed_source` | `ReflectionEagerWriteLite` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | -1.00 -> -1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `false_corroboration_adversarial_mixed_source` | `Mem0Lite` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | -1.00 -> -1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `false_corroboration_adversarial_mixed_source` | `cq_no_contestation_demotion` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `false_corroboration_adversarial_mixed_source` | `cq_no_wider_scope_pending_override` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `false_corroboration_adversarial_mixed_source` | `cq_no_pending_lookup_use` | +1.00 -> +1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `false_corroboration_adversarial_mixed_source` | `cq_no_source_independence_gate` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | -0.60 -> -0.60 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `memory_poisoning_scope_laundered` | `ReflectionEagerWriteLite` | -1.00 -> -1.00 | +1.00 -> +1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `memory_poisoning_scope_laundered` | `Mem0Lite` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `memory_poisoning_scope_laundered` | `cq_no_contestation_demotion` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `memory_poisoning_scope_laundered` | `cq_no_wider_scope_pending_override` | -1.00 -> -1.00 | +1.00 -> +1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `memory_poisoning_scope_laundered` | `cq_no_pending_lookup_use` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `memory_poisoning_scope_laundered` | `cq_no_source_independence_gate` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `preference_drift_long_horizon_corrections` | `ReflectionEagerWriteLite` | -1.00 -> -1.00 | +1.00 -> +1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `preference_drift_long_horizon_corrections` | `Mem0Lite` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `preference_drift_long_horizon_corrections` | `cq_no_contestation_demotion` | -1.00 -> -1.00 | +1.00 -> +1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `preference_drift_long_horizon_corrections` | `cq_no_wider_scope_pending_override` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `preference_drift_long_horizon_corrections` | `cq_no_pending_lookup_use` | +0.00 -> +0.00 | +1.00 -> +1.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
| `preference_drift_long_horizon_corrections` | `cq_no_source_independence_gate` | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 | +0.00 -> +0.00 |
