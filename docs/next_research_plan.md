# Next Research Plan

Date: 2026-05-20

Status: active roadmap with 2026-05-20 pending multi-evidence follow-up notes.

## Status Update — 2026-05-17

Workstream A landed. The CQR path-normalized repair was exercised on
2026-05-16 and produced a second Bucket D under
`locked_run_json_sha_mismatch`; the Phase 4 null-row attribution remained
unsettled until Workstream A.5.

Workstream A.5 landed (2026-05-17 evening). A registered post-hoc QR-canon
audit ships in `docs/qr_canon_audit_registration.md` and
`docs/qr_canon_audit_results.md`. It reuses the locked CQR Section A
`cqr_set_membership` metric and the locked CQR alias function verbatim,
reads from a small committed `data/results/qr_canon_source_table.csv`
(no Phase 4 run-JSON byte reproducibility required at audit time), and
emits per-row Wilson CIs, a joint B-cubed F1 vs QR-canon table, and a
synthetic counterexample row showing B-cubed F1 `1.00` with QR-canon
(exact) `0.00`. Five of seven Phase 4 rows clear the existing B-cubed F1
floor while QR-canon (exact) is below 5 percent; the locked CQR alias
function also returns zero on four of those rows. The audit reattributes
those rows from "unattributed null" to "policy-facing query interface
contract failure" and ships QR-canon as a required diagnostic alongside
clustering-quality component metrics in
`docs/benchmark_methodology_draft.md` and `docs/paper_outline.md`. The
audit does not unlock the locked CQR Bucket D verdict, does not amend the
Phase 4 Bucket B result, and does not propose a new pass/fail threshold.

Workstream B landed. `docs/benchmark_methodology_draft.md` now serves as the
technical-report spine, and `docs/paper_outline.md` adds the reviewer-facing
outline with unified evidence ledger, limits, future work, and appendices.
Both documents now also carry the QR-canon contribution.

Workstream C item 2 landed. `CQDatedContestation` repaired base CQ's
`temporal_skew` failure in oracle mode and preserved the four originally won
mechanisms, but did not clear the CQ-vs-Reflection win criterion.

Workstream D landed as feasibility-only. `docs/longmemeval_feasibility_memo.md`
and `data/results/longmemeval_feasibility_coding.csv` record a 500-case
coding pass with 72 LongMemEval oracle `knowledge-update` cases that map to
`contradiction_edge`, but the decision is descriptive-only future work because
the released artifacts do not provide a shared CQ-style candidate stream,
contradiction edges, canonical slots, or a policy-query canonical-id contract.
LongMemEval should not be run against policies until a separate
adapter/annotation preregistration creates those inputs. Any LongMemEval
adapter must also establish a QR-canon target before any policy run.

## Status Update — 2026-05-18

Workstream A.6 landed. Policy-facing lookup-contract (PFLC) diagnostics
generalize QR-canon from a CQ-internal post-hoc audit into a field-level
diagnostic class. The registration
(`docs/policy_facing_lookup_contract_registration.md`) locks the contract;
the proposition (`docs/policy_facing_lookup_contract_proposition.md`) gives
the formal core (Proposition 1 over cluster-partition metrics, proved by
an injective relabeling `ρ: L_gold → Σ` whose image is disjoint from
`{g*}` and which therefore satisfies both `ρ(g*) ≠ g*` and
`g* ∉ image(ρ)`; the codomain is the label alphabet `Σ`, not `L_gold`,
since a bijective self-map of `L_gold` necessarily covers `g*`. Lemmas
1 and 2 by construction for retrieval@k and answer-accuracy metrics). Four per-anchor feasibility memos
(`docs/qr_canon_longmemeval_feasibility.md`,
`docs/qr_canon_mem0_locomo_feasibility.md`,
`docs/qr_canon_memoryagentbench_feasibility.md`,
`docs/qr_canon_membench_feasibility.md`) land at descriptive-only with
named PFLC instances (answer-handle, dialog-evidence-id,
conflict-resolution-id, fact-id). Four benchmark-targeted synthetic
counterexample rows ship in
`data/results/qr_canon_field_diagnostic_metrics.csv` with byte-stable
manifest. The workstream lands at outcome bucket **B-3
(artifact-blocked)** per the registration's preregistered bucket scheme:
no anchor benchmark releases per-question system-emitted identifier
artifacts standardly. B-3 is itself a publishable structural finding
about released-artifact contracts in the current memory-benchmark field.
BEAM's conditional promotion rule did not fire (it triggers on
Mem0/LoCoMo = blocked, not descriptive-only). The consolidated results
doc is `docs/qr_canon_field_diagnostic_results.md`. Methodology spine
(`docs/benchmark_methodology_draft.md` §5) and paper outline
(`docs/paper_outline.md` §1, §3, §4, §5, §8) both carry the field-level
diagnostic; QR-canon is now framed as the canonical-id instance of the
PFLC class. The workstream did not unlock CQR Bucket D, amend Phase 4
Bucket B, modify the byte-locked CQR alias function, or run any policy
against any external benchmark.

