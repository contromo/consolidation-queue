# MemoryAgentBench — PFLC Feasibility Memo

Date: 2026-05-18

Decision: **descriptive-only**.

Named PFLC instance: **conflict-resolution-id PFLC** (a fact-id / slot-id
variant) — for the Conflict_Resolution (CR) split and the
FactConsolidation subset specifically, the lookup target is the
canonical fact-id the policy should resolve to after a contradiction or
update. The check is whether the system's per-question emitted fact-id
matches the gold target; the headline retrieval / accuracy metrics can
score positively even when this check fails.

## 1. Task-Design Survey

MemoryAgentBench (Hu et al., ICLR 2026; arXiv:2507.05257) evaluates memory
in LLM agents via incremental multi-turn interactions across four core
competencies: Accurate Retrieval (AR), Test-Time Learning (TTL),
Long-Range Understanding (LRU), and Conflict Resolution (CR). The
released artifacts are public at
`https://github.com/HUST-AI-HYZ/MemoryAgentBench`, with the dataset at
`https://huggingface.co/datasets/ai-hyz/MemoryAgentBench`.

The benchmark uses an "inject once, query multiple times" design: one
long text corresponds to multiple questions, improving evaluation
efficiency. Underlying dataset sources include adapted prior benchmarks
(RULER, NIAH, ∞Bench-QA) plus two newly constructed datasets: **EventQA**
(temporal event chains) and **FactConsolidation** (conflict resolution).

### 1.1 Released per-question schema

From the HuggingFace dataset card and GitHub README:

| Field | Meaning |
| --- | --- |
| `context` | the long document / passage text injected |
| `questions` | a list of questions for this context |
| `answers` | a list of corresponding answers |
| `metadata.qa_pair_ids` | identifier for each question-answer pair (replaces earlier `uuid`) |
| `metadata.keypoints` | semantic markers added in July 2025 update (LRU split) |
| `metadata.previous_events` | ordered event chains for narrative coherence |
| `metadata.demo`, `metadata.haystack_sessions` | appear null in shown examples |

**`qa_pair_ids` is a question-pair identifier, not a memory-slot or
canonical-id lookup target.** It indexes the question; it does not point
to a specific gold memory location in the context.

### 1.2 Split shapes

| Split | Rows | Mechanism |
| --- | ---: | --- |
| Accurate_Retrieval (AR) | 22 | single/multi-hop fact retrieval |
| Test_Time_Learning (TTL) | 6 | learning new skills during interaction |
| Long_Range_Understanding (LRU) | 110 | global narrative comprehension |
| Conflict_Resolution (CR) | 8 | detecting/updating contradictory information |

The CR split is the smallest in row count but the most directly
PFLC-relevant: conflict resolution is exactly the mechanism that
requires a memory-governance system to resolve a canonical lookup
handle after contradiction.

### 1.3 Released metrics

The README does not enumerate per-split metrics with the level of detail
needed for PFLC pairing. The HuggingFace card describes only the four
split categories. Standard evaluation appears to use task-specific
accuracy via QA judging. No clustering-quality canonicalization metric
(B-cubed, ARI, NMI) is documented in the public materials surveyed.

## 2. Pre-Coding Rule

Frozen before opening any per-question case content:

### 2.1 Inclusion criteria

A MemoryAgentBench case is in-scope for descriptive PFLC analysis only
if:

1. The case is from the Conflict_Resolution (CR) split or the
   FactConsolidation subset.
2. The case requires the policy to resolve between two competing facts
   (one earlier, one later) — that is, the mechanism is contradiction-
   driven, not pure aggregation.
3. The released gold annotation identifies the *correct* fact to be
   resolved to, in a form that does not leak the reference answer text
   directly into the policy input.

### 2.2 Exclusion criteria

Out of scope:

1. AR cases where the lookup target is content-level retrieval without
   contradiction.
