# Component Gate Follow-Up Preregistration

Date: 2026-05-11

This note preregisters the Phase 3 follow-up evidence block before any new
follow-up runs execute. It does not modify the locked Phase 2.5 oracle
preregistration in `docs/preregistration.md`, and it does not reopen the
authoritative locked 7B `general_v1` verdict already recorded in
`data/results/component_gate_decision_general_v1_summary.json`.

## Purpose

The follow-up asks two targeted questions before drafting a benchmark-scale
paper:

1. Does a larger model reduce the concentrated blocker pattern on the current
   held-out gate surface?
2. Does a stronger generation-time schema materially reduce the same blocker
   pattern at 7B, or are the remaining failures not primarily a schema-shape
   issue?

The follow-up is methodological evidence only. It does not authorize noisy-mode
policy comparisons while the 7B primary gate remains locked.

## Fixed Baseline

The baseline for comparison is the locked 7B `general_v1` gate run already on
disk:

- primary scenario errors: `45`
- primary observed gate failures: `8`
- frozen-sentinel observed gate failures: `3`
- blocker subclasses already confirmed by artifact inspection:
  - empty `scope_key`
  - empty `canonical_id`
  - invalid `contradicts_event_ids` target

For the conditional quadrant trigger below, the comparison surface is the common
blocker region:

- `scope_contamination`
- `preference_drift`
- `memory_poisoning`
- frozen sentinel (`mechanism_diverse_heldout`, `frozen`)

## Runs To Execute

Both mandatory runs execute regardless of whether either one independently
clears the gate. A 32B improvement does not cancel the 7B schema run, and a 7B
schema improvement does not cancel the 32B run.

### Mandatory Run A — 32B Default-Schema Sweep

Use the existing gate contract and the existing default Ollama wrapper path.

Command:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py \
  --include-headroom \
  --headroom-family scope_contamination \
  --headroom-family preference_drift \
  --headroom-family memory_poisoning \
  --include-headroom-frozen-sentinel \
  --include-frozen-sentinel \
  --summary-label general_v1_followup_32b_default
```

Interpretation:

- the 32B rows are descriptive evidence only
- the 32B frozen sentinel is a gate-design artifact, not a statistical sample
- neither the 32B rows nor the 32B sentinel can reopen or reinterpret the
  locked 7B verdict

### Mandatory Run B — 7B Scenario-Conditioned Schema Sweep

Use the same gate contract but change the model wrapper path to a stronger
generation-time schema bundle on 7B:

- non-empty `scope_key`
- non-empty `canonical_id`
- `contradicts_event_ids` constrained to prior scenario `event_id` values at
  generation time

Run the full primary family set so the follow-up still observes
`false_corroboration`, even though the 32B sweep focuses on the concentrated
blocker region.

Command:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py \
  --model-command "python3 scripts/ollama_component_extractor.py --schema-profile scenario_conditioned" \
  --general-prompt-label general_v1_dynamic_schema \
  --include-frozen-sentinel
```

This intervention is attributed as one bundled schema-rescue path. Subclass
reporting remains separate, but the writeup does not claim that only one of the
three sub-constraints caused any improvement.

### Conditional Run C — 32B Plus Scenario-Conditioned Schema

Run this quadrant only if the symmetric trigger below fires.

Command:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py \
  --model-command "python3 scripts/ollama_component_extractor.py --schema-profile scenario_conditioned" \
  --general-prompt-label general_v1_dynamic_schema \
  --summary-label general_v1_followup_32b_dynamic_schema \
  --include-headroom \
  --headroom-family scope_contamination \
  --headroom-family preference_drift \
  --headroom-family memory_poisoning \
  --include-headroom-frozen-sentinel \
  --include-frozen-sentinel