Post-A.6 LoCoMo published-output follow-up landed later on 2026-05-18.
The corrected artifact gate is now recorded in
`docs/locomo_baseline_replay_survey.md`. The original A.6 anchor set remains
artifact-blocked, but a current Agent Memory Benchmark (AMB) sweep found
public per-question LoCoMo run gzips for Hindsight and hybrid-search whose
injected contexts contain recoverable LoCoMo `dia_id` values. The scorer
`scripts/score_locomo_amb_pflc.py` compares those emitted IDs with official
LoCoMo `qa[].evidence` and writes
`data/results/locomo_amb_pflc_rows.csv` plus
`data/results/locomo_amb_pflc_summary.json`. On the lookup-relevant
denominator (rows with non-empty gold `evidence`), Hindsight records answer
accuracy `92.0%`, all-evidence PFLC@10 `65.8%`, PFLC@20 `83.1%`, and
PFLC@50 `97.6%` with `36,235` average context tokens; hybrid-search records
answer accuracy `79.1%`, PFLC@10 `64.8%`, PFLC@20 `75.7%`, and PFLC@50
`90.5%` with `22,156` average context tokens. The right interpretation is
not "public systems fail PFLC"; it is that once public per-question context is
available, PFLC decomposes LoCoMo scores into evidence exposure, evidence
rank/context saturation, and answer-generation residuals. This remains a
published-output/context-derived benchmark-artifact diagnostic, not a CQ
policy transfer claim.

The LongMemEval fair-stream externalization workstream has now started under
the heavy-integration plan. Phase X.-1 landed in
`docs/longmemeval_externalization_anchor_gate.md`: V2 is verified as a real
public release with 451 question rows, but its public files strip answer-
bearing annotation labels, so V2 is demoted to descriptive evidence-exposure
work and LongMemEval v1 remains the primary controlled-pilot anchor. Phase X.0
also landed in `docs/fair_stream_externalization_preregistration.md`, with a
lock checker and local primitives for redacted loading, dual-path divergence
auditing, and hidden-answer verification. Phase X.1 has now frozen the
LongMemEval v1 annotation layer: both local-first annotation paths agree on 71
of 72 comparable in-denominator `contradiction_edge` cases, the one canonical-id
divergence is retained as an audit row, the hidden-answer verifier passes, and
the agreed annotation artifact includes candidate events for the adapter. Phase
X.1 leaves contradiction edges empty rather than inventing adjacent-session
links. Phase X.2 has now landed adapter construction and stream-hash pinning:
the agreed events map into shared `Scenario` and `CandidateUpdate` objects, the
adapter SHA is pinned against the preregistration lock, the adapter validates
the pin by default, and the N=6 adapter dry run reports zero drops with
identical candidate-stream hashes across the CQ, Reflection, and `Mem0Lite`
placeholder policy names. Because the current deterministic adapter does not
create event-level contradiction edges, contradiction recovery is out of scope
unless a later registered extractor amendment adds that support. This does not
authorize a policy run. The next step is smoke testing, PFLC scoring, and judge
calibration under the locked protocol.

## Status Update — 2026-05-19