2. TTL cases where the mechanism is skill learning, not fact resolution.
3. LRU cases where `keypoints` are semantic markers rather than stable
   fact identifiers.
4. Any case where deriving the lookup target requires inspecting the
   reference answer text (would leak oracle info).
5. Cases from any split where the gold annotation exposes only
   `qa_pair_ids` (a question-pair index) and no fact / canonical-id
   target.

### 2.3 PFLC instance lock

The named PFLC instance for this memo is **conflict-resolution-id PFLC**:

- Lookup target: the canonical fact-id (or slot-id) the policy should
  resolve to after contradiction. In the released CR schema, this is
  **not** exposed as a stable field; it would need to be added in a
  follow-up annotation layer.
- System-emitted identifier: the per-question fact-id the system
  resolved to during conflict resolution.
- Agreement check (set-membership variant): the gold fact-id is present
  in the system's emitted resolution set.
- Boundary-sensitivity check: NOT inheriting the byte-locked CQR alias
  function. MemoryAgentBench's fact-id namespace is distinct from the
  CQR canonical-id namespace.

## 3. Mechanism Mapping

MemoryAgentBench's four splits map to the following PFLC analogues:

| Split | PFLC analogue | Empirical eligibility |
| --- | --- | --- |
| Conflict_Resolution (CR) | conflict-resolution-id PFLC (fact-id) | blocked — no fact-id target in released schema |
| FactConsolidation subset | conflict-resolution-id PFLC (fact-id) | blocked — same reason |
| Accurate_Retrieval (AR) | retrieval-id PFLC (potentially via context spans) | unclear — would need context-span identifiers |
| Long_Range_Understanding (LRU) | keypoint-id PFLC (via `metadata.keypoints`) | only if keypoints are stable identifiers; appear semantic-marker-like |
| Test_Time_Learning (TTL) | no clear PFLC analogue | n/a |

The eight-row CR split is the most direct PFLC analogue, but it does not
expose a fact-id target in the released schema. Adding such a target
would be a separate preregistered annotation layer over MemoryAgentBench.

## 4. Fairness-Invariant Feasibility For PFLC

Three feasibility questions:

| Question | Readout | Reason |
| --- | --- | --- |
| Does MemoryAgentBench expose a per-question lookup-target identifier (fact-id, canonical-id, slot-id)? | **No** | Released schema exposes `qa_pair_ids` (a question-pair index) and `metadata.keypoints` (semantic markers for LRU). Neither is a stable fact-id / canonical-id lookup target. |
| Does the released artifact admit a per-question paired clustering / retrieval / accuracy metric? | **Partial** | Task-specific accuracy is reported aggregate per split; per-question breakdown of clustering or retrieval is not documented in surveyed materials. |
| Are per-question system-emitted fact-id outputs published by any standard baseline? | **No** | The released code emits accuracy-based scores; system-emitted fact-id artifacts are not part of the public release. |

The empirical PFLC path is blocked at the gold side: even if a baseline
published system-emitted fact-ids, there is no gold target to score
them against without an additional annotation layer.

## 5. Metric Mapping For PFLC

| PFLC component | MemoryAgentBench analogue | Mapping decision |
| --- | --- | --- |
| Lookup target (`relevant_canonical_id`-equivalent) | not exposed | would require fact-id / slot-id annotation layer over CR split |
| System-emitted identifier (`extracted_canonical_ids`-equivalent) | not exposed | not in baseline outputs |
| Paired clustering / canonicalization metric (`row_canonicalization_b_cubed_f1`-equivalent) | not reported | no B-cubed or ARI documented |
| Paired retrieval metric | unclear; AR split implies retrieval | per-question breakdown not documented |
| Paired accuracy metric | task-specific accuracy per split | aggregate reported; per-question breakdown not standardly published |

## 6. Failure-Interpretation Rules

For MemoryAgentBench under this workstream:

