# LongMemEval Feasibility Memo

Date: 2026-05-17

Decision: **descriptive-only future work**.

This memo decides whether LongMemEval can be used as a transfer probe for the
mechanism-local CQ result without violating this repository's same-candidate-
stream and same-substrate fairness invariants. It is a feasibility artifact,
not a policy run. No CQ, ReflectionEagerWrite, or `Mem0Lite` policy is executed
against LongMemEval here.

Primary LongMemEval sources reviewed before coding:

- Paper: [LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory](https://arxiv.org/abs/2410.10813)
- Official repository: [xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval)
- Official cleaned dataset listing: [xiaowu0162/longmemeval-cleaned](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/tree/main)

Dataset inspected for the denominator pass:

- `longmemeval_oracle.json`, downloaded from the official cleaned Hugging Face
  release on 2026-05-17
- bytes: `15388478`
- SHA256: `821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c`
- frozen-rule memo SHA before opening case contents:
  `bbe6a0981c07a869a22d09f13fb09e37cdfb6f85ff0a23732420934fd4e3a54d`

## 1. Task Design Survey

LongMemEval is a 500-question long-term chat-assistant memory benchmark. Its
published task structure covers five memory abilities: information extraction,
multi-session reasoning, knowledge updates, temporal reasoning, and abstention.
The released files include three benchmark variants:

| File | Operational meaning |
| --- | --- |
| `longmemeval_s_cleaned.json` | full LongMemEval-S histories, roughly 40 sessions / 115k tokens per instance |
| `longmemeval_m_cleaned.json` | full LongMemEval-M histories, roughly 500 sessions / 1.5M tokens per instance |
| `longmemeval_oracle.json` | oracle-retrieval variant containing only evidence sessions |

Each instance contains `question_id`, `question_type`, `question`, `answer`,
`question_date`, `haystack_session_ids`, `haystack_dates`,
`haystack_sessions`, and `answer_session_ids`. The official question types are
`single-session-user`, `single-session-assistant`,
`single-session-preference`, `temporal-reasoning`, `knowledge-update`, and
`multi-session`; question ids ending in `_abs` are abstention questions.

Operationally, LongMemEval is a transcript-derived memory benchmark. It does
not provide a system-controlled candidate stream comparable to CQ's
`CandidateUpdate` stream. Its own memory-system formulation is an indexing,
retrieval, and reading pipeline over timestamped history sessions. Its released
oracle split is oracle retrieval, not an oracle memory-governance candidate
stream: it includes evidence sessions, but does not label durable writes,
contradiction edges, source independence, policy scopes, or canonical slots in
the format required by this repo's policies.

Evaluation is question-answering correctness, using a model judge in the
official harness, plus optional retrieval metrics (`Recall@k`, `NDCG@k`) when a
system exposes retrieved sessions or turns. The official retrieval evaluation
skips abstention instances because they do not have ground-truth answer
locations.

## 2. Pre-Policy Coding Rule

This rule is frozen before opening any individual LongMemEval case from the
downloaded oracle split. The candidate slice is the full 500-instance
`longmemeval_oracle.json` file, because choosing a smaller slice after seeing
case contents would make the transfer denominator negotiable.

### Mechanism Labels

`contradiction_edge`
: A case where the transcript itself contains an explicit later correction or
  contradiction of an earlier user-relevant fact, preference, answer, or state,
  and the final question requires the memory system to prefer the corrected
  state. This is the only clean internal Bucket B transfer target.

`preference_correction`
: A case where the user preference or standing instruction changes, is refined,
  or is overridden by a later preference statement, and the final question
  requires using the updated preference rather than the older one. This is a
  secondary target because internal `preference_drift` survival is partial.

`dated_contradiction_boundary`
: A case where two time-indexed statements conflict or supersede each other
  and temporal metadata is necessary to choose the current or appropriate
  answer. This is a boundary probe only. `CQDatedContestation` repaired base
  CQ's oracle temporal-skew failure, but it did not clear a CQ-vs-Reflection
  win criterion.

`out_of_scope`
: Any case that does not qualify under the three labels above, including pure
  recall, multi-hop aggregation without update pressure, assistant-side recall,
  source-identity/source-independence reasoning, false-premise abstention,
  poisoning/trust reasoning, useful-pending-memory analogues, and cases that
  would require a richer substrate than CQ and Reflection share.

### Inclusion Criteria

A case may receive one of the first three labels only if all of the following
are visible from surface case fields (`question_type`, `question`, `answer`,
`question_date`, `haystack_dates`, `haystack_sessions`) without running any
policy:

1. The answer depends on a user- or assistant-history fact that appears in the
   evidence sessions, not on reference-answer text injected into policy input.
2. The needed evidence can be represented as one or more scoped
   `CandidateUpdate`-like observations using this repo's existing shared
   substrate fields: claim type, scope level/key, canonical id, confidence,
   source id, event id, timestamp, support/contradiction relation.
3. The distinguishing mechanism is update/correction/temporal supersession,
   not only retrieval breadth, answer synthesis, or semantic paraphrase.

### Exclusion Criteria

A case is `out_of_scope` if any of the following apply:

1. It is an abstention case (`question_id` ends with `_abs`), because the
   official retrieval metric has no answer-location denominator and this repo's
   Phase 4 transfer hypothesis is contradiction-like policy survival, not
   false-premise abstention.
2. It requires source-identity or source-independence reasoning not present in
   LongMemEval's released fields.
3. It requires aggregating unrelated facts across sessions without a correction
   or contradiction boundary.
4. It requires retaining assistant recommendations or previous assistant-side
   content as durable memory without a user-state update.
5. It can only be evaluated by feeding the full reference answer, evidence
   labels, or judge rubric into the policy input.
6. It cannot be represented in the shared scoped substrate without adding a
   CQ-only private memory representation.

### Coding Protocol

1. Label every case in the 500-instance oracle split once under the frozen rule.
2. Use `question_id`, `question_type`, `question`, `answer`, `question_date`,
   `haystack_dates`, and evidence-session text for coding.
3. Do not inspect policy outputs, do not run a CQ/Reflection/`Mem0Lite` policy,
   and do not modify prompts, thresholds, validators, adapters, policies, or
   storage.
4. Report the denominator exactly as the coding rule produces it, including
   zero or near-zero rows.
5. If more than one positive label appears plausible, prefer the most
   policy-specific label in this order: `contradiction_edge`,
   `preference_correction`, `dated_contradiction_boundary`, then
   `out_of_scope`.

## 3. Mechanism Mapping Under The Frozen Rule

The coding pass labels the full 500-instance oracle split once under §2.
Abstention cases are excluded before mechanism assignment because their
question ids end in `_abs` and the official retrieval metric has no answer
location denominator for them.

### Dataset Shape

| `question_type` | Total | Abstention | Non-abstention | Coding read |
| --- | ---: | ---: | ---: | --- |
| `knowledge-update` | 78 | 6 | 72 | update/correction candidates |
| `multi-session` | 133 | 12 | 121 | aggregation without a CQ-supported policy mechanism |
| `single-session-assistant` | 56 | 0 | 56 | assistant-side recall |
| `single-session-preference` | 30 | 0 | 30 | preference use without correction |
| `single-session-user` | 70 | 6 | 64 | single-fact recall |
| `temporal-reasoning` | 133 | 6 | 127 | time comparison without correction/contestability |

### Frozen-Rule Labels

| Label | Count | Source under rule | Interpretation |
| --- | ---: | --- | --- |
| `contradiction_edge` | 72 | non-abstention `knowledge-update` | feasible transfer denominator in principle: each case asks for an updated value after earlier evidence |
| `preference_correction` | 0 | none | `single-session-preference` cases use preferences but do not expose a later correction boundary |
| `dated_contradiction_boundary` | 0 | none | temporal cases require date reasoning, but the official type is not a dated contradiction / supersession lane under §2 |
| `out_of_scope` | 428 | all remaining cases | pure recall, aggregation, assistant-side recall, preference use, false-premise abstention, or unsupported mechanisms |

Every non-abstention `knowledge-update` case has exactly two oracle evidence
sessions. That gives LongMemEval a real correction/update denominator, but not
yet a CQ-compatible policy denominator: the released fields identify evidence
sessions and answer text, not candidate identities, contradiction edges, or
question-to-canonical-slot mappings.

Representative `contradiction_edge` examples from the coding pass:

| `question_id` | Question | Answer |
| --- | --- | --- |
| `6a1eabeb` | What was my personal best time in the charity 5K run? | `25 minutes and 50 seconds (or 25:50)` |
| `830ce83f` | Where did Rachel move to after her recent relocation? | `the suburbs` |
| `89941a93` | How many bikes do I currently own? | `4` |
| `ce6d2d27` | What day of the week do I take a cocktail-making class? | `Friday` |

The correct readout is therefore mixed: LongMemEval does contain a nontrivial
update/correction denominator, but the denominator is not automatically a
fair-policy benchmark for CQ.

## 4. Fairness-Invariant Feasibility

| Feasibility question | Readout | Reason |
| --- | --- | --- |
| Can LongMemEval's transcript stream be transformed into a shared `CandidateUpdate` stream that CQ, Reflection, and `Mem0Lite` consume identically? | **No for the current plan; possible only as a new annotation/adapter workstream.** | The released oracle split contains evidence sessions and answer labels, but no CQ-style candidate ids, canonical ids, scopes, source ids, confidence scores, support edges, or contradiction edges. A future extractor or manual coding layer could create such a stream, but that would be new benchmark construction and must be preregistered and component-scored before policy execution. |
| Can the shared scoped substrate be preserved across policies on LongMemEval inputs? | **Conditionally yes, after a valid candidate stream exists.** | The 72 update/correction cases appear representable in the existing shared substrate as scoped observations with timestamps and later supersession. They do not require a richer CQ-only memory representation. The blocker is upstream stream construction, not storage. |
| Can the policy-query interface be made consistent with the Phase 4 adapter contract? | **No under current artifacts.** | LongMemEval questions and answers do not expose `relevant_canonical_id` or a policy lookup key. Deriving a lookup key from the reference answer or `has_answer` labels would leak answer-side information into the policy interface. Deriving it from the question requires exactly the policy-facing canonical-id/query-resolution contract that remains unsettled in the Phase 4 null rows. |

The first and third answers are enough to block a preregister-and-run decision
under this plan. The benchmark has plausible transfer cases, but the current
repo does not have a fair, locked way to feed those cases into all policies as
the same upstream candidate stream and the same policy-query interface.

## 5. Metric Mapping

| Phase 4 metric | LongMemEval analogue | Mapping decision |
| --- | --- | --- |
| `answer_correctness` | official QA correctness judged from `question`, `answer`, and system `hypothesis` | Direct analogue for a future run, with the caveat that the official harness uses an API judge by default and this repo is local-first unless explicitly changed |
| `false_assertion_rate` | no direct official field | Requires a separate answer taxonomy distinguishing wrong assertions, abstentions, and non-answers. LongMemEval's QA correctness alone is insufficient. |
| `contradiction_recovery_rate` | no direct official field | Requires additional labels over the 72 `knowledge-update` cases: earlier value, later value, contradiction/supersession edge, and whether the policy answer tracks the later value. |
| `scope_leakage_rate` | no direct official field | Not available from released fields without a new scope annotation layer. |
| `poison_promotion_rate` | no analogue | Out of scope; LongMemEval does not label trusted/untrusted poison events. |
| `premature_promotion_rate` | no direct official field | Not available without durable-write lifecycle expectations, which LongMemEval does not provide. |
| retrieval `Recall@k` / `NDCG@k` | official optional memory-recall metrics | Useful for LongMemEval system comparison, but not a Phase 4 primary policy metric and not sufficient for CQ-vs-Reflection policy separation. |

Only `answer_correctness` maps cleanly. The policy-specific metrics that made
the internal comparison interpretable would need new annotations before any
claim stronger than descriptive QA transfer.

## 6. Failure-Interpretation Rules

If a future workstream creates a valid LongMemEval-CQ adapter and preregisters a
run, the following interpretation rules should be locked before execution:

1. `contradiction_edge` transfer requires the same sign as Phase 4
   `forced_contradiction`: CQ must improve over Reflection on the primary
   correction metric, with a one-sided lower confidence bound above zero. If
   only `answer_correctness` is available, the result is descriptive QA
   transfer, not full contradiction-recovery transfer.
2. `preference_correction` partial transfer requires a positive CQ-vs-Reflection
   direction on the preference-correction subset, but may be framed only as
   partial unless exact canonical-id/query alignment and claim/scope labels are
   clean enough to expose the same mechanism as internal `preference_drift`.
3. `dated_contradiction_boundary` cannot support a CQ-over-Reflection claim
   from the existing internal evidence. At most, it can report whether a dated
   contradiction mechanism is present and policy-distinguishable from
   `Mem0Lite`-style dated overwrite weakness.
4. A null row means: mechanism cases exist, but the shared noisy stream or
   policy-query interface does not expose CQ-vs-Reflection separation. It must
   not be upgraded into an extractor-floor or policy-failure explanation
   without a preregistered adapter/diagnostic audit.
5. Kill criteria for a future run: no locked candidate stream, no locked query
   canonical-id mapping, answer-label leakage into policy inputs, no
   per-mechanism denominator, or a need for CQ-only memory fields.

## 7. Decision Call

Decision: **(b) descriptive-only future work**.

LongMemEval should not be preregistered and run against CQ, Reflection, and
`Mem0Lite` yet. The coding pass found 72 plausible update/correction cases, so
the external benchmark is relevant to the internal contradiction-survival
thesis. However, the fairness invariants are not preserved by the released
LongMemEval artifacts:

- there is no shared `CandidateUpdate` stream
- there are no contradiction edges or canonical slots
- there is no policy-query `relevant_canonical_id` equivalent
- using answer/evidence labels to build the policy input would leak oracle
  answer information

The correct next step is not a LongMemEval policy run. It is either:

1. a separate LongMemEval adapter/annotation preregistration that creates a
   candidate stream, canonical-id query contract, and metric labels before any
   policy execution; or
2. the already licensed policy-facing adapter-contract audit / fresh Phase 4
   baseline path for the current benchmark null rows.

Until one of those exists, LongMemEval belongs in the report as an external
transfer limitation and future-work target, not as evidence for CQ.
