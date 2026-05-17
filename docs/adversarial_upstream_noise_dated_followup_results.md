# Adversarial Upstream-Noise Dated Follow-Up Results

Date: 2026-05-16

Outcome: **partial preregistered success**. `CQDatedContestation` repairs base
`ConsolidationQueueLite`'s failure on `adversarial_temporal_skew` and
preserves the four originally won mechanisms, but **does not clear the
preregistered primary success criterion** (a `CQDatedContestation` vs
`ReflectionEagerWriteLite` win under the family's mechanism win rule on
`adversarial_temporal_skew_v1`) because both policies land at
`answer_correctness=1.00` on this lane.

This file records the result of the preregistered `CQDatedContestation`
follow-up triggered by the 2026-05-15 `adversarial_upstream_noise` headline. It
does not edit, replace, or rewrite the original headline result in
`docs/adversarial_upstream_noise_results.md` or the original
`phase2_5` artifact set.

For scope, intervention, success/failure criteria, and writeup posture, read
`docs/adversarial_upstream_noise_dated_followup_preregistration.md` first.
This doc reports only the observed outcome and ties it to that preregistration.

## 1. Primary Readout — `temporal_skew`

Per the preregistration's "Primary Readout" section, the headline comparison
is `CQDatedContestation` vs `ReflectionEagerWriteLite` on
`adversarial_temporal_skew_v1`. The CQDated-vs-base-CQ row is the secondary
descriptive comparison. Numbers below are read directly from the tracked
metrics CSVs (paths in §6).

### Per-policy `answer_correctness`

| Policy | `mixed` (`temporal_skew_v1`) | `heldout` (`temporal_skew_v2`) |
| --- | ---: | ---: |
| `reflection_eager_write_lite` | `1.00` | `1.00` |
| `cq_dated_contestation` | `1.00` | `1.00` |
| `consolidation_queue_lite` (base) | `0.00` | `0.00` |
| `mem0_lite` | `0.00` | `0.00` |

### Deltas

| Comparison | `mixed` delta | `heldout` delta | Role |
| --- | ---: | ---: | --- |
| `cq_dated_contestation` − `reflection_eager_write_lite` | `+0.00` | `+0.00` | **Preregistered primary** |
| `cq_dated_contestation` − `consolidation_queue_lite` | `+1.00` | `+1.00` | Secondary descriptive |

The fixed-seed paired bootstrap helper is not computed on the primary row
because every per-scenario `(cq_dated_contestation, reflection_eager_write_lite)`
pair lands at `(1, 1)` on this lane, making the LCB trivially `0.0` and the
delta trivially `0.0`. The point-estimate alone is sufficient to determine
that the family mechanism win rule (point-estimate delta `>= 0.10` AND
one-sided 95% LCB `> 0`, per `docs/adversarial_upstream_noise_preregistration.md`)
is not cleared.

### Side notes from the same CSV rows

- Base CQ records `false_assertion_rate=0.00` on both temporal-skew rows. The
  mechanism by which base CQ "loses" `temporal_skew` is abstention (no usable
  durable answer) rather than asserting a stale answer; `CQDatedContestation`
  upgrades that to a correct answer from the fresher evidence.
- `mem0_lite` records `false_assertion_rate=1.00` and
  `stale_evidence_promotion_rate=1.00` on both temporal-skew rows — the
  documented Mem0-family weakness on dated contradiction.
- `reflection_eager_write_lite` already records `correctness=1.00` because
  eager-overwrite of the older durable with the fresher contradiction
  accidentally lines up with the temporal truth in this family. The original
  `adversarial_upstream_noise` headline locked this as the surprise lane:
  Reflection has always won `temporal_skew` against base CQ in this family,
  and the dated fix raises CQ to parity rather than past it.

## 2. Preregistered Success Criteria

The preregistration lists three success criteria for the follow-up to be
considered successful on `mixed`. Observed outcomes:

| # | Criterion | Result |
| --- | --- | --- |
| 1 | `CQDatedContestation` clears the original mechanism win rule against `ReflectionEagerWriteLite` on `adversarial_temporal_skew_v1` | **NOT MET** — point-estimate delta `+0.00`, fails `>= 0.10` |
| 2 | `CQDatedContestation` improves on `ConsolidationQueueLite` on `adversarial_temporal_skew_v1` | **MET** — point-estimate delta `+1.00` |
| 3 | The four originally won mechanisms do not reverse direction under the follow-up policy set | **MET** — see §3 below |

Two of three criteria are met. The primary criterion is not met because
Reflection's eager-overwrite already lands `temporal_skew` at the ceiling, so
there is no CQ-vs-Reflection separation room on this lane. The
preregistration's "Failure Criteria" section names "`CQDatedContestation`
still loses `adversarial_temporal_skew_v1`" as one failure mode; the observed
result is a tie rather than a loss, which sits in the gray zone between the
preregistration's explicit success and failure rules.

## 3. Four-Mechanism Preservation

Criterion 3 from §2 requires that the four originally won mechanisms do not
reverse direction under the follow-up policy set. Observed
`answer_correctness` for `CQDatedContestation` on both splits:

| Mechanism | `mixed` (`v1`) | `heldout` (`v2`) |
| --- | ---: | ---: |
| `adversarial_retraction` | `1.00` | `1.00` |
| `adversarial_witness_conflict` | `1.00` | `1.00` |
| `adversarial_scope_narrowing` | `1.00` | `1.00` |
| `adversarial_pending_competition` | `1.00` | `1.00` |

In addition, the mechanism-aligned outcome rates each match base CQ:

