# PFLC / QR-Canon Field Diagnostic — Consolidated Results

Date: 2026-05-18

Status: registered Workstream A.6 results, completed. Outcome
bucket: **B-3** (artifact-blocked). Registration:
`docs/policy_facing_lookup_contract_registration.md`. Proposition:
`docs/policy_facing_lookup_contract_proposition.md`.

## 1. Headline

A formal cluster-partition / lookup-contract gap holds by Proposition 1
under any injective relabeling `ρ: L_gold → Σ` whose codomain is the
label alphabet `Σ` (not `L_gold`) and whose image is disjoint from
`{g*}`. This relabeling satisfies both `ρ(g*) ≠ g*` and
`g* ∉ image(ρ)`; the codomain has to be `Σ` because a bijective self-map
of `L_gold` is necessarily surjective onto `L_gold ∋ g*` and so cannot
satisfy the disjoint-image condition. Two parallel existence lemmas
establish the same gap for
retrieval@k content-based metrics (Lemma 1) and answer-accuracy text-
based metrics (Lemma 2). A feasibility survey of four anchor memory
benchmarks (LongMemEval, Mem0/LoCoMo, MemoryAgentBench, MemBench) finds
that none expose the artifacts needed for empirical PFLC scoring — the
gold-side lookup target is exposed by Mem0/LoCoMo alone, and standard
baselines on every anchor publish aggregate scores rather than per-
question system-emitted identifiers. The workstream therefore lands at
**outcome bucket B-3 (artifact-blocked)**.

> **Memory benchmarks can report strong recall, retrieval, or clustering
> scores while failing to expose the policy-facing lookup contract that
> memory-governance systems actually need.**

This is a field-level methodological claim. It is supported by:

- a proved proposition (Section 3, Proposition 1) over cluster-partition
  metrics, validated by a unit test that hand-computes B-cubed F1 = 1.00
  while set-membership PFLC = 0;
- two constructive existence lemmas (Section 3, Lemmas 1 and 2) covering
  retrieval@k and answer-accuracy benchmarks, each instantiated by a
  benchmark-targeted synthetic counterexample (Section 5);
- a per-anchor-benchmark feasibility survey establishing why no anchor
  released artifacts support empirical PFLC scoring today (Section 4);
- a structural finding that B-3 itself documents: current memory-
  benchmark releases do not publish the policy-facing identifier layer
  the diagnostic requires.

The B-3 outcome is **not** a workstream failure. It is the field-level
finding the workstream went after.

## 2. Artifacts

- `docs/policy_facing_lookup_contract_registration.md` — registration
- `docs/policy_facing_lookup_contract_proposition.md` — Proposition 1 +
  Lemmas 1, 2 + corollary
- `docs/qr_canon_longmemeval_feasibility.md` — answer-handle PFLC,
  descriptive-only
- `docs/qr_canon_mem0_locomo_feasibility.md` — dialog-evidence-id PFLC,
  descriptive-only
- `docs/qr_canon_memoryagentbench_feasibility.md` —
  conflict-resolution-id PFLC, descriptive-only
- `docs/qr_canon_membench_feasibility.md` — fact-id PFLC,
  descriptive-only
- `scripts/build_qr_canon_field_diagnostic_metrics.py` — fixture
  generator; no external inputs
- `data/results/qr_canon_field_diagnostic_metrics.csv` — four
  synthetic-counterexample rows, one per anchor
- `data/results/qr_canon_field_diagnostic_metrics_manifest.json` —
  manifest with alias-SHA pin and Proposition 1 reproducibility summary
- `tests/test_qr_canon_field_diagnostic.py` — Proposition 1
  reproducibility, per-benchmark structure, byte-stable reproduction,
  alias SHA pin, no-external-input invariant

The existing QR-canon audit artifacts
(`docs/qr_canon_audit_registration.md`,
`docs/qr_canon_audit_results.md`,
`data/results/qr_canon_audit_metrics.csv`,
`data/results/qr_canon_audit_manifest.json`,
`scripts/build_qr_canon_source_table.py`,
`scripts/run_qr_canon_audit.py`,
`tests/test_qr_canon_audit.py`) are unchanged by this workstream.

## 3. Formal Spine

Three claims of decreasing formal strength, recorded in
`docs/policy_facing_lookup_contract_proposition.md`:

