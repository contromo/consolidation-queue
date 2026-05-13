# Abstention-Calibrated Memory Governance Preregistration

## Scope And Invariants

This is a Phase 2.6 oracle-only benchmark-strengthening step. It does not
reopen the Phase 2.5 frozen contract, the Phase 3 component gate, or Phase 4
noisy policy comparison. No policy thresholds, storage substrate, extractor
logic, or CQ policy behavior change.

The claim is **abstention-calibrated behavior**: CQ should abstain more than
`Mem0Lite` when evidence is genuinely conflicted, while remaining non-inferior
on commit-required cases. This is not a claim that the policy emits an explicit
reasoned abstention rationale.

## Metric Definitions

The abstention predicate is pinned to the shared runner/replay helper
`cq/eval/abstention.py::abstained_from_trace`:

```python
abstained = not asserted_ids and not list(getattr(probe_trace, "resolved_candidate_ids", []))
```

Definitions:

- `useful_abstention_rate`: abstain rate on scenarios with
  `abstention_ok=True`.
- `harmful_abstention_rate`: abstain rate on scenarios with
  `commit_required=True`.
- gray-zone scenarios, where both labels are false, are excluded from both
  primary denominators.
- bucket rates are unweighted means of per-mechanism rates, not pooled rates.
- Brier is omitted from primary reporting because under deterministic hard
  decisions it is equivalent to `1 - decision_accuracy`.

Bootstrap:

- stratified paired bootstrap by mechanism
- resample scenario pairs within mechanism with policy pairing preserved
- recompute per-mechanism rates per resample
- recompute unweighted bucket rates from those mechanism rates
- report one-sided 95% LCB for useful deltas and one-sided 95% UCB for harmful
  deltas

At about `120` scenarios per mechanism in the full `600`-scenario sweeps, the
gate is calibrated for deltas of at least `0.10`; an LCB failure may reflect
sample size as well as effect size.

## Section A: Recorded-Artifact Replay

This section is partial post-hoc evidence. The witness-conflict abstention cell
is already public in `docs/adversarial_upstream_noise_results.md`; replay rows
are descriptive and do not carry the primary claim.

Replay inputs:

- `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed.json`
- `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout.json`
- `data/runs/mechanism_diverse_heldout_oracle_frozen_phase2_5.json`

Preflight confirmed each input preserves:

- `policies[*].scenarios[*].question_traces[*].resolved_candidate_ids`
- `policies[*].scenarios[*].store_snapshot`
- `policies[*].scenarios[*].scenario.expected_lifecycle`

Intent mapping:

| Family / template | `abstention_ok` | `commit_required` | Role |
| --- | --- | --- | --- |
| `adversarial_witness_conflict` | true | false | useful abstention |
| other `adversarial_upstream_noise` mechanisms | false | true | harmful-abstention denominator |
| `false_corroboration_adversarial_mixed_source` | true | false | useful abstention |
| `memory_poisoning_scope_laundered` | false | true | harmful-abstention denominator |
| `preference_drift_long_horizon_corrections` | false | true | harmful-abstention denominator |

The mechanism-diverse replay mapping is owned by
`cq/simulator/scenario_generator.py::MECHANISM_DIVERSE_ABSTENTION_INTENTS`; new
frozen templates must be added there explicitly or replay fails fast.

Descriptive predictions:

| Replay surface | CQ vs `Mem0Lite` useful delta | CQ vs `Mem0Lite` harmful delta | Interpretation |
| --- | ---: | ---: | --- |
| adversarial witness conflict | `+1.00` | n/a | CQ abstains where `Mem0Lite` commits |
| adversarial temporal skew | n/a | `+1.00` expected | CQ's dated-evidence weakness can appear as harmful abstention |
| adversarial retraction / scope / pending | n/a | `0.00` expected | no CQ over-abstention expected |
| mechanism-diverse held-out | mixed / descriptive | mixed / descriptive | replay only; not primary evidence |

## Section B: Pre-Run Spectrum Predictions

The new family is `evidence_conflict_spectrum`.

Pre-Section-B non-degeneracy probe artifacts:

- `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_structure_mixed.json`
- `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_structure_heldout.json`
- `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_nondegeneracy_mixed.json`
- `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_nondegeneracy_heldout.json`

The structure summaries pass the preregistered variance checks for
`conflict_moderate`, `conflict_witness`, and `conflict_polluted`. The
non-degeneracy probes show
`abstain__commit` CQ/`Mem0Lite` action disagreement on both abstain-required
mechanisms (`conflict_moderate`, `conflict_witness`) and `commit__commit` on
the three commit-required mechanisms.

`conflict_witness` is intentionally heavier than `conflict_moderate`: moderate
scenarios vary across `3`, `4`, and `5` conflict candidates, while witness
scenarios vary across `4`, `5`, and `6` conflict candidates. The witness row is
therefore a multi-witness contestation anchor, not a relabeled copy of the
moderate row.

Mechanism intent table:

