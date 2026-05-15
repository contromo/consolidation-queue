# Canonical-Id Resolution Audit Preregistration

Date: 2026-05-15

Status: locked before replay.

canonical_id_resolution_audit_lock_sha256: d0b3a59905ca48201ec7e23ce7e933ab2fe161c9bfc507d54e2a99a90fc2c652

canonical_id_resolution_alias_source_sha256: 8176c5a93ffbdbfd99d48f73836b954aa27aee4ab08de567ca47ec63d7896de0

## 1. Scope And Invariants

This audit is a policy-facing canonical-id/query-resolution follow-up to the
Phase 4 Bucket B null rows. It tests whether exact canonical-id lookup can
diverge from cluster-oriented B-cubed F1 even when the 32B component artifacts
record perfect component metrics.

Load-bearing invariants:

- replay only; no prompt, schema, threshold, validator, adapter, policy, or
  substrate changes
- every policy remains on the same upstream extracted candidate stream
- the alias function is audit-time only and must never be imported into
  `cq/memory/*` or `cq/eval/extracted_candidate_runner.py`
- `useful_pending_memory` and `memory_poisoning` are the only thesis-gating
  families
- `false_corroboration` is descriptive because source identity is not extracted
  and the 32B scope-key metric is not perfect

Out of scope:

- rerunning or changing the Phase 4 noisy policy comparison outcome
- integrating CQR into `cq/eval/component_eval.py`
- changing `MemoryStore` exact lookup semantics
- claiming LongMemEval transfer
- using alias-CQR to rescue a component threshold or Bucket B gate

## 2. Locked Extractor Cell

The replay target is exactly the Phase 4 primary cell:

- primary model: `qwen2.5:32b-instruct-q4_K_M`
- schema profile: `default`
- policy set: `phase2_5`
- frozen sentinel: included

The runner first invokes:

```bash
python3 scripts/run_noisy_policy_comparison.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --policy-set phase2_5
```

It then verifies each regenerated run JSON and metrics CSV against the committed
per-family manifest. Any dirty pre-run worktree, missing artifact, replay error,
or SHA mismatch is Bucket D.

## 3. Metrics

Section A is descriptive reproduction:

- `cqr_set_membership`: the question's `relevant_canonical_id` is exactly in
  the extracted candidate canonical-id set
- `cqr_scope_matched`: exact canonical-id hit plus matching question
  `scope_level` and `scope_key`
- `b_cubed_f1`: copied from the matching 32B component-eval artifact
- `b_cubed_minus_cqr_gap`: descriptive gap
- per-policy answer-success and CQR-hit marginals

Section B is the strict pre-run alias-CQR prediction:

- `cqr_alias_set_membership`: the same per-question CQR denominator, but with
  the locked alias function below
- `alias_false_positive_rate`: among same-scenario `(extracted candidate,
  question)` pairs where the extracted id alias-matches at least one relevant
  id, the fraction where it does not match the relevant id for that question

Section C is the cross-tab diagnostic:

- for CQ on each thesis family,
  `P(answer_success | alias_CQR_hit) - P(answer_success | alias_CQR_miss) >= 0.30`
- if a thesis family has fewer than 5 alias-CQR hits, Section C is underpowered
  and falsified by default

## 4. Bucket Rules

First match wins:

1. Bucket D - abort: lock mismatch, input SHA mismatch, dirty pre-run worktree,
   missing artifact, or replay error before metric emission.
2. Bucket A - thesis confirmed: both `useful_pending_memory` and
   `memory_poisoning` clear their alias-CQR prediction, false-positive cap, and
   CQ cross-tab lift.
3. Bucket C - thesis falsified or contaminated: either thesis family misses its
   alias-CQR band, exceeds its false-positive cap, or fails/underpowers the CQ
   cross-tab lift.
4. Bucket B - partial/descriptive: all other non-abort outcomes.

`false_corroboration` is reported under every outcome but never gates Bucket A.

## 5. Locked Predictions

<!-- FROZEN_EVAL_PREDICTIONS_START -->
### Section B Alias-CQR Predictions

Thesis rows:

| Family | predicted `cqr_alias_set_membership` | tolerance | predicted `alias_false_positive_rate` cap |
| --- | --- | --- | --- |
| `useful_pending_memory` | `>= 0.40` | +/- 0.20 | `<= 0.05` |
| `memory_poisoning` | `>= 0.40` | +/- 0.20 | `<= 0.05` |

Descriptive companions:

| Family | predicted `cqr_alias_set_membership` | tolerance | predicted `alias_false_positive_rate` cap |
| --- | --- | --- | --- |
| `false_corroboration` | `0.10-0.60` | inside band | `<= 0.10` |
| `scope_contamination` | `<= 0.25` | +/- 0.10 | `<= 0.05` |
| `forced_contradiction` | `>= 0.85` | +/- 0.10 | `<= 0.05` |
| `preference_drift` | `0.25-0.60` | inside band | `<= 0.10` |
| `mechanism_diverse_heldout` | `<= 0.40` | +/- 0.20 | `<= 0.10` |

### Section C Cross-Tab Prediction

For CQ on both thesis families:

`P(policy_answer_success | alias_CQR_hit) - P(policy_answer_success | alias_CQR_miss) >= 0.30`

Both thesis families must meet the lift, and each must have at least 5 alias-CQR
hits.
<!-- FROZEN_EVAL_PREDICTIONS_END -->

## 6. Locked Alias Function

Strictly string-canonical. No fuzzy similarity, LLM rewrite, scenario-specific
carve-out, or family-specific carve-out is allowed.

