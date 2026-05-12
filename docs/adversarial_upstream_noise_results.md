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
- Artifact bulk: the three headline JSON files together are on the order of ~193 MB (per-scenario traces and store snapshots); the paired metrics CSVs are tiny (~37 KB) and suffice for the preregistered headline read. The JSONs are reproducibility- and inspection-oriented, not gate-deciding. Before more families or follow-up runs land similar blobs in git, decide a storage policy (for example Git LFS, object storage with checksums, or committing manifests plus archiving JSON separately) so clone weight does not compound.
- Dirty-sample inspection confirmed the preregistered structure on one `mixed` scenario per mechanism:
  - retraction includes explicit `contradicts` links from the retraction candidate
  - witness conflict uses four distinct `source_id` values and `abstention_ok=True`
  - temporal skew includes materially older `provenance.observed_at` on the stale contradictor
  - scope narrowing uses distinct workspace and project scope-key shapes
  - pending competition marks both candidates in `should_not_promote_candidate_ids`

All CQ-versus-Reflection and Mem0-versus-Reflection deltas below are read directly from the persisted `pairwise_template_id_comparisons` blocks in the two `phase2_5` JSON artifacts. The ablation table is computed from the saved per-scenario `answer_correctness` values in the mixed `phase2_5` artifact.

Polarized deltas (±1.00 for both point estimates and LCBs) reflect the family’s construction: for each mechanism, a given policy either always succeeds or always fails across scenarios, so paired bootstrap on zero-variance inputs returns the constant. The bootstrap LCBs equal point estimates on this run because per-mechanism correctness has zero per-scenario variance; the CI rule remains load-bearing for future families with mixed within-mechanism outcomes.

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

Each cell shows the mean mixed-split drop in scenario-level `answer_correctness`, computed as `full_CQ_correctness - ablation_correctness` over the 60 scenarios for that mechanism, followed by the preregistered label. Interpretation is sharper if you separate **direct mechanism handling** (the ablated component breaks the adversarial structure in the contestation path) from **downstream answer-surfacing** (contestation still behaves correctly, but the final answer depends on another stage—in this family, pending lookup—to propose the candidate that actually answers the turn).

| Mechanism | `CQNoContestationDemotion` | `CQNoWiderScopePendingOverride` | `CQNoPendingLookupUse` | `CQNoSourceIndependenceGate` |
| --- | --- | --- | --- | --- |
| `adversarial_retraction_v1` | `1.00 carries` | `0.00 inert` | `1.00 carries` | `0.00 inert` |
| `adversarial_witness_conflict_v1` | `1.00 carries` | `0.00 inert` | `0.00 inert` | `1.00 carries` |
| `adversarial_temporal_skew_v1` | `0.00 inert` | `0.00 inert` | `0.00 inert` | `0.00 inert` |
| `adversarial_scope_narrowing_v1` | `0.00 inert` | `1.00 carries` | `0.00 inert` | `0.00 inert` |
| `adversarial_pending_competition_v1` | `0.00 inert` | `0.00 inert` | `1.00 carries` | `0.00 inert` |

This is mostly aligned with the preregistered mechanism guesses. On `adversarial_retraction_v1`, the composition story is tighter than “an extra dependency”: after retraction, CQ correctly demotes the wrong durable via contestation, but the retraction candidate that should surface has strength below the `WORLD_FACT` threshold (for example 0.62 vs 0.85). Pending lookup is what proposes that candidate so the turn still gets a usable memory answer; without it, the honest outcome is “no usable memory” even though contestation did the right thing. The `CQNoPendingLookupUse` cell therefore marks **carries via downstream answer-surfacing**, not a failure of retraction mechanism logic in isolation.

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

Against Reflection, `Mem0Lite` ties on `witness_conflict` (delta 0), loses `temporal_skew`, and wins `retraction`, `scope_narrowing`, and `pending_competition` with the same +1.00 deltas as CQ on those three rows. The honest baseline comparison is therefore: among the policies tested here, CQ’s distinct advantage on this family is **abstention under witness conflict** (Mem0Lite does not replicate that win). The other three headline wins are achievable by simpler eager-then-update policies at Mem0Lite parity. Reserve a broad “CQ governs adversarial upstream noise” paper-level framing for a successful dated-evidence follow-up (`CQDatedContestation`); until then, the defensible unique claim versus partial baselines is the witness-conflict lane.

## Other Preregistered Headline Run

The preregistered `default` mixed run also landed and is preserved in the tracked artifact set. It is not the gate artifact, but it reproduces the same aggregate CQ-versus-Reflection separation at the policy-set default surface:

- `reflection_eager_write_lite` mixed `answer_correctness`: `0.20`
- `consolidation_queue_lite` mixed `answer_correctness`: `0.80`

## Writeup Direction

The writeup direction is now fixed by Bucket D:

- keep the headline result accurate at the mechanism-count level (CQ clears four of five lanes on this family and misses the dated-evidence lane), while foregrounding that **unique vs Mem0Lite-style baselines** is primarily **witness-conflict abstention**; the other three wins are not CQ-exclusive among tested baselines
- do not retrofit the headline `phase2_5` result
- treat `temporal_skew` as the preregistered named weakness
- evaluate the named post-hoc fix separately through `CQDatedContestation`; a stronger family-wide “CQ governs upstream noise” claim is appropriate in a paper mainly if that follow-up succeeds

That follow-up is preregistered in `docs/adversarial_upstream_noise_dated_followup_preregistration.md`. The original headline result in this document remains the authoritative preregistered read regardless of whether the follow-up succeeds.