LongMemEval Phase X.3.5 through X.5 landed. The path-1 survey found no official
per-case reference judge log, so X.3.5 used the local path-2 calibration:
15 realistic CQ-sourced rows plus 5 positive and 5 negative synthetic controls.
The locked 32B/7B judge run cleared kill criterion 10 with realistic-stratum
agreement `14/15`, no indeterminate verdicts, and perfect synthetic-control
correctness for both judges.

Phase X.4 executed the full judged controlled-pilot transfer from a clean
worktree. The run emitted 1,935 policy/cell/case rows over the Phase 2.5
policy set and three meaningful cells (`primary_contract`,
`path_a_only_denominator`, `path_b_only_denominator`). The headline PFLC metric
is `all_hit_at_50`; `answer_correct` is diagnostic only after both the smoke
and full run showed trace-shaped answers with 0 correct judge verdicts.

The transfer result is Bucket A-negative: methodology gates pass and the sign
is stable, but CQ loses `all_hit_at_50` to Reflection and `Mem0Lite` by `-1.0`
in every cell. The sibling `any_hit_at_50` metric is transfer-null: CQ exposes
at least one gold evidence session in every case, but it does not expose both.
The mechanism is CQ's pending lookup interface, which returns one
strongest/latest pending candidate; eager durable baselines reinforce one
durable with both evidence candidates.

Phase X.5 integrates this into the paper outline and methodology spine as a
controlled external transfer probe, not a CQ-positive generalization claim and
not a leaderboard result. At that point, any next LongMemEval move required a
separate preregistration; the pending multi-evidence branch landed the next
day and is recorded below.

## Status Update — 2026-05-20

The separately preregistered pending multi-evidence LongMemEval follow-up
landed. The preregistration lock is
`84b3c44148494c1b6f72e8201a8da886f8e1f48e49ce00197f535c7e08638840`, and the
follow-up ships `CQPendingMultiEvidence`,
`ReflectionEagerWriteCardinalityCapped`, and the `phase2_5_followup` policy
set.

The readout is Outcome A as an interface repair. `cq_pending_multi_evidence`
moves `all_hit_at_50` from base CQ's `0/71` to `71/71` on the primary
contract cell and to `72/72` on both denominator-sensitivity cells, matching
Reflection and `Mem0Lite`. The capped Reflection diagnostic falls to `0/71`
on the primary cell while preserving the eager write path, so the mechanism is
answer-time evidence cardinality rather than a richer CQ-only substrate.
Internal regression metrics match base CQ exactly across the five required
families (`max_delta = 0.0`).

This does not rewrite X.4. The original controlled-pilot transfer remains a
completed negative result for base `consolidation_queue_lite`; the follow-up
is a separate preregistered policy-interface repair. Further LongMemEval work
should be new preregistered science, not another rescue rerun.

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
3. LongMemEval follow-ups only when preregistered as mechanism-local transfer
   questions. The pending multi-evidence repair has landed; further
   LongMemEval work should target a new boundary rather than rerunning X.4.

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

Status:

- Phase X.-1 anchor gate is complete: LongMemEval v1 primary, V2 descriptive
  evidence-exposure only.
- Phase X.0 preregistration is locked.
- Phase X.1 annotation output is frozen: 72 comparable cases, 71 dual-path
  agreements, one canonical-id divergence, verifier pass, and adapter-ready
  agreed candidate events with contradiction links left empty.
- Phase X.2 adapter construction and pinning is complete: the adapter emits
  shared `Scenario`/`CandidateUpdate` objects, validates
  `docs/longmemeval_adapter_pin.json`, and passes the N=6 stream-hash
  invariant dry run with zero drops.
- Phase X.3/X.3.5 smoke, PFLC scorer, answer-correctness smoke, and local
  judge calibration landed.
- Phase X.4 full judged transfer landed as Bucket A-negative for base CQ on
  `all_hit_at_50`.
- Phase X.5 report integration landed.
- The 2026-05-20 pending multi-evidence follow-up landed as a separate
  preregistered interface repair.

Completed design requirements:

1. Preserve the frozen 71-case dual-path-agreed denominator when running the
   adapter-backed smoke and transfer cells.
2. Preserve the pinned adapter and stream-hash invariant so CQ,
   ReflectionEagerWrite, and `Mem0Lite` receive comparable upstream inputs.