| Statement | Type | Coverage | Reproducibility |
| --- | --- | --- | --- |
| Proposition 1 | proved | cluster-partition metrics (B-cubed F1, ARI, NMI, V-measure, pairwise cluster F1) | `tests/test_qr_canon_field_diagnostic.py::PropositionOneReproducibilityTests` hand-computes M_cluster = 1.00 and M_lookup = 0.00 from a renaming construction satisfying ρ(g*) ≠ g* AND g* ∉ image(ρ) |
| Lemma 1 | existence by construction | content-based retrieval@k metrics (BM25 overlap, embedding similarity, exact text match, judge agreement on snippets) | Mem0/LoCoMo and MemBench synthetic counterexample rows |
| Lemma 2 | existence by construction | text-based answer-accuracy metrics (judge agreement, normalized text match, exact-string match) | LongMemEval and MemoryAgentBench synthetic counterexample rows |

The corollary: no cluster-partition, content-based retrieval, or
text-based answer-accuracy metric is sufficient evidence of policy-
facing lookup-contract success.

## 4. Per-Benchmark Feasibility Status

| Anchor | PFLC instance | Headline metric | Decision | Why |
| --- | --- | --- | --- | --- |
| LongMemEval | answer-handle | overall_accuracy | **descriptive-only** | no canonical lookup handle exposed per question without leaking the reference answer into policy input; reuses the 2026-05-17 feasibility coding for the denominator |
| Mem0 / LoCoMo | dialog-evidence-id | recall_at_k | **descriptive-only** | LoCoMo's `evidence` field exposes a stable gold dialog-id lookup target per question (strongest gold side across the four anchors), but Mem0's framework and standard baselines publish aggregate scores rather than per-question retrieved-dialog-id outputs |
| MemoryAgentBench | conflict-resolution-id | task_accuracy | **descriptive-only** | the Conflict_Resolution / FactConsolidation split is the cleanest *design-level* PFLC analogue (contradiction resolution requires lookup-contract intact), but the released schema exposes `qa_pair_ids` (question-pair index) and `metadata.keypoints` (semantic markers) rather than a fact-id per question |
| MemBench | fact-id | factual_recall | **descriptive-only** (documented evidence floor) | the README documents only a categorical taxonomy; per-question fact-id schema is not exposed at the publicly documented level surveyed |

**BEAM promotion rule** (registration §6.1): promoted to active anchor
only if the Mem0/LoCoMo feasibility memo lands as "blocked." Mem0/LoCoMo
landed as descriptive-only, so the rule is **not** triggered. BEAM
remains in the field-exclusion table.

## 5. Per-Benchmark Synthetic Counterexample Rows

Rows shipped in
`data/results/qr_canon_field_diagnostic_metrics.csv`. Values are by
construction, not observation; `row_kind` makes that explicit.

| Benchmark | PFLC instance | Lemma | Paired headline | Headline value | PFLC exact | Wilson 95% UCB | Joint passes headline / lookup miss |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| LongMemEval | answer-handle | Lemma 2 | overall_accuracy | `1.000` | `0.000` | `0.793` | yes |
| Mem0 / LoCoMo | dialog-evidence-id | Lemma 1 | recall_at_k | `1.000` | `0.000` | `0.793` | yes |
| MemoryAgentBench | conflict-resolution-id | Lemma 2 | task_accuracy | `1.000` | `0.000` | `0.793` | yes |
| MemBench | fact-id | Lemma 1 | factual_recall | `1.000` | `0.000` | `0.793` | yes |

The Wilson UCB at `n = 1, k = 0` is `0.793451` per
`scripts/run_qr_canon_audit.py::_wilson_interval(0, 1)`, reused
verbatim by the field-diagnostic generator. The "joint passes headline /
lookup miss" column is True by construction for every synthetic row:
each fixture is exactly the kind of row a clustering / retrieval /
answer-accuracy metric would call clean while the lookup contract
fails.

## 6. Strict Mode Separation

The contribution is reportable across four evidence modes, separated
strictly:

| Mode | Source | This workstream |
| --- | --- | --- |
| **Empirical** (released system outputs scored under PFLC) | external benchmark released artifacts | **none** — outcome bucket B-3 |
| **Descriptively coded** (PFLC instance defined and a feasibility decision reached for each anchor) | per-benchmark feasibility memos | four memos |
| **Synthetic fixtures** (existence proofs by construction for Lemmas 1 and 2) | per-benchmark synthetic counterexample rows | four rows in `data/results/qr_canon_field_diagnostic_metrics.csv` |
| **Formally argued** (Proposition 1 over cluster-partition metrics) | proposition document + reproducibility unit test | one proposition + a hand-computed reproducibility test |

