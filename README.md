# Consolidation Queue

Local prototype for staged memory governance experiments.

The first slice in this repository is intentionally narrow:

- oracle-mode forced-contradiction scenarios
- oracle-mode scope-contamination scenarios, framed as broad-claim premature promotion plus workspace-parent/project-override shadowing
- oracle-mode preference-drift scenarios, framed as explicit update plus one-off/drift-back probes
- oracle-mode useful-pending-memory scenarios, framed as reversible pending utility
- oracle-mode false-corroboration scenarios, framed as explicit source-independence handling
- oracle-mode memory-poisoning scenarios, framed as below-floor and pending-eligible untrusted injection plus same-scope override attacks
- shared in-memory substrate
- `NoMemory-lite`
- `ReflectionEagerWrite-lite`
- `NaiveEagerWrite-lite`
- `CQ-Agent-lite`
- four Phase 2.5 CQ ablations
- `ScopeBlindTranscriptRAG-lite` on the scope-contamination, preference-drift, useful-pending-memory, false-corroboration, and memory-poisoning families
- locked mechanism-diverse held-out contracts with preregistered predictions
- Phase 3 component-evaluation reference artifacts
- transcript-only extractor bridge for Phase 4 smoke tests
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

Run the false-corroboration slice:

```bash
python3 -m cq.eval.runner --family false_corroboration --scenarios 4 --template-mix mixed
```

This writes:

- `data/runs/false_corroboration_oracle.json`
- `data/results/false_corroboration_oracle_metrics.csv`

Run the held-out false-corroboration slice:

```bash
python3 -m cq.eval.runner --family false_corroboration --scenarios 4 --template-mix heldout --output-json data/runs/false_corroboration_oracle_heldout.json --output-csv data/results/false_corroboration_oracle_heldout_metrics.csv
```

This writes:

- `data/runs/false_corroboration_oracle_heldout.json`
- `data/results/false_corroboration_oracle_heldout_metrics.csv`

Run the memory-poisoning slice:

```bash
python3 -m cq.eval.runner --family memory_poisoning --scenarios 10 --template-mix mixed
```

This writes:

- `data/runs/memory_poisoning_oracle.json`
- `data/results/memory_poisoning_oracle_metrics.csv`

Run the held-out memory-poisoning slice:

```bash
python3 -m cq.eval.runner --family memory_poisoning --scenarios 10 --template-mix heldout --output-json data/runs/memory_poisoning_oracle_heldout.json --output-csv data/results/memory_poisoning_oracle_heldout_metrics.csv
```

This writes:

- `data/runs/memory_poisoning_oracle_heldout.json`
- `data/results/memory_poisoning_oracle_heldout_metrics.csv`

Run the Phase 2.5 policy set on an existing family:

```bash
python3 -m cq.eval.runner --family false_corroboration --scenarios 4 --template-mix mixed --policy-set phase2_5
```

Run the locked mechanism-diverse held-out set after preregistration:

```bash
python3 -m cq.eval.runner --family mechanism_diverse_heldout --template-mix frozen --policy-set phase2_5
```

Check or recompute the frozen preregistration lock:

```bash
python3 -m cq.eval.preregistration_lock --check
python3 -m cq.eval.preregistration_lock --recompute
```

Run the Phase 3 component-evaluation oracle upper bound:

```bash
python3 -m cq.eval.component_eval --family forced_contradiction --scenarios 4 --template-mix dirty
```

Save the Phase 3 forced-contradiction reference artifact:

```bash
python3 -m cq.eval.component_eval --family forced_contradiction --scenarios 6 --template-mix mixed --output-json data/results/forced_contradiction_component_eval_oracle_upper_bound_mixed.json
```

Score saved component predictions from a noisy extractor:

```bash
python3 -m cq.eval.component_eval --family forced_contradiction --scenarios 4 --template-mix dirty --predictions-json data/results/component_predictions.json
```

Prediction JSON must use a top-level `scenario_predictions` object keyed by `scenario_id`. Extractor predictions should use event-aligned contradiction edges with `contradicts_event_ids`; legacy oracle/backcompat predictions may still use `candidate_id` and `contradicts`. Optional `confidence` values must be numeric or `null`.

