# Policy-Facing Lookup-Contract Diagnostic — Field-Level Registration

Date: 2026-05-18

Status: registered preregistration for Workstream A.6 in
`docs/next_research_plan.md`. Locks the workstream contract, the diagnostic
class definition, per-benchmark feasibility-coding contract, outcome buckets,
reproducibility contract, forbidden list, and field-exclusion table before
any per-benchmark scoring runs.

## 1. Scope And Posture

This workstream generalizes the existing QR-canon diagnostic
(`docs/qr_canon_audit_registration.md`) from a CQ-internal post-hoc audit to
a field-level diagnostic class — **policy-facing lookup-contract (PFLC)
diagnostics** — that should accompany clustering, retrieval, or answer-
accuracy scoring whenever a memory-governance benchmark is used to compare
policies.

This registration:

1. Locks the formal proposition and lemmas
   (`docs/policy_facing_lookup_contract_proposition.md`) as the load-bearing
   argument.
2. Names PFLC as the diagnostic class, with QR-canon (canonical-id PFLC) as
   one instance among several (retrieval-id, slot-id, fact-id).
3. Locks a per-benchmark feasibility-coding contract before any per-benchmark
   scoring.
4. Pre-buckets the workstream's possible outcomes (§4) so no empirical
   scoring lands as a pass/fail verdict.
5. Locks the reproducibility contract (committed source CSV, byte-stable
   manifest, regression check).
6. Identifies the four anchor benchmarks (§6) and the explicit field-
   exclusion table (§7) so reviewers can see the workstream is honest about
   what it covers.

This registration explicitly does **not**:

- replay, supersede, unlock, or amend the locked CQR audit's Bucket D
  verdict (`docs/canonical_id_resolution_audit_results.md`);
- amend the Phase 4 noisy policy-comparison Bucket B result
  (`docs/noisy_policy_comparison_results.md`);
- amend the registered post-hoc QR-canon audit
  (`docs/qr_canon_audit_registration.md`,
  `docs/qr_canon_audit_results.md`);
- modify the byte-locked CQR alias function
  (`scripts/run_canonical_id_resolution_audit.py:156-207`; SHA256 fixed in
  `docs/canonical_id_resolution_audit_preregistration.md` §6);
- propose a hard PFLC pass/fail threshold;
- run any CQ, ReflectionEagerWrite, `Mem0Lite`, or other policy against any
  external benchmark.

## 2. Disclosed Prior Observations

The following observations are already on the record in this repository and
inform the per-benchmark feasibility expectations in §6. They are reproduced
here so this registration cannot be misread as a fresh preregistered
discovery.

| Observation | Source | Used here for |
| --- | --- | --- |
| The CQ-internal synthetic counterexample shows B-cubed F1 = 1.00 with QR-canon (exact) = 0.00 on a real benchmark fixture. | `docs/qr_canon_audit_results.md`; `scripts/run_qr_canon_audit.py:178-207` | Worked example for Proposition 1 in `docs/policy_facing_lookup_contract_proposition.md`. |
| Five of seven Phase 4 rows clear the B-cubed F1 ≥ 0.65 floor while QR-canon (exact) is below 5 percent. | `docs/qr_canon_audit_results.md`; `data/results/qr_canon_audit_metrics.csv` | Motivates the field-level generalization. |
| LongMemEval's released oracle split contains 72 `knowledge-update` cases mapping to `contradiction_edge`, but the released artifacts do not expose CQ-style candidate streams, contradiction edges, canonical slots, or `relevant_canonical_id` mappings. | `docs/longmemeval_feasibility_memo.md`; `data/results/longmemeval_feasibility_coding.csv` | LongMemEval feasibility decision is pre-known as descriptive-only. |
| Mem0's public evaluation docs describe LoCoMo accuracy categories and result schemas; they do not appear to publish per-question B-cubed or other clustering / canonicalization artifacts. | https://docs.mem0.ai/core-concepts/memory-evaluation | Mem0/LoCoMo is a *possible* empirical candidate pending released-artifact verification, **not** an assumed empirical anchor. |

## 3. Registered New Computations And Contributions

These are not yet on the record and form the new contributions of this
workstream:

