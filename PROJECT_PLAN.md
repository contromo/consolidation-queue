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

## Core Research Invariants

These are load-bearing. Do not violate them casually.

1. Compare policies on the same upstream inputs.
2. Keep the same scoped storage substrate across CQ and ReflectionEagerWrite.
3. Separate architecture evaluation from pipeline evaluation.
4. Run oracle mode before making noisy-mode claims.
5. Measure component quality before claiming end-to-end noisy-mode wins.
6. Prefer reversible memory behavior over raw recall when tradeoffs are exposed.
7. Keep v1 local-first and API-free by default.

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
- `ScopeBlindTranscriptRAGLite` as an oracle-id recency baseline for scope-contamination, preference-drift, useful-pending, and false-corroboration probes
- oracle forced-contradiction scenario generation
- oracle scope-contamination scenario generation, framed as broad-claim premature promotion plus workspace-parent/project-override shadowing
- oracle preference-drift scenario generation with explicit-update, one-off exception, and drift-back probes
- oracle useful-pending-memory scenario generation with clean calibration and dirty refinement probes
- oracle false-corroboration scenario generation with clean independent-source and dirty mirrored-source probes
- multiple clean and dirty forced-contradiction templates with scenario metadata
- clean and dirty main-split scope-contamination templates, including workspace-parent override probes
- held-out scope-contamination templates for clean recency, broad-first premature-promotion, and workspace-parent override probes
- clean and dirty main-split preference-drift templates
- held-out preference-drift templates for stable preference and drift-back probes
- clean and dirty main-split useful-pending-memory templates
- held-out useful-pending-memory templates for clean calibration and dirty refinement probes
- clean and dirty main-split false-corroboration templates
- held-out false-corroboration templates for source-independence surface-form variants
- four reserved held-out dirty contradiction templates
- end-to-end oracle runner
- family-selectable oracle runner
- strict contradiction recovery metric plus `answer_correctness_after_contradiction`
- generic answer correctness, leakage, false assertion, and premature-promotion metrics with contradiction aliases
- per-template-kind and per-template-split oracle summaries
- per-template-id oracle summaries
- deterministic scenario-level failure example extraction in oracle artifacts
- trace dashboard with per-kind summary views and static turn timelines
- dashboard failure-example tables linked to full scenario traces
- running product progress notes in `docs/product_progress.md`
- regression coverage for contradiction branches, scope matching, and metric edge cases

Not implemented yet:

- poisoning scenarios
- lexical or embedding-based `TranscriptRAG`
- component evaluation harness
- local-model noisy pipeline
- 32B/70B routing
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

Status: in progress, broad-claim premature-promotion scope, workspace-parent override scope, preference-drift v1, useful-pending-memory v1, and false-corroboration v1 slices now have main and held-out variants

Add:

- scope contamination family
- `TranscriptRAG`
- preference drift family
- useful pending memory family
- false corroboration family
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
- local extraction and canonicalization pipeline
- local contradiction detection
- structured artifact logging for component outputs

Required outcome:

- oracle vs noisy gap is measurable
- bottlenecks are attributable instead of vague

### Phase 5: Local Adjudication Routing

Add:

- 32B default path
- 70B escalation for contradiction-sensitive cases
- routing diagnostics and latency accounting

Required outcome:

- better contradiction handling without indiscriminate 70B usage

### Phase 6: Final Evaluation and Writeup

Add:

- held-out template split
- threshold sensitivity curves
- latency and cost analysis
- failure-case appendix
- final paper/report structure

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

1. Add poisoning scenarios only when their oracle mechanisms are explicit and diagnosable.
2. Add more independent false-corroboration or scope mechanisms only when they test a distinct failure mode rather than another surface-form variant.
3. Write `docs/preregistration.md` once the oracle benchmark shape is stable.

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
