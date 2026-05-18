# Policy-Facing Lookup-Contract Diagnostics: Formal Proposition And Lemmas

Date: 2026-05-18

Status: registered formal artifact, locked alongside
`docs/policy_facing_lookup_contract_registration.md`. This document is the
load-bearing argument for the Workstream A.6 contribution; per-benchmark
feasibility memos, synthetic counterexamples, and any empirical scoring
reference it.

## 1. Purpose

This document gives the formal core of the policy-facing lookup-contract
(PFLC) diagnostic class. The thesis it supports is:

> Memory benchmarks can report strong recall, retrieval, or clustering
> scores while failing to expose the policy-facing lookup contract that
> memory-governance systems actually need.

The proposition (Section 3) is a proof for cluster-partition metrics. The
two lemmas (Sections 4 and 5) are existence proofs by construction for
retrieval-content and answer-accuracy metric classes. The corollary
(Section 6) collects the field-level claim.

This document does **not** propose a hard PFLC pass/fail threshold and
does **not** unlock, supersede, or amend any prior locked verdict in this
repo. See `docs/policy_facing_lookup_contract_registration.md` §5 for the
full forbidden list.

## 2. Notation

- `C_gold`: the gold cluster partition of evidence items in a benchmark
  instance. A partition is a set of disjoint clusters covering the items.
- `C_pred`: a predicted cluster partition over the same items.
- `L_gold`: the gold label space — the set of canonical identifiers
  assigned to gold clusters by the benchmark's reference annotation.
- `L_pred`: the predicted label space — the set of canonical identifiers
  assigned to predicted clusters by the system under evaluation.
- `q`: a query in the benchmark's evaluation set.
- `g* := relevant_canonical_id(q)`: the gold canonical identifier the
  benchmark requires the policy to resolve `q` against.
- `M_cluster(C_pred, C_gold)`: a cluster-partition metric over partitions
  only. Defined to be invariant under any label-renaming bijection that
  preserves the partition structure.
