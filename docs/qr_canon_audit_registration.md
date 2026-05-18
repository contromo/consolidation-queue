# Query-Resolvable Canonical-Id (QR-Canon) Audit Registration

Date: 2026-05-17

Status: registered post-hoc audit with disclosed prior observations. This is
**not** a replay of the locked CQR audit and **not** a new preregistered
discovery. It is a small, reproducible companion that lifts the
already-disclosed Section A counts out of the mechanism audit and packages
them with confidence intervals, a joint clustering-vs-resolution table, a
synthetic counterexample, and a methodology-paper reframing.

## 1. Scope And Posture

This audit:

1. Reuses the locked CQR audit's Section A definition (`cqr_set_membership`)
   under the umbrella name **QR-canon (exact)** and the locked alias function
   under the name **QR-canon (normalized)**.
2. Computes per-row QR-canon rates with Wilson confidence intervals from a
   small, committed source table that does **not** depend on the gitignored
   12-17 MB Phase 4 run JSONs at audit time.
3. Reports a joint B-cubed F1 vs QR-canon table and a synthetic
   counterexample showing the metrics can diverge by construction.
4. Reframes the central methodological claim: *clustering-quality component
   evaluation is insufficient for memory-policy evaluability; QR-canon is a
   small, reproducible diagnostic that should be reported alongside
   clustering metrics whenever a memory policy is evaluated under noisy
   extraction*.

This audit explicitly does **not**:

- replay or supersede `docs/canonical_id_resolution_audit_preregistration.md`
- claim a CQR Bucket A/B/C verdict (the locked CQR audit remains Bucket D
  aborted per `docs/canonical_id_resolution_audit_results.md`)
- issue any new policy claim, threshold, validator, adapter, prompt, or
  substrate change
- propose a hard QR-canon pass/fail threshold (QR-canon is a required
  diagnostic, not a gate)
- claim QR-canon proves semantic extractor failure (it is a measured
  policy-facing query contract failure)

The licensed paths for null-row attribution in `PROJECT_PLAN.md` are
(1) a policy-facing adapter-contract audit and (2) a fresh Phase 4 baseline
with committed or archived run-JSON payloads. This audit is path (1),
narrowed to canonical-id resolution and packaged so the result can be cited
without requiring replay of the locked Phase 4 manifests.

## 2. Disclosed Prior Observations

The exact per-row counts below were already disclosed in
`docs/noisy_policy_mechanism_audit.md` and in the committed
`data/results/noisy_policy_mechanism_audit_evidence.json`. They are
reproduced verbatim here so this audit cannot be misread as a fresh
preregistered discovery.

| Family | `exact_matches` | `question_traces_with_relevant_id` | Disclosed in mechanism audit |
| --- | ---: | ---: | --- |
| `forced_contradiction` | `112` | `120` | yes |
| `preference_drift` | `40` | `120` | yes |
| `scope_contamination` | `0` | `75` | yes |
| `useful_pending_memory` | `0` | `60` | yes |
| `memory_poisoning` | `0` | `60` | yes |
| `false_corroboration` | `0` | `60` | yes |
| `mechanism_diverse_heldout` (frozen) | `0` | `4` | yes |

The CQR preregistration's Section 7 disclosure also recorded that the
aggregate exact-match counts and up to three example mismatches per family
were observed before that audit's lock. The same observations are the
starting point for the registered new computations below.

## 3. Registered New Computations

These are not yet on the record and form the only properly registered new
contributions of this audit.

### 3.1 Per-Row QR-Canon Rate With Wilson CIs

For each family, compute QR-canon (exact) rate as `exact_matches /
question_traces_with_relevant_id` with a two-sided 95 percent Wilson
confidence interval. The Wilson interval is used because rates near zero
and one have skewed sampling distributions that the normal approximation
mishandles.

### 3.2 Joint B-cubed F1 vs QR-Canon Table

Report, per row, both the 32B `canonicalization_b_cubed_f1` from the
committed mechanism audit evidence and the QR-canon (exact) rate from this
audit. The joint table is the headline methodological figure: it makes
visible that B-cubed F1 can score `1.00` while QR-canon is `0.00`.

### 3.3 QR-Canon (Normalized) Sensitivity

Apply the locked CQR alias function (the `alias_match` function in
`docs/canonical_id_resolution_audit_preregistration.md` §6) to the
per-question records in the committed source table. Report
QR-canon (normalized) rate per row with Wilson CIs alongside QR-canon
(exact).

Framing rule: QR-canon (exact) is the active policy lookup contract used by
this benchmark. QR-canon (normalized) is a boundary sensitivity check that
bounds the alias-collision share of the gap. The deployed metric is
exact-string; the normalized variant is never substituted for it.

### 3.4 Synthetic Counterexample

A fixture-based toy two-event scenario where:

- two predicted candidates have the same `canonical_id` `pred-Y` and the
  same event-ids `e1`, `e2` as gold
- gold has two events `e1`, `e2` in one cluster with `canonical_id` `gold-X`
- B-cubed F1 between predicted clusters and gold clusters is `1.00`
- the question's `relevant_canonical_id` is `gold-X`
- the extracted candidate canonical-id set is `{pred-Y}`
- QR-canon (exact) on this fixture is `0.00`

This shipping fixture lets the methodological claim land even for a reviewer
who refuses to credit the Phase 4 noisy stream observations.

### 3.5 Methodology Reframing

