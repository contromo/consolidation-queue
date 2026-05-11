# Phase 3 Locked Gate Failure Taxonomy

Date: 2026-05-11

This note interprets the authoritative 7B `general_v1` CI-aware component gate
run as publication-facing component evidence only. It does not unlock
extracted-candidate policy comparisons, and it does not reinterpret the locked
7B verdict.

## Decision

The 7B `general_v1` path is locked for noisy-mode policy reporting.

What passed:

- Phase A prompt regression
- determinism check
- aggregate CI-supported gates
- aggregate observed gates

What still blocked unlock:

- `45` primary scenario errors
- `8` primary observed gate failures
- `3` frozen-sentinel observed gate failures

The important methodological conclusion is that aggregate gates passed while the
per-family and frozen-sentinel checks did the actual blocking work.

## Gate Snapshot

| Check | Result |
| --- | --- |
| `phase_a_passed` | `true` |
| `determinism_passed` | `true` |
| `aggregate_ci_gate_failure_count` | `0` |
| `aggregate_observed_gate_failure_count` | `0` |
| `primary_scenario_error_count` | `45` |
| `primary_observed_gate_failure_count` | `8` |
| `frozen_sentinel_observed_gate_failure_count` | `3` |
| `policy_comparison_unlocked` | `false` |

This note mirrors the counts already synchronized into
`docs/product_progress.md` so the interpretation remains durable even though the
local generated gate summary artifact is not git-tracked.

## Per-Family Blocker Pattern

| Family | Scenario errors | Observed gate failure count | Observed gate failures | Dominant interpretation |
| --- | ---: | ---: | --- | --- |
| `forced_contradiction` | 0 | 0 | none | passes cleanly; this family is not what blocked unlock |
| `scope_contamination` | 12 | 3 | `scope_level_accuracy`, `contradiction_f1`, `contradiction_recall` | schema-following and contradiction-linking failures concentrate here |
| `preference_drift` | 8 | 2 | `claim_type_accuracy`, `scope_level_accuracy` | durability and scope drift plus blank canonical identifiers |
| `useful_pending_memory` | 3 | 0 | none | limited but real required-field omission on override rows |
| `false_corroboration` | 17 | 1 | `canonicalization_b_cubed_f1` | repeated corroboration collapses because canonical identifiers are missing |
| `memory_poisoning` | 5 | 2 | `claim_type_accuracy`, `contradiction_recall` | override claims drift to temporary/session framing and contradiction links are missed |
| `mechanism_diverse_heldout` frozen sentinel | 1 | 3 | `canonicalization_b_cubed_f1`, `contradiction_f1`, `contradiction_recall` | the fixed sentinel itself reproduces the same extractor failure family |

Two facts matter most:

1. The blocker pattern is concentrated rather than diffuse.
2. The frozen sentinel fails on the same class of defects as held-out
   `preference_drift` rows, so this is not only a held-out-generalization
   problem.

## Mode-Level Taxonomy

### 1. Required-field omission

The model leaves schema-required fields blank despite the prompt and constrained
output contract.

Durable counts from the locked run:

- empty `scope_key`: `15` primary scenarios plus `1` frozen-sentinel scenario
- empty `canonical_id`: `25` primary scenarios

Why it matters:

- these are immediate validation failures
- they suppress candidate detection and canonicalization before policy behavior
  can even be evaluated

### 2. ID-namespace confusion

The model confuses two different schema namespaces: it emits a `canonical_id`
slug where the contract requires earlier `event_id` values inside
`contradicts_event_ids`.

Durable count from the locked run:

- invalid `contradicts_event_ids` target: `5` primary scenarios

Why it matters:

- this is not a runner alignment bug
- it is a real schema-following failure in the model output

### 3. Durable-claim drift

The model recasts durable user or project state as `temporary_constraint` in
`session` scope when gold expects a persistent preference or project-level
convention.

This pattern is most visible in:

- `preference_drift`
- `memory_poisoning`
- parts of `scope_contamination`

Why it matters:

- it degrades both claim-type accuracy and scope-level accuracy
- it turns long-horizon memory governance into one-off instruction handling

