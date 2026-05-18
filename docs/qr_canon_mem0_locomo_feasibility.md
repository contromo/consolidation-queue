# Mem0 / LoCoMo — PFLC Feasibility Memo

Date: 2026-05-18

Decision: **descriptive-only**.

Named PFLC instance: **dialog-evidence-id PFLC** — a retrieval-id PFLC
variant where the lookup target is the gold `evidence` list of dialog
identifiers per question in LoCoMo's released schema. The check is
whether the system's per-question retrieved-dialog-id output covers the
gold evidence dialog ids; clustering / retrieval-content metrics can
score positively even when this check fails.

## 1. Task-Design Survey

LoCoMo (Maharana et al., 2024; arXiv:2402.17753) is a long-term
conversational memory benchmark consisting of ten conversations averaging
300 turns and 9K tokens over up to 35 sessions. Tasks include
question-answering, event summarization, and multi-modal dialogue
generation. The released artifacts are public under CC BY-NC 4.0 at
`https://github.com/snap-research/locomo` with a project page at
`https://snap-research.github.io/locomo/`.

Mem0 (Chhikara et al., 2025; arXiv:2504.19413) provides a unified
evaluation framework over LoCoMo, LongMemEval, and BEAM at
`https://github.com/mem0ai/memory-benchmarks`. Mem0's evaluation docs
(`https://docs.mem0.ai/core-concepts/memory-evaluation`) describe an
"Ingest → Search → Evaluate" pipeline that ingests dialogues, retrieves
memories using semantic similarity + BM25 + entity boost, generates
answers, and scores QA correctness via an LLM judge. Per-question results
are written to a gitignored `results/` directory; published results in
the docs are aggregated category scores and category-delta tables.

### 1.1 Released per-question schema (LoCoMo dataset)

From the official README:

| Field | Meaning |
| --- | --- |
| `question` | the question text |
| `answer` | the gold answer text |
| `category` | a categorical label |
| `evidence` | a list of dialog identifiers containing the answer |

`evidence` is the load-bearing field for PFLC: it specifies which dialog
identifiers carry the gold answer. The dataset also includes an
`event_summary` field (significant events per speaker per session), but
the README does not confirm a bidirectional mapping from event ids to QA
items, so the dialog-id evidence list is the only stable lookup-target
field per question.

### 1.2 Released metrics

LoCoMo's official metrics are QA correctness (via judge), event
summarization quality, and retrieval Recall@k / NDCG@k when a system
exposes retrieved sessions. No clustering-quality canonicalization metric
(B-cubed, ARI, NMI, V-measure, pairwise cluster F1) is reported on
LoCoMo. Mem0's framework reports aggregate category scores and per-
benchmark category deltas; per-question canonical / memory ids are not
published in the docs.

## 2. Pre-Coding Rule

Frozen before opening any per-question case content:

### 2.1 Inclusion criteria

A LoCoMo case is in-scope for descriptive PFLC analysis only if:

1. The case is a QA item with a non-empty `evidence` list of dialog ids.
2. The dialog-id targets are stable across the released dataset (the
   evidence field is the gold lookup target).
3. The case is QA, not event summarization.

### 2.2 Exclusion criteria

Out of scope:

1. Event-summarization items (no question-level lookup target).
2. Multi-modal dialogue generation items.
3. Items where `evidence` is empty or where the question is purely a
   recall question whose answer is not localized to any dialog id.

### 2.3 PFLC instance lock

The named PFLC instance for this memo is **dialog-evidence-id PFLC** —
the retrieval-id PFLC variant where:

- Lookup target: the gold `evidence` list of dialog ids.
- System-emitted identifier: the per-question list of dialog ids the
  system reports as having been retrieved or consulted to answer.
- Agreement check (set-membership variant): every gold dialog id is
  present in the system's emitted list.