QR-canon enters the methodology paper as a **required diagnostic alongside
clustering-quality component metrics**, in the same role as the existing
per-family observed gate or the frozen sentinel: a check that catches a
specific failure mode that aggregate clustering metrics smooth over. No
hard QR-canon pass/fail threshold is proposed.

## 4. Reproducibility Contract

This audit must remain reproducible without depending on the gitignored
12-17 MB Phase 4 run JSONs at audit time.

### 4.1 Committed Source Table

`data/results/qr_canon_source_table.csv`, one row per question, with
columns:

- `family`
- `scenario_id`
- `question_id`
- `relevant_canonical_id`
- `extracted_canonical_ids` (semicolon-joined, sorted unique)
- `qr_canon_exact_hit` (`0`/`1`)
- `qr_canon_normalized_hit` (`0`/`1`)
- `row_canonicalization_b_cubed_f1` (denormalized per row)

`data/results/qr_canon_source_table_manifest.json`, recording **only
content-derived fields** so the manifest itself is byte-stable across
reruns from the same inputs:

- generator command (hardcoded literal) and a hardcoded `date`
- per-input-file SHA256, byte size, and replay-root-relative source path
  (the manifest stores `data/runs/...`, never the absolute path of the
  replay root used at generation time)
- per-family `qr_canon_exact_hit` and row counts
- regression check: per-family `qr_canon_exact_hit` sum must equal the
  `exact_matches` value in `data/results/noisy_policy_mechanism_audit_evidence.json`
  and per-family row count must equal `question_traces_with_relevant_id`

The manifest deliberately does **not** record `git_commit`,
`python_version`, or `working_tree_status`. Those fields would drift on
normal reruns even though the artifact this manifest documents (the
source CSV) is itself byte-stable; embedding them would silently break
manifest byte-reproducibility while leaving the CSV content unchanged.
Provenance about the historical generation environment lives in git log
on the commit that introduced the manifest, not in the manifest payload.

### 4.2 Generator And Audit Separation

`scripts/build_qr_canon_source_table.py` is the one-time generator. It
reads:

- the gitignored Phase 4 noisy policy-comparison run JSONs (for
  per-question records)
- the committed mechanism audit evidence (for regression target counts)

It emits the committed source table and manifest above.

`scripts/run_qr_canon_audit.py` is the audit. It reads **only** the
committed source table. It does not import the gitignored run JSONs at
audit time. It emits:

- `data/results/qr_canon_audit_metrics.csv` (per-row aggregates)
- `data/results/qr_canon_audit_manifest.json` (input/output SHAs,
  per-family summary, synthetic-counterexample summary, command literal,
  date literal, registration-doc reference, and alias-function source
  reference)

The audit manifest deliberately omits `git_commit`, `python_version`, and
`working_tree_status` so it is byte-stable from a fixed source CSV. The
test suite asserts manifest byte-stability directly. Independent
reviewers can reproduce both the metrics CSV and the manifest byte for
byte by running only the audit script against the committed source
table.

## 5. Forbidden In This Audit

- prompt, schema, threshold, validator, adapter, policy, or substrate
  changes
- new mechanism families
- claiming this audit unlocks the locked CQR audit's A/B/C verdict
- claiming QR-canon proves semantic extractor failure
- proposing a hard QR-canon pass/fail threshold
- altering the locked CQR alias function (the normalized variant must use
  the function in `docs/canonical_id_resolution_audit_preregistration.md`
  §6 verbatim)
- promoting the locked Bucket B noisy comparison beyond the mechanism
  audit's existing attribution

## 6. Outputs

- `docs/qr_canon_audit_registration.md` (this document)
- `docs/qr_canon_audit_results.md`
- `scripts/build_qr_canon_source_table.py`
- `scripts/run_qr_canon_audit.py`
- `data/results/qr_canon_source_table.csv`
- `data/results/qr_canon_source_table_manifest.json`
- `data/results/qr_canon_audit_metrics.csv`
- `data/results/qr_canon_audit_manifest.json`
- tests under `tests/test_qr_canon_audit*.py`

The methodology spine (`docs/benchmark_methodology_draft.md`) and paper
outline (`docs/paper_outline.md`) are updated to introduce QR-canon as a
required diagnostic alongside clustering-quality component metrics.

## 7. Relationship To Existing Documents

| Document | Relationship |
| --- | --- |
| `docs/canonical_id_resolution_audit_preregistration.md` | Source of metric definitions reused here. Locked, Bucket D aborted, unchanged. |
| `docs/canonical_id_resolution_audit_repair_preregistration.md` | Documented path-normalized repair; produced a second Bucket D. This audit does not retry that path. |
| `docs/canonical_id_resolution_audit_results.md` | Records both Bucket D aborts. This audit does not amend its conclusions. |
| `docs/noisy_policy_mechanism_audit.md` | Source of the disclosed prior observations in §2. Unchanged. |
| `docs/noisy_policy_mechanism_audit_hypothesis.md` | Hypothesis-side framing preserved. Unchanged. |
| `docs/benchmark_methodology_draft.md` | Receives a new §5 subsection introducing QR-canon as a required diagnostic. |
| `docs/paper_outline.md` | Receives a new subsection introducing QR-canon and an evidence-ledger row. |
| `docs/next_research_plan.md` | Workstream A.5 is added: registered post-hoc QR-canon audit. |
| `PROJECT_PLAN.md` | Immediate-next-tasks pointer updated. |
| `docs/product_progress.md` | Receives a 2026-05-17 progress note. |
