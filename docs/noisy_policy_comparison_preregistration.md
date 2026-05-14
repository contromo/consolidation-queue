# Noisy Policy Comparison Preregistration

Status: draft work item, not locked, not executable.

## Trigger

The 2026-05-14 local unlock probe reached Bucket A because both
`qwen2.5:32b-instruct-q4_K_M` primary gates (`default` and
`scenario_conditioned`) unlocked after the 7B anchor reproduced exact locked
counts.

This document is the required next preregistration before any extracted-candidate
CQ-vs-Reflection-vs-`Mem0Lite` policy comparison starts.

The locked version should follow
`docs/preregistered_memory_governance_evaluation_template.md` rather than this
stub's abbreviated structure.

## Scope To Lock Before Running

- primary model, schema profile, prompt path, decoding JSON, and Ollama digest
- exact scenario families, splits, counts, and template inclusion rules
- policy set and thresholds
- shared upstream candidate stream construction
- shared storage substrate configuration
- primary metrics, win rules, non-inferiority rules, and outcome buckets
- required manifests, traces, component-output artifacts, and failure examples
- abort conditions for component-quality drift, missing artifacts, model-digest
  mismatch, dirty preregistration state, or asymmetric policy inputs

## Required Fairness Constraints

- CQ, ReflectionEagerWrite, and `Mem0Lite` must consume the same extracted
  candidate stream.
- CQ must not receive a richer private memory representation than the baselines.
- Oracle-mode and noisy-mode claims must remain separate in the readout.
- Component-quality failures must be reported as component failures, not policy
  failures.
- Any policy comparison must save enough per-scenario traces to diagnose whether
  a result came from extraction, storage, or policy logic.

## Non-Goals

- This is not the Bucket C cross-family abstention assay.
- This is not a LongMemEval transfer run.
- This is not a prompt-tuning or validator-relaxation plan.
- This is not a repair of `CQDatedContestation` or `temporal_skew`.

## Lock Checklist

- [ ] Specify the primary extracted-candidate policy-comparison cells.
- [ ] Specify the exact component artifact inputs and cache/provenance checks.
- [ ] Specify all CQ-vs-Reflection and CQ-vs-`Mem0Lite` primary gates.
- [ ] Include per-mechanism, per-metric prediction rows.
- [ ] Include ablation attribution rules.
- [ ] Include oracle-vs-noisy delta predictions by policy.
- [ ] Include outcome precedence and disconfirmation buckets.
- [ ] Specify secondary ablation or sensitivity rows, if any.
- [ ] Specify artifact retention and manifest policy.
- [ ] Add focused regression or dry-run checks for same-stream enforcement.
- [ ] Mark this document locked before running any policy-comparison command.