- `retraction_demotion_rate=1.00` on retraction.
- `narrow_scope_override_success_rate=1.00` on scope narrowing.
- `pending_competition_resolution_rate=1.00` on pending competition.

No mechanism reverses direction. Criterion 3 satisfied on both splits.

## 4. Mapping To The Plan §4 CQDated Matrix

The approved execution plan §4 CQDated × writeup posture matrix had three
rows: "Repairs temporal skew and preserves four won mechanisms" (clean
repair), "Repairs temporal skew but reverses another mechanism" (constraint
discovery), and "Does not repair temporal skew" (unresolved weakness). The
observed outcome sits between rows 1 and 3:

- "Repair" interpreted narrowly as "base CQ failure mode fixed": **achieved**
  (CQDated `correctness=1.00` versus base CQ `0.00`).
- "Repair" interpreted as the preregistration's primary success criterion (a
  CQDated-vs-Reflection win on this lane): **not achieved**.

The plan §4 matrix glossed over this distinction. The honest framing the
writeup should use is the one stated in this doc's header: partial
preregistered success, with base CQ's failure mode repaired and the four
mechanisms preserved, but the preregistered Reflection win criterion not
cleared. The reframed-contribution claim that "the methodology supports a
clean post-hoc mechanism repair" is therefore partially supported: the
post-hoc repair works for the named base-CQ weakness, but it does not
manufacture a CQ-vs-Reflection separation where the eager-write baseline
already gets the lane right.

## 5. Writeup Posture

### Allowed claims (from the preregistration, narrowed to what the data supports)
- The original `adversarial_upstream_noise` family correctly predicted a CQ
  weakness on dated contradictory evidence.
- The weakness was specifically dated-evidence handling, not a broader CQ
  defect.
- A named post-hoc CQ variant (`CQDatedContestation`) measurably repairs base
  CQ's failure mode on that lane and preserves the four originally won
  mechanisms on both `mixed` and `heldout`.

### Claims that are NOT supported by this follow-up
- That `CQDatedContestation` clears the preregistered Reflection win
  criterion on `temporal_skew`. Both policies record `correctness=1.00`;
  delta is `0.00`.
- That `CQDatedContestation` produces a noisy-mode repair or any LongMemEval
  transfer.
- That the dated fix would manufacture a CQ-vs-Reflection win on any lane
  the eager-write baseline already gets right by accident-of-mechanism.

### Forbidden claims (from the preregistration)
- Do not rewrite the original headline Bucket D result.
- Do not present the follow-up as preregistered before the original headline
  runs.
- Do not merge `CQDatedContestation` into the original `phase2_5` artifact set
  or into any noisy-mode headline.
- Do not claim transfer to LongMemEval or any external benchmark.

## 6. Artifacts

Tracked (in this PR):

| Path | SHA256 | Bytes |
| --- | --- | ---: |
| `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_mixed_metrics.csv` | `8728e0a7ea12e2e23c3fdfb39a159c1405824f8cdbf2ec661ead0340e39eb14a` | 18400 |
| `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_heldout_metrics.csv` | `1ef01d3d7ea8becb4b6d88d3fcb895511b149f0fde557736e6ad35c960e4c7ab` | 18433 |

Regeneratable (large run JSONs, not tracked per the artifact policy; SHA and
size verified at write time on 2026-05-16):

| Path | SHA256 | Bytes | Archive status |
| --- | --- | ---: | --- |
| `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_mixed.json` | `a52e27760d9c1ba01052de00307fa067c8c44f09addd278aec55a2ccef44edfc` | 85264971 | `regeneratable_only` |
| `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_heldout.json` | `65e424337af49b3e869b97daf27b704564c43fb66b549b4b6a0d43197f59cfd9` | 86387118 | `regeneratable_only` |

Implementation (already on `main`):

- `cq/memory/consolidation_queue.py` — `CQDatedContestation` subclass
  (PR [#40](https://github.com/contromo/consolidation-queue/pull/40))
- `cq/eval/runner.py` — `POLICY_SET_FOLLOWUP` allowlist
  (PR [#40](https://github.com/contromo/consolidation-queue/pull/40))

## 7. Reproduction Commands

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner \
  --family adversarial_upstream_noise --policy-set followup \
  --template-mix mixed --scenarios 300 \
  --output-json data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_mixed.json \
  --output-csv data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_mixed_metrics.csv

PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.runner \
  --family adversarial_upstream_noise --policy-set followup \
  --template-mix heldout --scenarios 300 \
  --output-json data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_heldout.json \
  --output-csv data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_heldout_metrics.csv
```

The runs use oracle mode; no 32B model or component-eval artifacts are
required. They executed deterministically on 2026-05-16 with the CSV SHAs
recorded above.

## 8. Limits

- This is a post-hoc, preregistered follow-up. It does not alter the
  2026-05-15 `adversarial_upstream_noise` headline Bucket D result.
- The clean repair holds in oracle mode. The follow-up does not claim a
  noisy-mode repair of `temporal_skew`, does not claim transfer to
  LongMemEval, and does not claim that `CQDatedContestation` would repair the
  Phase 4 null rows.
- The four-mechanism preservation check uses scenario-level
  `answer_correctness`. Mechanism-aligned outcome columns
  (`retraction_demotion_rate`, `narrow_scope_override_success_rate`,
  `pending_competition_resolution_rate`) also match base CQ at `1.00`, but the
  preregistered direction check is on `answer_correctness`.
- The fixed-seed paired bootstrap helper referenced in the preregistration
  primary readout is not exercised here because every comparison cell lands at
  a deterministic 0/1 outcome on these mechanisms; a bootstrap is uninformative
  for unanimous rows and so is omitted to avoid implying CI precision the data
  does not support.
