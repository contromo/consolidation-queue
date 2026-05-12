# Adversarial Upstream-Noise Results

Bucket D: on the preregistered `mixed` `phase2_5` artifact, CQ loses only `temporal_skew` while clearing the four dedicated component lanes, so this family resolves as the dated-evidence surprise lane rather than a generic family-wide win.

## Audit Trail

- Original preregistration: `docs/adversarial_upstream_noise_preregistration.md`
- Tracked headline artifacts:
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_default_mixed.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_default_mixed_metrics.csv`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed_metrics.csv`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout_metrics.csv`
- Focused pre-flight bundle:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_adversarial_upstream_noise tests.test_bootstrap tests.test_cq_ablations tests.test_runner_policy_sets tests.test_metrics -q`
- Dirty-sample inspection confirmed the preregistered structure on one `mixed` scenario per mechanism:
  - retraction includes explicit `contradicts` links from the retraction candidate
  - witness conflict uses four distinct `source_id` values and `abstention_ok=True`
  - temporal skew includes materially older `provenance.observed_at` on the stale contradictor
  - scope narrowing uses distinct workspace and project scope-key shapes
  - pending competition marks both candidates in `should_not_promote_candidate_ids`

All CQ-versus-Reflection and Mem0-versus-Reflection deltas below are read directly from the persisted `pairwise_template_id_comparisons` blocks in the two `phase2_5` JSON artifacts. The ablation table is computed from the saved per-scenario `answer_correctness` values in the mixed `phase2_5` artifact.

## Mixed Headline Readout

The preregistered mixed headline gate is satisfied on four of the five mechanisms. The only failed mechanism is `adversarial_temporal_skew_v1`, exactly the preregistered surprise lane.

| Mechanism | Mixed CQ-Reflection delta | Mixed one-sided 95% LCB | Mixed win | Heldout CQ-Reflection delta | Heldout one-sided 95% LCB | Heldout win | Direction reversal |
| --- | ---: | ---: | --- | ---: | ---: | --- | --- |
| `adversarial_retraction_v1` | 1.00 | 1.00 | yes | 1.00 | 1.00 | yes | no |
| `adversarial_witness_conflict_v1` | 1.00 | 1.00 | yes | 1.00 | 1.00 | yes | no |
| `adversarial_temporal_skew_v1` | -1.00 | -1.00 | no | -1.00 | -1.00 | no | no |
| `adversarial_scope_narrowing_v1` | 1.00 | 1.00 | yes | 1.00 | 1.00 | yes | no |
| `adversarial_pending_competition_v1` | 1.00 | 1.00 | yes | 1.00 | 1.00 | yes | no |

Family decision:

- CQ clears the preregistered mechanism win rule on `4 / 5` mixed mechanisms.
- The only failed row is `adversarial_temporal_skew_v1`.
- Because CQ also clears the four dedicated component lanes (`retraction`, `witness_conflict`, `scope_narrowing`, `pending_competition`), the preregistered Bucket D surprise-lane rule takes precedence over the generic `>= 3` wins framing.

## Ablation Attribution

Each cell shows the mean mixed-split drop in scenario-level `answer_correctness`, computed as `full_CQ_correctness - ablation_correctness` over the 60 scenarios for that mechanism, followed by the preregistered label.

| Mechanism | `CQNoContestationDemotion` | `CQNoWiderScopePendingOverride` | `CQNoPendingLookupUse` | `CQNoSourceIndependenceGate` |
| --- | --- | --- | --- | --- |
| `adversarial_retraction_v1` | `1.00 carries` | `0.00 inert` | `1.00 carries` | `0.00 inert` |
| `adversarial_witness_conflict_v1` | `1.00 carries` | `0.00 inert` | `0.00 inert` | `1.00 carries` |
| `adversarial_temporal_skew_v1` | `0.00 inert` | `0.00 inert` | `0.00 inert` | `0.00 inert` |
| `adversarial_scope_narrowing_v1` | `0.00 inert` | `1.00 carries` | `0.00 inert` | `0.00 inert` |
| `adversarial_pending_competition_v1` | `0.00 inert` | `0.00 inert` | `1.00 carries` | `0.00 inert` |

This is mostly aligned with the preregistered mechanism guesses. The only notable extra dependency is `adversarial_retraction_v1`, which also falls when pending lookup use is disabled; in this family, CQ's retraction win is carried by contestation plus pending fallback rather than contestation alone.

## Held-Out Direction Check

No mechanism reverses direction between `mixed` and `heldout`. The held-out `_v2` rows reproduce the same four wins and the same `temporal_skew` loss, so the robustness split does not weaken or rescue any headline row.

## Mem0 Partial Baseline

`Mem0Lite` remains a partial-baseline sub-table only. It does not contribute to the family gate.

| Mechanism | Mixed Mem0-Reflection delta | Mixed one-sided 95% LCB |
| --- | ---: | ---: |
| `adversarial_retraction_v1` | 1.00 | 1.00 |
| `adversarial_witness_conflict_v1` | 0.00 | 0.00 |
| `adversarial_temporal_skew_v1` | -1.00 | -1.00 |
| `adversarial_scope_narrowing_v1` | 1.00 | 1.00 |
| `adversarial_pending_competition_v1` | 1.00 | 1.00 |

The partial-baseline read is narrower than CQ's headline read: `Mem0Lite` matches Reflection on witness conflict, loses temporal skew, and wins the other three mechanisms.

## Other Preregistered Headline Run

The preregistered `default` mixed run also landed and is preserved in the tracked artifact set. It is not the gate artifact, but it reproduces the same aggregate CQ-versus-Reflection separation at the policy-set default surface:

- `reflection_eager_write_lite` mixed `answer_correctness`: `0.20`
- `consolidation_queue_lite` mixed `answer_correctness`: `0.80`

## Writeup Direction

The writeup direction is now fixed by Bucket D:

- keep the headline result as "CQ governs four adversarial upstream-noise mechanisms and misses the dated-evidence lane"
- do not retrofit the headline `phase2_5` result
- treat `temporal_skew` as the preregistered named weakness
- evaluate the named post-hoc fix separately through `CQDatedContestation`

That follow-up is preregistered in `docs/adversarial_upstream_noise_dated_followup_preregistration.md`. The original headline result in this document remains the authoritative preregistered read regardless of whether the follow-up succeeds.
