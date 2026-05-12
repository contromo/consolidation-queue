# Adversarial Upstream-Noise Dated Follow-Up Preregistration

Date: 2026-05-12

This note preregisters the post-hoc dated-evidence follow-up triggered by the
headline `adversarial_upstream_noise` result. It does not modify the original
headline preregistration in `docs/adversarial_upstream_noise_preregistration.md`,
and it does not retroactively change the Bucket D read recorded in
`docs/adversarial_upstream_noise_results.md`.

## Trigger

The original preregistration committed a surprise-lane rule:

- if CQ loses only `temporal_skew` while clearing the four dedicated component
  lanes, name the weakness explicitly and evaluate a dated-evidence fix later as
  a separate follow-up

That trigger fired on the headline `phase2_5` mixed artifact:

- wins: `adversarial_retraction_v1`
- wins: `adversarial_witness_conflict_v1`
- loss: `adversarial_temporal_skew_v1`
- wins: `adversarial_scope_narrowing_v1`
- wins: `adversarial_pending_competition_v1`

The follow-up therefore evaluates the named fix that was already committed in
spirit: `CQDatedContestation`.

## Purpose

The follow-up asks a narrow mechanistic question:

- does adding `provenance.observed_at` awareness to CQ's contradiction handling
  recover the dated-evidence failure without rewriting the original headline
  result?

This is a post-hoc mechanism test, not a new headline result and not a retrofit
of the original `phase2_5` policy set.

## Intervention

Add a new CQ variant named `CQDatedContestation`.

Constraints:

- do not modify existing `ConsolidationQueueLite`
- do not change the shared candidate stream, shared substrate, or benchmark
  labels
- do not pollute the original `phase2_5` policy set
- run the follow-up through a separate policy-set path such as a new
  `POLICY_SET_FOLLOWUP`

Expected behavioral change:

- when contradictory evidence competes, use `provenance.observed_at` as an
  explicit signal in the contradiction-handling path so stale contradictors do
  not overrule fresher truth by default

This follow-up is allowed to help only because the original headline result has
already been fixed and written down as a weakness.

## Scope

The follow-up still evaluates the same family:

- family: `adversarial_upstream_noise`
- headline split for the follow-up: `mixed`
- robustness split for the follow-up: `heldout`
- scenario count: `300` per split

The family itself does not change. The intervention is policy-only.

## Run Design

Required code changes before any follow-up run:

1. add `CQDatedContestation` in `cq/memory/consolidation_queue.py`
2. wire it into a follow-up policy set that leaves `phase2_5` untouched
3. add a targeted regression test pinning the expected behavior on
   `adversarial_temporal_skew_v1`

Until those land, the intended CLI surface is not available end-to-end: the runner’s policy-set allowlist (for example `POLICY_SET_CHOICES` / `cq.eval.runner` wiring) currently includes only the headline sets (`default`, `phase2_5`), not `followup`. The commands in the next section are the preregistered contract; they will fail or reject `--policy-set followup` until `CQDatedContestation`, the new policy set, and the regression test are implemented.

Required follow-up runs after those code changes land:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner --family adversarial_upstream_noise --policy-set followup --template-mix mixed --scenarios 300 --output-json data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_mixed.json --output-csv data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_mixed_metrics.csv
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner --family adversarial_upstream_noise --policy-set followup --template-mix heldout --scenarios 300 --output-json data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_heldout.json --output-csv data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_heldout_metrics.csv
```

## Primary Readout

The follow-up primary readout is still scenario-level `answer_correctness`, with
the same fixed-seed paired bootstrap helper used for the headline family.

Primary row of interest:

- `CQDatedContestation` vs `ReflectionEagerWriteLite` on
  `adversarial_temporal_skew_v1`

Secondary row of interest:

- `CQDatedContestation` vs `ConsolidationQueueLite` on
  `adversarial_temporal_skew_v1`

The secondary row is descriptive. The original family gate remains anchored to
the headline CQ policy.

## Success Criteria

The follow-up is successful if all of the following hold on `mixed`:

1. `CQDatedContestation` clears the original mechanism win rule against
   `ReflectionEagerWriteLite` on `adversarial_temporal_skew_v1`
2. `CQDatedContestation` improves on `ConsolidationQueueLite` on
   `adversarial_temporal_skew_v1`
3. the four originally won mechanisms do not reverse direction under the
   follow-up policy set

The held-out `_v2` temporal-skew row remains a robustness check rather than the
headline decision row.

## Failure Criteria

The follow-up fails if any of the following occur:

- `CQDatedContestation` still loses `adversarial_temporal_skew_v1`
- the dated-evidence fix rescues `temporal_skew` only by breaking one or more of
  the four mechanisms CQ previously won
- the change improves only on `heldout` but not on the `mixed` headline row

If the follow-up fails, the correct writeup is still that the original family
exposed a real CQ weakness on dated contradictory evidence.

## Writeup Posture

Allowed claims if the follow-up succeeds:

- the original family correctly predicted a CQ weakness
- the weakness was specifically dated-evidence handling
- a named post-hoc fix (`CQDatedContestation`) measurably repairs that lane

Forbidden claims:

- do not rewrite the original headline bucket
- do not present the follow-up as if it were preregistered before the original
  runs
- do not merge the follow-up result into the original `phase2_5` artifact set

The correct framing is:

- original headline result: Bucket D weakness
- follow-up result: named post-hoc repair attempt on that weakness
