# Next Research Plan

Date: 2026-05-15

Status: active planning draft.

## Research Posture

The next phase should aim for an original, defensible research contribution
rather than a larger collection of benchmark runs.

The strongest current claim is not broad noisy-mode CQ superiority. The current
claim is more specific and more interesting:

- same-candidate-stream memory-policy evaluation can expose when a governance
  architecture remains visible after noisy extraction
- staged contestation/demotion survives clearly on forced contradiction and
  partially on preference drift
- several null rows are scientifically useful because they show when the noisy
  candidate stream or policy-query interface stops exposing the policy
  distinction

The paper should therefore center on memory-governance evaluation and
attribution discipline, with CQ as the main policy under test. It should not
present CQ as a general persistent-agent memory system.

## Working Thesis

Staged memory promotion is most valuable when the system can preserve a
contestable evidence trail long enough to adjudicate contradictions, source
independence, scope, and temporal order. Under noisy extraction, the policy
advantage appears only when the extracted candidate stream preserves the
policy-facing handles needed by the memory architecture.

That thesis is original because it shifts the question from:

- "which memory system has the highest aggregate recall?"

to:

- "when is a memory-governance policy still evaluable under shared noisy
  inputs, and which policy mechanisms survive the interface?"

## Near-Term Workstreams

### A. Repair CQR Reproducibility Without Retuning

Goal: turn the aborted canonical-id/query-resolution audit into either a valid
Bucket A/B/C readout or a documented, still-reportable abort.

Tasks:

1. Write a narrow repair preregistration for path-normalized replay checking.
2. Normalize or exclude path-sensitive run JSON fields such as absolute
   `predictions_path`.
3. Preserve checks for metrics CSV hashes, candidate-stream hashes, adapter
   identity, model digest, prompt identity, preregistration locks, and clean
   pre-run state.
4. Add tests proving that path changes do not alter stable replay equivalence
   while adapter, metric, prompt, model, and candidate-stream drift still abort.
5. Rerun the locked CQR audit and record the result.

Forbidden in this workstream:

- prompt changes
- schema changes
- threshold changes
- validator changes
- adapter semantics changes
- policy or substrate changes

Decision rule:

- If CQR emits Bucket A/B/C, update the methodology draft with the result.
- If it remains Bucket D for a non-path reason, keep null-row attribution
  unsettled and report that boundary directly.

### B. Lock The Mechanism-Local Paper Spine

Goal: make the writeup strong before adding more experiments.

Tasks:

1. Use `docs/noisy_policy_mechanism_audit.md` as the Phase 4 interpretation
   anchor.
2. Promote only the claims already supported by artifacts:
   - clean noisy survival on forced contradiction
   - partial noisy survival on preference drift
   - oracle-only abstention calibration support
   - fair same-stream benchmark methodology
   - component-gated noisy-mode discipline
3. Keep unsupported claims explicit:
   - broad noisy CQ superiority
   - noisy separation from `Mem0Lite` on the frozen sentinel
   - learned semantic scope inference
   - noisy source-independence survival
   - external transfer
4. Convert `docs/benchmark_methodology_draft.md` into a paper-outline draft
   only after CQR is non-abort or explicitly framed as an abort.

Decision rule:

- If the current evidence is enough for a credible workshop or technical
  report, prioritize writing over new benchmark families.
- If reviewers would reasonably ask "why did the null rows tie?", answer that
  through CQR or an adapter-contract audit before adding unrelated experiments.

### C. Run Only Mechanism-Justified Follow-Ups

Goal: add experiments only when they sharpen the current thesis.

Allowed follow-ups:

1. CQR or adapter-contract audit for the Phase 4 null rows.
2. `CQDatedContestation` as the already-preregistered post-hoc repair for the
   `temporal_skew` weakness in `adversarial_upstream_noise`.
3. A LongMemEval transfer check, but only after the internal mechanism-local
   story is settled and only if it can be framed as transfer rather than a new
   tuning target.

Not allowed without a new preregistration:

- new mechanism families
- prompt or extractor tuning to rescue null rows
- 70B routing as a core research result
- threshold sweeps after seeing Bucket B
- richer CQ-only storage or retrieval

### D. Prepare A Minimal External Transfer Check

Goal: test whether the contradiction-like mechanism that survived internally
also appears outside this benchmark.

LongMemEval should be treated as a transfer probe, not a leaderboard target.

Design requirements before implementation:

1. Identify LongMemEval cases that map to contradiction, correction, or stale
   memory mechanisms.
2. Define how CQ, ReflectionEagerWrite, and `Mem0Lite` receive comparable
   upstream inputs.
3. If a same-candidate-stream setup is not possible, label the result as
   descriptive transfer only.
4. Preregister the subset, metrics, baselines, and failure interpretation
   before running any policy.

Decision rule:

- If the transfer setup cannot preserve the fairness invariants, do not run it
  as evidence for CQ. Mention it as future work or run a descriptive-only
  feasibility study.

### E. Finish The Report Package

Goal: produce a shareable artifact that is honest, inspectable, and worth
reviewing.

Required pieces:

1. Final claim table separating oracle, noisy, and transfer claims.
2. Evidence ledger mapping each claim to committed artifacts.
3. Baseline table covering ReflectionEagerWrite, `Mem0Lite`, ablations,
   `NoMemory`, and transcript-retrieval baselines where applicable.
4. Failure-taxonomy appendix with representative trace links.
5. Artifact and reproducibility appendix explaining manifests, locks, and
   large-artifact policy.
6. Limitations section that names the unsettled null rows, dated-evidence
   weakness, source-identity gap, and real-user transfer gap.

## Suggested Order

1. CQR path-normalization preregistration and tests.
2. CQR non-abort replay or documented second abort.
3. Methodology draft update from the CQR outcome.
4. Paper-outline pass focused on the mechanism-local thesis.
5. Decide between `CQDatedContestation` and LongMemEval based on which one
   answers the most credible reviewer objection.

## Kill Criteria

Stop a line of work instead of expanding it if:

- it requires changing prompts, thresholds, validators, adapters, or policy code
  after seeing a result it is meant to explain
- it weakens the same-candidate-stream or same-substrate comparison
- it turns an oracle-only result into a noisy-mode claim
- it adds benchmark coverage without changing the interpretation
- it cannot leave committed artifacts, traces, and manifests

## One-Sentence Direction

Make the next contribution about when memory governance remains scientifically
evaluable under shared noisy inputs, then show the narrow mechanisms where CQ
survives, fails, or becomes untestable.