- Boundary-sensitivity check: NOT inheriting the byte-locked CQR alias
  function. The dialog-id namespace is structurally distinct from the
  canonical-id namespace, and applying the CQR alias function would be
  out of contract.

## 3. Mechanism Mapping

LoCoMo's QA items map to the following PFLC analogue:

| LoCoMo task surface | PFLC analogue |
| --- | --- |
| QA with `evidence` list of dialog ids | dialog-evidence-id PFLC |
| Recall@k retrieval score | content-side retrieval metric (paired) |
| QA correctness via judge | answer-text correctness (paired, distinct from PFLC) |
| Event summarization | no PFLC analogue; out of scope |
| Multi-modal dialogue | no PFLC analogue; out of scope |

This memo does **not** count individual LoCoMo cases or run a frozen
coding pass; the per-case denominator is inherited from LoCoMo's released
QA split. A separate coding pass would be necessary only for an
empirical PFLC computation (§4).

## 4. Fairness-Invariant Feasibility For PFLC

Three feasibility questions, each answered from released artifacts:

| Question | Readout | Reason |
| --- | --- | --- |
| Does LoCoMo expose a per-question lookup-target identifier? | **Yes** | The `evidence` field is a stable list of dialog ids per QA question. |
| Does the released artifact admit a per-question paired content / retrieval / accuracy metric? | **Yes** | Recall@k and NDCG@k are official auxiliary metrics; QA correctness is the headline metric. |
| Are per-question system-emitted dialog-id outputs published by any standard baseline? | **Not in standard releases** | Mem0's framework writes per-question results to a gitignored `results/` directory; the docs publish only aggregate scores. The LoCoMo paper's baseline outputs are not surveyed for per-question dialog-id dumps in this memo and would need to be confirmed before any empirical-replay attempt. |

The empirical-replay path is therefore conditional: it would require a
publicly available per-question retrieval-id output dump from a baseline
(Mem0, a LoCoMo-paper baseline, MemMachine, etc.) before any scoring.
Standard Mem0 evaluation runs published on Mem0's framework do not
expose this.

## 5. Metric Mapping For PFLC

| PFLC component | LoCoMo analogue | Mapping decision |
| --- | --- | --- |
| Lookup target (`relevant_canonical_id`-equivalent) | `evidence` list of dialog ids | direct analogue at the gold side |
| System-emitted identifier (`extracted_canonical_ids`-equivalent) | per-question retrieved-dialog-id list | not published in standard releases; would require a baseline that emits per-question retrieval ids |
| Paired clustering / canonicalization metric (`row_canonicalization_b_cubed_f1`-equivalent) | none reported | LoCoMo does not report B-cubed or other clustering-quality canonicalization |
| Paired retrieval metric | Recall@k, NDCG@k | aggregate; per-question breakdown is not standardly published |
| Paired answer-accuracy metric | QA correctness | the headline metric; pairs against dialog-evidence-id PFLC on the answer-text axis |

## 6. Failure-Interpretation Rules

For LoCoMo under this workstream:

1. A null PFLC row would mean that the released LoCoMo + Mem0 / standard
   baseline interface does not expose a per-question retrieval-id
   contract — exactly the structural finding the workstream is
   documenting.
2. The PFLC analogue here is retrieval-id, not canonical-id. The
   byte-locked CQR alias function is NOT inherited. A future PFLC
   instance for LoCoMo that wanted alias-normalization would require its
   own separately registered alias contract.
3. The synthetic counterexample (§7) is a constructive demonstration of
   Lemma 1 from `docs/policy_facing_lookup_contract_proposition.md`.
   It does not depend on LoCoMo case contents.
4. A "descriptive-only" decision here is **not** evidence that LoCoMo's
   schema is deficient. LoCoMo exposes a clean gold lookup target (the
   `evidence` field). The descriptive-only decision reflects what the
   Mem0 framework + standard baselines publish on the system-output
   side, not a defect in LoCoMo itself.

