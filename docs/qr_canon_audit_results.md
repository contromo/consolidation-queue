# Query-Resolvable Canonical-Id (QR-Canon) Audit Results

Date: 2026-05-17

Status: registered post-hoc audit, completed. Result is methodological, not
a new policy claim. Registration:
`docs/qr_canon_audit_registration.md`.

## Headline

Under shared noisy 32B extraction, clustering-quality component metrics
score perfect or near-perfect on five Phase 4 rows where the policy-facing
canonical-id lookup contract is satisfied for at most 5 percent of
questions. The locked CQR alias function bridges some of the gap on three
rows, but on four rows (including the mechanism-diverse frozen sentinel)
even alias matching scores zero. The audit ships a synthetic
counterexample where B-cubed F1 is `1.00` while QR-canon (exact) is
`0.00` by construction.

The methodological claim:

> Clustering-quality component evaluation is insufficient for memory-policy
> evaluability under shared noisy inputs. Query-resolvable canonical-id
> agreement (QR-canon) is a small, reproducible diagnostic that should be
> reported alongside clustering metrics whenever a memory policy is
> evaluated under shared noisy extraction.

QR-canon is a required diagnostic, not a tuneable pass/fail threshold.

## Artifacts

- `docs/qr_canon_audit_registration.md` — registration
- `data/results/qr_canon_source_table.csv` — one row per question
- `data/results/qr_canon_source_table_manifest.json` — generator manifest
  (input SHAs, regression check, paths relative to repo root)
- `scripts/build_qr_canon_source_table.py` — one-time source-table
  generator (reads gitignored Phase 4 run JSONs)
- `scripts/run_qr_canon_audit.py` — audit (reads only the committed source
  table)
- `data/results/qr_canon_audit_metrics.csv` — per-row audit metrics
- `data/results/qr_canon_audit_manifest.json` — audit manifest
- `tests/test_qr_canon_audit.py` — Wilson math, joint-diagnostic logic,
  synthetic counterexample, generator regression check, no-gitignored-input
  audit reproducibility

## Per-Row QR-Canon Table

Rates are per question. Wilson 95 percent confidence intervals (LCB / UCB)
are computed in `scripts/run_qr_canon_audit.py:_wilson_interval`. The
`B-cubed F1` column is copied per row from
`data/results/noisy_policy_mechanism_audit_evidence.json`'s 32B default
component metrics.

| Row | `n` | QR-canon (exact) | 95% LCB | 95% UCB | QR-canon (normalized) | 95% LCB | 95% UCB | B-cubed F1 | Joint: clustering-floor pass, lookup miss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `forced_contradiction` | `120` | `0.933` | `0.874` | `0.966` | `1.000` | `0.969` | `1.000` | `1.000` | no |
| `preference_drift` | `120` | `0.333` | `0.255` | `0.422` | `0.667` | `0.578` | `0.745` | `0.800` | no |
| `scope_contamination` | `75` | `0.000` | `0.000` | `0.049` | `0.200` | `0.125` | `0.304` | `0.889` | yes |
| `useful_pending_memory` | `60` | `0.000` | `0.000` | `0.060` | `0.000` | `0.000` | `0.060` | `1.000` | yes |
| `memory_poisoning` | `60` | `0.000` | `0.000` | `0.060` | `0.000` | `0.000` | `0.060` | `1.000` | yes |
| `false_corroboration` | `60` | `0.000` | `0.000` | `0.060` | `0.000` | `0.000` | `0.060` | `1.000` | yes |
| `mechanism_diverse_heldout` (frozen) | `4` | `0.000` | `0.000` | `0.490` | `0.000` | `0.000` | `0.490` | `0.952` | yes |
| synthetic counterexample | `1` | `0.000` | `0.000` | `0.793` | `0.000` | `0.000` | `0.793` | `1.000` | yes |

