# Publication-Hardening Preregistration

Date: 2026-05-25

Status: locked before any publication-hardening experiment, API-backed
extractor run, shared-answerer run, external distractor adapter execution, or
paper claim-ledger rewrite.

publication_hardening_lock_sha256: 05671290ae8ebcc665c915521128c18c48b13be075ace55472b5931874672590

This document implements the paper-hardening path for
`paper/When_Memory_Metrics_Hide_Memory_Policies.pdf`. It keeps the paper as a
methods-first archival report. It does not rewrite prior verdicts, rerun v1
LongMemEval to rescue a result, or authorize a broad CQ superiority claim.

<!-- PUBLICATION_HARDENING_PROTOCOL_START -->
## 1. Scope And Preserved Verdicts

The locked claim ledger for the hardened paper is:

1. Claim 1: same-stream audit discipline.
2. Claim 2: PFLC and metric blind spots.
3. Claim 3: preserved negative transfer.
4. Claim 4: CQ-Multi distractor survival, or the fallback PFLC output
   contract if CQ-Multi fails, ties, or blocks under distractors.

No result-dependent headline claim may be created after seeing new data. A
demoted claim becomes a sub-result or limitation.

The following verdicts and supporting artifacts remain historically intact:

- Phase 4 noisy comparison Bucket B;
- LongMemEval X.4 base-CQ transfer loss;
- CQR Bucket D aborts;
- CQ-Multi v1 follow-up and capped-Reflection control;
- CQ-Multi per-family regression artifact;
- LongMemEval v1 all-hit random-floor artifact;
- AMB LoCoMo PFLC replay.

Step 2 below is a generalization test. It is not a rerun or rewrite of v1
LongMemEval unless a separate delta is preregistered.

## 2. API Exception And Artifact Requirements

The repository remains local-first by default. For this publication-hardening
workstream only, hosted extractors, judges, and shared answerers are allowed if
they are preregistered here or in a named amendment and every live response is
cached.

Every API-backed cell must record:

- provider and model id;
- model version or date-stamped alias as exposed by the provider;
- fallback model id, if any;
- cost ceiling in USD, capped at `<= 10000` for this paper-hardening
  workstream unless a separate human-approved preregistered amendment raises
  the cap;
- prompt and schema hash;
- request hash and response hash;
- timestamp and cost;
- cached raw request/response path;
- replay manifest path;
- stability check outcome.

Paper tables must replay from cached responses. A provider-side model upgrade
requires a new preregistered revision cell; it cannot silently replace the
locked cache.

## 3. Policy Names And Runner Keys

Paper-facing names map to runner keys as follows:

| Paper name | Runner key |
| --- | --- |
| Base CQ | `consolidation_queue_lite` |
| CQ-Multi | `cq_pending_multi_evidence` |
| Reflection | `reflection_eager_write_lite` |
| Capped Reflection | `reflection_eager_write_cardinality_capped` |
| Mem0 WritePolicy Lite | `mem0_lite` |
| NoMemory | `no_memory_lite` |

Policy-set keys:

| Cell | Policy set |
| --- | --- |
| original internal headline | `phase2_5` |
| internal or external CQ-Multi follow-up | `phase2_5_followup` |
| fresh archived CQR replay | `phase2_5` |

The duplicate `phase2_5` entry is intentional: the fresh archived CQR replay
reuses the original Phase 4 policy set while changing archival and replay
requirements.

Random-k and recency-k are external distractor-floor labels, not current runner
policy names. If they become executable policies, their runner keys must be
registered before execution.

## 4. Step 2: CQ-Multi Under Distractors

Primary target: LongMemEval-S, but only if a public source artifact can be
pinned and inspected. The current local record is no-go:
`docs/longmemeval_s_feasibility_note.md`.

Fallback target: MemoryAgentBench conflict-resolution, but only with a
separate preregistered annotation layer. MemoryAgentBench is not a drop-in
LongMemEval replay. The annotation layer must lock:

- gold ids;
- distractor accounting;
- hidden-answer rules;
- adjudication procedure;
- source hash;
- feasibility checks.

If the annotation layer cannot be locked, the lane is blocked. Do not weaken
PFLC to fit MemoryAgentBench.

The operational distractor floor is checked after adapter drops. Scored cases
must average at least 10:1 non-gold to gold policy-visible evidence ids, using
the same id unit as the primary PFLC metric. The mean per-case ratio is the
hard gate. Raw-haystack ratio and minimum per-case ratio are diagnostics only.

Compare:

- Base CQ;
- CQ-Multi;
- Reflection;
- Capped Reflection;
- Mem0 WritePolicy Lite;
- random-k;
- recency-k;
- NoMemory where applicable.

Primary metrics:

- PFLC evidence recall/F1 at small k;
- `all_hit_at_k`;
- `any_hit_at_k`;
- distractor precision.

Answer correctness is secondary and cannot be headlined unless PFLC evidence
metrics pass and answerer sensitivity is stable.

Step 2 cannot execute until all of these preconditions are satisfied:

- LongMemEval-S pin or MemoryAgentBench annotation lock is green;
- random-k and recency-k have executable policy keys or a preregistered
  scorer-only baseline path;
- the distractor-floor check is wired into the adapter smoke path;
- the compared policy-set keys match Section 3.

