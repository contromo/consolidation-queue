# MemBench — PFLC Feasibility Memo

Date: 2026-05-18

Decision: **descriptive-only**.

Named PFLC instance: **fact-id PFLC** — for the factual-memory categories
(Participation-Factual / FirstAgentLowLevel, Observation-Factual /
ThirdAgentLowLevel), the lookup target would be a stable fact identifier
per question. The check is whether the system's per-question emitted
fact-id matches the gold target.

This memo is the thinnest of the four anchor memos: MemBench's released
materials surveyed for this workstream document a categorical taxonomy
but do not document a per-question identifier schema or evaluation
output schema beyond high-level metric names. The "descriptive-only"
decision reflects the publicly documented surface; a deeper artifact
inspection (downloading data from Baidu / Google Drive links in the
repo, or reading the paper PDF in full) could refine the picture but is
not part of this workstream's scope.

## 1. Task-Design Survey

MemBench (Tan et al., 2025; arXiv:2506.21605) evaluates LLM-agent memory
across factual memory and reflective memory levels, with participation
(first-person) and observation (third-person) interactive scenarios. The
released repository is at `https://github.com/import-myself/Membench`.

The taxonomy:

- **Participation-Reflective** (FirstAgentHighLevel) — first-person,
  implicit memory
- **Participation-Factual** (FirstAgentLowLevel) — first-person, explicit
  factual memory
- **Observation-Reflective** (ThirdAgentHighLevel) — third-person,
  implicit memory
- **Observation-Factual** (ThirdAgentLowLevel) — third-person, explicit
  factual memory

The paper reports the benchmark evaluates information extraction,
cross-session reasoning, knowledge updating, temporal reasoning, and
reflective summarization. Four named metrics: accuracy, recall, capacity,
temporal efficiency.

### 1.1 Released per-question schema (as documented publicly)

The README documents that data exists in JSON files organized by
category, but does **not** enumerate per-question fields. Concrete
field names (memory-slot ids, fact ids, canonical ids, event ids) are
not exposed at the README level. The repository points to external
data downloads (Baidu / Google Drive) rather than committing per-question
schema documentation directly.

This memo therefore cannot enumerate the released per-question fields
with the same precision as the LongMemEval, LoCoMo, or MemoryAgentBench
memos. The decision below reflects this evidence floor.

### 1.2 Released metrics

The four headline metrics (accuracy, recall, capacity, temporal
efficiency) are reported aggregate. No clustering-quality canonicalization
metric is documented. Per-question metric breakdowns are not standardly
published.

## 2. Pre-Coding Rule

Frozen before opening any per-question case content:

### 2.1 Inclusion criteria

A MemBench case is in-scope for descriptive PFLC analysis only if:

1. The case is from the Factual category (Participation-Factual or
   Observation-Factual), where "low-level" explicit facts could
   plausibly be addressed by a fact-id lookup.
2. The case has a stable per-question identifier in the released JSON
   schema.
3. The released gold annotation identifies a fact-id target that the
   policy should resolve to, without leaking the reference answer.

### 2.2 Exclusion criteria

Out of scope:

1. Reflective-category cases (high-level implicit memory), where the
   lookup contract is not fact-id-shaped.
2. Cases where the released JSON does not expose a per-question
   identifier beyond a question index.
3. Cases where deriving a fact-id target requires inspecting the
   reference answer (would leak oracle info).

### 2.3 PFLC instance lock

The named PFLC instance for this memo is **fact-id PFLC**:

- Lookup target: a canonical fact identifier per factual-memory
  question. **Not confirmed** to exist in the released schema based on
  publicly documented materials.
- System-emitted identifier: a per-question fact-id the system emits
  when resolving the answer.
- Agreement check (set-membership variant): the gold fact-id appears in
  the system's emitted fact-id set.
- Boundary-sensitivity check: NOT inheriting the byte-locked CQR alias
  function.

## 3. Mechanism Mapping

MemBench's four categories map to the following PFLC analogues:

| Category | PFLC analogue | Empirical eligibility |
| --- | --- | --- |
| Participation-Factual (FirstAgentLowLevel) | fact-id PFLC | blocked at evidence floor — no documented fact-id schema |
| Observation-Factual (ThirdAgentLowLevel) | fact-id PFLC | blocked at evidence floor — same reason |
| Participation-Reflective (FirstAgentHighLevel) | no clean PFLC analogue — implicit memory is not lookup-keyed | n/a |
| Observation-Reflective (ThirdAgentHighLevel) | no clean PFLC analogue | n/a |

The factual categories are the relevant PFLC surface; the reflective
categories are not lookup-contract-shaped.

## 4. Fairness-Invariant Feasibility For PFLC

