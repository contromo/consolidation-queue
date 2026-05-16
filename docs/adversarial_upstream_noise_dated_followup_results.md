# Adversarial Upstream-Noise Dated Follow-Up Results

Date: 2026-05-16

Outcome: **clean repair under the preregistered follow-up**.

This file records the result of the preregistered `CQDatedContestation`
follow-up triggered by the 2026-05-15 `adversarial_upstream_noise` headline. It
does not edit, replace, or rewrite the original headline result in
`docs/adversarial_upstream_noise_results.md` or the original
`phase2_5` artifact set.

For scope, intervention, success/failure criteria, and writeup posture, read
`docs/adversarial_upstream_noise_dated_followup_preregistration.md` first. This
doc reports only the observed outcome and ties it to that preregistration.

## 1. Primary Readout — `temporal_skew`

The headline row of interest is `CQDatedContestation` versus
`ConsolidationQueueLite` on `adversarial_temporal_skew_v{1,2}`. Numbers below
are read directly from the tracked metrics CSVs (paths in §5).

| Policy | `mixed` (`temporal_skew_v1`) `answer_correctness` | `heldout` (`temporal_skew_v2`) `answer_correctness` |
| --- | ---: | ---: |
| `consolidation_queue_lite` (base) | `0.00` | `0.00` |
| `cq_dated_contestation` | `1.00` | `1.00` |
| `reflection_eager_write_lite` | `1.00` | `1.00` |
| `mem0_lite` | `0.00` | `0.00` |

Side notes from the same CSV rows:

- Base CQ records `false_assertion_rate=0.00` on both temporal-skew rows. The
  mechanism by which base CQ "loses" `temporal_skew` is abstention (no usable
  durable answer) rather than asserting a stale answer; `CQDatedContestation`
  upgrades that to a correct answer from the fresher evidence.
- `mem0_lite` records `false_assertion_rate=1.00` and
  `stale_evidence_promotion_rate=1.00` on both temporal-skew rows — the
  documented Mem0-family weakness on dated contradiction.
- `reflection_eager_write_lite` happens to win `temporal_skew` because
  eager-overwrite of the older durable with the fresher contradiction
  accidentally lines up with the temporal truth in this family. The original
  `adversarial_upstream_noise` headline locked this as the surprise lane.

## 2. Four-Mechanism Preservation

The preregistration's success criterion (§5 of
`docs/adversarial_upstream_noise_dated_followup_preregistration.md`) requires
that the four originally won mechanisms do not reverse direction under the
follow-up policy set. Observed `answer_correctness` for `CQDatedContestation`
on both splits:

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

No mechanism reverses direction. The preregistered success criterion is
satisfied on both splits.

## 3. Mapping To The Plan §4 CQDated Matrix

From the approved execution plan §4 CQDated × writeup posture matrix:

> **Repairs temporal skew and preserves four won mechanisms:** claim a named
> post-hoc repair of the dated-evidence weakness. Under the reframed
> contribution, this also becomes evidence that the methodology supports a
> clean post-hoc mechanism repair without rewriting the headline.

The observed outcome on both splits matches this row exactly. The follow-up
demonstrates the methodology supports a preregistered post-hoc mechanism
repair without retrofitting the original `phase2_5` headline.

## 4. Writeup Posture

### Allowed claims (from the preregistration)
- The original `adversarial_upstream_noise` family correctly predicted a CQ
  weakness on dated contradictory evidence.
- The weakness was specifically dated-evidence handling, not a broader CQ
  defect.
- A named post-hoc fix (`CQDatedContestation`) measurably repairs that lane on
  both mixed and held-out templates without reversing the four originally won
  mechanisms.

### Forbidden claims (from the preregistration)
- Do not rewrite the original headline Bucket D result.
- Do not present the follow-up as preregistered before the original headline
  runs.
- Do not merge `CQDatedContestation` into the original `phase2_5` artifact set
  or into any noisy-mode headline.
- Do not claim transfer to LongMemEval or any external benchmark.

## 5. Artifacts

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

## 6. Reproduction Commands

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

## 7. Limits

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