1. A null PFLC row would mean the released CR / FactConsolidation
   schema does not expose a fact-id contract. This is the structural
   finding the workstream documents; it cannot be re-interpreted as
   evidence about baseline performance on MemoryAgentBench.
2. The synthetic counterexample (§7) is a constructive demonstration of
   Lemma 1 from `docs/policy_facing_lookup_contract_proposition.md` for
   the retrieval-id variant, and structurally similar to the slot-id
   variant for the CR split mechanism.
3. A "descriptive-only" decision here does **not** claim
   MemoryAgentBench's design is deficient. The CR split's
   contradiction-resolution framing is exactly PFLC-relevant; the
   absence of a fact-id annotation is what would need to be added by a
   future workstream to enable empirical PFLC scoring.

## 7. Synthetic Counterexample (Conflict-Resolution-Id PFLC)

Tied to MemoryAgentBench CR's task-specific accuracy metric, this
counterexample lands as a shipped fixture row in
`data/results/qr_canon_field_diagnostic_metrics.csv` under
`row_kind = synthetic_memoryagentbench_counterexample` when that artifact
lands.

Construction (Lemma 1 / Lemma 2 hybrid):

- A MemoryAgentBench CR-shaped instance with two competing facts in the
  context: the original assertion `fact_A = v_old` (slot id `slot-7` in
  a hypothetical fact-id annotation) and a later correction
  `fact_A = v_new` (slot id `slot-13`).
- The system correctly identifies `v_new` as the answer (task accuracy
  scores `1.0` under judge correctness).
- The system's internal memory writes the correction under slot id
  `slot-2` rather than `slot-13` (different identifier namespace).
- Conflict-resolution-id PFLC checks whether the system's emitted
  resolution slot id matches the gold target. `slot-13 ≠ slot-2`, so
  PFLC = `0`.

The fixture demonstrates that task-accuracy scoring on CR does not
imply the underlying memory-resolution contract is intact. A
downstream policy operation keyed on the gold slot id would fail.

## 8. Decision Call

Decision: **(b) descriptive-only**.

Rationale: MemoryAgentBench's Conflict_Resolution (CR) split is the
single most PFLC-aligned mechanism in any of the four anchor benchmarks
— contradiction resolution requires the memory-governance lookup
contract to be intact. However, the released schema does not expose a
fact-id / canonical-id / slot-id lookup target per question. The closest
fields (`qa_pair_ids` and `metadata.keypoints`) are not stable lookup
targets.

For this workstream, MemoryAgentBench is recorded as:

1. The case study illustrating the slot-id / conflict-resolution-id
   PFLC instance.
2. The benchmark whose CR/FactConsolidation mechanism is the strongest
   *design-level* PFLC analogue, even though its released artifacts do
   not currently support empirical scoring.
3. A future-work target: a preregistered fact-id annotation layer over
   CR / FactConsolidation would convert this memo's decision from
   "descriptive-only" to "empirical".

The BEAM promotion rule in the registration is **not** triggered by
this memo (the Mem0/LoCoMo memo also landed descriptive-only, not
blocked).

## 9. Relationship To Locked Artifacts

| Document | Relationship |
| --- | --- |
| `docs/policy_facing_lookup_contract_registration.md` | The locked registration this memo answers under. §6.1 anchor expectation is now resolved: descriptive-only. |
| `docs/policy_facing_lookup_contract_proposition.md` | Lemma 1 (retrieval-id) and a slot-id variant of the proposition are instantiated by §7. |
| `docs/canonical_id_resolution_audit_preregistration.md` §6 | The byte-locked CQR alias function. NOT inherited by the conflict-resolution-id PFLC instance. |
| `https://github.com/HUST-AI-HYZ/MemoryAgentBench` | MemoryAgentBench official repo and ICLR 2026 implementation. |
| `https://huggingface.co/datasets/ai-hyz/MemoryAgentBench` | Released dataset card and schema source. |
| `https://arxiv.org/abs/2507.05257` | MemoryAgentBench paper. |
