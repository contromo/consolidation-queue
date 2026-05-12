# Preregistered Memory-Governance Evaluation Template

This document distills the repo's current preregistration discipline into a reusable template for future memory-policy evaluations.

The goal is not to force every benchmark family into the same empirical story. The goal is to make it hard to retrofit claims after seeing the results. The evaluation contract should allow a positive result, a mixed result, or a negative result without changing the benchmark after the fact.

## 1. Separate Components From Policy

When the scientific question is about policy behavior, hold extraction constant and move the noise to the correct locus.

Rules:

- compare policies on the same upstream candidate stream
- keep the same storage substrate across policies
- keep oracle-mode claims separate from noisy-mode claims
- do not treat extractor failures as policy evidence

Applied here:

- the `adversarial_upstream_noise` family injects adversarial structure into oracle candidate streams
- the locked Phase 3 and Phase 4 extracted-candidate path stays unchanged
- the family is runner-eligible but not component-eval-eligible and not local-extractor-eligible

This is the key decoupling rule: if the question is "does CQ govern adversarial candidate streams better than eager write?", then the evaluation should not silently become "does one extractor feed CQ better candidates than it feeds Reflection?"

## 2. Use a Two-Part Win Rule

A mechanism counts as a win only if it clears both:

1. a practically meaningful point-estimate threshold
2. a confidence bound in the same direction

For the current oracle policy comparisons, the template rule is:

- point-estimate delta `>= 0.10`
- one-sided `95%` lower confidence bound `> 0`

This avoids two common failure modes:

- overclaiming on tiny noisy gains
- treating a large but unstable point estimate as settled evidence

The current repo uses fixed-seed paired bootstrap over scenario-level correctness deltas so reruns remain deterministic and auditable.

## 3. Guard Multiple Testing at the Family Level

Do not Bonferroni every mechanism row by default if the real scientific claim is family-wise and mechanism-specific.

Instead:

- preregister a small number of mechanism rows
- define a family success rule before running
- evaluate the family claim against that rule

The current pattern is `k`-of-`n`:

- example: "family thesis supported if CQ wins at least `k` of `n` mechanisms"

Why this helps:

- it keeps the decision rule aligned with the actual claim
- it avoids pretending that every mechanism row is an independent paper
- it makes partial support and partial refutation expressible without post-hoc framing

In the adversarial upstream-noise family, the family decision is not just "how many rows are green?" It also includes an explicit surprise-lane branch for a predicted weakness.

## 4. Precommit Attribution Thresholds

If a family includes policy ablations, preregister how you will interpret their effect sizes before running.

The current attribution template:

- drop `>= 0.15`: the component carries the mechanism
- drop `<= 0.05`: the component is inert
- anything between: mixed / inconclusive

Why these thresholds exist:

- at the current scenario counts, a 5-point change is roughly noise scale
- a 10-point change is practically interesting for headline wins
- a 15-point change is large enough to carry a mechanism-level attribution claim

The key discipline is rhetorical: do not upgrade a mixed cell into a clean mechanism story after looking at the run.

## 5. Precommit Outcome Framings

Every preregistration should define the allowable writeup framings before execution.

At minimum, define:

- what counts as family support
- what counts as narrow support
- what counts as partial refutation
- any special surprise-lane rule that triggers a named post-hoc follow-up

This matters because benchmark work is especially vulnerable to narrative drift after results land. Precommitting the framing forces the writeup to follow the result rather than the other way around.

## 6. Keep New Families Out of Locked Harnesses

If the repo already has a locked evaluation path, new families should not silently enroll themselves.

Use explicit allowlists for:

- component-eval eligibility
- local-extractor eligibility
- other locked harnesses with stronger preregistration constraints

The pattern in this repo is simple:

- a new family can be runner-eligible
- that does not imply component-eval-eligible
- that does not imply local-extractor-eligible

This lets the benchmark grow without accidentally contaminating a previously locked comparison.

## 7. Artifact Rules

Every preregistered run should produce artifacts that let a later reader reconstruct the decision:

- run JSON with per-policy summaries, per-template summaries, traces, and comparison blocks
- metrics CSV with both summary rows and preregistered comparison rows
- stable paths committed or otherwise archived before the writeup

Good artifact practice:

- read headline deltas and confidence bounds from the saved artifact, not from ad hoc recomputation in the writeup
- compute any allowed post-hoc descriptive tables from saved per-scenario records, not from rerunning a moving target
- keep the file paths short and predictable

## 8. Worked Example: Adversarial Upstream Noise

The current family shows the full template in one place.

Inputs:

- preregistration: `docs/adversarial_upstream_noise_preregistration.md`
- headline artifacts:
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed_metrics.csv`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout_metrics.csv`
- result readout: `docs/adversarial_upstream_noise_results.md`

Preregistered decision structure:

- five mechanisms
- mixed split as headline
- heldout split as robustness only
- mechanism win requires both `delta >= 0.10` and `LCB > 0`
- special surprise-lane rule if CQ loses only `temporal_skew` while clearing the four dedicated component lanes

Observed result:

- CQ wins `retraction`, `witness_conflict`, `scope_narrowing`, and `pending_competition`
- CQ loses only `temporal_skew`
- heldout does not reverse any direction
- the result is therefore the preregistered Bucket D surprise lane

Methodological value of this example:

- it shows a benchmark that can support CQ while still exposing a named weakness
- it demonstrates that the special-case follow-up was committed before the run, not invented after disappointment
- it shows how ablations and family-level framing can coexist without turning every result into a success story

## 9. Reusable Template Skeleton

Use the following structure for future preregistrations:

1. Scope and invariants
2. Motivation
3. Family contract
4. Mechanisms and hypotheses
5. Run design
6. Primary metric
7. Decision rules
8. Ablation attribution rule
9. Baseline reporting
10. Outcome framing committed pre-run
11. Lock interaction
12. Planned run order

Use the following structure for future result docs:

1. First sentence names the preregistered bucket
2. Audit trail and artifact paths
3. Headline mixed readout
4. Ablation attribution table
5. Held-out direction check
6. Partial-baseline sub-table
7. Writeup direction fixed by the preregistered bucket

## 10. What This Template Does Not Solve

This template improves evaluation discipline. It does not remove all judgment calls.

It does not solve:

- bad mechanism design
- mislabeled scenarios
- poor component quality in noisy-mode pipelines
- overbroad claims that ignore the actual family contract
- polarized mechanism design where every instance of a mechanism yields the same policy outcome (all-or-nothing correctness within mechanism): the template’s paired-bootstrap CI step assumes enough within-mechanism variance for bounds to be inferential; if each scenario repeats the same deterministic outcome, the CI step is descriptive (it confirms the constant delta) rather than a noisy-effect gate, and headline sample size is less informative for that inferential role

Those still require honest benchmark design and honest writing. The template is there to reduce hindsight bias, not to replace scientific judgment.