"Joint: clustering-floor pass, lookup miss" marks rows where the existing
Phase 3 noisy-mode B-cubed F1 gate (`>= 0.65`, see PROJECT_PLAN.md
"Noisy-Mode Quality Gates") is satisfied but QR-canon (exact) is below 5
percent. This column is descriptive: it does **not** define a new
QR-canon gate. It exposes the methodological gap.

## Joint B-cubed F1 vs QR-Canon Headline

Five rows pass the existing clustering-quality floor while the
policy-facing exact-lookup rate is below 5 percent:

- `scope_contamination`: B-cubed `0.889`, QR-canon (exact) `0.000`
- `useful_pending_memory`: B-cubed `1.000`, QR-canon (exact) `0.000`
- `memory_poisoning`: B-cubed `1.000`, QR-canon (exact) `0.000`
- `false_corroboration`: B-cubed `1.000`, QR-canon (exact) `0.000`
- `mechanism_diverse_heldout` (frozen): B-cubed `0.952`, QR-canon (exact)
  `0.000`

Three of these have **zero failure examples** in the saved 32B component
artifacts (`useful_pending_memory`, `memory_poisoning`, and
`false_corroboration` apart from `scope_key`). On those rows the
extractor is unimpeachable by clustering-quality measurement and still
the policy lookup contract fails for every question.

## Alias-Normalized QR-Canon Sensitivity

The locked CQR alias function from
`docs/canonical_id_resolution_audit_preregistration.md` Section 6 is used
verbatim via `scripts/run_canonical_id_resolution_audit.py`. It applies
case-fold, dash-normalize, prefix-strip, and a 2-token-overlap rule. It is
explicitly designed to permit benign normalization while rejecting
cross-mechanism slot remapping.

The sensitivity behavior splits cleanly into three patterns:

| Row | Exact | Normalized | Pattern |
| --- | ---: | ---: | --- |
| `forced_contradiction` | `0.933` | `1.000` | alias closes the gap; residual cases are token-swap variants like `world-fact-forge-orchid-acquisition-status` vs `world-fact-orchid-forge-acquisition-status` |
| `preference_drift` | `0.333` | `0.667` | alias closes part of the gap; the remainder is the real `temporary_constraint`/`session` drift documented in `docs/noisy_policy_mechanism_audit.md` |
| `scope_contamination` | `0.000` | `0.200` | alias finds a partial bridge through workspace-scoped overrides, but most cases fail the 2-token overlap |
| `useful_pending_memory` | `0.000` | `0.000` | even the alias function rejects the gap; the extractor names `project-atlas-pre-merge-check-command`, the question asks `useful-pending-project-command`, non-stop-token overlap is empty |
| `memory_poisoning` | `0.000` | `0.000` | same pattern; extractor uses project-specific slots, question asks the cross-mechanism slot |
| `false_corroboration` | `0.000` | `0.000` | same pattern; extractor uses per-project release-audit slots, question asks `false-corroboration-project-command` |
| `mechanism_diverse_heldout` (frozen) | `0.000` | `0.000` | same pattern across the three frozen mechanism rows |

The deployed metric is QR-canon (exact). The normalized variant is a
boundary sensitivity check, not the policy lookup contract.

## Synthetic Counterexample

The audit ships a toy counterexample as a row in
`data/results/qr_canon_audit_metrics.csv` with `row_kind =
synthetic_counterexample`. Construction:

- Gold has two events `e1`, `e2` in a single cluster, both with
  `canonical_id = "gold-X"`
- Predicted has the same two events `e1`, `e2` in a single cluster, both
  with `canonical_id = "pred-Y"`
- The cluster partition is identical (`{e1, e2}` versus `{e1, e2}`); for
  each event the precision and recall against its gold cluster are `1.00`,
  so B-cubed F1 is `1.00`
- The question asks for `relevant_canonical_id = "gold-X"`; the extracted
  canonical-id set is `{"pred-Y"}`; exact-string set membership fails, so
  QR-canon (exact) is `0.00`