3. Preserve the dual-path disagreement report as an audit artifact; future
   sensitivity cells may use path-A-only and path-B-only subsets, but the
   primary contract is the agreed subset.
4. Validate the hidden-answer verifier, stream-hash invariant, and judge
   calibration before running any policy.

Decision rule:

- If the transfer setup cannot preserve the fairness invariants, do not run it
  as evidence for CQ. Mention it as future work or run a descriptive-only
  feasibility study.
- For completed LongMemEval variants, preserve the result labels: X.4 is
  negative for base CQ, and the pending multi-evidence successor is an
  interface repair only.

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

1. CQR path-normalization preregistration and tests. **Landed.**
2. CQR non-abort replay or documented second abort. **Landed as second
   documented Bucket D.**
3. Methodology draft update from the CQR outcome. **Landed.**
4. Paper-outline pass focused on the mechanism-local thesis. **Landed.**
5. Decide between `CQDatedContestation` and LongMemEval based on which one
   answers the most credible reviewer objection. **`CQDatedContestation`
   landed as partial preregistered success; LongMemEval later landed as a
   controlled-pilot external transfer probe with a stable CQ-negative
   evidence-completeness result.**
6. Registered post-hoc QR-canon audit reattributing the four
   perfect-clustering null rows. **Landed (Workstream A.5).**
7. PFLC field-level diagnostic generalization: registration +
   proposition + four per-anchor feasibility memos + four synthetic
   counterexamples + consolidated results doc + methodology-spine /
   paper-outline updates. **Landed (Workstream A.6, outcome bucket
   B-3).**
8. LoCoMo published-output PFLC follow-up over current AMB outputs:
   artifact gate + scorer + per-question rows + summary manifest. **Landed
   as a narrow published-output/context-derived replay, not a policy
   comparison.**
9. LongMemEval Phase X.1 dual-path annotation layer: redacted local-first
   annotation paths, dual-path audit, agreed annotations, verifier report, and
   byte-stable manifest. **Landed as annotation freeze only; no policy
   execution.**
10. LongMemEval Phase X.2 adapter construction and pinning: agreed annotation
    events map into shared scenarios and candidate streams, the live adapter SHA
    is pinned against the preregistration lock, and the N=6 dry-run stream-hash
    invariant passes with zero drops. **Landed as adapter plumbing only; no
    smoke policy run, PFLC scoring, judge calibration, or transfer comparison.**
11. LongMemEval Phase X.3/X.3.5 smoke, PFLC scorer, judge calibration, and
    answer-correctness smoke. **Landed; `answer_correct` demoted to diagnostic,
    `all_hit_at_50` selected as the X.4 headline PFLC metric.**
12. LongMemEval Phase X.4 full judged transfer. **Landed as Bucket A-negative:
    stable negative CQ-vs-Reflection and CQ-vs-`Mem0Lite` signs on
    `all_hit_at_50`; transfer-null on `any_hit_at_50`.**
13. Phase X.5 paper-outline and methodology-spine integration. **Landed:
    LongMemEval is now framed as a controlled external transfer failure of
    current CQ's evidence-completeness interface, not as a broad transfer win.**
14. Pending multi-evidence LongMemEval follow-up. **Landed as Outcome A:
    plural pending readout closes the evidence-completeness gap, capped
    Reflection reproduces the loss, and internal regression checks match base
    CQ exactly.**
15. Public preprint/artifact pointer for *When Memory Metrics Hide Memory
    Policies*. **Landed as report-package discoverability only; no benchmark
    result or policy verdict changed.**

Next-next, none of which is licensed by this plan without a separate
preregistration:

- report integration of the AMB LoCoMo PFLC replay, including the context-
  saturation caveat and the distinction between evidence exposure and answer
  generation
- a policy-facing adapter-contract experiment that runs the CQR Section C
  cross-tab (QR-canon hit vs per-policy answer success) on a fresh Phase 4
  baseline or a separately archived locked-input environment
- a further separately preregistered LongMemEval follow-up, if any, focused on
  a new split, adapter, or stricter boundary; do not rerun X.4 or the
  completed pending multi-evidence follow-up to rescue a metric
- threshold or prompt or validator changes — explicitly forbidden by the
  Kill Criteria below

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
