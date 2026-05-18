# LongMemEval — PFLC Feasibility Memo

Date: 2026-05-18

Decision: **descriptive-only**.

Named PFLC instance: **answer-handle PFLC** — the canonical lookup handle the
policy would need to resolve to internally, distinct from the answer text the
LongMemEval judge scores.

This memo is a PFLC-specific wrapper over the existing
`docs/longmemeval_feasibility_memo.md` (2026-05-17) and the committed
per-case coding artifact
`data/results/longmemeval_feasibility_coding.csv`. It does **not** open
new LongMemEval case contents or run a new coding pass. The 72
`knowledge-update` / `contradiction_edge` denominator established on
2026-05-17 is reused verbatim.

## 1. Task-Design Survey

LongMemEval (arXiv:2410.10813) is a 500-question long-term chat-assistant
memory benchmark covering information extraction, multi-session reasoning,
knowledge updates, temporal reasoning, and abstention. Released split shapes
are documented in `docs/longmemeval_feasibility_memo.md` §1.

Per-instance fields: `question_id`, `question_type`, `question`, `answer`,
`question_date`, `haystack_session_ids`, `haystack_dates`,
`haystack_sessions`, `answer_session_ids`. Question ids ending in `_abs`
are abstention questions.

Headline evaluation metric: QA-correctness judged from `question`, `answer`,
and a system `hypothesis`, with the official harness using a model judge by
default. Retrieval metrics (`Recall@k`, `NDCG@k`) are optional auxiliaries
that apply only when a system exposes retrieved sessions or turns.

## 2. Pre-Policy Coding Rule

Reused verbatim from `docs/longmemeval_feasibility_memo.md` §2. No new
coding pass.

Frozen labels under the 2026-05-17 rule:

- `contradiction_edge`
- `preference_correction`
- `dated_contradiction_boundary`
- `out_of_scope`