| Mechanism | Intensity | `abstention_ok` | `commit_required` | Primary role |
| --- | --- | --- | --- | --- |
| `conflict_zero` | `zero` | false | true | harmful bucket |
| `conflict_mild` | `mild` | false | true | harmful bucket |
| `conflict_moderate` | `moderate` | true | false | useful primary mechanism |
| `conflict_witness` | `witness` | true | false | useful primary mechanism |
| `conflict_polluted` | `polluted` | false | true | harmful bucket |

Primary CQ-vs-`Mem0Lite` predictions on `mixed`:

| Row | Predicted delta | Required gate |
| --- | ---: | --- |
| `conflict_moderate` useful abstention | `+1.00` | `delta >= 0.10` and LCB `> 0` |
| `conflict_witness` useful abstention | `+1.00` | `delta >= 0.10` and LCB `> 0` |
| harmful bucket (`zero`, `mild`, `polluted`) | `0.00` | delta `<= 0.05` and UCB `<= 0.05` |

Secondary predictions:

| Comparator | Moderate useful delta | Witness useful delta | Harmful bucket delta |
| --- | ---: | ---: | ---: |
| CQ vs Reflection | `+1.00` | `+1.00` | `0.00` |
| CQ vs `cq_no_contestation_demotion` | `+1.00` | `+1.00` | `0.00` |
| CQ vs `cq_no_wider_scope_pending_override` | `0.00` | `0.00` | `0.00` |
| CQ vs `cq_no_pending_lookup_use` | `0.00` | `0.00` | `0.00` |
| CQ vs `cq_no_source_independence_gate` | `0.00` | `0.00` | `0.00` |

Outcome rules:

- full support: mixed and held-out pass all three primary gates
- narrow witness-only support: `witness` passes but `moderate` fails
- unsupported abstention-axis claim: harmful non-inferiority fails, regardless
  of useful-side performance
- narrow support: mixed passes but held-out fails any primary gate
- benchmark-axis contribution only: both abstain-required mechanisms fail

## Amendment, 2026-05-13: Artifact Policy And Outcome Precedence

This amendment is locked before the full `evidence_conflict_spectrum` sweeps.
It changes artifact handling and reporting precedence only; it does not change
scenario contracts, policy thresholds, storage substrate, extractor logic, or
CQ policy behavior.

Durable artifact policy:

- small headline-verification artifacts are tracked in git:
  `*_metrics.csv`, structure summaries, non-degeneracy probes, abstention
  replay JSON/CSV files, and `*_manifest.json` files
- per-scenario sweep JSON artifacts over about `5 MB` are not tracked by
  default; they are recorded as `regeneratable_only` unless an actual uploaded
  URI is present
- each manifest records the artifact path, byte size, SHA256, git commit,
  Python version, working-tree status, exact runner command, and
  `archive_status`
- `working_tree_status` is recorded at manifest write time after runner outputs
  have been generated; the preregistration-clean state is established by the
  separate pre-sweep `git status` and pre-flight checks
- the three existing large `adversarial_upstream_noise` JSONs are grandfathered
  and remain tracked; this policy applies prospectively

Replay extension:

- Section B secondary rows may use `pairwise_abstention_comparisons` for CQ vs
  Reflection and CQ vs the four named CQ ablations when those policies are
  present
- the primary gate remains only the CQ-vs-`Mem0Lite`
  `consolidation_queue_vs_mem0_primary_abstention` block
- harmful primary non-inferiority is evaluated only on that block's single
  `harmful_bucket_row` over `conflict_zero`, `conflict_mild`, and
  `conflict_polluted`

Outcome precedence is applied top-to-bottom; first match wins:

1. **Unsupported abstention-axis claim.** The harmful bucket fails on `mixed` or
   `heldout`: CQ-vs-`Mem0Lite` delta `> 0.05` or one-sided 95% UCB `> 0.05`.
2. **Benchmark-axis contribution only.** Precedence 1 does not fire, and both
   `conflict_moderate` and `conflict_witness` useful-side gates fail on
   `mixed`.
3. **Narrow witness-only support.** Precedence 1-2 do not fire, and on `mixed`,
   `conflict_witness` passes while `conflict_moderate` fails. Held-out is
   descriptive and cannot upgrade this bucket.
4. **Narrow support.** Precedence 1-3 do not fire, both useful-side gates pass
   on `mixed`, and any primary gate fails on `heldout`.
5. **Full support.** Precedence 1-4 do not fire; all three primary gates pass on
   both `mixed` and `heldout`.

Full sweeps, to be run only after this preregistration is committed:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner \
  --family evidence_conflict_spectrum --policy-set phase2_5 \
  --template-mix mixed --scenarios 600 \
  --output-json data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed.json \
  --output-csv data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed_metrics.csv

PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner \
  --family evidence_conflict_spectrum --policy-set phase2_5 \
  --template-mix heldout --scenarios 600 \
  --output-json data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout.json \
  --output-csv data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout_metrics.csv
```
