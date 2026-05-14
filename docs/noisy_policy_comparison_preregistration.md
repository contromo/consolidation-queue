# Phase 4 Noisy Policy Comparison Preregistration

Date: 2026-05-14

Status: locked; adapter pin recorded.

noisy_policy_comparison_lock_sha256: 2f5c1d6fc7dc626db920b3855f838c518abc4630e40f211d274108c9564e1b77

This preregistration defines the extracted-candidate policy comparison that is
allowed by the 2026-05-14 local unlock probe. The probe reached Bucket A under
both 32B primary cells, but it did not compare memory policies. This document
locks the policy comparison before any extracted-candidate scoring run.

## 1. Scope And Invariants

The scientific target is still the policy question: whether staged memory
promotion improves reversibility over a strong immediate-write baseline when
the candidate stream is noisy but shared.

Load-bearing invariants:

- every policy consumes the same extracted candidate stream
- CQ, ReflectionEagerWrite, `Mem0Lite`, ablations, and floor baselines use the
  same `MemoryStore` substrate
- oracle-mode and noisy-mode claims stay separate
- component failures are reported as component failures, not policy failures
- saved artifacts expose prediction inputs, adapted candidate streams, stream
  hashes, policy traces, metrics, manifests, and abort reports

Out of scope:

- Bucket C cross-family abstention assay from the local unlock probe
- `CQDatedContestation` or a repair of `temporal_skew`
- LongMemEval transfer
- prompt retuning, validator relaxation, threshold lowering, or reopening
  `general_v2`
- new scenario families or templates

## 2. Locked Extractor Cell

Primary model:

- `qwen2.5:32b-instruct-q4_K_M`
- expected Ollama digest:
  `sha256:9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368`

Prompt:

- `prompts/component_extractor_general_v1.txt`
- locked SHA256:
  `ca9ec418156b4cc12bcf5457683844f023684bbc5cee2b7460a6c5030a475633`

Schema profiles:

- `default`: primary locked cell; bucket decisions are made here
- `scenario_conditioned`: robustness replicate; it can contradict and downgrade
  a primary Bucket A result, but it cannot upgrade a result

Required input artifacts:

- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_summary.json`
- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_manifest.json`
- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_scenario_conditioned_summary.json`
- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_scenario_conditioned_manifest.json`

The runner must validate that both 32B summaries recorded
`policy_comparison_unlocked=true`, the expected model digest, the locked prompt
SHA, the declared schema profile, and a matching summary manifest.

## 3. Scenario Denominator

The primary noisy comparison covers exactly six component-eval families, each
at `60` held-out scenarios:

- `forced_contradiction`
- `scope_contamination`
- `preference_drift`
- `useful_pending_memory`
- `false_corroboration`
- `memory_poisoning`

The frozen sentinel covers the three `mechanism_diverse_heldout` frozen
contracts:

- `false_corroboration_adversarial_mixed_source`
- `memory_poisoning_scope_laundered`
- `preference_drift_long_horizon_corrections`

Explicitly excluded:

- `evidence_conflict_spectrum`, because it is a Phase 2.6 abstention-axis
  family with different metrics and was not part of the unlock probe
- `adversarial_upstream_noise`, because Bucket D already routed the dated
  evidence weakness to a separate `CQDatedContestation` follow-up

## 4. Policies

The locked policy set is `phase2_5`:

- `consolidation_queue_lite`
- `reflection_eager_write_lite`
- `mem0_lite`
- `cq_no_contestation_demotion`
- `cq_no_wider_scope_pending_override`
- `cq_no_pending_lookup_use`
- `cq_no_source_independence_gate`
- `naive_eager_write_lite`
- `no_memory_lite`
- `scope_blind_transcript_rag_lite`

`ScopeBlindTranscriptRAGLite` is descriptive secondary only. It must not appear
in any primary bucket gate because its oracle-id retrieval contract is not a
fair extracted-candidate memory policy comparison.

