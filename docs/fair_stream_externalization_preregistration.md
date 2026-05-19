# Fair-Stream Externalization Preregistration

Date: 2026-05-18

Status: locked before annotation, adapter execution, or policy execution;
relocked on 2026-05-19 after Phase X.2 review to make pin validation default
and remove the unmeasurable contradiction-recovery metric before Phase X.3
smoke or policy execution.

fair_stream_externalization_lock_sha256: a7b8b5df50d3dbe41bbf8922c2ba1bbd9b98775c302f25d29313ece093000f53

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
- scope level/key;

and the agreed annotation artifact carries candidate events sufficient for the
shared adapter used by all compared policies.

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

Phase X.1 annotations do not invent contradiction edges. Contradictions are
constructed only after the adapter/extractor phase has event-level support, and
then fanned out to emitted candidate ids after candidate id rewriting.
Candidate stream hashes must match across policies for every scenario. A
mismatch aborts Bucket D before policy scoring.

## 4. Hidden-Answer Annotation Protocol

Both annotation paths load LongMemEval through
`cq.eval.external.longmemeval.redacted_loader`, which replaces `answer` and
`answer_session_ids` with hash-only redactions at load time. Attempting to read
those fields raises an exception. The loader recursively scrubs answer-side
keys matching answer/gold/ground-truth/rubric/label patterns from exported
`raw` payloads. `haystack_sessions` remain available because they are the
annotation context, but answer-side keys nested inside that context are also
redacted before export.

Path A: deterministic question-slug path. It uses a frozen question-surface
token filter plus evidence-session turn selector to derive
`relevant_canonical_id` and candidate events. It is local-first and uses no
model call.

Path B: independent deterministic question-rewrite path. It uses regex
surface rewrites and a separate evidence-overlap turn selector, must not share
Path A's canonical-id function or stopword set object, and must not introduce
new runtime dependencies without explicit user authorization.

Both paths filter the same 38-word vocabulary, encoded as a set in Path A and
as regex alternations in Path B. The dual-path check tests stability across two
surface-form derivation mechanisms; it is not evidence of independence over
the underlying filter vocabulary.

Both paths assign flat `confidence = 0.70` to Phase X.1 candidate events. This
is a deterministic annotation contract, not a semantic confidence estimate;
policy-facing use of confidence must remain identical across all compared
policies.

Both paths emit `contradiction_edges = []` and empty per-event
`contradicts_event_ids` in Phase X.1. The Phase X.2 deterministic adapter does
not synthesize contradiction edges. Contradiction recovery is therefore not a
primary LongMemEval transfer metric under this locked adapter; it may only be
added by a separate registered extractor/edge-construction amendment, not by an
adjacent-session chain assumption.

Path outputs are compared by
`cq.eval.external.longmemeval.dual_path_audit` per case. Cases are labeled:

- `agree`;
- `disagree_canonical_id`;
- `disagree_scope`;
- `missing_path_a`;
- `missing_path_b`.

Only `agree` cases enter `annotations_agreed.json`. Disagreement rows remain
in the divergence report and are never patched silently.

The hidden-answer verifier fails closed unless it receives the dual-path audit
summary. A bare `annotations_agreed.json` file is not sufficient for
`verifier_passed=true` because it cannot prove the denominator or disagreement
rate. The verifier also scans annotator source files for answer-side field,
redaction-hash, or forbidden-key-helper references. The binomial upper-tail
check uses a preregistered `p=0.5` chance agreement null as a diagnostic sanity
check only; it is not a claim that the two annotation paths are statistically
independent and is not part of the hard `verifier_passed` conjunction.

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
- `false_assertion_rate`;
- dialog-evidence-id PFLC at the locked cutoffs;
- fixed-seed paired bootstrap CIs for CQ-vs-Reflection and CQ-vs-`Mem0Lite`.

`contradiction_recovery_rate` is explicitly out of scope for the current
LongMemEval transfer adapter because the agreed Phase X.1 annotations and the
Phase X.2 deterministic adapter produce no contradiction edges. If a later
registered extractor amendment adds event-level contradiction support, that
amendment must relock the metric list before any policy execution that reports
contradiction recovery.

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

## Post-Lock Phase X.3.5 Calibration Amendment

Date: 2026-05-19

This amendment is intentionally outside the locked protocol block above. It
does not change the candidate stream, policy set, or PFLC target. A later X.4
amendment below changes the headline bucket metric and sensitivity-cell set
after empirical smoke testing.

Because the preferred path-1 survey found no official per-case LongMemEval
reference judge log, Phase X.3.5 uses path 2 with a stratified calibration set:

- 15 realistic rows from deterministic source-policy execution on sorted agreed
  case ids;
- 5 synthetic positive-control rows with `candidate_answer = gold_answer`;
- 5 synthetic negative-control rows with `candidate_answer = "I do not know."`.

The path-2 stability gate is interpreted as:

- `>= 0.85` cross-judge agreement on the realistic stratum;
- `>= 20` paired judge verdicts total;
- at most one error per judge on each 5-row synthetic control stratum.

Gold-answer access for constructing the synthetic control rows is restricted to
the scoring-side `gold_loader` path and remains outside policy input,
annotation, adapter, and verifier code.

## Post-Lock Phase X.4 Transfer Metric And Sensitivity Amendment

Date: 2026-05-19

This amendment is intentionally outside the locked protocol block above. It
narrows the transfer claim after implementation-level smoke testing exposed two
vacuities in the originally planned X.4 execution surface.

### Headline Metric

`answer_correct` is demoted from the X.4 headline bucket metric to a diagnostic
tracked in per-case rows and joint-count summaries.

Empirical trigger: `scripts/run_longmemeval_answer_correct_smoke.py` wrote
`data/external/longmemeval/answer_correct_smoke.json`, a 3-case by 9-policy
smoke with the locked primary judge (`qwen2.5:32b-instruct-q4_K_M`). The judge
marked 0/27 realistic policy candidate answers correct. The policy interface
currently emits structured memory-trace strings rather than natural-language
answers, so using
`answer_correct` as the bucket metric would make a transfer-null Bucket B result
structurally likely regardless of policy behavior.

X.4 bucket signs now use the preregistered PFLC-side metric `all_hit_at_50`,
computed from resolved candidate ids mapped back to LongMemEval source session
ids. This keeps the headline tied to the observable transfer behavior the
current policy interface can fairly measure: whether a policy preserved all gold
evidence sessions in its top-50 resolved context.

### Sensitivity Cells

The X.4 contract-sensitivity audit is narrowed to:

- `primary_contract`;
- `path_a_only_denominator`;
- `path_b_only_denominator`.

The originally planned `alternate_canonicalizer` and `flat_user_global_scope`
cells are dropped. Under the locked deterministic adapter, the alternate
canonicalizer was only a one-to-one slot rename, and the flat-USER_GLOBAL scope
cell was identical to the already-universal annotation scope. Keeping those
cells would inflate the apparent sensitivity surface without testing a
meaningfully different contract. X.4 must therefore claim stability across
three meaningful cells, not five nominal cells.