| Question | Readout | Reason |
| --- | --- | --- |
| Does MemBench expose a per-question lookup-target identifier (fact-id)? | **Not documented publicly** | The README describes categorical organization but does not enumerate per-question fields. A confirmation would require direct artifact inspection (Baidu / Google Drive downloads) or reading the paper PDF in full. |
| Does the released artifact admit a per-question paired clustering / retrieval / accuracy metric? | **Aggregate only** | The four headline metrics (accuracy, recall, capacity, temporal efficiency) are reported aggregate per category. |
| Are per-question system-emitted fact-id outputs published by any standard baseline? | **Not documented publicly** | No information in surveyed materials. |

The empirical PFLC path is blocked at the documented evidence floor.

## 5. Metric Mapping For PFLC

| PFLC component | MemBench analogue | Mapping decision |
| --- | --- | --- |
| Lookup target (`relevant_canonical_id`-equivalent) | not documented | would require direct inspection of factual-category JSON files |
| System-emitted identifier (`extracted_canonical_ids`-equivalent) | not documented | not in surveyed materials |
| Paired clustering / canonicalization metric (`row_canonicalization_b_cubed_f1`-equivalent) | not reported | no clustering metric documented |
| Paired retrieval metric | `recall` (aggregate) | aggregate; per-question breakdown not standardly published |
| Paired accuracy metric | `accuracy` (aggregate) | the headline metric; aggregate only |
| Capacity, temporal efficiency | no PFLC analogue | both are system-resource metrics, not lookup-contract |

## 6. Failure-Interpretation Rules

For MemBench under this workstream:

1. A null PFLC row would mean the released MemBench schema does not
   expose a fact-id contract per factual-memory question. This is a
   structural finding about released artifacts; it cannot be
   re-interpreted as evidence about MemBench's design quality.
2. The synthetic counterexample (§7) is a constructive demonstration of
   Lemma 1 (retrieval-content / retrieval-id) adapted to a factual
   memory recall context.
3. The "descriptive-only" decision reflects the *documented* evidence
   floor. A future inspection of the released JSON files (Baidu /
   Google Drive downloads) could refine this to "blocked" or to
   "empirical" depending on what the data files actually contain. That
   inspection is not in scope for this workstream.

## 7. Synthetic Counterexample (Fact-Id PFLC)

Tied to MemBench's factual-memory recall metric, this counterexample
lands as a shipped fixture row in
`data/results/qr_canon_field_diagnostic_metrics.csv` under
`row_kind = synthetic_membench_counterexample` when that artifact lands.

Construction (Lemma 1 adapted to factual recall):

- A MemBench-shaped Participation-Factual / FirstAgentLowLevel item
  with a gold fact text `f_gold` keyed (in a hypothetical fact-id
  annotation) as `fact-91`.
- A system retrieves the correct fact text `f_gold` (factual recall
  scores `1.0`) but assigns it fact-id `fact-44` in its internal memory
  layout.
- Fact-id PFLC checks set membership of `fact-91` in the system's
  emitted fact-id set. `fact-91 ∉ {fact-44}`, so PFLC = `0`.

The fixture demonstrates that factual-recall scoring does not imply
the underlying fact-id lookup contract is intact. A downstream policy
operation keyed on `fact-91` would not find the corresponding fact in
the system's state.

## 8. Decision Call

Decision: **(b) descriptive-only**.

Rationale: MemBench's factual-memory categories are an appropriate target
for a fact-id PFLC instance in principle. The publicly documented
materials surveyed for this workstream do not expose a per-question
fact-id schema, so empirical scoring is blocked at the documented
evidence floor.

A future workstream could:

1. Conduct a direct inspection of MemBench's released JSON files via
   the Baidu / Google Drive download links to confirm or refute the
   existence of per-question fact-id annotations.
2. If fact-ids exist, attempt empirical-replay PFLC scoring on any
   published system outputs that include fact-id emissions.
3. If fact-ids do not exist, propose a preregistered fact-id annotation
   layer over the factual-memory categories as a separate transfer
   workstream.

None of these are licensed by this memo. The current decision is
descriptive-only at the documented evidence floor.

## 9. Relationship To Locked Artifacts

| Document | Relationship |
| --- | --- |
| `docs/policy_facing_lookup_contract_registration.md` | The locked registration this memo answers under. §6.1 anchor expectation is now resolved: descriptive-only. |
| `docs/policy_facing_lookup_contract_proposition.md` | Lemma 1 adapted by §7 to the factual-recall context. |
| `docs/canonical_id_resolution_audit_preregistration.md` §6 | The byte-locked CQR alias function. NOT inherited by the fact-id PFLC instance. |
| `https://github.com/import-myself/Membench` | MemBench official repo. |
| `https://arxiv.org/abs/2506.21605` | MemBench paper. Full PDF was not inspected by this memo. |