1. **Formal proposition + lemmas.**
   `docs/policy_facing_lookup_contract_proposition.md`. Proposition 1 covers
   cluster-partition metrics, proved by an injective relabeling
   `ρ: L_gold → Σ` whose image is disjoint from `{g*}` (the codomain
   is the label alphabet `Σ`, not `L_gold` — a bijective self-map of
   `L_gold` cannot satisfy the disjoint-image condition, so the
   relabeling must be allowed to land in a fresh label space);
   Lemma 1 covers retrieval-content / retrieval-id; Lemma 2 covers
   answer-text / lookup-handle. A unit test in
   `tests/test_qr_canon_field_diagnostic.py` will instantiate Proposition 1
   directly by construction.
2. **PFLC diagnostic class definition.** §5 of this document. QR-canon is
   the canonical-id instance. Other instances are named, defined, and
   instantiated by per-benchmark synthetic counterexamples.
3. **Per-benchmark feasibility memos** for each anchor benchmark (§6),
   following the LongMemEval template
   (`docs/longmemeval_feasibility_memo.md`), each ending in a decision call
   of {empirical, descriptive-only, blocked}.
4. **Per-benchmark synthetic counterexamples** tied to each anchor
   benchmark's headline metric (§5.2), landing as shipped fixtures in
   `data/results/qr_canon_field_diagnostic_metrics.csv`.
5. **Empirical scoring**, conditional on a feasibility memo landing as
   "empirical", on Mem0/LoCoMo (primary) and on BEAM (only if the Mem0/
   LoCoMo memo is blocked). Reported under the outcome buckets in §4.
6. **Consolidated results doc**
   `docs/qr_canon_field_diagnostic_results.md` collecting the formal claim,
   per-benchmark feasibility status, per-row Wilson CIs for any empirical
   row, and per-benchmark synthetic counterexamples.
7. **Methodology spine and paper outline updates** to
   `docs/benchmark_methodology_draft.md` and `docs/paper_outline.md`,
   promoting PFLC/QR-canon from internal audit to a field-level minimum-
   diagnostic recommendation.

## 4. Outcome Buckets

Workstream outcomes are pre-bucketed to keep the empirical attempt from
becoming an implicit pass/fail gate.

- **B-1 empirical strong-gap.** At least one external empirical row where
  a benchmark's headline metric clears its reported floor while the
  corresponding PFLC instance is well below it (e.g., near zero). The
  row(s) ship as the headline empirical evidence in the consolidated
  results doc.
- **B-2 empirical weak-or-no-gap.** Empirical scoring lands, but PFLC
  tracks the headline metric closely on the scored benchmark. Still a
  publishable methodology contribution: it shows the gap is contingent on
  benchmark construction, not universal.
- **B-3 artifact-blocked.** No anchor benchmark releases artifacts
  sufficient for empirical PFLC scoring. The workstream contribution is
  the formal proposition + lemmas + feasibility survey + synthetic
  counterexamples; the absence of empirical anchors is itself a structural
  finding about released-artifact contracts in the field.
- **B-4 synthetic-only fallback.** Triage stops short of any empirical or
  descriptive coding (e.g., all benchmarks fall to blocked); the
  contribution rests on the formal section + per-benchmark synthetic
  counterexamples alone. Reportable but the weakest bucket.

No "X-percent gap" or similar quantitative threshold is preregistered. The
bucket assignment is descriptive and does not impose a pass/fail line.

**Bucket assignment rule.** The consolidated results doc must record the
final bucket and the per-benchmark feasibility decisions that produced it.
A bucket change between this registration and the final results doc must
be flagged as a registered amendment, not a silent reclassification.

## 5. PFLC Diagnostic Class Definition

### 5.1 General form

A PFLC diagnostic instance is a per-question agreement check between:

- a benchmark-supplied policy-lookup target (canonical id, retrieval id,
  slot id, fact id, etc.); and
- the identifier the system under evaluation emits for the cluster /
  retrieved item / fact that the query resolves to.

A PFLC instance is fully specified by:

1. the **lookup-target field** in the benchmark's released or annotated
   artifacts;
2. the **system-emitted-identifier field** the policy would consume;
3. the **agreement check** (default: exact-string set membership);
4. an optional **boundary-sensitivity check** using a documented alias
   function. For the canonical-id instance only, the boundary check is
   the byte-locked CQR alias function
   (`scripts/run_canonical_id_resolution_audit.py:156-207`; SHA256 fixed
   in `docs/canonical_id_resolution_audit_preregistration.md` §6). No
   modification permitted by this workstream. Other PFLC instances do not
   inherit this alias function; they may define their own only as part of
   a separately registered follow-up.

### 5.2 Named instances

