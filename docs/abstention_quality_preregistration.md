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
