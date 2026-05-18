# Paper Outline: Fair Policy Evaluation For Memory Governance

Date: 2026-05-17

Target: arXiv technical report first; workshop submission only after the
argument is tight enough that unsupported claims are visibly out of scope.

Core claim: same-candidate-stream memory-policy evaluation can show when a
memory-governance architecture remains visible after noisy extraction, and when
the noisy stream or policy-query interface stops exposing the policy
distinction. This is a benchmark and attribution-discipline contribution, not a
claim of broad noisy CQ superiority or a replacement persistent-agent memory
system.

## Abstract

This report introduces a preregistered fair-policy benchmark for persistent
agent memory governance. Under a shared upstream candidate stream and shared
scoped substrate, CQ's contradiction-edge-driven contestation/demotion mechanism
survives noisy 32B extraction cleanly on `forced_contradiction` and partially on
`preference_drift`. The remaining Phase 4 ties are recorded as policy-facing
query interface contract failures rather than unattributed nulls, under a
registered post-hoc QR-canon audit that ships per-row Wilson confidence
intervals and a synthetic counterexample showing clustering-quality
canonicalization can score `1.00` while exact policy-query canonical-id
agreement remains `0.00`. The report contributes: a same-stream benchmark, a
component-gated noisy-mode unlock discipline, a mechanism audit for Bucket B,
a query-resolvable canonical-id diagnostic that should accompany any
clustering-quality component evaluation of memory-policy benchmarks, and a
reproducibility posture strict enough to report a second Bucket D CQR abort
instead of forcing a verdict.

## 1. Introduction And Contributions

### Problem

Persistent memory systems can appear to improve long-horizon behavior for the
wrong reason: richer private state, asymmetric extraction, easier storage, or
aggregate metrics that hide concentrated failures. The benchmark isolates the
policy question by giving CQ, ReflectionEagerWrite, `Mem0Lite`, ablations, and
other baselines the same upstream candidate stream and the same scoped storage
substrate.

### Contributions

1. **Fair policy benchmark.** Shared candidate streams, shared scoped storage,
   lifecycle traces, oracle/noisy separation, and saved artifacts make CQ-vs-
   baseline claims inspectable.
2. **Aggregate gate.** Aggregate CI-supported component gates are necessary but
   insufficient; the locked 7B run passed aggregate gates but still stayed
   locked.
3. **Per-family observed gate.** Per-family checks caught concentrated
   extractor failures that aggregate rollups smoothed over.
4. **Frozen sentinel gate.** Mechanism-diverse frozen scenarios blocked
   overgeneralized noisy claims on the exact rows used for
   mechanism-generalization claims.
5. **Phase A prompt regression.** A forced-contradiction prompt regression check
   stopped unstable extractor rows before broader scoring.
6. **Deterministic replay.** Determinism and replay-equivalence checks prevent
   post-hoc methodology repairs from emitting verdicts when locked inputs drift.
7. **QR-canon diagnostic.** Clustering-quality canonicalization (B-cubed F1)
   can score `1.00` while exact policy-query canonical-id agreement remains
   `0.00` on a real benchmark; the registered post-hoc QR-canon audit
   surfaces this gap on five of seven Phase 4 rows and ships a synthetic
   counterexample. QR-canon enters the methodology as a required diagnostic
   alongside the clustering-quality gates above, not as a tuneable
   pass/fail threshold.

Key artifacts:

- `docs/preregistration.md`
- `docs/local_unlock_probe_preregistration.md`
- `docs/noisy_policy_comparison_preregistration.md`
- `data/results/component_gate_decision_general_v1_summary.json`
- `docs/component_gate_failure_taxonomy.md`
- `docs/noisy_policy_mechanism_audit.md`
- `docs/canonical_id_resolution_audit_results.md`
- `docs/qr_canon_audit_registration.md`
- `docs/qr_canon_audit_results.md`
- `data/results/qr_canon_audit_metrics.csv`

## 2. Benchmark And Policies

### Shared Invariants

- Same upstream `CandidateUpdate` stream for CQ and eager baselines.
- Same scoped substrate across CQ, ReflectionEagerWrite, and `Mem0Lite`.
- Oracle-mode claims are separated from noisy-mode claims.
- No noisy-mode policy claim is made before component outputs pass the locked
  gate.