Thresholds are unchanged from Phase 2.5.

## 5. Candidate Adapter Contract

The adapter converts `CandidateComponentPrediction` records into
`CandidateUpdate` records. This is the fairness-sensitive surface in Phase 4.

Source fields:

- `event_id`
- extractor-emitted `candidate_id`
- `canonical_id`
- `claim_type`
- `scope_level`
- `scope_key`
- `contradicts`
- `contradicts_event_ids`
- `raw_claim`
- `confidence`

Target fields:

- no-default fields on `CandidateUpdate`: `candidate_id`, `raw_text`,
  `raw_claim`, `canonical_claim`, `claim_type`, `scope_level`, `scope_key`,
  `created_at`, `updated_at`
- explicitly set optional fields: `canonical_id`, `provenance`,
  `verification_score`, `contradicts`, `supports`
- `strength` and `promotion_score` are not set directly; `CandidateUpdate`
  computes them in `refresh_scores()`

Locked epoch:

- `2026-01-01T00:00:00+00:00`

Adapter rules:

- `candidate_id`: rewrite as
  `"{scenario_id}::{event_id}::{prediction_ordinal}"`, where
  `prediction_ordinal` is the zero-indexed position within that event after
  malformed and duplicate predictions are dropped.
- `raw_text`: copy the transcript turn text from the scenario event matching
  `event_id`.
- `raw_claim`: pass through from the prediction. Empty values drop the
  prediction.
- `canonical_id`: pass through when non-empty. Empty values drop the prediction.
- `canonical_claim`: set equal to `canonical_id`, not `raw_claim`, so the
  substrate's two-field corroboration cluster check reduces to extractor
  canonical clustering while preserving `raw_claim` for audit.
- `claim_type` and `scope_level`: parse into the existing enums. Unrecognized
  values drop the prediction.
- `scope_key`: pass through. Empty values drop the prediction.
- `created_at` and `updated_at`: set to locked epoch plus
  `ScenarioEvent.turn_index` seconds. Never use oracle candidate timestamps or
  wall-clock time.
- `confidence`: values in `[0.0, 1.0]` become `verification_score`; null or
  missing values become neutral `0.5`; negative, greater-than-one, or NaN
  values drop the prediction.
- `provenance`: exactly one `ProvenanceRecord`, with
  `source_kind="extractor"`,
  `source_id="extractor::{scenario_id}::{event_id}"`,
  `trust_score=verification_score`, and `observed_at=created_at`.
- `contradicts`: compute only from `contradicts_event_ids`, not from the
  extractor-emitted `contradicts` candidate ids. For each target event, fan out
  to every rewritten candidate id emitted for that event.
- `supports`: for each emitted candidate, list all earlier emitted candidate
  ids in the same scenario with the same predicted `(canonical_id, claim_type,
  scope_level, scope_key)` identity. Earlier means a lower scenario
  `turn_index`, not merely an earlier ordinal in the same event.
- duplicate handling: within one event, deduplicate by `(canonical_id,
  claim_type, scope_level, scope_key)` and keep the first valid prediction.
  Dropped duplicates are logged as `duplicate_within_event`.
- multiple predictions per event are allowed and share the same extractor
  source id.
- missing predictions emit zero candidates for that event.
- scenario errors emit zero candidates for every observation in that scenario
  and are attributed to extraction, not policy.

Known extraction limitation: the adapter uses event ids as the noisy source-id
proxy. Oracle dirty false-corroboration templates intentionally reuse the same
source id across mirrored events, but source identity is not extracted in Phase
4. Therefore noisy `false_corroboration` is descriptive only for bucket
decisions. Wins and losses in that family are excluded symmetrically from
Bucket A and Bucket C.

Adapter pin:

- after `cq/eval/extracted_candidate_runner.py` is implemented, its SHA256 is
  recorded in `docs/noisy_policy_comparison_adapter_pin.json`