| PFLC instance | Lookup target | Anchor benchmark(s) | Headline metric paired against |
| --- | --- | --- | --- |
| **Canonical-id PFLC** (= QR-canon) | `relevant_canonical_id` per question | Internal CQ benchmark; Mem0/LoCoMo (pending verification) | cluster-partition metrics (B-cubed F1, ARI, NMI, V-measure, pairwise cluster F1) |
| **Retrieval-id PFLC** | retrieved-item identifier (slot id, doc id) | MemoryAgentBench (provisional) | retrieval@k, NDCG@k |
| **Slot-id PFLC** | test-time-learning slot identifier | MemoryAgentBench (provisional) | test-time learning accuracy |
| **Fact-id PFLC** | factual-memory identifier | MemBench (provisional) | factual recall, reflective memory accuracy |
| **Answer-handle PFLC** | canonical lookup handle behind the answer | LongMemEval | overall_accuracy / QA judge |

Provisional instances are confirmed only by their per-benchmark feasibility
memo. A memo may rename or refine its named PFLC instance to match the
benchmark's actual artifact shape; the renaming is part of the memo's
locked content.

### 5.3 What PFLC is *not*

- It is not a clustering metric. Cluster-partition agreement is necessary
  but not sufficient (Proposition 1).
- It is not a retrieval metric. Content-based retrieval agreement is
  necessary but not sufficient (Lemma 1).
- It is not an answer-accuracy metric. Text-based answer correctness is
  necessary but not sufficient (Lemma 2).
- It is not a pass/fail gate. PFLC is a required diagnostic alongside the
  benchmark's headline metric. No threshold is preregistered here.
- It is not evidence that an extractor is semantically wrong. A non-zero
  PFLC gap is interface-level evidence — a mismatch between the policy
  lookup contract and the identifier the system emits — not a semantic
  failure claim.

## 6. Per-Benchmark Feasibility-Coding Contract

### 6.1 Anchor benchmarks

This workstream commits to a representative anchor set, not exhaustive
coverage. The anchors are:

| Anchor | Citation | Initial expectation |
| --- | --- | --- |
| LongMemEval | arXiv:2410.10813 | Descriptive-only. Wraps `docs/longmemeval_feasibility_memo.md` and `data/results/longmemeval_feasibility_coding.csv`. No new coding pass. |
| Mem0/LoCoMo | Mem0 arXiv:2504.19413; LoCoMo arXiv:2402.17753; https://docs.mem0.ai/core-concepts/memory-evaluation | Possible empirical candidate, **unverified**. First triage task is to verify whether any per-question clustering / canonicalization / retrieval-id artifact exists in released code, datasets, or paper tables. If none, falls to descriptive-only. |
| MemoryAgentBench | arXiv:2507.05257 | Unknown. Triage task: determine retrieval-id and slot-id artifact shape. |
| MemBench | arXiv:2506.21605 | Unknown. Triage task: determine fact-id artifact shape. |
| BEAM | conditional | Excluded by default (§7). Promoted to active anchor only if the Mem0/LoCoMo feasibility memo lands as "blocked"; promotion requires its own feasibility memo. |

### 6.2 Feasibility memo template

Each per-benchmark feasibility memo follows the structure of
`docs/longmemeval_feasibility_memo.md`:

1. **Task-design survey.** Released artifacts, evaluation protocol,
   headline metric, evidence fields.
2. **Pre-policy coding rule.** Frozen before opening case contents.
   Includes inclusion / exclusion criteria and a coding protocol.
3. **Mechanism mapping under the frozen rule.** Per-question labels and
   resulting denominators.
4. **Fairness-invariant feasibility.** Whether the benchmark exposes a
   policy-lookup target, a candidate stream, and a query interface
   without leaking the reference answer into policy input.
5. **Metric mapping.** What this repo's primary metrics, if any,
   correspond to in the external benchmark, and which do not map.
6. **Failure-interpretation rules.** What a null PFLC row means and what
   it does not mean on this benchmark.
7. **Decision call.** Exactly one of {empirical, descriptive-only,
   blocked}, with the named PFLC instance, the released-artifact source,
   and the prerequisites for any future change.

### 6.3 Workflow checkpoint

Per the LongMemEval template, each memo locks a workflow-checkpoint SHA
over the initial skeleton (source survey, pre-policy coding rule, and
placeholder sections) before any case contents are opened. The checkpoint
records workflow discipline, not a committed standalone artifact. A memo
whose case coding precedes its workflow checkpoint is rejected.

### 6.4 Empirical-scoring contract (conditional)

If a feasibility memo decision is "empirical":