The synthetic row makes the methodological claim land independent of the
Phase 4 numbers. Any reviewer who refuses to credit the noisy-stream
evidence can still observe the gap by construction. Unit tests in
`tests/test_qr_canon_audit.py:SyntheticCounterexampleTests` pin this row
in the metrics CSV.

## Re-Attribution Of Phase 4 Null Rows

The Phase 4 mechanism audit attributed the following five rows as either
"unattributed null" or "descriptive only":

| Row | Mechanism audit attribution | After QR-canon |
| --- | --- | --- |
| `scope_contamination` | unattributed-null with 32B extractor defects | policy-facing query interface contract failure plus residual 32B defects |
| `useful_pending_memory` | unattributed-null | policy-facing query interface contract failure under perfect 32B clustering quality |
| `memory_poisoning` | unattributed-null | policy-facing query interface contract failure under perfect 32B clustering quality |
| `false_corroboration` | descriptive-only event-source proxy | policy-facing query interface contract failure on top of the missing source-identity extraction |
| `mechanism_diverse_heldout` frozen | unattributed-null with one 32B defect trace | policy-facing query interface contract failure plus one frozen 32B defect |

The mechanism audit's "policy ties are not evidence of policy equivalence;
they are evidence the interface failed to expose the distinction" framing
becomes load-bearing rather than buried. The phrase "policy-facing query
interface contract failure" is the active attribution for the four rows
where the locked alias function also returns zero.

This re-attribution **does not** upgrade the mechanism audit's Bucket B
contribution beyond its existing scope. It does not promote
`useful_pending_memory` or `memory_poisoning` into CQ noisy-policy wins.
It changes the failure label, not the policy verdict.

## Relationship To The Locked CQR Audit

The locked CQR audit at
`docs/canonical_id_resolution_audit_preregistration.md` defined
`cqr_set_membership` (the same metric as QR-canon (exact)) and
`cqr_alias_set_membership` (the same metric as QR-canon (normalized)) and
preregistered numeric predictions for both. It aborted twice under Bucket
D on `locked_input_sha_mismatch` and remains aborted per
`docs/canonical_id_resolution_audit_results.md`.

The QR-canon audit:

- reuses the CQR audit's Section A metric definitions exactly
- reuses the CQR audit's locked alias function exactly
- reads from a small committed source table that does not require Phase 4
  run-JSON byte reproducibility
- does **not** issue a CQR Bucket A/B/C verdict; the locked CQR audit is
  unchanged
- does **not** evaluate the CQR audit's Section B alias-CQR prediction
  bands as a strict pre-run prediction (this audit is registered
  post-hoc with disclosed prior observations, not preregistered)
- adds Wilson CIs, a joint B-cubed/QR-canon table, the synthetic
  counterexample, and the methodology-paper reframing

## Limits

- The audit measures the policy-facing exact-lookup contract under a
  specific Phase 4 adapter and policy-query interface. Lifting that
  contract (for example by changing how policy lookups are keyed) is a
  separate research move that requires its own preregistration and is
  forbidden in this audit.
- The synthetic counterexample shows the gap can exist by construction;
  it does not show the gap is the only failure mode on each Phase 4 row.
  Rows with residual 32B clustering defects (`scope_contamination` and
  the frozen sentinel) still have those defects independent of the
  contract failure.
- The audit does not settle whether the noisy ties on
  `useful_pending_memory`, `memory_poisoning`, and `false_corroboration`
  would survive a policy-query contract that admitted alias matching. The
  CQR audit's Section C cross-tab is the right next experiment, and
  remains future work blocked on a CQR replay-discipline path that does
  not exist yet.
- This is descriptive evidence over a single locked 32B noisy comparison.
  External transfer requires a separately preregistered adapter and
  annotation layer, per `docs/longmemeval_feasibility_memo.md`.
