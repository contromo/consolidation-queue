# Fair-Stream Externalization Preregistration

Date: 2026-05-18

Status: locked before annotation, adapter execution, or policy execution.

fair_stream_externalization_lock_sha256: 0edf74633d8129a9b043dffce0eb76aa46356fcadf2ea2dc5628a039a81c2c56

This preregistration defines a protocol-level externalization methodology for
memory benchmarks. The policy readout is a supporting experiment only. The
headline contribution is the reusable protocol: shared candidate stream,
hidden-answer annotation, policy-facing lookup contract, PFLC scoring, and
abort discipline.

The Phase X.-1 anchor gate is
`docs/longmemeval_externalization_anchor_gate.md`. It selects LongMemEval v1 as
the primary controlled-pilot anchor and demotes LongMemEval-V2 to descriptive
evidence-exposure work because V2's public release strips the gold-side
answer-bearing annotation labels needed for matched PFLC scoring.

<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_START -->
## 1. Scope And Invariants

The scientific question is whether an external memory benchmark can be adapted
into a fair same-stream memory-policy comparison without giving any policy
private fields, better extraction inputs, or a different storage substrate.

Load-bearing invariants:

- every policy consumes the same `CandidateUpdate` stream;
- CQ, ReflectionEagerWrite, `Mem0Lite`, ablations, and floor baselines use the
  same scoped `MemoryStore` substrate;
- oracle-mode, noisy-mode, and externalization claims stay separate;
- answer labels and gold evidence labels are never used to build policy input;
- saved artifacts expose annotation inputs, agreement/divergence, adapted
  candidate streams, stream hashes, policy traces, PFLC rows, metrics, and
  manifests;
- disagreements between annotation paths are audited and dropped from the
  agreed policy denominator, not patched after inspection.

Out of scope:

- prompt, threshold, validator, schema, or policy changes after any annotation,
  smoke, or policy result is visible;
- new mechanism families;
- 70B routing;
- promoting BEAM beyond survey-only without a separate registered amendment;
- using LongMemEval-V2 for gold PFLC unless a future registered amendment
  obtains gold-side evidence identifiers;
- claiming CQ generalizes broadly from a narrow LongMemEval denominator.

## 2. Anchor And Denominator

Primary anchor: LongMemEval v1 oracle controlled pilot.

Primary denominator before dual-path filtering: the 72 non-abstention
`knowledge-update` cases coded as `contradiction_edge` in
`data/results/longmemeval_feasibility_coding.csv` and documented in
`docs/longmemeval_feasibility_memo.md`.

The 72-case denominator is not automatically a policy denominator. It becomes a
policy denominator only after both independent annotation paths agree on:

- `relevant_canonical_id`;
- contradiction-edge structure;
- scope level/key;
- candidate stream construction sufficient for all compared policies.

LongMemEval-V2 role: descriptive evidence-exposure appendix only in this
workstream. It is not a primary policy anchor and not a matched gold PFLC row.

## 3. Externalization Adapter Contract

An externalization adapter must produce:

- one scenario per agreed in-denominator case;
- OBSERVATION events carrying shared `CandidateUpdate` records;
- one final QUESTION event carrying a `QuestionSpec`;
- `candidate_stream_sha256` for every scenario;
- `candidate_ids_by_event_id` and dropped-row audit details;
- a candidate-stream hash invariant report across CQ, ReflectionEagerWrite,
  and `Mem0Lite`;
- a byte-stable adapter pin tying the adapter SHA to this preregistration lock.

Candidate fields follow the shared `CandidateUpdate` dataclass:

- required fields: `candidate_id`, `raw_text`, `raw_claim`, `canonical_claim`,
  `claim_type`, `scope_level`, `scope_key`, `created_at`, `updated_at`;
- explicit optional fields: `canonical_id`, `provenance`,
  `verification_score`, `contradicts`, `supports`;
- no CQ-only fields are permitted;
- `strength` and `promotion_score` are computed by `CandidateUpdate`, not set
  privately by the adapter.

Contradictions are constructed from event-level contradiction edges and fanned
out to emitted candidate ids after candidate id rewriting. Candidate stream
hashes must match across policies for every scenario. A mismatch aborts Bucket
D before policy scoring.

## 4. Hidden-Answer Annotation Protocol

Both annotation paths load LongMemEval through
`cq.eval.external.longmemeval.redacted_loader`, which replaces `answer` and
`answer_session_ids` with hash-only redactions at load time. Attempting to read
those fields raises an exception.

Path A: locked local-model path, intended to use the existing
`qwen2.5:32b-instruct-q4_K_M` local model cell plus a frozen question/evidence
prompt and a slugify-over-question-noun-phrase canonical-id rule.

Path B: independent deterministic or smaller-local-model path with a different
canonical-id derivation rule. It must not share canonical-id derivation code
with Path A and must not introduce new runtime dependencies without explicit
user authorization.

Path outputs are compared by
`cq.eval.external.longmemeval.dual_path_audit` per case. Cases are labeled:

- `agree`;
- `disagree_canonical_id`;
- `disagree_contradiction_edges`;
- `disagree_scope`;
- `missing_path_a`;
- `missing_path_b`.