- A per-benchmark generator script
  `scripts/build_qr_canon_source_table_<benchmark>.py` reads released
  benchmark artifacts and projects to the eight-column source CSV schema
  used by the internal QR-canon audit
  (`family`, `scenario_id`, `question_id`, `relevant_canonical_id`,
  `extracted_canonical_ids`, `qr_canon_exact_hit`,
  `qr_canon_normalized_hit`, `row_canonicalization_b_cubed_f1`). For
  non-canonical-id PFLC instances, the column names retain the same
  schema but the values reflect the named instance (retrieval-id,
  slot-id, fact-id, answer-handle); the per-benchmark generator script
  documents the projection mapping.
- A committed per-benchmark source CSV is emitted with a byte-stable
  manifest that records only content-derived fields (per-input-file
  SHA256, byte size, replay-root-relative path; per-family hit and row
  counts; regression-check tie to a committed evidence file). The
  manifest deliberately omits `git_commit`, `python_version`, and
  `working_tree_status`.
- The audit script reads only the committed source CSV and emits a
  byte-stable per-benchmark metrics CSV and manifest.

## 7. Field-Exclusion Table

The following 2026 memory-evaluation benchmarks are explicitly out of
scope for v1 of this workstream. Their inclusion would be a separately
registered follow-up.

| Benchmark | Why excluded for v1 | Promotion rule |
| --- | --- | --- |
| BEAM | not in anchor set; v1 anchors already cover four representative benchmarks. | Promoted to active anchor only if the Mem0/LoCoMo feasibility memo decision is "blocked"; promotion requires its own feasibility memo before scoring. |
| MemGUI-Bench | GUI-agent memory; outside this workstream's text-conversational anchor framing. | Future workstream. |
| LoCoMo-Plus | superset of LoCoMo; if LoCoMo's released artifacts support empirical PFLC, LoCoMo-Plus may be a future follow-up. | Future workstream. |
| Memory for Autonomous LLM Agents (2026 survey corpus, arXiv:2603.07670) | aggregator survey; individual benchmarks within it would each need their own feasibility memo. | Future workstream. |
| Other persistent-memory benchmarks not enumerated here | not surveyed for v1. | Future workstream; this registration does not extend silently. |

This table is the load-bearing acknowledgment that the field has more
benchmarks than this workstream addresses. The workstream does **not**
claim "all persistent-memory benchmarks"; it claims the diagnostic
applies to its anchor set with named PFLC instances, and the field-level
recommendation extends to other benchmarks only as an inference from the
formal proposition.

## 8. Reproducibility Contract

The reproducibility discipline mirrors the internal QR-canon audit's
contract (`docs/qr_canon_audit_registration.md` §4).

- **Source CSV per benchmark.** Committed. Eight columns as listed in
  §6.4.
- **Source manifest per benchmark.** Committed, byte-stable across reruns
  from the same inputs. Records the generator command literal, a
  hardcoded date, per-input-file SHA256, byte size, and replay-root-
  relative source path; per-family hit and row counts; a regression
  check tying counts to a committed evidence file.
- **Audit metrics CSV per benchmark.** Per-row aggregates with Wilson
  confidence intervals. Byte-stable from the committed source CSV.
- **Audit manifest per benchmark.** Records input/output SHAs, per-family
  summary, synthetic-counterexample summary if shipped, command literal,
  date literal, registration-doc reference, and alias-function source
  reference. Byte-stable from the committed source CSV.
- **No gitignored input dependency at audit time.** The audit script must
  reproduce the metrics CSV and manifest from the committed source CSV
  alone, with no read of large per-scenario JSONs.
- **Test coverage.**
  - All 19 existing tests in `tests/test_qr_canon_audit.py` must remain
    green byte-stable.
  - `tests/test_qr_canon_field_diagnostic.py` adds: per-benchmark
    generator regression checks (only for benchmarks with empirical
    scoring); per-benchmark synthetic counterexample structure
    assertions for every anchor benchmark; audit reproducibility without
    gitignored input; manifest byte-stability across benchmarks; alias-
    function SHA pin; and a formal-proposition reproducibility test
    instantiating the renaming construction by hand and asserting
    `M_cluster = 1.00` with `M_lookup = 0.00`.

## 9. Forbidden In This Workstream

- prompt, schema, threshold, validator, adapter, policy, or substrate
  changes;
- new mechanism families;
- claiming this workstream unlocks the locked CQR audit's Bucket D
  verdict (`docs/canonical_id_resolution_audit_results.md`);