The field-level claim (Section 1 headline) is supported by the four
modes jointly. Removing any single mode weakens the claim but does not
falsify it; the formal proposition alone establishes the gap exists for
cluster-partition metrics over any benchmark with a label space of size
at least two.

## 7. Why B-3 Is The Right Outcome

Outcome bucket B-3 is defined in
`docs/policy_facing_lookup_contract_registration.md` §4 as: "No anchor
benchmark releases artifacts sufficient for empirical PFLC. Workstream
contribution is the formal proposition + lemmas + feasibility survey +
synthetic counterexamples; the absence of empirical anchors is itself a
structural finding about released-artifact contracts in the field."

The honest reading:

- **B-1 (empirical strong-gap)** was the highest-value bucket but is
  blocked at the system-output side. Mem0/LoCoMo has the cleanest
  gold-side target (`evidence` dialog ids); no standard baseline
  publishes per-question retrieval-id outputs as a downloadable
  artifact. Locating one would convert the workstream from B-3 to B-1
  via empirical-replay. The registration permits that follow-up; this
  workstream does not perform it.
- **B-2 (empirical weak-gap)** is irrelevant — without any empirical
  row, we cannot land at B-2.
- **B-3 (artifact-blocked)** is what the evidence supports today. The
  finding is itself a structural observation about released-artifact
  contracts in the current memory-benchmark field.
- **B-4 (synthetic-only fallback)** would have applied if no anchor
  even supported a descriptive feasibility memo. The workstream
  produced four such memos with locked PFLC instance names, so B-4 is
  not the outcome.

## 8. What This Result Does Not Claim

- It does not claim the four anchor benchmarks are deficient. LoCoMo's
  `evidence` field is a clean gold-side PFLC target; MemoryAgentBench's
  Conflict_Resolution mechanism is exactly the PFLC scenario that
  matters. The workstream is recording what released artifacts publish,
  not auditing benchmark design.
- It does not propose a hard PFLC pass/fail threshold. PFLC is a
  required diagnostic alongside clustering / retrieval / accuracy
  metrics, never a gate.
- It does not unlock the locked CQR Bucket D verdict
  (`docs/canonical_id_resolution_audit_results.md`).
- It does not amend the Phase 4 noisy policy-comparison Bucket B result
  (`docs/noisy_policy_comparison_results.md`).
- It does not amend the registered post-hoc QR-canon audit
  (`docs/qr_canon_audit_results.md`).
- It does not run any policy on any external benchmark. The four
  feasibility memos are descriptive; the synthetic counterexamples are
  by construction; the empirical scoring section is absent because no
  anchor supported it.
- It does not modify the byte-locked CQR alias function. The alias-SHA
  pin in `data/results/qr_canon_field_diagnostic_metrics_manifest.json`
  is documentary and is verified by a unit test against the
  preregistration doc frontmatter.

## 9. Relationship To Locked Artifacts

| Document | Relationship |
| --- | --- |
| `docs/policy_facing_lookup_contract_registration.md` | Registration this results doc answers under. §4 outcome buckets, §6.1 anchor table, §6.3 workflow checkpoint discipline, §7 field-exclusion table all locked at registration commit time. |
| `docs/policy_facing_lookup_contract_proposition.md` | Proposition 1 + Lemmas 1, 2 + corollary. Reproducibility test pins Proposition 1 to a hand-computed construction. |
| `docs/qr_canon_audit_registration.md` | The CQ-internal canonical-id PFLC registration this workstream generalizes from. Unchanged. |
| `docs/qr_canon_audit_results.md` | The CQ-internal results that motivate the field-level generalization. Unchanged. |
| `docs/canonical_id_resolution_audit_preregistration.md` §6 | Source of the byte-locked CQR alias function SHA; pinned by the field-diagnostic manifest and a unit test. |
| `docs/longmemeval_feasibility_memo.md` | Wrapped by the LongMemEval PFLC feasibility memo; per-case coding CSV not re-coded. |
| `docs/next_research_plan.md` | Workstream A.6 lifecycle anchor; receives a status update once the methodology spine and paper outline updates land. |