- Artifacts preserve traces, lifecycle transitions, manifests, and failure
  examples.

### Policies

- `ConsolidationQueueLite` / `CQ-Agent-lite`
- `ReflectionEagerWriteLite`
- `Mem0Lite` as an ADD/UPDATE/NOOP published-family baseline over the shared
  substrate, not a full Mem0 reproduction
- `NoMemoryLite`, `NaiveEagerWriteLite`, `ScopeBlindTranscriptRAGLite`
- Four CQ ablations:
  `cq_no_contestation_demotion`,
  `cq_no_wider_scope_pending_override`,
  `cq_no_pending_lookup_use`,
  `cq_no_source_independence_gate`
- `CQDatedContestation` as a separately preregistered follow-up policy set, not
  part of the original `phase2_5` headline

## 3. Related Work

### External Memory Benchmarks

LongMemEval evaluates long-term interactive chat memory across information
extraction, multi-session reasoning, knowledge updates, temporal reasoning, and
abstention ([arXiv:2410.10813](https://arxiv.org/abs/2410.10813)). It is the
right external transfer target for this project only if a same-candidate-stream
candidate layer and policy-query contract can be preserved. The 2026-05-17
feasibility memo found 72 update/correction cases in its oracle split but
classified the current transfer path as descriptive-only future work because
the released fields do not expose CQ-style candidate streams, contradiction
edges, or canonical query ids.

MemoryAgentBench evaluates memory agents through incremental multi-turn
interactions and emphasizes accurate retrieval, test-time learning,
long-range understanding, and selective forgetting
([OpenReview](https://openreview.net/pdf?id=DT7JyQC3MR)). MemBench evaluates
LLM-agent memory across factual/reflective memory and
participation/observation scenarios ([arXiv:2506.21605](https://arxiv.org/abs/2506.21605)).
These benchmarks occupy the external-evaluation lane. They are valuable
positioning and future transfer targets, but they do not by themselves enforce
this repo's fair same-stream policy comparison.

### Memory Systems And Write Policies

Mem0 proposes a production-oriented memory architecture that dynamically
extracts, consolidates, and retrieves salient conversational memory, with a
graph variant for relational structure ([arXiv:2504.19413](https://arxiv.org/abs/2504.19413)).
This repo's `Mem0Lite` is narrower: it tests an ADD/UPDATE/NOOP write-time
discipline over the same CQ candidate stream and storage substrate. A-MEM
organizes memories through dynamic indexing, linking, and memory evolution
([arXiv:2502.12110](https://arxiv.org/abs/2502.12110)). Those systems motivate
comparison targets and design language, but this report does not claim CQ is a
drop-in replacement for them.

### Preregistered Benchmark Methodology

The lane for this project is preregistered fair policy comparison plus
component-gated noisy-mode attribution. The contribution is not another recall
leaderboard: it is an experiment design that keeps policy inputs, storage, and
candidate streams comparable, then refuses to make noisy-mode claims when the
component stream or replay contract is not strong enough.

## 4. Method

### Oracle Stage

The oracle benchmark establishes policy behavior when candidate observations,
scope keys, contradiction/support relations, and source information are known.
It includes forced contradiction, scope contamination, preference drift,
useful-pending memory, false corroboration, memory poisoning,
mechanism-diverse frozen held-out scenarios, adversarial upstream noise, and
the evidence-conflict spectrum.

### Noisy Stage

The noisy path renders transcripts, scores local extractor outputs against
component gold labels, converts accepted predictions into shared candidate
streams, and runs policies only after the preregistered component gate unlocks.
The 7B path stayed locked; the 32B local unlock probe reached Bucket A; the
separately preregistered Phase 4 noisy comparison then reached Bucket B.

### Attribution Stage

The Bucket B mechanism audit separates rows where policy mechanisms remain
visible from rows where ties are unattributed. It uses Phase 4 policy artifacts,
component-eval artifacts, exact policy-query canonical-id alignment, ablation
patterns, and representative traces.

### Query-Resolvable Canonical-Id Diagnostic

The QR-canon audit is a registered post-hoc companion to the attribution
stage. It reuses the locked CQR Section A `cqr_set_membership` metric and
the locked CQR alias function verbatim, but reads from a small committed
per-question source table that does **not** depend on the gitignored
12-17 MB Phase 4 run JSONs at audit time. It emits per-row QR-canon (exact
and alias-normalized) rates with Wilson confidence intervals, a joint
B-cubed F1 vs QR-canon (exact) table, and a synthetic counterexample
fixture demonstrating that B-cubed F1 can be `1.00` while QR-canon (exact)
is `0.00` by construction. The audit does not unlock the locked CQR
Bucket D verdict, does not issue a new pass/fail threshold, and does not
change any policy verdict. It reattributes the perfect-clustering null
rows from "unattributed null" to "policy-facing query interface contract
failure."

## 5. Evidence Ledger

| Claim | Mode | Preregistration / contract | Committed evidence | Readout | Boundary |
| --- | --- | --- | --- | --- | --- |
| Frozen oracle predictions were locked before execution and matched observed deltas. | Oracle | `docs/preregistration.md` | `docs/predictions_vs_results.md`; `data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_metrics.csv` | All 108 frozen oracle deltas matched. CQ's support over `Mem0Lite` is narrow and centered on `premature_promotion_rate`. | No broad answer-quality superiority over `Mem0Lite`. |
| CQ has a witness-conflict advantage and a dated-evidence weakness under adversarial upstream noise. | Oracle | `docs/adversarial_upstream_noise_preregistration.md` | `docs/adversarial_upstream_noise_results.md`; `data/results/adversarial_upstream_noise/*phase2_5*_metrics.csv` | CQ wins four mechanisms, loses only `temporal_skew`, and held-out directions do not reverse. | Does not govern all adversarial upstream-noise mechanisms. |
| `CQDatedContestation` repairs base CQ's temporal-skew failure but not the CQ-vs-Reflection win criterion. | Oracle follow-up | `docs/adversarial_upstream_noise_dated_followup_preregistration.md` | `docs/adversarial_upstream_noise_dated_followup_results.md`; `data/results/adversarial_upstream_noise/*followup*_metrics.csv` | Base CQ moves `0.00` to `1.00`; CQDated ties Reflection at `1.00`; four original mechanisms are preserved. | Not a noisy repair, not a LongMemEval transfer, not a retrofit of `phase2_5`. |
| CQ passes the designed abstention-calibration axis. | Oracle | `docs/abstention_quality_preregistration.md` | `docs/abstention_quality_results.md`; spectrum metrics, manifests, replay artifacts | Full support on mixed and held-out: useful moderate/witness pass and harmful bucket remains non-inferior. | Oracle-only; not external validation. |
| The 7B component gate correctly blocked a false noisy unlock. | Noisy component eval | `docs/component_gate_failure_taxonomy.md`; gate runner contracts | `data/results/component_gate_decision_general_v1_summary.json`; taxonomy doc | Aggregate gates passed, but 45 scenario errors, 8 per-family observed failures, and 3 frozen-sentinel failures kept policy comparison locked. | No 7B noisy policy claim. |
| The 32B local unlock probe made a separately preregistered noisy comparison eligible. | Noisy component eval | `docs/local_unlock_probe_preregistration.md` | 7B anchor and 32B summary/manifest artifacts | 7B anchor reproduced locked counts; both 32B primary cells cleared unlock checks. | Unlock alone is not a policy result. |
| Phase 4 noisy comparison reaches Bucket B with mechanism-local support. | Noisy policy comparison | `docs/noisy_policy_comparison_preregistration.md`; adapter pin | `docs/noisy_policy_comparison_results.md`; `data/results/noisy_policy_comparison_summary.json`; per-family metrics/manifests | CQ wins vs Reflection on forced contradiction and preference drift, records no countable directional losses, ties `Mem0Lite` on frozen sentinel, and has no replicate contradictions. | Not broad noisy CQ superiority. |
| The mechanism audit attributes only forced contradiction cleanly and preference drift partially. | Noisy audit | `docs/noisy_policy_mechanism_audit_hypothesis.md` | `docs/noisy_policy_mechanism_audit.md`; `data/results/noisy_policy_mechanism_audit_evidence.json`; three audit traces | `forced_contradiction` survives through contradiction edges and contestation/demotion; `preference_drift` partially survives; other rows remain unattributed or descriptive. | No noisy scope/source/pending/poisoning survival claim. |
| CQR replay repair refused to emit a verdict under a second Bucket D. | Reproducibility audit | `docs/canonical_id_resolution_audit_preregistration.md`; `docs/canonical_id_resolution_audit_repair_preregistration.md` | `docs/canonical_id_resolution_audit_results.md`; `data/results/canonical_id_resolution_audit_stop_2026-05-15.json`; `data/results/canonical_id_resolution_audit_stop_2026-05-16.json` | The repair separated path-sensitive fields but still aborted on locked run-JSON non-reproducibility. | No CQR A/B/C attribution; null rows remain unsettled until QR-canon reattributed them. |
| QR-canon exposes clustering-vs-lookup gap and reattributes four null rows. | Component diagnostic, registered post-hoc | `docs/qr_canon_audit_registration.md` (reuses CQR Section A metrics) | `docs/qr_canon_audit_results.md`; `data/results/qr_canon_audit_metrics.csv`; `data/results/qr_canon_source_table.csv`; synthetic counterexample row | Five of seven Phase 4 rows clear the B-cubed F1 `>= 0.65` floor while QR-canon (exact) is below 5 percent; locked CQR alias function also returns zero on four of those rows. | No QR-canon pass/fail gate; no CQR A/B/C verdict; no change to policy verdicts. |
| LongMemEval is relevant but not yet a fair transfer run. | Feasibility only | `docs/next_research_plan.md` Workstream D; frozen coding rule in memo | `docs/longmemeval_feasibility_memo.md`; `data/results/longmemeval_feasibility_coding.csv` | 72 `knowledge-update` cases map to `contradiction_edge`, but candidate stream and policy-query invariants are not preserved. | Descriptive-only future work; no policy run. A future LongMemEval adapter must establish a QR-canon target before any policy run. |

## 6. Discussion

The result is a contingency map. When the noisy stream preserves contradiction
edges and the policy-query surface stays aligned, CQ's contestation/demotion
mechanism remains visible. When the stream does not expose canonical slots,
query alignment, source identity, or the relevant policy handle, policy ties are
not evidence that the policies are equivalent; they are evidence that the
current interface failed to expose the distinction.

This framing makes the negative and mixed rows useful. The 7B gate shows why
aggregate component metrics are not enough. The 32B Bucket B audit shows why a
successful component unlock is also not enough: each policy row still needs
mechanism-level attribution. The QR-canon audit closes the loop on the
downstream side: clustering-quality metrics passing at `1.00` does not imply
the policy-facing query lookup contract is satisfied. On four of the seven
Phase 4 rows the lookup contract is satisfied for zero questions even under
the locked CQR alias function, so a clustering-only view of extractor quality
would have read those rows as "policies are equivalent" rather than "the
interface failed to expose the distinction." A complete memory-policy
benchmark therefore needs three layered diagnostics — concentrated per-family
component failures, frozen mechanism-diverse sentinels, and query-resolvable
canonical-id agreement — none of which is sufficient alone.

## 7. Local Unlock Probe

The local unlock probe is the bridge from failure-taxonomy evidence to a valid
noisy policy comparison. The 7B anchor reproduced the locked failure counts,
while both 32B cells cleared the preregistered gate. The probe did not itself
claim CQ superiority; it only licensed the separate Phase 4 policy comparison
that later reached Bucket B.

## 8. Limitations

### Unsupported Current Claims

- broad noisy-mode end-to-end CQ superiority
- noisy separation from `Mem0Lite` on the frozen sentinel
- learned semantic scope inference
- noisy source-independence survival
- noisy scope-aware pending override survival
- noisy useful-pending or poisoning defense survival
- extractor-floor convergence for `useful_pending_memory` or
  `memory_poisoning` under the current 32B artifacts
- real-user, weeks-long helpfulness
- LongMemEval or other external transfer
- a hard QR-canon pass/fail threshold; QR-canon is a required diagnostic
  alongside clustering-quality metrics, not a new gate
- semantic extractor failure as the cause of the QR-canon gap; the gap is
  a policy-facing query contract failure, not evidence that the extractor
  is semantically wrong

### CQDated Boundary

`CQDatedContestation` repairs base CQ's temporal-skew failure in oracle mode,
but it does not clear a CQ-vs-Reflection win on that lane. The follow-up is not
a noisy-mode repair, not a Phase 4 null-row repair, not a LongMemEval transfer,
and not part of the original `phase2_5` headline.

### CQR Boundary

The CQR repair attempt produced no Bucket A/B/C readout. The second Bucket D is
evidence that the replay discipline refuses a methodology-only fix when locked
inputs cannot be reproduced. It does not settle the Phase 4 null-row
attribution.

### QR-Canon Boundary

The QR-canon audit reattributes four mechanism-audit null rows from
"unattributed null" to "policy-facing query interface contract failure"
based on disclosed prior observations plus newly registered Wilson CIs and
a synthetic counterexample. It does not unlock the locked CQR Bucket D
verdict; it does not amend the Phase 4 noisy policy comparison's Bucket B
result; it does not run a cross-tab between QR-canon hits and per-policy
answer success (the CQR audit's Section C cross-tab remains future work
blocked on the same replay path); and it does not introduce a new
QR-canon pass/fail threshold. The deployed metric is exact-string set
membership, framed as the active policy lookup contract; the
alias-normalized variant is a frozen boundary sensitivity check that uses
the locked CQR alias function and never substitutes for the exact metric.

### External Transfer Boundary

The LongMemEval feasibility memo and per-case coding CSV found a relevant
`knowledge-update` denominator, but no fair policy run is licensed yet. The
released artifacts do not provide CQ-style candidate streams, contradiction
edges, canonical ids, or a policy-query contract. A future LongMemEval-CQ run
must first create and preregister that adapter/annotation layer.

## 9. Future Work

1. Preregister a policy-facing adapter-contract experiment, or run a fresh
   Phase 4 baseline with committed or archived run-JSON payloads, before
   making new null-row attribution claims beyond the QR-canon reattribution.
   The CQR audit's Section C cross-tab (QR-canon hit vs per-policy answer
   success) is the natural follow-on diagnostic but remains blocked on the
   same replay path; it is not licensed against the existing locked Phase 4
   manifests.
2. If LongMemEval remains the transfer target, write a separate adapter and
   annotation preregistration that freezes candidate construction, canonical-id
   query mapping, per-mechanism labels, metrics, baselines, and kill criteria
   before any policy execution.
3. If a future LongMemEval adapter cannot preserve the same-candidate-stream
   invariant, keep LongMemEval as descriptive future work rather than evidence
   for CQ.
4. Package the report with a final claim table, baseline table, reproducibility
   appendix, and failure taxonomy appendix.

## Appendix A. Failure Taxonomy

The Phase 3 taxonomy centers on four failure modes:

- required-field omission (`scope_key`, `canonical_id`)
- ID-namespace confusion (`canonical_id` emitted where event ids are required)
- durable-claim drift into temporary/session framing
- contradiction-edge misses

Representative traces:

- `data/results/audit_trace_forced_contradiction_default.html`
- `data/results/audit_trace_scope_contamination_default.html`
- `data/results/audit_trace_useful_pending_memory_default.html`

These traces are inspection aids. Numeric claims come from metrics, manifests,
component summaries, and compact audit evidence.

## Appendix B. Artifacts And Reproducibility

The report should summarize:

- manifest fields for command, model, prompt/schema profile, git commit,
  artifact hashes, candidate-stream hashes, adapter identity, Python version,
  and working-tree status
- preregistration locks and lock-only checks
- `archive_status=regeneratable_only` for large artifacts that are not tracked
- the policy that small headline-verification artifacts should be committed
- path-normalized replay rules for CQR
- the 2026-05-16 second Bucket D as a reproducibility-discipline example, not a
  failed attempt to rescue a preferred result