Outcome rules:

- CQ-Multi beats Reflection/Mem0 on completeness without worse distractor
  precision: Claim 4 remains a mechanism-local repair.
- CQ-Multi improves only cardinality, not distractor discrimination: demote
  current Claim 4 and make PFLC output contract the new Claim 4.
- CQ-Multi ties Reflection/Mem0 on both completeness and distractor precision:
  treat the same as the cardinality-only outcome.
- Adapter pinning, annotation locking, hidden-answer verification, or
  distractor floor fails: treat Claim 4 as demoted and proceed to Step 4.

## 5. Step 3: Fresh Archived CQR Cross-Tab Replay

This is a separate replay. It must not be combined with Step 5.

Precondition: the existing CQR repair verification is green, or the skip is
documented before execution.

Scope is pinned to the original CQR Section C denominator:

- primary model: `qwen2.5:32b-instruct-q4_K_M`;
- schema profile: `default`;
- policy set: `phase2_5`;
- frozen sentinel included only as descriptive companion;
- thesis families: `useful_pending_memory` and `memory_poisoning`;
- descriptive companion: `false_corroboration`;
- minimum N: each thesis family must have at least five alias-CQR hits.

The replay must archive raw component outputs, candidate streams, policy
outputs, lookup handles, answer traces, manifests, and hashes.

Primary success criterion: the targeted cross-tab cells are populated and can
evaluate `P(answer_success | alias_CQR_hit) -
P(answer_success | alias_CQR_miss)` for CQ on both thesis families.

Outcome rules:

- Cross-tab resolves PFLC null rows: incorporate into Claim 2.
- Cross-tab remains inconclusive: keep CQR as an unresolved limitation.
- Preconditions fail: use fixed limitation text and do not delay Step 2 or
  Step 4.

## 6. Step 4: PFLC Output-Contract Backfill

If Claim 4 is demoted or blocked in Step 2, PFLC output contract becomes the
headline replacement only if it clears this evidence threshold:

- two empirical replays plus one constructive worked example demonstrate the
  same PFLC JSONL contract.

The two empirical replays are:

1. AMB LoCoMo replay from released artifacts.
2. One controlled external adapter from Step 2, if adapter construction passed
   even when CQ-Multi did not win.

The constructive worked example is:

- MemBench factual-memory fact-id PFLC, showing the minimal fields needed to
  unblock PFLC. This is not independent empirical validation.

Minimum PFLC output-contract fields:

- `question_id`;
- `source_sha256`;
- `gold_evidence_ids` and ranked `returned_evidence_ids` for evidence-id
  surfaces;
- `gold_fact_ids` and ranked `returned_fact_ids` or `returned_memory_ids` for
  fact-id surfaces;
- `answer_text`;
- `system_label`;
- `manifest_path`.

Post-publication acceptance criterion remains maintainer adoption by at least
one benchmark. Adoption is not required before submission.

## 7. Step 5: Optional API-Backed Internal Extractor Extension

Step 5 is optional and not authorized until a concrete API model pin is added
by amendment. The amendment must name provider, model id, fallback model, cost
ceiling, and stability check before execution.

Run only if either:

- Steps 2 and 3 both succeed, in which case the paper is already publishable
  and Step 5 is optional strengthening; or
- Step 2 fails or blocks, Step 4 succeeds, and stronger internal evidence is
  needed for reviewer confidence.

Target only bounded-null rows:

- source-independence;
- scope-contamination;
- useful-pending;
- poisoning.

Keep same-stream hashes and same-substrate storage unchanged.

Outcome rules:

- Stronger extraction separates CQ: report mechanism-local support.
- Stronger extraction produces ties: reclassify rows as policy ties or
  weaknesses.
- API outputs are unstable: exclude from headline claims.

## 8. Existing AMB LoCoMo Preservation Rule

The current AMB LoCoMo PFLC decomposition remains a preserved
released-artifact replay result. Do not rerun or reinterpret it as a
CQ-vs-system comparison.

Any naturalistic extension beyond AMB LoCoMo requires a separately
preregistered artifact set and success/null criteria.

## 9. Answerer And API Calibration

Shared answer synthesis is secondary unless PFLC evidence metrics pass.

Calibration requirements:

- two prompts;
- one evidence-order shuffle;
- one model/provider swap where feasible;
- sensitivity intervals in the report.

Do not headline answer correctness if sign or rank changes across calibration
cells.

## 10. Verification Expectations

Before any new empirical claim enters the paper, tests must cover:

- PFLC JSONL validation;
- ranked evidence metrics;
- random/recency baselines;
- distractor floor checks;
- capped controls;
- policy-name to runner-key mapping;
- dataset pinning;
- annotation-lock validation;
- answer leakage and hidden-answer exclusion;
- candidate-stream equality;
- gold evidence extraction;
- cached API replay without network.
<!-- PUBLICATION_HARDENING_PROTOCOL_END -->

## Lock Maintenance

The lock is computed over the block between
`PUBLICATION_HARDENING_PROTOCOL_START` and
`PUBLICATION_HARDENING_PROTOCOL_END`.

Check:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.publication_hardening_lock --check
```

Recompute:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.publication_hardening_lock --recompute
```
