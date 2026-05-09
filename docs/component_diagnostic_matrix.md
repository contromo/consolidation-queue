# Phase 3 Component Diagnostic Matrix Interpretation

Date: 2026-05-09

This report interprets the completed `general_v1` noisy component diagnostic matrix as component evidence only. It does not rank scenario families, does not make a noisy-mode policy claim, and does not unlock extracted-candidate policy comparisons.

## Decision

The next active task should be targeted prompt/schema diagnostics, not CI-aware gate-decision design yet.

The operational rule was: choose prompt/schema diagnostics first if at least 2 families show the same taxonomy bucket at both 7B and 32B; otherwise choose CI-aware gate-decision design. The rule is met:

- `scope_key_or_level_drift` appears at both 7B and 32B in `preference_drift`, `scope_contamination`, and `mechanism_diverse_heldout`.
- `canonical_split_or_merge` appears at both 7B and 32B in `preference_drift` and `scope_contamination`.

Policy comparisons remain locked until component outputs are saved, scored, inspectable, and gate-decision results are reported separately from policy outcomes.

## Strongest Headroom Signal

The highest-signal 32B row is `preference_drift` held-out. It has 10 failure examples, the largest 32B failure count in the current matrix notes, despite all measured quality gates passing.

Direct inspection shows the failures concentrate on two held-out drift-back scenarios. In both, an event phrased as a one-checkpoint return to the earlier style was predicted as a `temporary_constraint` scoped to `session`, while gold labels treat it as a `user_preference` in `user_global` scope. That single interpretation pattern fans out into:

- 4 `canonical_split_or_merge` examples
- 4 `scope_key_or_level_drift` examples
- 2 `claim_type_drift` examples

This is a prompt/schema diagnostic signal because it is visible in the 32B headroom path and overlaps with 7B defects rather than being only a small-model capacity issue.

## Artifact Inventory

Verified artifact inventory:

- 13 Qwen 2.5 7B `Q4_K_M` floor diagnostic rows.
- 7 Qwen 2.5 32B `Q4_K_M` headroom diagnostic rows.
- Phase A forced-contradiction regression artifacts are treated separately, including the 32B `forced_contradiction` mixed `general_v1` row.

No model inference was rerun for this interpretation.

## Failure Taxonomy

Every failure example was assigned to exactly one bucket using this fixed precedence:

1. `scenario_error`
2. `candidate_miss_or_extra`
3. `repetition_as_contradiction`
4. `scope_key_or_level_drift`
5. `canonical_split_or_merge`
6. `claim_type_drift`

The artifact-to-bucket mapping is:

- `component=scenario` or `failure_type=scenario_error` -> `scenario_error`
- `component=candidate_detection` -> `candidate_miss_or_extra`
- `component=contradiction` -> `repetition_as_contradiction`
- `component=scope_key` or `component=scope_level` -> `scope_key_or_level_drift`
- `component=canonicalization` -> `canonical_split_or_merge`
- `component=claim_type` -> `claim_type_drift`

This taxonomy maps all observed failure examples with no unmapped cases. Because the fixed taxonomy has one contradiction bucket, both `contradiction_extra` and `contradiction_missing` examples are counted under `repetition_as_contradiction`; the underlying artifact `failure_type` should be inspected when that subcase matters.

## Row-Level Metrics

`NA` means the component metric was not applicable or not defined for that row, not that the row passed a measured gate.

| Family | Split | Model | n | Errors | Failure examples | Failed measured gates | Cand F1 | Claim acc | Scope level | Scope key | Canon F1 | Contr F1 |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| false_corroboration | heldout | 32B | 4 | 0 | 0 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | NA |
| false_corroboration | heldout | 7B | 4 | 3 | 18 | candidate_detection_f1, canonicalization_b_cubed_f1 | 0.40 | 1.00 | 1.00 | 1.00 | NA | NA |
| false_corroboration | mixed | 7B | 4 | 0 | 0 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | NA |
| forced_contradiction | heldout | 32B | 4 | 0 | 0 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| forced_contradiction | heldout | 7B | 4 | 0 | 2 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.86 |
| forced_contradiction | mixed | 7B | 6 | 0 | 2 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.89 |
| mechanism_diverse_heldout | frozen | 32B | 3 | 0 | 3 | none | 1.00 | 1.00 | 1.00 | 0.91 | 0.95 | 0.86 |
| mechanism_diverse_heldout | frozen | 7B | 3 | 1 | 11 | canonicalization_b_cubed_f1, contradiction_f1, contradiction_recall | 0.78 | 1.00 | 0.86 | 0.71 | NA | 0.40 |
| memory_poisoning | heldout | 32B | 10 | 0 | 0 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| memory_poisoning | heldout | 7B | 10 | 3 | 16 | candidate_detection_f1, canonicalization_b_cubed_f1, contradiction_f1, contradiction_recall | 0.73 | 0.88 | 0.88 | 0.88 | NA | 0.40 |
| memory_poisoning | mixed | 7B | 10 | 0 | 12 | claim_type_accuracy | 1.00 | 0.71 | 0.71 | 0.71 | 1.00 | 1.00 |
| preference_drift | heldout | 32B | 4 | 0 | 10 | none | 1.00 | 0.75 | 0.75 | 0.75 | 0.80 | 1.00 |
| preference_drift | heldout | 7B | 4 | 0 | 16 | claim_type_accuracy, contradiction_precision, scope_key_accuracy, scope_level_accuracy | 1.00 | 0.62 | 0.62 | 0.50 | 0.74 | 0.80 |
| preference_drift | mixed | 7B | 6 | 1 | 14 | contradiction_f1, contradiction_precision, contradiction_recall | 0.89 | 0.75 | 0.75 | 0.62 | 0.93 | 0.40 |
| scope_contamination | heldout | 32B | 4 | 0 | 3 | none | 1.00 | 1.00 | 0.86 | 0.86 | 0.92 | 1.00 |
| scope_contamination | heldout | 7B | 4 | 1 | 12 | canonicalization_b_cubed_f1, contradiction_f1, contradiction_recall, scope_level_accuracy | 0.83 | 0.80 | 0.40 | 0.60 | NA | 0.67 |
| scope_contamination | mixed | 7B | 8 | 2 | 19 | canonicalization_b_cubed_f1, contradiction_f1, contradiction_precision, contradiction_recall, scope_level_accuracy | 0.83 | 1.00 | 0.60 | 0.70 | NA | 0.00 |
| useful_pending_memory | heldout | 32B | 4 | 0 | 0 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| useful_pending_memory | heldout | 7B | 4 | 0 | 0 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| useful_pending_memory | mixed | 7B | 4 | 0 | 0 | none | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## Bucketed Failure Examples