```

## Vacuous-Content Rule

The stronger schema does not automatically count as success if it merely turns
empty fields into placeholders.

For follow-up reporting, normalize `scope_key` and `canonical_id` with
trim-plus-lowercase and treat the following as vacuous:

- empty string
- whitespace-only string
- `unknown`
- `n/a`
- `na`
- `none`
- `null`
- `todo`

Rule:

- schema-valid but vacuous values are counted as failures against gold in the
  same subclass bucket that an empty value would have occupied
- a run does not receive schema-rescue credit for replacing empties with these
  placeholders

Subclass reporting stays explicit even though intervention attribution is
bundled:

- empty/vacuous `scope_key`
- empty/vacuous `canonical_id`
- invalid `contradicts_event_ids` target

## Symmetric Conditional-Quadrant Trigger

Define the common-surface schema-shaped burden as the total count, across the
common blocker region only, of:

- empty/vacuous `scope_key`
- empty/vacuous `canonical_id`
- invalid `contradicts_event_ids` target

Trigger the conditional 32B-plus-schema quadrant if and only if:

1. one mandatory run reduces this common-surface burden by at least `75%`
   relative to the locked 7B baseline, and
2. the other mandatory run reduces it by less than `50%`

This trigger is symmetric. Either split direction qualifies:

- stronger schema helps materially while default-schema 32B does not
- default-schema 32B helps materially while stronger-schema 7B does not

If both mandatory runs help materially or both fail to help materially, do not
run the quadrant.

## Preregistered Expectations

### Run A — 32B Default Schema

Expected direction:

- the common-surface schema-shaped burden decreases materially relative to the
  locked 7B baseline
- `memory_poisoning` is the likeliest family to approach a clean descriptive
  pass
- `scope_contamination` and the frozen sentinel are likely to improve enough
  that remaining issues, if any, are measured failures or failure examples
  rather than validation-shaped scenario errors
- `preference_drift` is the likeliest selected family to retain nontrivial
  observed claim/scope drift even if validation errors disappear

Expected interpretation:

- if 32B materially reduces the schema-shaped burden, capacity is part of the
  story
- if 32B still reproduces the same schema-shaped burden, the failure taxonomy is
  not primarily a 7B-only ceiling

### Run B — 7B Scenario-Conditioned Schema

Expected direction:

- empty/vacuous `scope_key`, empty/vacuous `canonical_id`, and invalid
  `contradicts_event_ids` target errors drop sharply relative to the locked 7B
  baseline
- `false_corroboration` should improve materially if blank `canonical_id`
  emission was the dominant blocker there
- residual observed-gate failures are still likely in `scope_contamination`,
  `preference_drift`, `memory_poisoning`, and possibly the frozen sentinel
- overall expectation: the run improves materially but still does not earn an
  unconditional noisy-policy claim

Expected interpretation:

- if the stronger schema clears most schema-shaped burden but observed failures
  persist, the remaining limitations are not just output-shape violations
- if the stronger schema does not materially reduce the schema-shaped burden, the
  current failure taxonomy is not rescued by this generation-time intervention

### Run C — 32B Plus Scenario-Conditioned Schema

Expected interpretation only if triggered:

- if the combined quadrant clears the common-surface schema-shaped burden when
  neither main effect alone did, schema strictness and capacity are
  complementary
- if the combined quadrant adds little beyond the stronger main effect, the
  interaction is weak and the benchmark story should not overstate it
- if the combined quadrant still fails materially, the remaining blockers are
  not explained by either factor alone

## Drafting Rule

Do not begin the paper draft unless the follow-up evidence supports a
methodology contribution that can be defended without leaning on the single
CQ-versus-`Mem0Lite` delta driven by
`false_corroboration_adversarial_mixed_source`.

If that bar is not met after the mandatory runs and any triggered quadrant, the
next step is to expand frozen held-out benchmark evidence with new
preregistered predictions before drafting.

## Boundaries

- do not reopen `general_v2`
- do not loosen validators or lower thresholds
- do not convert descriptive 32B evidence into a route that unlocks noisy-mode
  policy comparison
- do not treat the frozen sentinel as a statistical family sample
- do not cancel one mandatory run because the other one looked favorable early