## 7. Synthetic Counterexample (Dialog-Evidence-Id PFLC)

Tied to LoCoMo's Recall@k retrieval-content metric, this counterexample
lands as a shipped fixture row in
`data/results/qr_canon_field_diagnostic_metrics.csv` under
`row_kind = synthetic_locomo_counterexample` when that artifact lands.

Construction (per `docs/policy_facing_lookup_contract_proposition.md`
Lemma 1):

- A LoCoMo-shaped QA item with gold `evidence = [dialog-7, dialog-13]`.
- A system retrieves the same two dialog turns by content (semantic
  similarity + BM25), so the retrieved content matches gold.
- The system emits its per-question retrieval list as
  `[dialog-2, dialog-9]` because its dialog-id assignment is keyed
  differently (e.g., on a renormalized session index).
- Content-based Recall@k scores `1.0` (the gold evidence content was
  retrieved at rank ≤ k under any reasonable k).
- Dialog-evidence-id PFLC checks set membership of gold dialog ids in the
  system's emitted list. `dialog-7 ∉ [dialog-2, dialog-9]` and
  `dialog-13 ∉ [dialog-2, dialog-9]`, so PFLC = `0`.

The fixture instantiates Lemma 1 directly. The gap is at the identifier
layer, not the content layer; it is a policy-facing-contract gap, not a
retrieval-quality gap.

## 8. Decision Call

Decision: **(b) descriptive-only**.

Rationale: LoCoMo's released schema cleanly exposes the gold lookup
target (`evidence` dialog ids) — this is the *strongest* gold-side PFLC
signal across all four anchor benchmarks in this workstream. However,
standard published baseline outputs (Mem0's framework, the LoCoMo paper's
baselines) do not expose per-question system-emitted retrieval-id outputs
as downloadable artifacts; only aggregate scores are public.

Empirical-replay is therefore **conditional, not blocked**: it would
become feasible if a baseline's per-question dialog-id retrieval outputs
were located as a downloadable artifact. This memo does not commit the
workstream to that search; if a future follow-up locates such outputs,
empirical-replay PFLC on LoCoMo could be scored without changing the
locked registration. Any such follow-up must use **empirical-replay
only** (analyzing released baseline outputs) and must not run any policy.

For this workstream, LoCoMo is recorded as:

1. The case study illustrating Lemma 1 (retrieval-content / retrieval-id
   gap), instantiated through the synthetic counterexample in §7.
2. The benchmark with the cleanest gold-side PFLC target, useful as the
   reference example for what released artifacts *would* need to expose
   on the system-output side to support empirical PFLC.

The BEAM promotion rule in the registration is **not** triggered by
this memo because the decision is descriptive-only rather than blocked.
BEAM remains in the field-exclusion table.

## 9. Relationship To Locked Artifacts

| Document | Relationship |
| --- | --- |
| `docs/policy_facing_lookup_contract_registration.md` | The locked registration this memo answers under. §6.1 anchor expectation is now resolved: descriptive-only. |
| `docs/policy_facing_lookup_contract_proposition.md` | Lemma 1 instantiated by §7. |
| `docs/canonical_id_resolution_audit_preregistration.md` §6 | The byte-locked CQR alias function. NOT inherited by the dialog-evidence-id PFLC instance; LoCoMo's dialog-id namespace is structurally distinct. |
| `docs/qr_canon_audit_results.md` | The internal CQ canonical-id PFLC findings the workstream generalizes from. Unchanged. |
| `https://github.com/snap-research/locomo` | LoCoMo official repo and dataset schema source. CC BY-NC 4.0. |
| `https://docs.mem0.ai/core-concepts/memory-evaluation` | Mem0 evaluation docs; source of the aggregate-only published-result observation. |
| `https://github.com/mem0ai/memory-benchmarks` | Mem0 unified evaluation framework; gitignored `results/` directory documented as the per-question output sink that is not standardly published. |
