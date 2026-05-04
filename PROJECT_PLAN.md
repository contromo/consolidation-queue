# Consolidation Queue Project Plan

Last updated: 2026-05-04

## Goal

Build a local research prototype and benchmark that tests whether staged memory promotion improves reversibility over a strong immediate-write baseline.

Primary comparison:

- `CQ-Agent` / `ConsolidationQueueLite`
- `ReflectionEagerWrite` / `ReflectionEagerWriteLite`

Secondary comparisons:

- `NoMemory`
- `TranscriptRAG`
- `NaiveEagerWrite`

External/published-family comparison:

- `Mem0Lite`, a rule-based ADD/UPDATE/DELETE/NOOP write-time policy over the same CQ oracle/noisy candidates

## Core Research Invariants

These are load-bearing. Do not violate them casually.

1. Compare policies on the same upstream inputs.
2. Keep the same scoped storage substrate across CQ and ReflectionEagerWrite.
3. Separate architecture evaluation from pipeline evaluation.
4. Run oracle mode before making noisy-mode claims.
5. Measure component quality before claiming end-to-end noisy-mode wins.
6. Prefer reversible memory behavior over raw recall when tradeoffs are exposed.
7. Keep v1 local-first and API-free by default.
8. When adapting a published system into a `Lite` baseline, document what is and is not faithful.

## Research Question

Does staged memory promotion improve long-horizon personalization and factual consistency compared with a strong immediate-write baseline, especially under:

- contradiction
- preference drift
- scope contamination
- memory poisoning
- false corroboration
- useful-but-not-yet-durable context

## Current Repository Status

Implemented:

- shared in-memory substrate with lifecycle logging
- shared explicit source-independence corroboration counting for supported candidate observations
- shared candidate and durable memory schemas
- `ReflectionEagerWriteLite`
- `NaiveEagerWriteLite`
- `NoMemoryLite`
- `ConsolidationQueueLite`
- `ScopeBlindTranscriptRAGLite` as an oracle-id recency baseline for scope-contamination, preference-drift, useful-pending, false-corroboration, and memory-poisoning probes
- oracle forced-contradiction scenario generation
- oracle scope-contamination scenario generation, framed as broad-claim premature promotion plus workspace-parent/project-override shadowing
- oracle preference-drift scenario generation with explicit-update, one-off exception, and drift-back probes
- oracle useful-pending-memory scenario generation with clean calibration and dirty refinement probes
- oracle false-corroboration scenario generation with clean independent-source and dirty mirrored-source probes
- oracle memory-poisoning scenario generation with clean trusted, dirty below-floor injection, dirty pending-eligible injection, and same-scope override-attack probes
- multiple clean and dirty forced-contradiction templates with scenario metadata
- clean and dirty main-split scope-contamination templates, including workspace-parent override probes
- held-out scope-contamination templates for clean recency, broad-first premature-promotion, and workspace-parent override probes
- clean and dirty main-split preference-drift templates
- held-out preference-drift templates for stable preference and drift-back probes
- clean and dirty main-split useful-pending-memory templates
- held-out useful-pending-memory templates for clean calibration and dirty refinement probes
- clean and dirty main-split false-corroboration templates
- held-out false-corroboration templates for source-independence surface-form variants
- clean and dirty main-split memory-poisoning templates, including override shadow and borderline regimes
- held-out memory-poisoning templates for untrusted-injection and override surface-form variants
- four reserved held-out dirty contradiction templates
- end-to-end oracle runner
- family-selectable oracle runner
- strict contradiction recovery metric plus `answer_correctness_after_contradiction`
- generic answer correctness, leakage, false assertion, and premature-promotion metrics with contradiction aliases
- clean durable displacement metric for poisoning override diagnostics
- per-template-kind and per-template-split oracle summaries
- per-template-id oracle summaries
- deterministic scenario-level failure example extraction in oracle artifacts
- trace dashboard with per-kind summary views and static turn timelines
- dashboard failure-example tables linked to full scenario traces
- running product progress notes in `docs/product_progress.md`
- regression coverage for contradiction branches, scope matching, and metric edge cases

Not implemented yet:

