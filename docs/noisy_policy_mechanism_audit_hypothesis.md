# Noisy Policy Mechanism Audit Hypothesis

Date: 2026-05-15

This note locks the interpretation that the Bucket B mechanism audit will test
against the saved 32B noisy policy-comparison artifacts. It is descriptive
interpretation, not a new statistical gate, threshold, or policy-comparison
claim.

## Hypothesis

CQ-vs-Reflection survival under noisy extraction tracks whether the policy
decision depends on extractor outputs that the 32B cell emits reliably for that
family.

Survival is expected for contestation/demotion under contradiction-like drift:

- `forced_contradiction`
- `preference_drift`

Convergence to exact ties may reflect extractor-floor convergence. In that
case, the 32B noisy outputs on the tied families would exhibit the same
component-level defect classes already locked in the 7B failure taxonomy:

- `scope_contamination`: scope keys plus contradiction-edge target validity
- `memory_poisoning`: claim-type durability plus contradiction edges
- `useful_pending_memory`: required-field omission on fields needed for
  pending-vs-durable policy decisions
- `mechanism_diverse_heldout`: mixed schema-shaped failures and
  contradiction-link failures, especially on the preference-drift sentinel

This audit must verify or reject that interpretation directly against the 32B
noisy policy-comparison artifacts. The 32B component-gate cells cleared at the
aggregate, per-family, and frozen-sentinel levels, so the 7B failure taxonomy is
only a suggestive prior. It is not evidence that residual extractor defects
persisted in the 32B noisy policy-comparison outputs.

## Interpretation Rules

The audit will treat each family independently:

- A survival row requires artifact evidence that the 32B noisy outputs preserved
  the extractor signal needed by the policy mechanism.
- An extractor-floor convergence row requires artifact evidence that the 32B
  noisy outputs measurably reproduced the relevant defect class, enough to deny
  the policy a needed signal.
- A capacity-bounded row requires evidence that the strict-schema 32B follow-up
  also reproduced the same failure pattern, not merely the older 7B taxonomy.
- If the artifacts do not support either survival or convergence, the row will
  be recorded as an unattributed null rather than forced into the hypothesis.

The audit may use the 7B locked-gate taxonomy to state priors and contrast
defect classes, but all attribution calls must rest on committed 32B noisy
policy-comparison artifacts.