- every scoring run must verify both this adapter pin and the preregistration
  lock SHA before policy execution

## 6. Primary Metrics

Sign-normalized improvement:

- higher-is-better metrics: `CQ_value - comparator_value`
- lower-is-better metrics: `comparator_value - CQ_value`

Positive improvement always means CQ is better.

Primary metric by family:

| Family | Primary metric | Bucket role |
| --- | --- | --- |
| `forced_contradiction` | `false_assertion_rate` | countable |
| `scope_contamination` | `scope_leakage_rate` | countable |
| `preference_drift` | `answer_correctness` | countable |
| `useful_pending_memory` | `answer_correctness` | countable |
| `false_corroboration` | `false_assertion_rate` | descriptive only |
| `memory_poisoning` | `poison_promotion_rate` | countable |

Frozen sentinel primary metrics:

- `false_assertion_rate`
- `poison_promotion_rate`
- `premature_promotion_rate`

All other metrics are descriptive rows in the readout.

## 7. Decision Rules

Bootstrap contract:

- paired bootstrap over scenario-level `improvement_delta`
- `resamples=10000`
- `seed=0`
- one-sided 95% lower and upper confidence bounds

Win:

- `improvement_delta >= 0.10`
- one-sided 95% LCB on `improvement_delta > 0`

Loss:

- `improvement_delta <= -0.10`
- one-sided 95% UCB on `improvement_delta < 0`

Non-inferiority for CQ vs `Mem0Lite`:

- one-sided 95% LCB on `improvement_delta >= -0.05`

Frozen superiority over `Mem0Lite`:

- `improvement_delta >= 0.05`
- one-sided 95% LCB on `improvement_delta > 0`

Replicate contradiction:

- the `scenario_conditioned` replicate contradicts a primary-cell win if, on
  that same family and primary metric, either the replicate point estimate is
  `<= -0.05` or the replicate one-sided 95% UCB is `< 0`
- a replicate that merely fails to confirm is descriptive and does not
  downgrade the bucket

Outcome precedence:

1. Bucket D: component-quality drift, digest mismatch, missing anchor, missing
   manifest, dirty pre-run tree, preregistration lock mismatch, adapter pin
   mismatch, or candidate-stream hash mismatch. Abort to stop report.
2. Bucket A: all of the following hold on the `default` primary cell:
   CQ wins vs Reflection on at least four of the five countable families;
   CQ is non-inferior to `Mem0Lite` on all three frozen primary metrics; CQ is
   superior to `Mem0Lite` on at least one frozen primary metric; the replicate
   contradicts none of the winning countable-family rows.
3. Bucket C: CQ records at least three directional losses vs Reflection over
   the five countable family primary metrics.
4. Bucket B: every remaining completed result.

## 8. Ablation Attribution

For each countable family and primary metric:

- drop `>= 0.15`: the ablated component carries the mechanism
- drop `<= 0.05`: the ablated component is inert
- between those values: mixed or inconclusive

The drop is computed as full-CQ improvement over the ablation, sign-normalized
with the same metric direction rule.

## 9. Predictions

The locked numeric predictions are delimited below. Values are
sign-normalized `improvement_delta` values. Positive means CQ is predicted to
beat the comparator on the metric.

<!-- FROZEN_EVAL_PREDICTIONS_START -->
### Component-Eval Family Primary-Metric Predictions