- amending the locked Phase 4 noisy policy-comparison Bucket B result
  (`docs/noisy_policy_comparison_results.md`);
- amending or superseding the registered post-hoc QR-canon audit
  (`docs/qr_canon_audit_results.md`);
- modifying the byte-locked CQR alias function
  (`scripts/run_canonical_id_resolution_audit.py:156-207`);
- proposing a hard PFLC pass/fail threshold;
- running any CQ, ReflectionEagerWrite, `Mem0Lite`, or other policy
  against any external benchmark;
- deriving an external benchmark's `relevant_canonical_id` (or analogous
  PFLC target) from the reference answer, evidence labels, or judge
  rubric in a way that would leak oracle information into policy input;
- silent promotion of BEAM or any other excluded benchmark out of the
  field-exclusion table (§7) without its own feasibility memo;
- silent bucket reassignment between this registration and the
  consolidated results doc;
- turning a descriptive observation into a noisy-mode CQ policy claim.

## 10. Outputs

This workstream produces:

- `docs/policy_facing_lookup_contract_registration.md` (this document)
- `docs/policy_facing_lookup_contract_proposition.md`
- `docs/qr_canon_longmemeval_feasibility.md`
- `docs/qr_canon_mem0_locomo_feasibility.md`
- `docs/qr_canon_memoryagentbench_feasibility.md`
- `docs/qr_canon_membench_feasibility.md`
- `docs/qr_canon_beam_feasibility.md` (conditional on Mem0/LoCoMo being
  blocked)
- `docs/qr_canon_field_diagnostic_results.md`
- `data/results/qr_canon_field_diagnostic_metrics.csv` and its manifest
- per-benchmark empirical artifacts (only if the corresponding
  feasibility memo decision is "empirical"): generator script
  `scripts/build_qr_canon_source_table_<benchmark>.py`, committed source
  CSV `data/results/qr_canon_source_table_<benchmark>.csv` + manifest,
  audit metrics CSV `data/results/qr_canon_audit_metrics_<benchmark>.csv`
  + manifest
- tests under `tests/test_qr_canon_field_diagnostic*.py`
- updates to `docs/benchmark_methodology_draft.md`, `docs/paper_outline.md`,
  `docs/next_research_plan.md`, `PROJECT_PLAN.md`, and
  `docs/product_progress.md`
- conditional refactor (triggered only if any benchmark lands as
  "empirical"): `scripts/_qr_canon_lib.py`, thinned
  `scripts/build_qr_canon_source_table.py` and
  `scripts/run_qr_canon_audit.py`, and `tests/test_qr_canon_lib.py`

## 11. Relationship To Existing Documents

| Document | Relationship |
| --- | --- |
| `docs/policy_facing_lookup_contract_proposition.md` | Load-bearing formal artifact. Locked alongside this registration. |
| `docs/canonical_id_resolution_audit_preregistration.md` | Source of the byte-locked CQR alias function (SHA256 fixed in §6). The canonical-id PFLC instance's boundary-sensitivity check reuses this function verbatim. Unchanged by this workstream. |
| `docs/canonical_id_resolution_audit_results.md` | Records both Bucket D aborts. Unchanged by this workstream. |
| `docs/qr_canon_audit_registration.md` | Source of the canonical-id PFLC reproducibility contract template. Unchanged by this workstream. |
| `docs/qr_canon_audit_results.md` | Source of the disclosed prior observations in §2. Unchanged by this workstream. |
| `docs/noisy_policy_comparison_results.md` | The Phase 4 Bucket B result. Unchanged by this workstream. |
| `docs/noisy_policy_mechanism_audit.md` | The mechanism-audit attribution. Unchanged by this workstream. |
| `docs/longmemeval_feasibility_memo.md` | Template for per-benchmark feasibility memos. The LongMemEval PFLC memo wraps this artifact rather than re-coding. |
| `docs/benchmark_methodology_draft.md` | Receives a new §5 subsection "Policy-Facing Lookup-Contract Diagnostics" after the consolidated results doc lands. CQ-internal Phase 4 readout already in §5 is not modified. |
| `docs/paper_outline.md` | Receives a new contribution (PFLC class) and refines contribution 7 (QR-canon) as the canonical-id instance. Related Work and Evidence Ledger gain per-benchmark rows. |
| `docs/next_research_plan.md` | Workstream A.6 is the lifecycle anchor for this registration. |
| `PROJECT_PLAN.md` | Immediate-next-tasks pointer updated when the registration lands. |
| `docs/product_progress.md` | Receives a 2026-05-18 dated entry. |