Run the transcript-only local extractor bridge smoke tests:

```bash
python3 -m cq.pipeline.local_extractor --family forced_contradiction --scenarios 6 --template-mix mixed --mode weak --output-json data/results/forced_contradiction_local_extractor_weak_predictions.json
python3 -m cq.eval.component_eval --family forced_contradiction --scenarios 6 --template-mix mixed --predictions-json data/results/forced_contradiction_local_extractor_weak_predictions.json --output-json data/results/forced_contradiction_local_extractor_weak_component_eval.json
python3 -m cq.pipeline.local_extractor --family forced_contradiction --scenarios 6 --template-mix mixed --mode positive_control --output-json data/results/forced_contradiction_local_extractor_positive_control_predictions.json
python3 -m cq.eval.component_eval --family forced_contradiction --scenarios 6 --template-mix mixed --predictions-json data/results/forced_contradiction_local_extractor_positive_control_predictions.json --output-json data/results/forced_contradiction_local_extractor_positive_control_component_eval.json
```

The weak mode is a negative control that should fail measured gates on forced contradiction. The positive-control mode is a deterministic text matcher that validates the bridge; it is not extractor-quality evidence.

Run a transcript-only command-adapter extractor with a user-provided local model wrapper:

```bash
python3 -m cq.pipeline.local_extractor --family forced_contradiction --scenarios 6 --template-mix mixed --mode model --model-command './run_local_extractor.sh' --model-id 'local-model-name:revision' --prompt-template-path path/to/extractor_prompt.txt --decoding-json '{"temperature": 0}' --per-scenario-timeout-seconds 120 --output-json data/results/forced_contradiction_local_extractor_model_predictions.json
python3 -m cq.eval.component_eval --family forced_contradiction --scenarios 6 --template-mix mixed --predictions-json data/results/forced_contradiction_local_extractor_model_predictions.json --output-json data/results/forced_contradiction_local_extractor_model_component_eval.json
```

In `model` mode, the command runs once per scenario and receives a transcript-only JSON envelope on stdin. It must write strict JSON on stdout with a top-level `predictions` list. Per-scenario failures are saved in `scenario_errors`; `component_eval` reports them and scores those scenarios as zero predictions.

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
- Oracle upper-bound component artifacts are reference artifacts only. They validate labels, scorer wiring, and saved output shape by construction; they do not show that a noisy pipeline works.
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
- False-corroboration includes main and held-out source-independence probes where weak `PROJECT_CONVENTION` candidates only corroborate through explicit `supports` edges and distinct provenance source ids. Dirty mirrored-source templates test the shared oracle independence gate, not learned semantic independence; ScopeBlindTranscriptRAG fails dirty probes by recency rather than durable promotion.
- Memory-poisoning includes main and held-out untrusted-injection probes plus same-scope override attacks against an existing clean durable. Below-floor dirty templates show eager durable poison promotion from immediate writes; pending-eligible dirty templates intentionally expose CQ false assertion from pending memory while still avoiding durable poison promotion. Override shadow and borderline templates expose CQ's exact-scope durable demotion path and are measured with `clean_durable_displacement_rate`. This v1 family does not test adversarial corroboration or scope-laundered poison.
- Component contradiction scoring now supports extractor-safe `contradicts_event_ids` and treats edges as undirected within a scenario. If a scenario set has no gold or predicted contradiction edges, contradiction gates are marked not applicable instead of failed; false-positive predicted edges still fail the measured gates.
- The transcript-only extractor bridge exposes only `scenario_id`, event order, `event_id`, event kind, and text. It excludes oracle candidates, gold ids, lifecycle expectations, metrics, and policy traces.
- Component evaluation reads extractor `scenario_errors` when present, reports them separately, and scores errored scenarios as zero predictions rather than excluding them.
- The current component gold has one candidate per observation event. Extra same-event predictions are counted as false positives while the best same-event prediction is used for claim, scope, and canonicalization scoring.