### 4. Contradiction-edge misses

The model fails to represent contradiction relations even when the underlying
slot is still recoverable.

This pattern is most visible in:

- `scope_contamination`
- `memory_poisoning`
- the frozen sentinel

Why it matters:

- contradiction recovery is one of the benchmark's core safety signals
- missing contradiction links hide exactly the reversibility behavior Phase 4
  was supposed to test

## Representative Failure Evidence

- `scope_contamination_014`: the model emits
  `contradicts_event_ids=["workspace-wide-test-convention"]` even though that
  string is a `canonical_id` slug, not the earlier event id
  `scope_contamination_014-event-1`
- `preference_drift_012`: multiple predictions emit `canonical_id=""`, showing
  that canonicalization can fail before any policy-specific interpretation
- `memory_poisoning_005`: an override claim is emitted with `scope_level=session`
  and `scope_key=""`, then the contradiction edge against the trusted note is
  missed downstream
- `frozen_preference_drift_001`: the frozen sentinel reproduces the held-out
  `preference_drift` failure pattern: empty `scope_key` values plus missed
  contradiction edges across the revision chain

These examples matter because they show that the failure taxonomy is grounded in
raw model output and evaluator failure examples, not only in top-line counts.

## Why Aggregate Gates Were Not Enough

The locked run is a useful gate-design result in its own right:

- `aggregate_ci_gate_failure_count=0`
- `aggregate_observed_gate_failure_count=0`
- unlock still fails because the per-family and frozen-sentinel checks catch
  concentrated defects that aggregate rollups smooth away

That is a benchmark design success, not a bookkeeping accident. The per-family
gate prevented a false unlock that the aggregate view alone would have missed.

## How This Fits the Oracle-Mode Story

The publication package should not present this taxonomy in isolation.

The oracle-mode frozen benchmark already provides the positive benchmark result:

- all 108 preregistered oracle-mode deltas matched the observed deltas
  (`3` frozen families x `6` comparators x `6` metrics)
- CQ shows narrow oracle-mode support over `Mem0Lite`, primarily on
  `premature_promotion_rate`
- CQ does not show broad oracle-mode superiority on answer correctness or false
  assertion versus `Mem0Lite`

The noisy-mode story is therefore not "CQ failed." The more accurate statement
is:

- the benchmark and preregistration discipline worked
- the oracle-mode comparison produced a narrow, honest policy result
- the local noisy extractor did not clear the component-quality gate needed to
  make any noisy-mode CQ policy claim publishable

That is why the publication framing is benchmark plus failure taxonomy rather
than noisy-policy contribution.

## Minimum Additional Evidence Still Worth Collecting

The minimum descriptive follow-up that could strengthen the publication package
without reopening the gate decision is:

- one 32B `scope_contamination` row

Purpose:

- test whether the most schema-sensitive failure family looks like a pure 7B
  capacity ceiling or a broader task/prompt problem

Boundary:

- this is descriptive-only evidence
- it cannot unlock policy comparison
- it cannot rewrite the locked 7B verdict
- before running it, expected outcomes should be written down first so the
  interpretation is not post-hoc:
  - if 32B materially reduces the `scope_contamination` failure pattern, treat
    that as capacity-sensitive evidence
  - if 32B reproduces the same pattern, treat that as broader task/prompt/schema
    evidence
- both outcomes are publishable and neither outcome should, by default, trigger
  a wider follow-up run set

A second model-family row is optional and should be added only if the eventual
publication starts making a generalization claim that one 32B row cannot
support.

## LongMemEval Positioning

LongMemEval is not part of the current empirical contribution.

For this paper package it should be treated as:

- external positioning
- future work after noisy-mode validation exists
- not a contemporaneous transfer result

The correct framing is whether a future CQ-versus-baseline comparison transfers
to a benchmark the project did not design, not whether this work "beats"
LongMemEval.

## Boundaries To Preserve

- do not reopen `general_v2`
- do not loosen validators or lower thresholds
- do not reinterpret the locked 7B gate from any later descriptive headroom row
- do not start noisy-policy comparisons while
  `policy_comparison_unlocked=false`