The 2026-05-17 workflow checkpoint SHA over the initial skeleton is
`bbe6a0981c07a869a22d09f13fb09e37cdfb6f85ff0a23732420934fd4e3a54d`
(recorded for workflow discipline at the original memo's commit time).
The per-case coding CSV SHA256 is
`d8932f39a4006ce6b0d98adbef0b013fd912129b873d8cebf4491673cd3e46e3`.

## 3. Mechanism Mapping Under The Frozen Rule

Reused from `docs/longmemeval_feasibility_memo.md` §3. The relevant
denominator for this workstream:

| Label | Count | Source |
| --- | ---: | --- |
| `contradiction_edge` | 72 | non-abstention `knowledge-update` cases |
| `preference_correction` | 0 | excluded by inclusion criterion 3 |
| `dated_contradiction_boundary` | 0 | excluded by inclusion criterion 3 |
| `out_of_scope` | 428 | all remaining cases |

Every non-abstention `knowledge-update` case has exactly two oracle evidence
sessions. That gives LongMemEval a real correction/update denominator —
useful as a descriptive comparison surface for the PFLC contribution — but
not yet a CQ-compatible policy denominator. The shortfall is identified in
the original memo's §4.

## 4. Fairness-Invariant Feasibility For PFLC

The original memo identified three fairness blockers for any future policy
run. For PFLC scoring specifically, the relevant question is narrower: does
the released split expose a per-question lookup target that a memory-
governance policy would be required to resolve, without leaking the
reference answer into policy input?

| Question | Readout | Reason |
| --- | --- | --- |
| Does LongMemEval expose a per-question canonical-id / lookup-handle target? | **No** | The released fields are `question_id`, `question_type`, `question`, `answer`, `question_date`, `haystack_session_ids`, `haystack_dates`, `haystack_sessions`, `answer_session_ids`. The `answer` field is free-text — not a stable identifier the policy could be evaluated against without judge intervention. |
| Could a lookup target be derived from released fields without answer leakage? | **No** | Deriving a canonical-id target from `answer` text would leak reference answer information into the policy interface. Deriving one from the question alone requires the policy-facing canonical-id/query-resolution contract that this repo's CQR audit could not settle (two Bucket D aborts in `docs/canonical_id_resolution_audit_results.md`). |
| Does a published system output expose system-emitted memory identifiers per question? | **No, not in released LongMemEval artifacts** | The official harness scores QA correctness from a system `hypothesis` text; published baselines do not expose canonical or memory ids per question that could be checked against a target. |
| Does the released artifact admit a per-question paired clustering or canonicalization metric? | **No** | LongMemEval reports QA correctness and optional retrieval `Recall@k`/`NDCG@k`. Neither is a clustering-quality canonicalization metric. |

The PFLC empirical path is therefore blocked by the same fairness invariants
that blocked the policy-comparison feasibility on 2026-05-17.

## 5. Metric Mapping For PFLC

| PFLC component | LongMemEval analogue | Mapping decision |
| --- | --- | --- |
| Lookup target (`relevant_canonical_id`-equivalent) | reference `answer` text | not a stable identifier; deriving an id from answer text would leak oracle info |
| System-emitted identifier (`extracted_canonical_ids`-equivalent) | not released | not exposed in standard LongMemEval system outputs |
| Paired clustering / canonicalization metric (`row_canonicalization_b_cubed_f1`-equivalent) | not released | LongMemEval does not report clustering-quality canonicalization |
| Paired retrieval metric | `Recall@k`, `NDCG@k` (optional) | published only when systems opt in; would not pair against a PFLC instance because there is no lookup target |
| Paired answer-accuracy metric | overall QA correctness | this is the headline metric. It maps to the answer-handle PFLC's *headline-side*, not its *lookup-side*. |

## 6. Failure-Interpretation Rules

For LongMemEval specifically under this workstream:

1. A null PFLC row would mean that the released LongMemEval interface does
   not expose the policy-lookup contract — exactly the structural finding
   already on record. It cannot be re-interpreted as evidence about
   semantic extractor quality.
2. The 72 `contradiction_edge` denominator is a descriptive comparison
   surface only. It cannot be promoted to a CQ-vs-Reflection-vs-`Mem0Lite`
   transfer claim from this workstream; a separate adapter/annotation
   preregistration would be required first.
3. The synthetic counterexample (§7) does **not** depend on any LongMemEval
   coding or any LongMemEval case content. It is a constructive
   demonstration of Lemma 2 from
   `docs/policy_facing_lookup_contract_proposition.md`.

## 7. Synthetic Counterexample (Answer-Handle PFLC)

Tied to LongMemEval's headline metric (overall_accuracy under a judge),
this counterexample lands as a shipped fixture row in
`data/results/qr_canon_field_diagnostic_metrics.csv` under
`row_kind = synthetic_longmemeval_counterexample` when that artifact lands.

Construction (per `docs/policy_facing_lookup_contract_proposition.md`
Lemma 2):

- A LongMemEval-shaped instance with two evidence sessions exposing an
  updated value `v_new` (a knowledge-update / correction).
- Gold annotation assigns canonical update slot `update_gold_X` to the
  later session.
- A system's memory write places `v_new` under `update_pred_Y`, where
  `update_pred_Y ≠ update_gold_X`.
- The system's emitted answer text is `v_new`, identical to the reference
  answer.
- LongMemEval's overall_accuracy judge sees the correct answer text and
  scores `1.0`.
- Answer-handle PFLC checks whether the system's canonical lookup handle
  matches the gold slot. The system's handle is `update_pred_Y`; the gold
  slot is `update_gold_X`; the check fails, so PFLC = `0`.

This fixture is benchmark-targeted but does not depend on LongMemEval case
contents. It instantiates Lemma 2 directly.

## 8. Decision Call

Decision: **(b) descriptive-only**.

Rationale: LongMemEval is highly relevant to the workstream — it's the
canonical external memory benchmark and has a meaningful update/correction
denominator — but its released artifacts do not expose a per-question
lookup target nor system-emitted canonical identifiers without leaking
reference-answer information into policy input. The fairness blockers
identified on 2026-05-17 still hold.

For this workstream, LongMemEval is recorded as:

1. The case study illustrating Lemma 2 (answer-text / lookup-handle gap),
   instantiated through the synthetic counterexample in §7.
2. The descriptive denominator (72 contradiction-edge cases) that any
   future LongMemEval adapter would need to fairly score against, with
   PFLC required as part of that adapter's contract.

Future LongMemEval work is **not licensed** by this memo. A future
LongMemEval adapter/annotation preregistration would need to (a) create a
candidate stream and policy-query canonical-id contract, (b) establish a
PFLC target before any policy execution, and (c) keep the answer-handle
PFLC instance distinct from QA-text correctness so the Bucket B
mechanism-local distinction this repo already supports is preserved.

## 9. Relationship To Locked Artifacts

| Document | Relationship |
| --- | --- |
| `docs/policy_facing_lookup_contract_registration.md` | The locked registration this memo answers under. |
| `docs/policy_facing_lookup_contract_proposition.md` | Lemma 2 instantiated by §7. |
| `docs/longmemeval_feasibility_memo.md` | Source of §1–§3 content reused verbatim. No new coding pass. |
| `data/results/longmemeval_feasibility_coding.csv` | 500-case coded denominator referenced in §3. |
| `docs/canonical_id_resolution_audit_results.md` | The two Bucket D aborts cited in §4 as the structural reason answer-leakage cannot be substituted. |
| `docs/qr_canon_audit_results.md` | The four Phase 4 null rows already reattributed to "policy-facing query interface contract failure" — same family of failure mode as the LongMemEval blocker named here. |