Only `agree` cases enter `annotations_agreed.json`. Disagreement rows remain
in the divergence report and are never patched silently.

## 5. Scope Mapping And Contract Sensitivity

Primary scope mapping: per LongMemEval `question_type`, with
`knowledge-update` mapped to `USER_GLOBAL` unless the annotation path assigns a
more specific preregistered scope from question-only evidence.

Scope-heterogeneity cap: if the agreed annotations contain more than two
distinct `ScopeLevel` values and the preregistered mapping table did not fire,
abort Bucket D.

Sensitivity cells are locked now and must be run in the same preregistered
policy comparison, not after inspecting the primary result:

- primary canonicalizer plus primary scope mapping;
- alternate canonicalizer plus primary scope mapping;
- primary canonicalizer plus flat `USER_GLOBAL` scope mapping;
- primary contract on Path A-only denominator;
- primary contract on Path B-only denominator.

Any headline CQ-vs-Reflection sign flip across cells downgrades to Bucket C.

## 6. PFLC Target And Metrics

Primary PFLC target: dialog-evidence-id PFLC keyed on LongMemEval v1
`answer_session_ids`. These ids are scoring targets only; they must not be
available to policy input or annotation logic before freeze.

PFLC cutoffs: `1`, `5`, `10`, `20`, `50`.

Policy metrics:

- `answer_correctness`;
- `contradiction_recovery_rate`;
- `false_assertion_rate`;
- dialog-evidence-id PFLC at the locked cutoffs;
- fixed-seed paired bootstrap CIs for CQ-vs-Reflection and CQ-vs-`Mem0Lite`.

Judge/scoring default: local `qwen2.5:32b-instruct-q4_K_M`, reusing the Phase 4
local unlock digest discipline. Published judge logs are preferred for
calibration if they exist. If no published logs exist, use a local cross-judge
stability check against the locked 7B anchor. API calibration requires explicit
user authorization and a cost manifest before any call.

Calibration kill criterion: if the selected judge path fails agreement
`>= 0.85` on the locked 20-case subset, escalate to the user before any policy
run.

## 7. Policies

The locked comparison set mirrors `phase2_5` where compatible:

- `consolidation_queue_lite`;
- `reflection_eager_write_lite`;
- `mem0_lite`;
- `cq_no_contestation_demotion`;
- `cq_no_wider_scope_pending_override`;
- `cq_no_pending_lookup_use`;
- `cq_no_source_independence_gate`;
- `naive_eager_write_lite`;
- `no_memory_lite`.

`ScopeBlindTranscriptRAGLite` is excluded from primary externalization buckets
unless a separately registered retrieval-contract cell is added. It has a
different retrieval interface from the shared candidate-stream policy question.

## 8. Kill And Downgrade Criteria

Bucket D aborts:

1. no locked candidate stream;
2. no locked query canonical-id mapping;
3. answer-label leakage into policy inputs;
4. no per-mechanism denominator;
5. need for CQ-only memory fields;
6. candidate stream SHA mismatch across CQ, ReflectionEagerWrite, or
   `Mem0Lite`;
7. scope-heterogeneity cap violation;
8. judge validation fails and the user does not authorize a registered
   fallback.

Bucket C downgrades:

1. dual-path divergence exceeds 25 percent on in-denominator cases;
2. dual-path-agreed denominator falls below 50 cases;
3. paired-bootstrap CI width exceeds 0.30 on the headline policy metric;
4. contract-sensitivity cells sign-flip or destabilize the headline
   CQ-vs-Reflection result.

## 9. Outcome Buckets

Bucket A: externalization methodology plus transferable policy readout.
Protocol invariants pass, agreed denominator is at least 50, CI width is
informative, contract sensitivity is stable, judge validation passes, and the
CQ-vs-baseline readout is directionally interpretable.

Bucket B: externalization methodology plus transfer-null policy readout. All
methodology checks pass, but CQ ties Reflection or the transfer result is null.

Bucket C: derived-benchmark protocol contribution. The protocol is still
publishable, but the policy readout is conditional on contract choices or too
wide to headline.

Bucket D: adapter-blocked documented abort. No policy result is emitted.

## 10. Required Outputs Before Policy Execution

- `docs/longmemeval_externalization_anchor_gate.md`;
- this preregistration and its lock checker;
- redacted loader tests;
- dual-path annotation outputs;
- dual-path divergence report;
- hidden-answer verifier report;
- adapter pin;
- smoke run on 6 agreed cases;
- judge calibration/stability report;
- dirty-pre-run worktree check;
- candidate-stream hash invariant report.
<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_END -->

## Lock Maintenance

The lock is computed over the block between
`FAIR_STREAM_EXTERNALIZATION_PROTOCOL_START` and
`FAIR_STREAM_EXTERNALIZATION_PROTOCOL_END`.

Check:

```bash
python3 -m cq.eval.external.longmemeval.preregistration_lock --check
```

Recompute:

```bash
python3 -m cq.eval.external.longmemeval.preregistration_lock --recompute
```
