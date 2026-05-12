# Adversarial Upstream-Noise Preregistration

## Scope and invariants

This is a separate oracle-only policy comparison at the correct locus of noise:
adversarial upstream candidate streams with extraction held constant. It does
not modify the locked Phase 3 component-eval path or the on-hold Phase 4 noisy
policy-comparison path.

Repo invariants carried over from `AGENTS.md`:

- compare CQ and `ReflectionEagerWriteLite` on the same upstream candidate stream
- keep the same storage substrate across policies
- separate oracle-mode claims from noisy-mode claims
- do not hide failure cases
- keep artifacts and traces inspectable

## Motivation

The current 7B noisy-policy comparison remains correctly locked because
extractor failures are policy-asymmetric. This family isolates the policy
question by injecting adversarial noise into oracle candidate streams instead of
into extraction.

## Family contract

The family name is `adversarial_upstream_noise`.

Allowed template mixes:

- `mixed`
- `dirty`
- `heldout`

This family intentionally rejects `clean`; the adversarial structure is the
family.

All templates use a single question phase, `adversarial_probe`, so failure
examples and family-specific metrics remain family-based rather than
template-specific plumbing.

## Mechanisms and hypotheses

### 1. `adversarial_retraction_v1` / `_v2`

- Mechanism: a claim is observed, corroborated from an independent source, and
  then explicitly retracted via a contradictory candidate before the probe.
- Hypothesis: full CQ beats `ReflectionEagerWriteLite` by demoting the earlier
  claim through contestation; `CQNoContestationDemotion` should collapse toward
  eager behavior.
- Primary descriptive diagnostic: `retraction_demotion_rate`.

### 2. `adversarial_witness_conflict_v1` / `_v2`

- Mechanism: symmetric X-versus-Y conflict from four independent witnesses.
- Gold behavior: abstention, represented as empty `resolved_candidate_ids` with
  `expected_lifecycle["abstention_ok"] = True`.
- Hypothesis: CQ wins narrowly by refusing to overcommit; both
  `CQNoContestationDemotion` and `CQNoSourceIndependenceGate` should regress.

### 3. `adversarial_temporal_skew_v1` / `_v2`

- Mechanism: a current authoritative claim is followed by a stale-but-strong
  contradictor with much older `provenance.observed_at`, then a weaker current
  corroboration of the newer truth.
- Hypothesis: CQ may not clearly win. None of the current Phase 2.5 toggles is
  `observed_at`-aware, so this is the explicit surprise lane / weakness probe.
- Primary descriptive diagnostic: `stale_evidence_promotion_rate`.

### 4. `adversarial_scope_narrowing_v1` / `_v2`

- Mechanism: a wider-scope durable is legitimate, then a narrower project-scope
  correction arrives and should shadow only within the narrower scope.
- Hypothesis: CQ wins via exact-scope pending override;
  `CQNoWiderScopePendingOverride` regresses by leaking the wider claim or
  ignoring the narrower correction.
- Primary descriptive diagnostic: `narrow_scope_override_success_rate`.

### 5. `adversarial_pending_competition_v1` / `_v2`

- Mechanism: two competing pending candidates remain below promotion threshold
  at probe time; the stronger candidate is gold.
- Hypothesis: CQ wins by answering from the strongest pending candidate;
  `CQNoPendingLookupUse` returns no usable memory.
- Primary descriptive diagnostic: `pending_competition_resolution_rate`.

Held-out `_v2` variants must be genuine surface-form robustness checks, not
relabeled `v1`s. They vary entity/value pools, wording, scope-key shapes, and
ordering while preserving the same mechanism. In particular,
`scope_narrowing_v2` uses materially different project key shapes from `v1`.

This family keeps `witness_conflict` as the only primary source-independence
lane. It does not add a second corroboration-style mechanism that materially
overlaps the already-frozen
`false_corroboration_adversarial_mixed_source` contract.

## Run design

- headline split: `mixed`
- robustness split: `heldout`
- headline size: `60` scenarios per mechanism
- family total per headline split: `300` scenarios (`5 x 60`)
- bootstrap procedure: fixed-seed `10,000`-resample paired bootstrap over
  scenario-level correctness deltas

## Primary metric

The primary metric is binary scenario-level `answer_correctness` for all five
mechanisms.

- correct = `1.0`
- incorrect = `0.0`

For `witness_conflict`, correct abstention is `1.0`; any concrete forbidden
assertion or other miss is `0.0`.