<!-- CQR_ALIAS_SOURCE_START -->
STOP_TOKENS = {
    "project", "workspace", "user", "session", "global", "frozen",
    "temporary", "constraint",
    "command", "setting", "preference", "config", "value",
    "default", "current", "new", "old",
}
PREFIXES_TO_STRIP = {
    "project",
    "workspace",
    "user",
    "session",
    "temporary-constraint",
    "frozen",
}


def normalize(value):
    return "-".join(token for token in value.lower().split("-") if token)


def tokens(value):
    return set(normalize(value).split("-")) if normalize(value) else set()


def strip_extracted_prefix(value):
    normalized = normalize(value)
    for prefix in sorted(PREFIXES_TO_STRIP, key=len, reverse=True):
        if normalized == prefix:
            return ""
        prefix_with_dash = prefix + "-"
        if normalized.startswith(prefix_with_dash):
            return normalized[len(prefix_with_dash):]
    return normalized


def alias_match(extracted_id, relevant_id):
    if extracted_id == relevant_id:
        return True
    normalized_extracted = normalize(extracted_id)
    normalized_relevant = normalize(relevant_id)
    if normalized_extracted == normalized_relevant:
        return True
    if strip_extracted_prefix(extracted_id) == normalized_relevant:
        return True
    extracted_tokens = tokens(extracted_id) - STOP_TOKENS
    relevant_tokens = tokens(relevant_id) - STOP_TOKENS
    return len(extracted_tokens & relevant_tokens) >= 2 and len(relevant_tokens) >= 2
<!-- CQR_ALIAS_SOURCE_END -->

The known mismatch `project-atlas-pre-merge-check-command` versus
`useful-pending-project-command` is rejected by the locked function because
their non-stop-token intersection is empty.

## 7. Disclosure Of Pre-Lock Observations

Before lock, the planner observed the aggregate exact-CQR counts and up to three
example mismatches per family in `data/results/noisy_policy_mechanism_audit_evidence.json`,
the three focused audit traces, and the 32B component metrics summarized in
`docs/noisy_policy_mechanism_audit.md`.

The planner did not observe the alias function's output on the full Phase 4
streams, the full mismatch list for any family, any per-family alias
false-positive rate, or any Section C cross-tab.

## 8. Locked Input SHAs

The lock covers these manifest and 32B component-eval inputs in addition to the
prediction block and alias source.

<!-- CQR_LOCKED_INPUT_SHAS_START -->
- `data/runs/noisy_policy_comparison_forced_contradiction_default_manifest.json`: `03d9715cae2e34ab639a9c17f638787aff3128ce56cb4eb21846c63c7ee5f8af`
- `data/results/component_gate_decision_forced_contradiction_local_extractor_qwen2_5_32b_q4km_general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json`: `4e907697977137ef2ad76f2660f72683233a617cad70a66c8b82a94430b3c381`
- `data/runs/noisy_policy_comparison_scope_contamination_default_manifest.json`: `cdc9beed9e2579605dacc172b0c53ea1fd50318ed696757860a2157170e27fd1`
- `data/results/component_gate_decision_scope_contamination_local_extractor_qwen2_5_32b_q4km_general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json`: `5677030035356fd3cd50f1a51a46f1d170496aef5d59055a709a0edd824ee6f6`
- `data/runs/noisy_policy_comparison_preference_drift_default_manifest.json`: `0c9bbead34ebffcc2587b1861213acc4205f5d343b80f8cdb07f23b28ad8b4a0`
- `data/results/component_gate_decision_preference_drift_local_extractor_qwen2_5_32b_q4km_general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json`: `948c92ca1e1a722d1d12011c86af8714fd25810500b40b8e7cfe2c0ea111e12d`
- `data/runs/noisy_policy_comparison_useful_pending_memory_default_manifest.json`: `4ab1d2ae841f5dace6f3f1435b331c6276468bb890258b000dbef30dfcb0b345`
- `data/results/component_gate_decision_useful_pending_memory_local_extractor_qwen2_5_32b_q4km_general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json`: `4969f25c16caa1ff4d10cb9f43344f52b9c8c8f23c7b87fb5419926ec67d6432`
- `data/runs/noisy_policy_comparison_memory_poisoning_default_manifest.json`: `b5e2831d741fae8616ff9eabc3ffbb8707e178336cc652877b8f03ac2aa1dce1`
- `data/results/component_gate_decision_memory_poisoning_local_extractor_qwen2_5_32b_q4km_general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json`: `3dd918891d8716c8dfc094961aa61c86f3b4d2feb7a18dc504fefe99da9912d2`
- `data/runs/noisy_policy_comparison_false_corroboration_default_manifest.json`: `cc5a3c0752bb1f48cad603108315bd765858ba3a49c8131767ef3affda58e035`
- `data/results/component_gate_decision_false_corroboration_local_extractor_qwen2_5_32b_q4km_general_v1_default_heldout_n60_primary_unlock_probe_component_eval.json`: `a74aef67b4ffcbf286332bd9bb252285a37bc0e7894abe8aa969f7561ac64121`
- `data/runs/noisy_policy_comparison_mechanism_diverse_heldout_default_manifest.json`: `4602b856c7f89f516100567983bab7fcc9258d04db7da6c3f7c0a12ac1e375c7`
- `data/results/component_gate_decision_mechanism_diverse_heldout_local_extractor_qwen2_5_32b_q4km_general_v1_default_frozen_n3_frozen_sentinel_primary_component_eval.json`: `6e582a7896193333d01453ec7d0ee1be02ce8273a146d70fbc43695939c19860`
<!-- CQR_LOCKED_INPUT_SHAS_END -->

## 9. Verification

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_canonical_id_resolution_audit -q
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_canonical_id_resolution_audit.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --check-lock-only
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_canonical_id_resolution_audit.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q
```
