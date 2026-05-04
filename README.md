# Consolidation Queue

Local prototype for staged memory governance experiments.

The first slice in this repository is intentionally narrow:

- oracle-mode forced-contradiction scenarios
- oracle-mode scope-contamination scenarios, framed as broad-claim premature promotion plus workspace-parent/project-override shadowing
- oracle-mode preference-drift scenarios, framed as explicit update plus one-off/drift-back probes
- oracle-mode useful-pending-memory scenarios, framed as reversible pending utility
- shared in-memory substrate
- `NoMemory-lite`
- `ReflectionEagerWrite-lite`
- `NaiveEagerWrite-lite`
- `CQ-Agent-lite`
- `ScopeBlindTranscriptRAG-lite` on the scope-contamination, preference-drift, and useful-pending-memory families
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

Run the scope-contamination slice:

```bash
python3 -m cq.eval.runner --family scope_contamination --scenarios 10 --template-mix mixed
```

This writes:

- `data/runs/scope_contamination_oracle.json`
- `data/results/scope_contamination_oracle_metrics.csv`

Run the held-out scope-contamination slice:

```bash
python3 -m cq.eval.runner --family scope_contamination --scenarios 4 --template-mix heldout --output-json data/runs/scope_contamination_oracle_heldout.json --output-csv data/results/scope_contamination_oracle_heldout_metrics.csv
```

This writes:

- `data/runs/scope_contamination_oracle_heldout.json`
- `data/results/scope_contamination_oracle_heldout_metrics.csv`

Run the preference-drift slice:

```bash
python3 -m cq.eval.runner --family preference_drift --scenarios 6 --template-mix mixed
```

This writes:

- `data/runs/preference_drift_oracle.json`
- `data/results/preference_drift_oracle_metrics.csv`

Run the held-out preference-drift slice:

```bash
python3 -m cq.eval.runner --family preference_drift --scenarios 4 --template-mix heldout --output-json data/runs/preference_drift_oracle_heldout.json --output-csv data/results/preference_drift_oracle_heldout_metrics.csv
```

This writes:

- `data/runs/preference_drift_oracle_heldout.json`
- `data/results/preference_drift_oracle_heldout_metrics.csv`

Run the useful-pending-memory slice:

```bash
python3 -m cq.eval.runner --family useful_pending_memory --scenarios 4 --template-mix mixed
```

This writes:

- `data/runs/useful_pending_memory_oracle.json`
- `data/results/useful_pending_memory_oracle_metrics.csv`

Run the held-out useful-pending-memory slice:

```bash
python3 -m cq.eval.runner --family useful_pending_memory --scenarios 4 --template-mix heldout --output-json data/runs/useful_pending_memory_oracle_heldout.json --output-csv data/results/useful_pending_memory_oracle_heldout_metrics.csv
```

This writes:

- `data/runs/useful_pending_memory_oracle_heldout.json`
- `data/results/useful_pending_memory_oracle_heldout_metrics.csv`

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
  - scope-blind transcript RAG is an oracle-id recency baseline that intentionally ignores scope
- `contradiction_recovery_rate` remains the headline memory-governance metric.
- `answer_correctness_after_contradiction` is the policy-agnostic answer-quality view used alongside recovery.
- Scope-contamination now includes main and held-out broad-claim probes plus workspace-parent/project-override probes. These show oracle scope-key behavior, premature promotion, and active wider-scope shadowing, not a general claim that CQ reasons semantically about scope better than Reflection.
- Preference-drift now includes main and held-out probes. The explicit-update template is contradiction-like, while the one-off and drift-back templates distinguish staged promotion from pure recency.
- Useful-pending-memory includes main and held-out probes where every candidate is a `PROJECT_CONVENTION` in the `[0.35, 0.70)` strength band. Clean templates calibrate that pending utility does not cost answer correctness; dirty refinement templates show eager reversibility debt when no claim is durable-eligible. ScopeBlindTranscriptRAG follows truth by recency here, so this family is not evidence about retrieval quality.