Auxiliary diagnostics remain descriptive and do not alter the bootstrap scale.
For metric-shape consistency, `useful_recall` mirrors `answer_correctness` on
this family even on abstention-correct rows; interpret that field as a shared
binary outcome column rather than literal recalled content.

## Decision rules

### Mechanism win rule

On the `mixed` split, full CQ counts as winning a mechanism against
`ReflectionEagerWriteLite` only if both conditions hold:

1. point-estimate `answer_correctness` delta is at least `0.10`
2. one-sided `95%` lower confidence bound from the fixed-seed paired bootstrap
   exceeds `0`

### Family success rule

Full CQ supports the family thesis only if it clears the mechanism win rule on
at least `2` of the `5` mechanisms on `mixed`.

If CQ clears fewer than `2`, the thesis is partially refuted and must be
written up that way.

Held-out results are robustness checks and are reported separately from the
headline gate.

### Multiple-testing posture

No separate Bonferroni correction is applied across the five mechanism rows.
The preregistered `>= 2`-of-`5` success rule is the family-wise multiple-testing
guard. Under independence assumptions with one-sided `alpha = 0.05` per row,
the null family false-positive rate is approximately `2.3%`. This is an
approximation; dependence changes the exact rate.

### Threshold rationale

At `N = 60` scenarios per mechanism, the noise scale on a proportion is roughly
`6-7` points.

- `0.05` = inert / noise-scale
- `0.10` = minimum practically interesting policy gain
- `0.15` = clearly load-bearing ablation drop

Scenario calibration depends on the current lifecycle thresholds in
`cq/memory/lifecycle.py`: `world_fact_promotion=0.85`,
`non_world_promotion=0.70`, and `overwrite_margin=0.05`. Changes to those
values require recalibration before this family is rerun.

## Ablation attribution rule

For a given mechanism, compare each CQ ablation against full CQ:

- drop `>= 0.15`: that component "carries" the mechanism
- drop `<= 0.05`: that component is "inert"
- anything between: report as mixed / inconclusive

Predicted primary component-mechanism relationships:

- `retraction` -> `CQNoContestationDemotion`
- `witness_conflict` -> `CQNoContestationDemotion`, `CQNoSourceIndependenceGate`
- `temporal_skew` -> no clean existing toggle prediction; this is a weakness
  probe
- `scope_narrowing` -> `CQNoWiderScopePendingOverride`
- `pending_competition` -> `CQNoPendingLookupUse`

## Baseline reporting

`Mem0Lite` is reported as a partial-baseline sub-table. It does not contribute
to the family success rule. For consistency, its deltas versus
`ReflectionEagerWriteLite` are still reported with the same fixed-seed paired
bootstrap lower bound.

## Outcome framing committed pre-run

- If CQ loses only `temporal_skew` while clearing the dedicated component lanes,
  write it up as a named CQ weakness tied to lack of dated-evidence handling and
  name the follow-up concretely: `CQDatedContestation`, evaluated later as a
  separate post-hoc follow-up on the same family.
- If CQ clears exactly `2` of `5`, write it up as narrow mechanism-specific
  support rather than broad support for noisy candidate-stream governance in
  general.
- If CQ clears fewer than `2` of `5`, write it up as a partial refutation:
  "CQ governs these mechanisms, not those."
- If CQ clears `3` or more, write it up as the oracle policy comparison at the
  correct locus of noise, with the ablation table carrying the mechanism story.

## Phase 3 / lock interaction

- this family is runner-eligible but not component-eval-eligible
- this family is runner-eligible but not local-extractor-eligible
- `scripts/run_component_gate_decision.py` remains unchanged in spirit
- this family does not enter `cq/eval/preregistration_lock.py` yet; SHA-256 lock
  inclusion is deferred until the mechanism set has survived at least one
  revision cycle

## Planned run order

1. commit this preregistration
2. run focused tests
3. inspect a tiny `dirty` sample
4. run:
   - `python3 -m cq.eval.runner --family adversarial_upstream_noise --policy-set default --template-mix mixed --scenarios 300`
   - `python3 -m cq.eval.runner --family adversarial_upstream_noise --policy-set phase2_5 --template-mix mixed --scenarios 300`
   - `python3 -m cq.eval.runner --family adversarial_upstream_noise --policy-set phase2_5 --template-mix heldout --scenarios 300`
