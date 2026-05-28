# Agent Instructions

Read this file first. Then read `PROJECT_PLAN.md` and `docs/product_progress.md` before making architecture, benchmark, or policy changes.

## Read Order

For any non-trivial task, use this order:

1. `AGENTS.md`
2. `PROJECT_PLAN.md`
3. `docs/product_progress.md`
4. `README.md`
5. the relevant spec or code file for the task

If the user gives instructions that conflict with this file or the project plan:

- follow the user
- do not argue with the repo
- update `PROJECT_PLAN.md` if the new direction materially changes priorities

## What This Repository Is

This repo is a research prototype for memory governance in persistent agents.

The main scientific constraint is simple:

- compare memory policies fairly

That means CQ must not quietly win because it got better inputs, better storage, or easier scenarios than the eager baseline.

## Non-Negotiable Invariants

1. Keep CQ and ReflectionEagerWrite on the same upstream candidate stream when running a comparison.
2. Keep the same storage substrate unless the task is explicitly about changing the shared substrate for both systems.
3. Separate oracle-mode claims from noisy-mode claims.
4. Do not claim noisy-mode success without checking component quality.
5. Prefer local-first, API-free implementations unless the user explicitly asks otherwise. Any API-backed paper-hardening work must be preregistered, cached, and replayable before it can support a claim.
6. Keep the experiment inspectable through saved artifacts and traces.

## How To Work In This Repo

When you start a substantive task:

1. Identify which item in `PROJECT_PLAN.md` the task advances.
2. Read the relevant existing implementation before editing.
3. Preserve shared interfaces where the comparison depends on them.
4. Add or update tests if policy behavior changes.
5. Update `PROJECT_PLAN.md` if the repo status, milestone order, or next tasks changed.
6. Add a concise entry to `docs/product_progress.md` when the change materially affects benchmark coverage, results, or conclusions.

When adding new benchmark families:

1. Add latent/oracle structure first.
2. Add clean and dirty templates.
3. Keep template splits explicit.
4. Add metrics before adding commentary.

When changing a memory policy:

1. Keep the comparison fair.
2. Log lifecycle transitions.
3. Preserve provenance, scope, and reversibility fields.
4. Add a targeted regression test.

When adding noisy-mode work:

1. Keep it clearly separate from oracle mode.
2. Record component outputs so failures are diagnosable.
3. Do not blur extractor quality with policy quality in writeups or summaries.

## What To Avoid

- do not add a richer private CQ-only memory representation
- do not inflate benchmark wins with asymmetric plumbing
- do not hide failure cases
- do not expand dependencies casually
- do not replace inspectable traces with opaque scoring only
- do not skip plan updates after meaningful scope changes

## Definition Of A Good Change

A good change in this repo usually does at least three things:

- improves the experiment itself
- improves observability of failure modes
- keeps the comparison sharper instead of blurrier

## File Maintenance

Treat `PROJECT_PLAN.md` as a living execution document.

Update it when:

- a phase meaningfully changes
- a major task is completed
- immediate next tasks change
- the research framing or constraints materially change

Do not rewrite the whole plan for minor implementation details.
