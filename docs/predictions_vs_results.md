# Predictions vs Results

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
