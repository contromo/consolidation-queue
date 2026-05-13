# Abstention-Calibrated Memory Governance Results

Outcome: **full support** for the preregistered oracle-only
abstention-calibration axis.

Both the `mixed` and `heldout` `evidence_conflict_spectrum` sweeps pass all
three primary gates: CQ beats `Mem0Lite` on useful abstention for
`conflict_moderate` and `conflict_witness`, and CQ stays non-inferior on the
single harmful bucket over `conflict_zero`, `conflict_mild`, and
`conflict_polluted`.

## Audit Trail

Preregistration:

- `docs/abstention_quality_preregistration.md`
- amendment date: 2026-05-13, before full sweeps
- amendment scope: artifact policy, replay-extension note, outcome precedence

Pre-run artifacts:

| Artifact | Role |
| --- | --- |
| `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_structure_mixed.json` | structure summary |
| `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_structure_heldout.json` | structure summary |
| `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_nondegeneracy_mixed.json` | CQ-vs-`Mem0Lite` probe |
| `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_nondegeneracy_heldout.json` | CQ-vs-`Mem0Lite` probe |

Sweep artifacts:

| Split | Metrics CSV | Manifest | Replay artifact |
| --- | --- | --- | --- |
| `mixed` | `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed_metrics.csv` | `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed_manifest.json` | `data/results/abstention/evidence_conflict_spectrum_oracle_phase2_5_mixed_abstention.json` |
| `heldout` | `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout_metrics.csv` | `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout_manifest.json` | `data/results/abstention/evidence_conflict_spectrum_oracle_phase2_5_heldout_abstention.json` |

The full per-scenario sweep JSONs are not tracked because they are about
`174 MB` each. They are recorded as `regeneratable_only` in the manifests:

| Split | JSON path | Bytes | SHA256 |
| --- | --- | ---: | --- |
| `mixed` | `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed.json` | `182838865` | `afe24e5046948816e7546397eb53a7cdb54a6bb05c1cb36640a07b2a9844bfbd` |
| `heldout` | `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout.json` | `182869137` | `3b7a8f9427f7614fe0e253aabf41e7ce8f1a22c160d0152de949b274dc2b78d9` |

Pre-flight verification:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_abstention tests.test_evidence_conflict_spectrum tests.test_runner_policy_sets tests.test_bootstrap tests.test_metrics tests.test_adversarial_upstream_noise tests.test_component_eval tests.test_local_extractor tests.test_frozen_preregistration tests.test_artifact_manifest -q
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_abstention_replay.py --dry-run
```

Full sweep and explicit replay commands:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner --family evidence_conflict_spectrum --policy-set phase2_5 --template-mix mixed --scenarios 600 --output-json data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed.json --output-csv data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed_metrics.csv
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_abstention_replay.py --inputs data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed.json

PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner --family evidence_conflict_spectrum --policy-set phase2_5 --template-mix heldout --scenarios 600 --output-json data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout.json --output-csv data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout_metrics.csv
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_abstention_replay.py --inputs data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout.json
```

## Section A: Recorded-Artifact Replay

These rows are descriptive, partial, and post-hoc. They do not carry the
primary Phase 2.6 claim.

| Surface | Split | CQ-vs-`Mem0Lite` row | Delta | LCB | Count | Read |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `adversarial_upstream_noise` | `mixed` | useful `adversarial_witness_conflict` | `+1.00` | `+1.00` | `60` | supports witness-conflict abstention |
| `adversarial_upstream_noise` | `heldout` | useful `adversarial_witness_conflict` | `+1.00` | `+1.00` | `60` | same direction |
| `adversarial_upstream_noise` | `mixed` | harmful `adversarial_temporal_skew` | `+1.00` | `+1.00` | `60` | dated-evidence weakness appears as harmful abstention |
| `adversarial_upstream_noise` | `heldout` | harmful `adversarial_temporal_skew` | `+1.00` | `+1.00` | `60` | same weakness |
| `mechanism_diverse_heldout` | `frozen` | useful `false_corroboration_adversarial_mixed_source` | `+0.00` | `+0.00` | `1` | descriptive only |
| `mechanism_diverse_heldout` | `frozen` | harmful poisoning/drift rows | `+0.00` | `+0.00` | `1` each | descriptive only |