| Family | Split | Model | Total | Candidate | Repetition as contradiction | Scope drift | Canon split/merge | Claim type | Scenario errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| false_corroboration | heldout | 32B | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| false_corroboration | heldout | 7B | 18 | 15 | 0 | 0 | 0 | 0 | 3 |
| false_corroboration | mixed | 7B | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forced_contradiction | heldout | 32B | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| forced_contradiction | heldout | 7B | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| forced_contradiction | mixed | 7B | 2 | 0 | 2 | 0 | 0 | 0 | 0 |
| mechanism_diverse_heldout | frozen | 32B | 3 | 0 | 1 | 1 | 1 | 0 | 0 |
| mechanism_diverse_heldout | frozen | 7B | 11 | 4 | 3 | 3 | 0 | 0 | 1 |
| memory_poisoning | heldout | 32B | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| memory_poisoning | heldout | 7B | 16 | 6 | 3 | 2 | 1 | 1 | 3 |
| memory_poisoning | mixed | 7B | 12 | 0 | 0 | 8 | 0 | 4 | 0 |
| preference_drift | heldout | 32B | 10 | 0 | 0 | 4 | 4 | 2 | 0 |
| preference_drift | heldout | 7B | 16 | 0 | 1 | 7 | 5 | 3 | 0 |
| preference_drift | mixed | 7B | 14 | 2 | 3 | 5 | 1 | 2 | 1 |
| scope_contamination | heldout | 32B | 3 | 0 | 0 | 2 | 1 | 0 | 0 |
| scope_contamination | heldout | 7B | 12 | 2 | 1 | 5 | 2 | 1 | 1 |
| scope_contamination | mixed | 7B | 19 | 4 | 2 | 7 | 4 | 0 | 2 |
| useful_pending_memory | heldout | 32B | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| useful_pending_memory | heldout | 7B | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| useful_pending_memory | mixed | 7B | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Across the 20 diagnostic rows, the bucket totals are:

- `scope_key_or_level_drift`: 44
- `candidate_miss_or_extra`: 33
- `canonical_split_or_merge`: 19
- `repetition_as_contradiction`: 18
- `claim_type_drift`: 13
- `scenario_error`: 11

These counts are diagnostic only. They are not weighted by scenario importance, confidence, or downstream policy effect.

## 7B Held-Out vs Main-Split Sanity Check

This check looks only at families with both mixed/main and held-out rows at 7B.

| Family | 7B mixed failures | 7B held-out failures | Interpretation |
|---|---:|---:|---|
| forced_contradiction | 2 | 2 | No sharp split divergence. Both rows show repetition/support observations being marked as contradiction edges. |
| scope_contamination | 19 | 12 | No held-out-only spike. Both splits show broad scope/canonicalization fragility, with mixed somewhat worse. |
| preference_drift | 14 | 16 | No sharp split divergence. Both splits show scope, canonicalization, and claim-type drift around preference updates and temporary-looking language. |
| useful_pending_memory | 0 | 0 | No observed split fragility in this diagnostic matrix. |
| false_corroboration | 0 | 18 | Sharp held-out divergence. The 7B held-out row has validation errors from empty `canonical_id` values, causing candidate misses; 32B held-out is clean. |
| memory_poisoning | 12 | 16 | No sharp count divergence, but held-out adds validation-error and candidate-miss failures while mixed is dominated by scope and claim-type drift. |

The false-corroboration held-out spike is the clearest 7B split-fragility signal. It does not appear in the 32B held-out row, so it does not by itself trigger prompt/schema-first under the cross-size decision rule.

## Phase A Separation

The forced-contradiction Phase A artifacts remain a regression guard, not a cross-family prompt safety claim. After the final prompt revision:

- the 32B forced-contradiction mixed `general_v1` artifact has 0 scenario errors, 0 failure examples, `candidate_detection_f1=1.00`, and `contradiction_f1=1.00`
- the 7B forced-contradiction mixed `general_v1` row improved candidate detection to `1.00` but still has 2 contradiction-extra examples

Phase A therefore cleared the acquisition-status smoke row, but the broader diagnostic matrix shows remaining cross-family issues in scope and canonicalization.

## Next Diagnostic Slice

The next prompt/schema diagnostic slice should focus on:

1. Preference-drift one-off or drift-back wording that looks temporary but is gold-labeled as durable user preference state.
2. Scope-key and scope-level handling for workspace/project/user/session distinctions.
3. Canonicalization behavior when a later event updates or reuses the same memory slot but changes the observed value.
4. Validation failures where 7B emits empty required fields under constrained decoding.

Any prompt/schema change should rerun the forced-contradiction Phase A regression path first, then rerun the affected diagnostic rows before CI-aware gate-decision design resumes.