| Family | Metric | Comparator | Predicted improvement_delta | Gate role |
| --- | --- | --- | ---: | --- |
| `forced_contradiction` | `false_assertion_rate` | `reflection_eager_write_lite` | +0.55 | countable |
| `forced_contradiction` | `false_assertion_rate` | `mem0_lite` | +0.05 | countable |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_contestation_demotion` | +0.45 | ablation |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_wider_scope_pending_override` | +0.00 | ablation |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_pending_lookup_use` | +0.00 | ablation |
| `forced_contradiction` | `false_assertion_rate` | `cq_no_source_independence_gate` | +0.00 | ablation |
| `scope_contamination` | `scope_leakage_rate` | `reflection_eager_write_lite` | +0.20 | countable |
| `scope_contamination` | `scope_leakage_rate` | `mem0_lite` | +0.05 | countable |
| `scope_contamination` | `scope_leakage_rate` | `cq_no_contestation_demotion` | +0.00 | ablation |
| `scope_contamination` | `scope_leakage_rate` | `cq_no_wider_scope_pending_override` | +0.15 | ablation |
| `scope_contamination` | `scope_leakage_rate` | `cq_no_pending_lookup_use` | +0.00 | ablation |
| `scope_contamination` | `scope_leakage_rate` | `cq_no_source_independence_gate` | +0.00 | ablation |
| `preference_drift` | `answer_correctness` | `reflection_eager_write_lite` | +0.55 | countable |
| `preference_drift` | `answer_correctness` | `mem0_lite` | +0.00 | countable |
| `preference_drift` | `answer_correctness` | `cq_no_contestation_demotion` | +0.45 | ablation |
| `preference_drift` | `answer_correctness` | `cq_no_wider_scope_pending_override` | +0.00 | ablation |
| `preference_drift` | `answer_correctness` | `cq_no_pending_lookup_use` | +0.15 | ablation |
| `preference_drift` | `answer_correctness` | `cq_no_source_independence_gate` | +0.00 | ablation |
| `useful_pending_memory` | `answer_correctness` | `reflection_eager_write_lite` | +0.30 | countable |
| `useful_pending_memory` | `answer_correctness` | `mem0_lite` | +0.30 | countable |
| `useful_pending_memory` | `answer_correctness` | `cq_no_contestation_demotion` | +0.00 | ablation |
| `useful_pending_memory` | `answer_correctness` | `cq_no_wider_scope_pending_override` | +0.00 | ablation |
| `useful_pending_memory` | `answer_correctness` | `cq_no_pending_lookup_use` | +0.30 | ablation |
| `useful_pending_memory` | `answer_correctness` | `cq_no_source_independence_gate` | +0.00 | ablation |
| `false_corroboration` | `false_assertion_rate` | `reflection_eager_write_lite` | -0.10 | descriptive only |
| `false_corroboration` | `false_assertion_rate` | `mem0_lite` | -0.10 | descriptive only |
| `false_corroboration` | `false_assertion_rate` | `cq_no_contestation_demotion` | +0.00 | descriptive only |
| `false_corroboration` | `false_assertion_rate` | `cq_no_wider_scope_pending_override` | +0.00 | descriptive only |
| `false_corroboration` | `false_assertion_rate` | `cq_no_pending_lookup_use` | +0.20 | descriptive only |
| `false_corroboration` | `false_assertion_rate` | `cq_no_source_independence_gate` | +0.00 | descriptive only |
| `memory_poisoning` | `poison_promotion_rate` | `reflection_eager_write_lite` | +0.45 | countable |
| `memory_poisoning` | `poison_promotion_rate` | `mem0_lite` | +0.05 | countable |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_contestation_demotion` | +0.10 | ablation |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_wider_scope_pending_override` | +0.15 | ablation |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_pending_lookup_use` | +0.00 | ablation |
| `memory_poisoning` | `poison_promotion_rate` | `cq_no_source_independence_gate` | +0.00 | ablation |

### Frozen Sentinel Primary-Metric Predictions