The adversarial replay is consistent with
`docs/adversarial_upstream_noise_results.md`: CQ's unique advantage versus
`Mem0Lite`-style baselines is witness-conflict abstention, while
`temporal_skew` remains the named weakness.

## Section B: Pre-Run Spectrum Results

Primary gate rows are CQ vs `Mem0Lite`. Useful-side rows require delta
`>= 0.10` and one-sided 95% LCB `> 0`. The harmful row is one single bucket
over `conflict_zero`, `conflict_mild`, and `conflict_polluted`; it requires
delta `<= 0.05` and one-sided 95% UCB `<= 0.05`.

| Split | Primary row | Delta | LCB | UCB | Count | Gate |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `mixed` | useful `conflict_moderate` | `+1.00` | `+1.00` | `+1.00` | `120` | pass |
| `mixed` | useful `conflict_witness` | `+1.00` | `+1.00` | `+1.00` | `120` | pass |
| `mixed` | harmful bucket | `+0.00` | `+0.00` | `+0.00` | n/a | pass |
| `heldout` | useful `conflict_moderate` | `+1.00` | `+1.00` | `+1.00` | `120` | pass |
| `heldout` | useful `conflict_witness` | `+1.00` | `+1.00` | `+1.00` | `120` | pass |
| `heldout` | harmful bucket | `+0.00` | `+0.00` | `+0.00` | n/a | pass |

Secondary replay rows match the preregistered predictions on both `mixed` and
`heldout`:

| Comparator | Moderate useful delta/LCB/UCB | Witness useful delta/LCB/UCB | Harmful mechanism rows |
| --- | --- | --- | --- |
| CQ vs Reflection | `+1.00 / +1.00 / +1.00` | `+1.00 / +1.00 / +1.00` | all `+0.00 / +0.00 / +0.00` |
| CQ vs `cq_no_contestation_demotion` | `+1.00 / +1.00 / +1.00` | `+1.00 / +1.00 / +1.00` | all `+0.00 / +0.00 / +0.00` |
| CQ vs `cq_no_wider_scope_pending_override` | `+0.00 / +0.00 / +0.00` | `+0.00 / +0.00 / +0.00` | all `+0.00 / +0.00 / +0.00` |
| CQ vs `cq_no_pending_lookup_use` | `+0.00 / +0.00 / +0.00` | `+0.00 / +0.00 / +0.00` | all `+0.00 / +0.00 / +0.00` |
| CQ vs `cq_no_source_independence_gate` | `+0.00 / +0.00 / +0.00` | `+0.00 / +0.00 / +0.00` | all `+0.00 / +0.00 / +0.00` |

The secondary harmful entries are per-mechanism descriptive rows from
`pairwise_abstention_comparisons`, not the primary harmful bucket gate.

## Outcome Classification

Applying the locked precedence:

1. Unsupported does not fire: harmful bucket delta and UCB are `+0.00` on both
   splits.
2. Benchmark-axis only does not fire: both useful mechanisms pass on `mixed`.
3. Narrow witness-only does not fire: `conflict_moderate` also passes on
   `mixed`.
4. Narrow support does not fire: all primary gates pass on `heldout`.
5. The result is therefore **full support**.

This strengthens the witness-conflict finding into a broader
abstention-calibration axis under the designed oracle assay.

## Held-Out Direction Check

No primary mechanism reverses between `mixed` and `heldout`. The useful
moderate and witness deltas remain `+1.00`, and the harmful bucket remains
`+0.00`.

The secondary rows also do not reverse: CQ continues to separate from
Reflection and `cq_no_contestation_demotion` on the two useful mechanisms, and
ties the other named ablations on this assay.

## Limits And Forbidden Upgrades

- This is oracle-only. It does not unlock Phase 4 noisy policy comparison.
- The Phase 3 component gate remains locked (`policy_comparison_unlocked=false`).
- `evidence_conflict_spectrum` is a designed mechanism assay along the
  abstention axis. It is not external validation, noisy transfer evidence, or a
  LongMemEval result.
- The result does not repair the `adversarial_temporal_skew` weakness. That
  remains reserved for the separate `CQDatedContestation` follow-up.
- No claim here retrofits the Phase 2.5 frozen contract or the original
  `adversarial_upstream_noise` headline artifact.
