# Consolidation Queue

Local prototype for staged memory governance experiments.

The first slice in this repository is intentionally narrow:

- oracle-mode forced-contradiction scenarios
- shared in-memory substrate
- `NoMemory-lite`
- `ReflectionEagerWrite-lite`
- `NaiveEagerWrite-lite`
- `CQ-Agent-lite`
- end-to-end metrics and run artifacts
- a small local dashboard for inspecting traces
- a running product progress log in `docs/product_progress.md`

The goal is to isolate the memory policy question before adding noisy extraction.

## Quickstart

Run the oracle benchmark:

```bash
python3 -m cq.eval.runner --scenarios 25
```

This writes:

- `data/runs/forced_contradiction_oracle.json`
- `data/results/forced_contradiction_oracle_metrics.csv`

Open the dashboard against the saved run:

```bash
python3 -m cq.dashboard.app data/runs/forced_contradiction_oracle.json --port 8000
```

Or render a static HTML file:

```bash
python3 -m cq.dashboard.app data/runs/forced_contradiction_oracle.json --write-html data/results/dashboard.html
```

Run tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Design Notes

- The first implementation is stdlib-only so it runs on the default macOS Python.
- Schema fields mirror the standalone write-up, but use dataclasses instead of Pydantic for now.
- All policies share the same substrate. The main difference is policy:
  - no memory is the zero-history floor baseline
  - naive eager write commits immediately and keeps contradictory durables active
  - reflection eager write commits immediately but only overwrites on a contradiction margin
  - CQ can use pending memory without durable promotion
- `contradiction_recovery_rate` remains the headline memory-governance metric.
- `answer_correctness_after_contradiction` is the policy-agnostic answer-quality view used alongside recovery.
- `TranscriptRAG-lite` is intentionally deferred until the first scope-contamination patch, where transcript retrieval can fail informatively.
