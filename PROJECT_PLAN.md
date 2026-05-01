# Consolidation Queue Project Plan

Last updated: 2026-04-26

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
- shared candidate and durable memory schemas
- `ReflectionEagerWriteLite`
- `NaiveEagerWriteLite`
- `ConsolidationQueueLite`
- oracle forced-contradiction scenario generation
- multiple clean and dirty forced-contradiction templates with scenario metadata
- four reserved held-out dirty contradiction templates
- end-to-end oracle runner
- per-template-kind and per-template-split oracle summaries
- per-template-id oracle summaries
- trace dashboard with per-kind summary views and static turn timelines
- running product progress notes in `docs/product_progress.md`
- regression coverage for contradiction branches, scope matching, and metric edge cases

Not implemented yet:

- `NoMemory`
- `TranscriptRAG`
- preference drift scenarios
- scope contamination scenarios
- poisoning scenarios
- false corroboration scenarios
- useful-pending-memory scenarios beyond the current contradiction slice
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
- it still needs more held-out variants and richer failure extraction before conclusions mean much

### Phase 2: Stronger Oracle Benchmark

Add:

- preference drift family
- scope contamination family
- `NoMemory` and `TranscriptRAG`
- scenario-level failure example extraction

Required outcome:

- CQ and ReflectionEagerWrite diverge on meaningful held-out oracle cases
- metrics cover scope leakage and premature promotion in addition to contradiction recovery

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

Without:

- `> 10` point useful recall loss
- `> 3x` wall-clock cost

## Immediate Next Tasks

These are the highest-priority implementation steps right now.

1. Add more held-out contradiction templates with distinct failure mechanisms.
2. Add `NoMemory` and `TranscriptRAG` baselines on the same substrate interface where possible.
3. Add preference drift and scope contamination oracle families.
4. Extend the progress log with concise experiment-result entries as major benchmark slices land.
5. Write `docs/preregistration.md` once the oracle benchmark shape is stable.

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