- lexical or embedding-based `TranscriptRAG`
- `Mem0Lite` external published-family baseline
- CQ ablation policy variants
- mechanism-diverse frozen held-out scenarios
- component evaluation harness
- local-model noisy pipeline
- optional 32B/70B routing
- LongMemEval transfer check
- preregistration and final writeup docs

## Repository Map

- `PROJECT_PLAN.md`: source of truth for execution order and research constraints
- `AGENTS.md`: instructions for future coding agents
- `docs/product_progress.md`: running log of what shipped, what mattered, and what the latest results say
- `README.md`: setup and quickstart
- `docs/`: focused specs and later preregistration material
- `cq/schemas/`: core dataclasses and enums
- `cq/memory/`: substrate and policy implementations
- `cq/simulator/`: oracle scenarios and transcript rendering
- `cq/eval/`: metrics, runner, and evaluation logic
- `cq/dashboard/`: local trace inspection
- `tests/`: focused behavioral tests
- `data/runs/`, `data/results/`: saved experiment artifacts

## Phases

### Phase 1: Oracle Forced-Contradiction Slice

Status: in progress, first thin slice exists

Required outcome:

- shared substrate works
- CQ and ReflectionEagerWrite run on the same oracle scenarios
- lifecycle traces are inspectable
- contradiction metrics are reproducible

Immediate gap:

- the contradiction family now has multiple dirty variants and four held-out templates
- the held-out split now includes both a Naive-recovery case and a confidence-first Naive failure case
- `NoMemoryLite` and `answer_correctness_after_contradiction` now make the contradiction slice easier to interpret
- it still needs more held-out variants before conclusions mean much

### Phase 2: Stronger Oracle Benchmark

Status: in progress, broad-claim premature-promotion scope, workspace-parent override scope, preference-drift v1, useful-pending-memory v1, false-corroboration v1, and memory-poisoning v1 slices now have main and held-out variants

Add:

- scope contamination family
- `TranscriptRAG`
- preference drift family
- useful pending memory family
- false corroboration family
- memory poisoning family
- scenario-level failure example extraction

Required outcome:

- CQ and ReflectionEagerWrite diverge on meaningful held-out oracle cases
- metrics cover scope leakage and premature promotion in addition to contradiction recovery
- transcript retrieval baselines can be evaluated on a family where off-scope text should hurt

Current caveat:

- the scope-contamination split should still be described as oracle scope-key behavior, not evidence that CQ performs better semantic scope inference than Reflection
- workspace-parent override probes evaluate CQ's exact-scope pending override lookup while keeping the wider workspace durable active; Reflection receives the same shared scope matching but keeps eager-write baseline behavior
- preference drift now includes an explicit-update calibration point plus one-off and drift-back probes that distinguish staged promotion from pure recency
- useful-pending memory now includes clean calibration and dirty refinement probes where all candidates are below durable-promotion threshold but strong enough for pending use
- scenario-level failure examples now expose assertion, leakage, premature-promotion, and no-memory floor failures in saved artifacts and the dashboard
- Phase 2 scope coverage now includes a non-`WORLD_GLOBAL` mechanism, but broader scope-inference claims still require noisy scope-inference evaluation
- ScopeBlindTranscriptRAG follows truth by recency on useful-pending-memory probes, so that family should be read as CQ-vs-eager policy evidence, not retrieval-baseline evidence
- false-corroboration probes test explicit oracle source-id independence, not learned semantic source independence
- false-corroboration held-out templates are surface-form variants of the same mirrored-source mechanism, not mechanism-diversity evidence
- ScopeBlindTranscriptRAG fails dirty false-corroboration probes by recency, not by durable promotion
- memory-poisoning v1 tests untrusted injection plus same-scope override attacks against existing clean durables
- pending-eligible memory-poisoning probes intentionally expose CQ false assertion from pending memory while preserving zero durable poison promotion
- override-attack probes expose CQ's exact-scope durable demotion path; shadow and borderline are strength regimes of the same mechanism, not distinct mechanisms
- memory-poisoning held-out templates are surface-form variants, not evidence of mechanism diversity
- adversarial corroboration and scope-laundered poison remain untested