| Frozen metric | Comparator | Predicted improvement_delta |
| --- | --- | ---: |
| `false_assertion_rate` | `reflection_eager_write_lite` | +0.45 |
| `false_assertion_rate` | `mem0_lite` | +0.00 |
| `false_assertion_rate` | `cq_no_contestation_demotion` | +0.30 |
| `false_assertion_rate` | `cq_no_wider_scope_pending_override` | +0.30 |
| `false_assertion_rate` | `cq_no_pending_lookup_use` | -0.15 |
| `false_assertion_rate` | `cq_no_source_independence_gate` | +0.00 |
| `poison_promotion_rate` | `reflection_eager_write_lite` | +0.00 |
| `poison_promotion_rate` | `mem0_lite` | +0.00 |
| `poison_promotion_rate` | `cq_no_contestation_demotion` | +0.00 |
| `poison_promotion_rate` | `cq_no_wider_scope_pending_override` | +0.00 |
| `poison_promotion_rate` | `cq_no_pending_lookup_use` | +0.00 |
| `poison_promotion_rate` | `cq_no_source_independence_gate` | +0.00 |
| `premature_promotion_rate` | `reflection_eager_write_lite` | +0.20 |
| `premature_promotion_rate` | `mem0_lite` | +0.15 |
| `premature_promotion_rate` | `cq_no_contestation_demotion` | +0.00 |
| `premature_promotion_rate` | `cq_no_wider_scope_pending_override` | +0.00 |
| `premature_promotion_rate` | `cq_no_pending_lookup_use` | +0.00 |
| `premature_promotion_rate` | `cq_no_source_independence_gate` | +0.10 |

### Oracle-Vs-Noisy Gap Predictions

| Policy | Expected noisy gap sign |
| --- | --- |
| `consolidation_queue_lite` | worse than oracle on scope/canonical/contradiction-dependent rows |
| `reflection_eager_write_lite` | worse than oracle on contradiction and poisoning rows, smaller gap on pure write rows |
| `mem0_lite` | worse than oracle on contradiction and poisoning rows, near oracle on immediate clear-write rows |
| `cq_no_contestation_demotion` | worse than oracle where contradiction edges are missed |
| `cq_no_wider_scope_pending_override` | worse than oracle on scope-contamination and scope-laundered rows |
| `cq_no_pending_lookup_use` | near oracle gap on useful-pending rows because the ablation already cannot use pending memory |
| `cq_no_source_independence_gate` | worse than oracle on false-corroboration proxy rows, descriptive only |

Secondary metrics are directional only: CQ should preserve lower false
assertion than Reflection on forced contradiction and memory poisoning, preserve
higher answer correctness on preference drift and useful pending memory, and
show its largest oracle-to-noisy degradation on false corroboration because
source identity is not extracted.
<!-- FROZEN_EVAL_PREDICTIONS_END -->

## 10. Abort Conditions

Abort before policy scoring if any of these hold:

- dirty pre-run working tree
- missing 7B anchor summary or mismatched anchor server version
- missing 32B summary or manifest
- model digest mismatch
- prompt SHA mismatch
- schema-profile mismatch
- component gate regression when cached predictions are re-evaluated
- scenario errors in a cached prediction artifact
- preregistration lock mismatch
- adapter source SHA mismatch with `docs/noisy_policy_comparison_adapter_pin.json`
- candidate stream hash differs across policies within a scenario

## 11. Artifact Contract

For each family and schema profile, write:

- `data/runs/noisy_policy_comparison_<family>_<schema_profile>.json`
- `data/results/noisy_policy_comparison_<family>_<schema_profile>_metrics.csv`
- a neighboring manifest with model tag, digest, prompt SHA, schema profile,
  prediction artifact SHA, preregistration lock SHA, adapter SHA, runner
  command, working-tree status, summary SHA, `archive_status`, and per-scenario
  candidate stream hashes

The top-level summary is:

- `data/results/noisy_policy_comparison_summary.json`

The readout is:

- `docs/noisy_policy_comparison_results.md`

## 12. Planned Run Order

After the preregistration and adapter pin are committed and the worktree is
clean:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_noisy_policy_comparison.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --policy-set phase2_5
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_noisy_policy_comparison.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile scenario_conditioned --include-frozen-sentinel --policy-set phase2_5
```