- `M_lookup(q, C_pred, L_pred)`: a query-resolvable lookup-contract metric
  requiring agreement between `g*` and predicted labels. Two variants
  matter:
  - **Set-membership** (this repo's QR-canon-exact): the check is
    `g* ∈ image(L_pred)`.
  - **Label-on-the-relevant-cluster**: the check is that `L_pred(c*) = g*`
    where `c*` is the predicted cluster the query resolves to.

## 3. Proposition 1 — Cluster-Partition / Lookup-Contract Gap

**Hypotheses.**

- `M_cluster` is invariant under label-renaming bijections that preserve
  the partition structure. B-cubed F1, adjusted Rand index, normalized
  mutual information, V-measure, and pairwise cluster F1 satisfy this
  property.
- The benchmark exposes at least one query target `g*` and the label
  space `L_gold` has size at least two.

**Proposition.** There exists a label-renaming function `ρ` over
`L_gold` such that:

1. `ρ(g*) ≠ g*` — the queried gold label is renamed; and
2. `g* ∉ image(ρ)` — the renamed label space does not include `g*`.

Define `L_pred := ρ ∘ L_gold` and `C_pred := C_gold`. Under this
construction:

- `M_cluster(C_pred, C_gold) = 1.00`, because the predicted partition is
  identical to the gold partition and `M_cluster` ignores label identity.
- `M_lookup(q, C_pred, L_pred) = 0`:
  - for set-membership PFLC, because the check `g* ∈ image(L_pred)` is
    false by condition (2);
  - for label-on-the-relevant-cluster PFLC, because the label attached to
    `c*` is `ρ(g*) ≠ g*` by condition (1).

**Proof sketch.** Existence of `ρ` follows from the label-space-size
hypothesis. Pick any label `ℓ ∈ L_gold` with `ℓ ≠ g*` and set
`ρ(g*) := ℓ`. Complete `ρ` to a bijection on `L_gold ∖ {g*}` whose image
avoids `g*` — for example, by mapping `L_gold ∖ {g*}` into a fresh
namespace disjoint from `{g*}`. `M_cluster = 1.00` follows from
label-renaming invariance applied to identical partitions. The lookup
metric value follows from the two conditions on `ρ`.

For the stronger label-on-the-relevant-cluster PFLC variant, condition
(1) alone suffices: even if `g*` is reused somewhere else in `image(ρ)`,
the label attached to the queried cluster `c*` is not `g*`.

**Worked example.** The existing internal CQ synthetic counterexample
in `scripts/run_qr_canon_audit.py` (lines 178–207) instantiates exactly
this construction:

- gold partition: events `e1`, `e2` in one cluster, labeled `gold-X`;
- predicted partition: the same one cluster, labeled `pred-Y`;
- query target: `g* = gold-X`;
- renaming: `ρ(gold-X) = pred-Y`, with `pred-Y ≠ gold-X` and
  `gold-X ∉ {pred-Y}` — both conditions hold.

The fixture scores B-cubed F1 = 1.00 (perfect partition agreement) and
QR-canon exact = 0.00 (set-membership PFLC fails). This counterexample
exists by construction in the repo today; reproducibility is enforced by
`tests/test_qr_canon_audit.py`.

## 4. Lemma 1 — Retrieval-Content / Retrieval-Id Gap

**Hypotheses.**

- `M_retrieval` is a retrieval@k metric whose score is determined by the
  content of retrieved items only — BM25 overlap, embedding similarity,
  exact text match, or judge agreement on retrieved snippets all
  satisfy this.
- The policy under evaluation keys its lookup on a stable retrieval
  identifier — slot id, doc id, or canonical id — distinct from the
  content itself.

**Lemma (existence).** There exists a benchmark instance and a system
output where `M_retrieval = 1.00` (the gold content is retrieved at
rank ≤ k) while the corresponding retrieval-id PFLC = 0 (the identifier
attached to the retrieved item disagrees with the policy's required
lookup identifier).

**Proof by construction.** Fix a gold evidence span `c` keyed in the
benchmark as `slot-A`. Let the system retrieve the same content `c` but
emit it under retrieval identifier `slot-B ≠ slot-A`. Content-based
`M_retrieval` is invariant to the identifier: it scores 1. Retrieval-id
PFLC, which checks identifier agreement against `slot-A`, scores 0.

This is the MemoryAgentBench/MemBench-shaped fixture in the per-benchmark
synthetic counterexamples (see
`docs/policy_facing_lookup_contract_registration.md` §3).

## 5. Lemma 2 — Answer-Text / Lookup-Handle Gap

**Hypotheses.**

- `M_answer` is an answer-accuracy metric whose score is determined by
  judge agreement, normalized text match, or exact-string match against
  a reference answer.
- The policy under evaluation depends on resolving a canonical lookup
  handle (canonical id, slot id, or other policy-internal identifier) to
  reach the correct internal state for downstream actions.

**Lemma (existence).** There exists a benchmark instance and a system
output where `M_answer = 1.00` (the answer text scores as correct) while
the canonical lookup handle PFLC = 0 (the policy's required canonical
identifier is unresolved).

**Proof by construction.** Fix a benchmark instance where a transcript
exposes an updated value `v_new` (e.g., a correction or knowledge update)
through two distinct sessions whose canonical update slots in the gold
annotation diverge — say `update_gold_X` for the gold slot and
`update_pred_Y` for whatever slot the system happens to write. The
benchmark's answer-text judge sees `v_new` and scores `M_answer = 1`. A
downstream policy operation keyed on `update_gold_X` does not find a
matching durable handle in the system's state, so canonical-id PFLC
scores 0.

This is the LongMemEval-shaped fixture in the per-benchmark synthetic
counterexamples (see
`docs/policy_facing_lookup_contract_registration.md` §3).

## 6. Corollary

No cluster-partition metric, content-based retrieval metric, or
text-based answer-accuracy metric is sufficient evidence of policy-facing
lookup-contract success. Any persistent-memory benchmark whose policy
comparison depends on a lookup contract must report a PFLC diagnostic
alongside its headline metric.

## 7. What This Document Does Not Claim

- **Not a pass/fail threshold.** PFLC instances are required diagnostics
  alongside clustering/retrieval/accuracy metrics, never gates.
- **Not a claim about extractor semantic quality.** Counterexamples
  show interface-level gaps; they do not establish whether the
  underlying extraction is semantically wrong.
- **Not a noisy-mode CQ policy claim.** The proposition and lemmas are
  policy-agnostic; they apply to any system whose lookup is keyed on
  identifiers.
- **Not an unlock or amendment of any prior locked verdict.** The
  locked CQR audit's Bucket D remains Bucket D; the Phase 4 noisy
  comparison's Bucket B remains Bucket B; the QR-canon audit's
  registered post-hoc reattribution remains the registered post-hoc
  reattribution.

## 8. Relationship To Locked Artifacts

| Document | Relationship |
| --- | --- |
| `docs/canonical_id_resolution_audit_preregistration.md` §6 | Source of the byte-locked CQR alias function (SHA256 fixed). The PFLC registration references this alias function for QR-canon (normalized). No modification permitted by this workstream. |
| `docs/qr_canon_audit_registration.md` | Source of the canonical-id PFLC instance and its reproducibility contract. This proposition document generalizes the proposition that audit's synthetic counterexample already instantiates. |
| `docs/qr_canon_audit_results.md` | The five-of-seven Phase 4 rows that motivate the field-level diagnostic. Unchanged by this workstream. |
| `scripts/run_qr_canon_audit.py:178-207` | Existing implementation of the internal worked example for Proposition 1. Unchanged by this workstream. |
| `tests/test_qr_canon_audit.py` | Existing 17 tests that enforce reproducibility of the internal counterexample. Must remain green byte-stable. |
| `docs/policy_facing_lookup_contract_registration.md` | The registration document that locks the workstream contract and references this proposition as its load-bearing claim. |