### Phase 2.5: External Baseline, Ablations, and Frozen Generalization Set

Status: not started

This phase must happen before Phase 3 component evaluation and before preregistering noisy-mode predictions. The point is to commit to comparison targets and disconfirmation tests before more pipeline work can tune around them.

Add:

- `Mem0Lite`, implemented as a rule-based ADD/UPDATE/DELETE/NOOP policy over the shared candidate and storage substrate
- four named CQ ablation variants
- a mechanism-diverse held-out set with net-new mechanisms
- `docs/preregistration.md` with prediction-bearing quantitative commitments

`Mem0Lite` design call:

- Do not put a Mem0-style LLM operation classifier into the oracle comparison.
- Do not claim this is a faithful reproduction of Mem0's full system.
- Frame it as testing whether the ADD/UPDATE/DELETE/NOOP write discipline beats staged promotion when both policies receive the same oracle candidates, scopes, strengths, and contradiction/support metadata.
- Treat oracle-mode `Mem0Lite` as a partial baseline result because it is likely close to eager write with deduplication. The headline `Mem0Lite` comparison belongs after Phase 4, where noisy extraction and update decisions can matter.

Required CQ ablations:

- `cq_no_contestation_demotion`: disables the contestation/demotion path for contradictory candidates and active durables.
- `cq_no_wider_scope_pending_override`: disables the narrower pending override exception for active wider-scope durables.
- `cq_no_pending_lookup_use`: disables answering from pending candidates on lookup.
- `cq_no_source_independence_gate`: disables source-independence corroboration gating for CQ promotion decisions while keeping the candidate stream and substrate fields visible.

Ablation rules:

- Run each ablation with the same thresholds unless a preregistered sensitivity run explicitly changes them.
- Label ablation artifacts separately from full CQ artifacts.
- Do not add new CQ features after seeing frozen held-out or ablation results without marking the run as post-hoc.

Mechanism-diverse held-out set:

- `false_corroboration_adversarial_mixed_source`: mirrored false reports interleaved with one legitimate independent source.
- `memory_poisoning_scope_laundered`: poison enters through a legitimate wider scope before a narrower query exposes contamination.
- `preference_drift_long_horizon_corrections`: multiple drift and correction episodes rather than one-off update or drift-back.

Held-out rules:

- These are not relabeled v2 surface-form templates.
- Freeze scenario contracts, expected lifecycle, and metrics before CQ tuning or threshold changes.
- Use this set as the only basis for mechanism-generalization claims.
- Continue reporting existing v2 held-outs as surface-form robustness checks, not mechanism-diversity evidence.

Preregistration requirements:

- `docs/preregistration.md` must contain predictions, not only task lists.
- Predictions must include numeric deltas for CQ vs `Mem0Lite`, CQ vs ReflectionEagerWrite, and full CQ vs each named CQ ablation.
- Predictions must include oracle-mode and noisy-mode expectations, including expected oracle-vs-noisy gaps by policy.
- If results contradict the predictions, report the contradiction directly in the final writeup.

Required outcome:

- reviewers can see that external comparison, ablation, and mechanism-generalization tests were specified before noisy-mode work
- the project can produce negative, mixed, or CQ-favorable results without changing the evaluation contract

### Phase 3: Component Evaluation Harness

Add:

- candidate extraction eval
- claim type eval
- scope inference eval
- canonicalization eval
- contradiction detection eval

Required outcome:

- explicit quality gates before noisy-mode claims
- gold labels attached to scenarios

### Phase 4: Noisy Local-Model Pipeline

Add:

- natural-language transcript mode
- off-the-shelf local extractor using a model such as Llama 3.1 8B or Qwen 2.5 7B
- local extraction, canonicalization, and contradiction detection without model fine-tuning
- structured artifact logging for component outputs

Scope cap:

- cap Phase 4 extractor work at four weeks
- run the existing benchmark with extracted candidates instead of oracle candidates
- measure component F1 against Phase 3 gold labels
- compare oracle-vs-noisy gaps per policy
- if component quality misses the gates below, report the failure and stop rather than turning extractor tuning into a separate research project

Required outcome:

- oracle vs noisy gap is measurable
- bottlenecks are attributable instead of vague

### Phase 5: Optional Local Adjudication Routing

Add:

- 32B default path
- 70B escalation for contradiction-sensitive cases
- routing diagnostics and latency accounting

Required outcome:

- better contradiction handling without indiscriminate 70B usage

Priority note:

- this is engineering optimization, not the core research contribution
- do not start Phase 5 before Phase 2.5, Phase 3, Phase 4, and the preregistered evaluation pass are complete unless the user explicitly reprioritizes it

### Phase 6: Final Evaluation and Writeup

Add:

- held-out template split
- mechanism-diverse held-out analysis
- CQ ablation analysis
- `Mem0Lite` comparison, clearly separated into oracle-mode and noisy-mode claims
- threshold sensitivity curves
- LongMemEval transfer check
- latency and cost analysis
- failure-case appendix
- final paper/report structure

LongMemEval positioning:

- Use LongMemEval as an external task-design transfer check after Phase 4.
- Do not frame the claim as "beating LongMemEval".
- Frame the claim as whether the CQ-vs-baseline policy comparison transfers to a benchmark the project did not design.
- Keep real-user, weeks-long helpfulness as an explicit limitation and future-work item.

## Scenario Families

Target families:

1. forced contradiction
2. preference drift
3. scope contamination
4. memory poisoning
5. false corroboration
6. useful pending memory

For each family:

- include clean templates
- include dirty templates
- split by template, not just instance
- store latent truth, oracle events, transcript, and expected lifecycle

## Metrics That Matter

Primary metrics:

- useful recall
- false assertion rate
- contradiction recovery rate
- time to demotion
- scope leakage rate
- poison promotion rate
- premature promotion rate
- memory precision
- memory recall
- pending utility gain

Secondary composite:

- reversible memory score

Do not let the composite metric dominate interpretation.

## Noisy-Mode Quality Gates

Before claiming noisy-mode end-to-end wins, target these minimums:

- candidate detection F1: `>= 0.75`
- claim type accuracy: `>= 0.75`
- scope level accuracy: `>= 0.70`
- scope key accuracy: `>= 0.60`
- canonicalization B-cubed F1: `>= 0.65`
- contradiction F1: `>= 0.75`
- contradiction precision: `>= 0.75`
- contradiction recall: `>= 0.70`

If the pipeline misses these gates, report that directly.

## Cost and Latency Gates

Precommit:

- CQ should stay within `<= 2x` wall-clock time of ReflectionEagerWrite under similar extraction quality

Relaxed ceiling:

- CQ must stay within `<= 3x`

CQ should earn its complexity with at least one of:

- `>= 10` point contradiction recovery improvement
- `>= 10` point poison promotion reduction
- `>= 10` point scope leakage reduction
- pending utility gain without useful recall loss

Without:

- `> 10` point useful recall loss
- `> 3x` wall-clock cost

## Immediate Next Tasks

These are the highest-priority implementation steps right now.

1. Implement Phase 2.5 specs before Phase 3: `Mem0Lite`, named CQ ablations, and mechanism-diverse held-out scenarios.
2. Write `docs/preregistration.md` with numeric predictions before running Phase 2.5 result sweeps or noisy-mode evaluations.
3. Start the component evaluation harness only after the Phase 2.5 comparison contract is frozen.
4. Add more independent false-corroboration, poisoning, scope, or drift mechanisms only when they test a distinct failure mode rather than another surface-form variant.

## Working Rules

1. Do not give CQ a richer storage model than ReflectionEagerWrite.
2. Do not “win” by giving one system better extraction inputs.
3. Prefer minimal code that keeps the experiment legible.
4. Keep saved artifacts inspectable.
5. Add tests for policy behavior, not just helpers.
6. When a change materially alters priorities or milestones, update this file in the same patch.
7. If a user request conflicts with this plan, follow the user and then reconcile the plan.

## Definition of Done For A Meaningful Milestone

A milestone is only done when all of the following are true:

- implementation exists
- tests cover the new behavior
- runner or artifact output exposes the behavior
- the dashboard or saved traces make failures inspectable
- the plan and relevant docs are updated
