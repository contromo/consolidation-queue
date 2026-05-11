# Product Progress

## 2026-05-11 — Publication outline and locked-gate taxonomy drafted

### What shipped

- added `docs/component_gate_publication_outline.md` to define the publishable benchmark-plus-failure-taxonomy package, target framing, section structure, and minimum additional evidence decision
- added `docs/component_gate_failure_taxonomy.md` as a repo-tracked interpretation note for the locked 7B `general_v1` gate, including the per-family blocker pattern, four mode-level failure modes, and the oracle/noisy bridge
- kept the locked 7B verdict fixed while drafting: no new 7B rerun, no 32B descriptive row, no second model-family row, and no validator or threshold changes

### Why it matters

- the publication story now has an explicit structure: oracle-mode benchmark result, gate methodology, failure taxonomy, and blocked noisy-mode policy claim
- the minimum extra evidence is now scoped to one descriptive 32B `scope_contamination` row; a second model family is conditional rather than assumed
- the locked noisy-mode result is now integrated with the existing oracle-mode `Mem0Lite` comparison instead of living as a standalone postmortem
- LongMemEval is positioned as future transfer work rather than a missing current experiment

### Evidence

- new docs:
  - `docs/component_gate_publication_outline.md`
  - `docs/component_gate_failure_taxonomy.md`
- no new Ollama inference was run
- no tests were run because this change is documentation-only

### Open issues / next

- run one descriptive 32B `scope_contamination` row only if the publication draft still needs size-scaling evidence beyond the current 7B lock
- otherwise continue by folding the oracle benchmark result and the locked-gate taxonomy into a single paper/report draft

## 2026-05-11 — Real 7B component gate run stayed locked

### What shipped

- ran the authoritative 7B `general_v1` CI-aware gate decision through `scripts/run_component_gate_decision.py` with the required frozen sentinel and without 32B headroom
- wrote the full gate artifact set under `data/results/`, including the summary artifact `component_gate_decision_general_v1_summary.json`
- confirmed the preflight guards passed in the real run: `phase_a_passed=true` and `determinism_passed=true`

### Why it matters

- the gate remained locked: `policy_comparison_unlocked=false`
- the lock was not driven by aggregate CI math; aggregate CI failure count was `0` and aggregate observed canonicalization failure count was `0`
- the decisive blockers were component-quality/model-following failures: `45` primary scenario errors, `8` primary observed gate failures, and `3` frozen-sentinel observed gate failures
- primary scenario errors were concentrated in invalid model outputs rather than runner arithmetic: `scope_contamination` `12`, `preference_drift` `8`, `useful_pending_memory` `3`, `false_corroboration` `17`, and `memory_poisoning` `5`
- direct payload inspection confirmed the scenario-error subclasses are model-output defects, not runner bugs: empty `scope_key`, empty `canonical_id`, and canonical-id slugs incorrectly emitted as `contradicts_event_ids` entries
- the inspected failure taxonomy now resolves into four mode-level patterns: required-field omission, ID-namespace confusion between `canonical_id` and `contradicts_event_ids`, durable-claim drift into `temporary_constraint`/`session`, and contradiction-edge misses
- the cross-family rollup masked the failure pattern; aggregate gates passed while per-family and frozen-sentinel checks did the actual blocking work
- the `8` primary observed gate failures were concentrated rather than diffuse: `scope_contamination` `3`, `preference_drift` `2`, `false_corroboration` `1`, and `memory_poisoning` `2`
- the frozen sentinel miss is substantive rather than just held-out spread: the fixed `frozen_preference_drift_001` scenario itself carries the same empty-`scope_key` and contradiction-chain defects
- under the project contract, this keeps Phase 4 noisy policy comparison work on hold and shifts the current writeup framing toward benchmark/failure-taxonomy contribution rather than a CQ noisy-policy contribution

### Evidence

- command: `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py --include-frozen-sentinel`
- runtime: `3279157` ms (`54m 39s`)
- summary artifact: `data/results/component_gate_decision_general_v1_summary.json`
- inspected scenario-error subclass counts:
  - empty `scope_key`: `15` primary scenarios plus `1` frozen-sentinel scenario
  - empty `canonical_id`: `25` primary scenarios
  - invalid `contradicts_event_ids` target: `5` primary scenarios, all from canonical-id slugs emitted where earlier event ids were required
- unlock checks:
  - `phase_a_passed=true`
  - `determinism_passed=true`
  - `primary_scenario_error_count=45`
  - `primary_observed_gate_failure_count=8`
  - `frozen_sentinel_observed_gate_failure_count=3`
  - `aggregate_ci_gate_failure_count=0`
  - `aggregate_observed_gate_failure_count=0`
  - `policy_comparison_unlocked=false`

### Constraints / next steps

- begin the failure-taxonomy writeup from the locked 7B gate evidence, using the inspected per-family blocker breakdown and mode-level taxonomy as the starting artifact
- optionally run one separate descriptive 32B headroom row on `scope_contamination` for size-scaling evidence only; it must not reopen or reinterpret the locked 7B gate verdict
- do not start extracted-candidate policy comparisons under the current gate result
- do not reopen `general_v2`, relax validators, or lower the gate contract to turn invalid outputs into passes
- treat a future retry as requiring a separately scoped component-model change with the same gate contract, not a prompt-tuning loop on the current branch

## 2026-05-11 — Component gate-decision contract hardened

### What shipped

- promoted canonical-id map access through `cq.eval.component_eval.canonical_component_maps` so the gate runner no longer imports a private evaluator classifier
- documented that Phase A and determinism helpers fail by raising `StopConditionError`, that pairwise canonicalization is an uncalibrated proxy for the B-cubed threshold, and that determinism is checked on the fixed forced-contradiction sentinel rather than every held-out gate row
- made canonicalization unlock require both the aggregate observed B-cubed threshold and the pairwise CI-supported proxy threshold
- removed the duplicate scenario-error blocker source and derived the aggregate CI failure count from emitted blockers
- added gate-decision tests for Phase A/determinism blockers, aggregate CI failure, aggregate observed B-cubed failure, frozen sentinel failure, schema-backed cache reuse, and the CLI stop exit-code/report contract
- added focused public-API coverage for `canonical_component_maps`

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_gate_decision tests.test_component_eval tests.test_component_scoring_matrix -q` passes with 61 tests
- no Ollama inference or extracted-candidate policy comparison was run in this change

## 2026-05-09 — CI-aware component gate-decision runner added

### What shipped

- added `scripts/run_component_gate_decision.py` as a separate Phase 3 gate runner rather than extending the diagnostic-only matrix runner
- reused the existing Phase A prompt-regression contract and 7B deterministic JSON check from `scripts/run_component_scoring_matrix.py`
- fixed the primary gate rows at 7B `general_v1`, held-out split, 60 scenarios per benchmark family, with optional descriptive 32B headroom and optional frozen-sentinel rows
- added gate artifact semantics that avoid statistical overclaiming: `wilson_lower_bound_event_assumption` for binomial ratios, `f1_conservative_composite_from_wilson_pr` for F1, observed-only `canonicalization_b_cubed_f1`, and a separate pairwise canonicalization CI-support gate
- added exact current-generator denominator reporting for candidate events, contradiction edges, and positive canonical pairs, plus an explicit warning that the rows are deterministic template-rotation variants rather than independent new mechanisms
- exposed claim/scope correct/count denominators in component-eval metrics so aggregate CI gates do not scrape capped failure examples
- added focused tests for row definitions, denominator expectations, Wilson math, F1 naming, B-cubed labeling, dry-run output, oracle-pass unlock, and scenario-error blocking

### Why it matters

- the project now has the CI-aware gate-decision machinery requested before any extracted-candidate policy comparison
- policy comparison unlock remains strict and 7B-primary: Phase A must pass, determinism must pass, primary rows must have zero scenario errors, aggregate CI-supported gates must pass, and per-family observed gates must pass
- 32B headroom is explicitly descriptive and cannot unlock policy comparison by itself
- the artifact distinguishes statistical decision aids from true confidence claims, especially for F1 and canonicalization
- this remains component-quality infrastructure only; no noisy-mode policy claim has been made

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_gate_decision tests.test_component_eval tests.test_component_scoring_matrix -q` passes with 54 tests
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py --dry-run --include-headroom --include-frozen-sentinel` emits valid JSON with 13 planned rows and the expected aggregate denominators: 849 candidate events, 204 undirected contradiction edges, and 909 positive canonical pairs
- no Ollama inference or extracted-candidate policy comparison was run in this change

### Open issues / next

- run the real 7B `general_v1` gate decision, optionally with 32B headroom and frozen sentinel rows
- keep extracted-candidate policy comparisons blocked unless the gate summary explicitly sets `policy_comparison_unlocked=true`

## 2026-05-09 — Prompt diagnostic slice runner added and v2 branch failed

### What shipped

- added `prompts/component_extractor_general_v2.txt` as the single prompt-only diagnostic candidate for the selected Phase 3 branch
- extended `scripts/run_component_scoring_matrix.py` with `--row-set full|prompt_schema_diagnostic`, prompt path/label overrides, and unchanged default `full` row ordering and artifact stems
- added targeted prompt-schema diagnostic rows for the affected 7B and 32B families only
- added diagnostic summary artifacts with raw bucket counts, pre-enumerated benchmark-boundary exclusions, adjusted counts, and `policy_comparison_unlocked: false`
- added regression tests for the default matrix contract, targeted `general_v2` artifact naming, and boundary-adjusted counting
- ran the targeted `general_v2` diagnostic row-set after confirming local Qwen 2.5 7B/32B `Q4_K_M` availability

### Why it matters

- the planned prompt/schema branch can be tested without rerunning the entire matrix by default
- the acceptance arithmetic now excludes only the two documented 32B preference-drift one-off scope-boundary events from scope drift, while still counting their canonicalization failures
- `general_v2` keeps one-off/current-request preference constraints as `temporary_constraint`/`session`, so this pass does not force-fit the prompt to disputed gold labels
- the branch did not resolve: adjusted 32B scope drift was `5` against the `< 4` target, adjusted 32B canonical split/merge was `7` against the `< 3` target, and six 7B scenario errors remained from empty `scope_key` validation failures
- those six 7B errors were prompt-following failures where the model still emitted empty `scope_key` values despite the v2 fallback instruction; the validator rejected emptiness, not the shape of a fallback slug
- branch resolution uses a strict zero targeted-row scenario-error requirement, not a no-regression comparison against v1
- this remains component diagnostic evidence only; no noisy-mode claim or policy comparison is unlocked by this change

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_scoring_matrix -q` passes with 13 tests
- the requested unit bundle passes: `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_scoring_matrix tests.test_local_extractor tests.test_component_eval tests.test_ollama_component_extractor -q`
- targeted dry-run completed with the Phase A rows plus 11 `general_v2` diagnostic rows
- local Ollama tags were present: `qwen2.5:7b-instruct-q4_K_M` and `qwen2.5:32b-instruct-q4_K_M`; server version was `0.23.1`
- an initial sandboxed run stopped because localhost Ollama access was blocked; the approved `--force` rerun completed and overwrote those placeholder Phase A artifacts
- completed run output: `Wrote or reused 11 diagnostic rows in /Users/manav/code/consolidation-queue/data/results`
- summary artifact: `data/results/component_scoring_matrix_prompt_schema_diagnostic_general_v2_summary.json`
- summary acceptance:
  - `branch_resolved=false`
  - `adjusted_32b_scope_key_or_level_drift=5`
  - `adjusted_32b_canonical_split_or_merge=7`
  - `scenario_error_count=6`, all on 7B floor rows
  - `policy_comparison_unlocked=false`

### Open issues / next

- stop prompt iteration for this branch and proceed to CI-aware gate-decision design with the current component evidence
- keep `general_v1` as the current default for future full diagnostic/gate runs unless a separate task explicitly changes the default
- keep extracted-candidate policy comparisons blocked

## 2026-05-09 — Diagnostic matrix interpreted and prompt/schema branch selected

### What shipped

- added `docs/component_diagnostic_matrix.md` as the Phase 3 diagnostic interpretation report
- verified the completed diagnostic inventory as 13 Qwen 2.5 7B floor rows and 7 Qwen 2.5 32B headroom rows, with Phase A forced-contradiction regression artifacts treated separately
- assigned every saved failure example to one fixed bucket: candidate miss/extra, contradiction-edge drift, scope-key/level drift, canonical split/merge, claim-type drift, or scenario error
- directly inspected the 32B `preference_drift` held-out row because it had 10 failure examples, the largest 32B headroom failure count
- updated `PROJECT_PLAN.md` so the next active task is targeted prompt/schema diagnostics before CI-aware gate-decision design

### Why it matters

- the post-hoc operational branch rule selected prompt/schema diagnostics: `scope_key_or_level_drift` appears at both 7B and 32B in `preference_drift`, `scope_contamination`, and `mechanism_diverse_heldout`, while `canonical_split_or_merge` appears at both sizes in `preference_drift` and `scope_contamination`
- the 32B `preference_drift` held-out failures are concentrated in temporary-looking drift-back language that the model predicts as `temporary_constraint`/`session` while gold labels treat it as durable `user_preference`/`user_global`; this is now framed as a prompt/schema-or-benchmark-boundary diagnostic rather than a simple extractor defect
- the next diagnostic slice is capped at one prompt/schema revision pass, with explicit 32B headroom targets before CI-aware gate-decision design resumes
- the 7B held-out/main sanity check found the sharpest split-specific spike in false-corroboration held-out, where empty `canonical_id` validation errors caused candidate misses; that spike did not appear in the 32B held-out row
- this remains component diagnostic evidence only, not a noisy-mode claim and not a policy comparison unlock

### Evidence

- no model inference was rerun
- `docs/component_diagnostic_matrix.md` records the row-level metrics, bucket counts split by model size, 7B held-out/main sanity check, branch decision, and diagnostic stop criteria
- policy comparisons remain locked until component outputs are saved, scored, inspectable, and CI-aware gate-decision results are reported separately from policy outcomes

### Open issues / next

- run targeted prompt/schema diagnostics for scope-key/scope-level drift, canonical slot reuse, preference-drift temporary-looking language, benchmark-boundary handling, and empty required-field validation failures
- after any prompt/schema adjustment, rerun the forced-contradiction Phase A regression path before broader diagnostic rows
- keep CI-aware gate-decision design and extracted-candidate policy comparison blocked until the prompt/schema diagnostic branch is resolved

## 2026-05-08 — Prompt revision cleared Phase A and diagnostic matrix completed

### What shipped

- revised `prompts/component_extractor_general_v1.txt` in place with family-neutral rules that extraction is per observation event, not per unique memory slot
- added explicit prompt guidance that repeated, confirming, supporting, or reaffirming observations still get their own predictions and are not contradictions
- tightened the canonicalization wording so repeated or supporting observations "should reuse" the same `canonical_id`, without a "usually" hedge
- aligned the contradiction-exclusion terminology with the extraction rule: repetition, support, confirmation, reaffirmation, and restatement are not contradictions
- clarified that repeated or supporting observations should reuse the `canonical_id` of the claim or claims they support or confirm, avoiding a singular "earlier claim" antecedent
- reran `scripts/run_component_scoring_matrix.py` with script defaults and no `--force` after the final prompt wording
- Phase A cleared after the prompt change, and the runner wrote or reused 20 diagnostic rows
- no statistical gate verdict was issued and no policy comparison was unlocked

### Why it matters

- the prior 32B `general_v1` forced-contradiction stop was addressed without adding acquisition-specific examples or changing the output schema, runner, evaluator, thresholds, or model settings
- the previous `general_v1` mixed artifacts were regenerated in place through prompt-hash provenance mismatch; the earlier stop report preserves the pre-fix regression details, but those pre-fix prediction JSON contents were not archived separately
- Phase A remains only a forced-contradiction smoke/regression guard, not evidence that `general_v1` generalizes
- Phase A does not guard cross-family regressions in scope, drift, false-corroboration, useful-pending, memory-poisoning, or mechanism-diverse rows; those can only be caught by inspecting the diagnostic artifacts directly
- the forced-contradiction held-out diagnostic row did not show an obvious 32B overfit signal: the 32B held-out component artifact had zero scenario errors and zero failure examples
- 7B still showed contradiction-edge observations on forced-contradiction held-out support/refinement cases, so those should be treated as diagnostic model behavior rather than proof that the prompt is broadly fixed
- mechanism-diverse held-out extractor artifacts now exist for 7B and 32B, but remain diagnostic only and must not shape CQ thresholds, policy logic, contract design, or scenario design before locked policy comparisons

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_scoring_matrix -q` passed with 10 tests before the rerun
- `python3 scripts/run_component_scoring_matrix.py` completed with: `Wrote or reused 20 diagnostic rows in data/results`
- runner completion line: `No statistical gate verdicts were issued.`
- all `qwen2_5` `general_v1` prediction artifacts now match the final prompt hash, so the diagnostic artifacts reflect the tightened canonicalization wording rather than stale provenance-cache reuse
- diagnostic artifacts now include:
  - 13 `qwen2.5:7b-instruct-q4_K_M` floor rows across the planned family/split matrix
  - 7 `qwen2.5:32b-instruct-q4_K_M` headroom rows across the planned held-out/frozen matrix
  - the 32B forced-contradiction mixed Phase A artifact regenerated by the prompt hash mismatch
- descriptive row observations:
  - no row reported extra same-event predictions; max predictions per event was `1`
  - 32B headroom rows reported no scenario errors and no measured artifact gate failures, but several rows are small enough that one scenario flip could move a descriptive pass to a failure
  - 32B headroom failure-example counts by row: forced-contradiction held-out `0`, scope-contamination held-out `3`, preference-drift held-out `10`, useful-pending-memory held-out `0`, false-corroboration held-out `0`, memory-poisoning held-out `0`, mechanism-diverse frozen `3`
  - the final prompt wording moved the 32B scope-contamination held-out failure-example count from `4` to `3` relative to the immediately preceding matrix artifact, a small diagnostic improvement rather than a stable quality claim
  - 7B floor rows reported scenario errors on some scope, preference-drift, and memory-poisoning rows
  - 7B floor rows reported measured artifact gate failures on some scope, preference-drift, memory-poisoning, and mechanism-diverse rows

### Open issues / next

- interpret the completed matrix as diagnostic component evidence only, with row-level observations rather than family rankings or noisy-mode claims
- decide whether the next task should be CI-aware gate-decision design or more prompt/schema diagnostics based on the completed matrix, not on Phase A alone
- keep extracted-candidate policy comparisons blocked until component outputs are saved, scored, inspectable, and gate-decision results are reported separately

## 2026-05-08 — Diagnostic noisy component matrix stopped by prompt regression guard

### What shipped

- ran the planned preflight for `scripts/run_component_scoring_matrix.py`
- confirmed the exact local Ollama tags are installed: `qwen2.5:7b-instruct-q4_K_M` and `qwen2.5:32b-instruct-q4_K_M`
- recorded the Ollama server version as `0.23.1`
- started the diagnostic matrix with script defaults and no `--force`
- the runner stopped before broader diagnostic rows because the Phase A prompt-regression guard fired

### Why it matters

- the stop condition worked as intended: no rows were run around the guard, no policy comparison was unlocked, and no noisy-mode gate verdict was issued
- the concrete stop was 32B-only on forced-contradiction `general_v1`: `candidate_detection_f1` moved from `1.00` under `forced_v1` to `0.963`, and `forced_contradiction_006` flipped from correct to incorrect
- the saved failure example is a single missing corroborating observation: `forced_contradiction_006-event-2`, "Brightline later confirmed the acquisition of Redwood."
- mechanism-diverse held-out extractor rows were not reached in this run; when they are eventually produced, they must remain diagnostic only and must not shape CQ thresholds, policy logic, contract design, or scenario design before locked policy comparisons
- extracted-candidate policy comparisons remain blocked

### Evidence

- `python3 scripts/run_component_scoring_matrix.py --dry-run` passed and emitted the planned diagnostic matrix
- `ollama list` showed both required Qwen 2.5 `Q4_K_M` tags installed
- `ollama --version` reported `0.23.1`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_scoring_matrix -q` passed with 10 tests
- stopped run report: `data/results/component_scoring_matrix_phase_a_stop_20260508T052810445255Z.json`
- stop reason: `prompt_regression_failed`
- stop details:
  - `qwen2.5:32b-instruct-q4_K_M` `candidate_detection_f1`: baseline `1.00`, general `0.963`
  - `qwen2.5:32b-instruct-q4_K_M` scenario regression: `forced_contradiction_006`
- saved row artifacts:
  - `data/results/forced_contradiction_local_extractor_qwen2_5_7b_q4km_general_v1_mixed_floor_predictions.json`
  - `data/results/forced_contradiction_local_extractor_qwen2_5_7b_q4km_general_v1_mixed_floor_component_eval.json`
  - `data/results/forced_contradiction_local_extractor_qwen2_5_32b_q4km_general_v1_mixed_headroom_predictions.json`
  - `data/results/forced_contradiction_local_extractor_qwen2_5_32b_q4km_general_v1_mixed_headroom_component_eval.json`

### Open issues / next

- inspect whether `component_extractor_general_v1` should explicitly preserve corroborating observations as candidates even when they repeat an acquisition-status claim
- after any prompt/schema adjustment, rerun the prompt-regression path before attempting the full diagnostic matrix
- keep CI-aware gate-decision design and extracted-candidate policy comparison blocked until the diagnostic matrix completes cleanly and is reported separately

## 2026-05-08 — Diagnostic noisy component matrix runner added

### What shipped

- added `prompts/component_extractor_general_v1.txt` for cross-family transcript-only extraction
- added `scripts/run_component_scoring_matrix.py`, a stdlib runner around the existing local extractor and component evaluator
- encoded Phase A stop conditions: forced-contradiction prompt non-regression for 7B and 32B, per-scenario correct-to-incorrect regression blocking, and byte-exact deterministic JSON checks with array order preserved
- guarded cached artifact reuse with provenance checks for prompt hash, model id, decoding params, timeout, family, split, and scenario count
- added collision-resistant artifact names that include Qwen family, size, quantization, prompt label, split, and floor/headroom role
- added dry-run output for the fixed matrix and tests for row definitions, artifact names, command generation, metric regressions, per-scenario regressions, and deterministic JSON comparison

### Why it matters

- this broadens noisy component scoring infrastructure without silently converting small diagnostic rows into gate verdicts
- the forced-contradiction regression only checks that `general_v1` does not break the easy acquisition-status smoke case; it does not prove harder scope-key or canonicalization competence
- `mechanism_diverse_heldout` noisy rows remain descriptive only at `n=3`, including the 32B headroom point
- extracted-candidate policy comparisons remain blocked until a separate CI-aware gate-decision run is designed and reported

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_scoring_matrix -q` passes with 10 tests
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_scoring_matrix.py --dry-run` emits the planned diagnostic matrix without writing artifacts or issuing gate verdicts
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_local_extractor tests.test_component_eval tests.test_ollama_component_extractor tests.test_component_scoring_matrix -q` passes with 73 tests
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q` passes with 241 tests

### Open issues / next

- run the real diagnostic matrix against local Ollama after confirming the required Qwen 2.5 `Q4_K_M` models are available
- add the separate CI-aware gate-decision protocol before any extracted-candidate policy comparison

## 2026-05-07 — Component failure examples added

### What shipped

- refactored `cq.eval.component_eval` so one classification pass drives both component metrics and diagnostic examples
- added capped component failure examples to component-eval artifacts with `failure_example_count`, `failure_example_limits`, and `failure_example_overflow`
- covered candidate missing/extra/duplicate predictions, claim type and scope mismatches, canonicalization split/merge pairs, contradiction missing/extra edges, and `scenario_errors`
- kept oracle upper-bound artifacts on the same schema with empty failure examples
- regenerated the weak, positive-control, Qwen 7B, and Qwen 32B forced-contradiction component-eval artifacts from existing prediction JSON without rerunning Ollama

### Why it matters

- broader noisy component scoring can now be inspected by failure type instead of raw prediction JSON only
- canonicalization examples still surface when B-cubed is suppressed by low coverage, so low-recall extractor behavior remains diagnosable
- this is observability for Phase 3/4 component quality, not a policy comparison or a new noisy-mode quality claim

### Evidence

- regenerated artifact failure-example counts:
  - weak negative control: `22`
  - positive control: `0`
  - Qwen 2.5 7B floor: `4`
  - Qwen 2.5 32B headroom: `0`
- tests:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_eval -q` passes with 33 tests
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q` passes with 231 tests

### Open issues / next

- broaden local-model component scoring beyond the 6-scenario forced-contradiction smoke before making stable extractor-quality or size-scaling claims
- keep extracted-candidate policy comparisons blocked until component outputs are saved, scored, and inspectable separately

## 2026-05-07 — First local-model forced-contradiction smoke scored

### What shipped

- added a stdlib-only Ollama wrapper at `scripts/ollama_component_extractor.py` backed by `cq.pipeline.ollama_component_extractor`
- added `prompts/forced_contradiction_component_extractor_v1.txt` for transcript-only acquisition-status extraction
- extended model-mode artifacts to preserve optional `model_diagnostics` without changing `scenario_predictions` or component scoring
- normalized Ollama model digests into `sha256:...` form and saved the digest both at top level and in `model_diagnostics`
- implemented constrained JSON generation plus narrow logged repair counters: `candidate_id_cleared`, `contradicts_renamed`, and `extra_top_level_dropped`
- mapped structured wrapper backend failures onto the existing `command_error` scenario error path
- added model-diagnostic drift detection so a mid-sweep digest or Ollama-version change becomes a `backend_drift` scenario error instead of being silently hidden by first-write-wins aggregation
- changed malformed or non-object model JSON responses into `command_error` wrapper failures, preserving the distinction between backend/output transport failure and valid-JSON schema validation failure
- added a minimum Ollama version check for JSON-schema constrained decoding and documented that `OLLAMA_BASE_URL` can route transcript text away from localhost if explicitly set
- pulled and used the exact Phase 4 floor model tag `qwen2.5:7b-instruct-q4_K_M`, rather than substituting an installed larger model

### Why it matters

- the first real noisy component artifacts now exist behind the transcript-only bridge and were scored before any extracted-candidate policy run
- floor and headroom runs use matched Qwen 2.5 `Q4_K_M` quantization, so this smoke does not conflate model size with quantization tier
- the 6-scenario run is only an end-to-end bridge smoke sample, not a stable extractor-quality estimate
- the 7B-vs-32B difference in this sample is headroom instrumentation only; it is not Phase 4-vs-Phase 5 evidence without a larger paired run
- noisy-mode policy comparisons remain blocked until component outputs are saved, scored, and inspected separately across a broader set

### Evidence

- 7B floor command:
  - `python3 -m cq.pipeline.local_extractor --family forced_contradiction --scenarios 6 --template-mix mixed --mode model --model-command 'python3 scripts/ollama_component_extractor.py' --model-id 'qwen2.5:7b-instruct-q4_K_M' --prompt-template-path prompts/forced_contradiction_component_extractor_v1.txt --decoding-json '{"temperature": 0, "seed": 7, "top_p": 1}' --per-scenario-timeout-seconds 180 --output-json data/results/forced_contradiction_local_extractor_qwen7b_predictions.json`
  - model digest: `sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`
  - Ollama server version: `0.23.1`
  - scenarios: 6 attempted, 6 successful, 0 errors
  - repair totals: `candidate_id_cleared=0`, `contradicts_renamed=0`, `extra_top_level_dropped=0`
  - scored artifact: `data/results/forced_contradiction_local_extractor_qwen7b_component_eval.json`
  - metrics: `candidate_detection_f1=0.963`, `claim_type_accuracy=1.00`, `scope_level_accuracy=1.00`, `scope_key_accuracy=1.00`, `canonicalization_b_cubed_f1=1.00`, `contradiction_f1=0.824`, `contradiction_precision=0.778`, `contradiction_recall=0.875`
  - all measured quality gates passed on this smoke sample
- 32B headroom command:
  - same command shape, prompt, decoding, scenarios, and timeout with `--model-id 'qwen2.5:32b-instruct-q4_K_M'` and output `data/results/forced_contradiction_local_extractor_qwen32b_headroom_predictions.json`
  - model digest: `sha256:9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368`
  - Ollama server version: `0.23.1`
  - scenarios: 6 attempted, 6 successful, 0 errors
  - repair totals: `candidate_id_cleared=0`, `contradicts_renamed=0`, `extra_top_level_dropped=0`
  - scored artifact: `data/results/forced_contradiction_local_extractor_qwen32b_headroom_component_eval.json`
  - metrics: all reported component metrics and measured quality gates were `1.00`
- tests:
  - `python3 -m unittest tests.test_local_extractor tests.test_component_eval tests.test_ollama_component_extractor -q` passes with 59 tests
  - `python3 -m unittest discover -s tests -p 'test_*.py' -q` passes with 227 tests

### Open issues / next

- add per-component failure examples for non-oracle predictions
- broaden noisy component scoring beyond the 6-scenario forced-contradiction smoke before making stable extractor-quality or size-scaling claims
- keep extracted-candidate policy comparisons blocked until component outputs are saved, scored, and inspectable separately

## 2026-05-06 — Transcript-only command-adapter extractor added

### What shipped

- added additive `model` mode to `cq.pipeline.local_extractor` for a user-provided local command behind the existing transcript-only bridge
- persisted reproducibility metadata for model-mode artifacts: exact command, required model id, prompt template path/text/hash, per-scenario stdin envelope hashes, decoding params, timeout, scenario counts, and input contract
- added per-scenario `scenario_errors` for timeouts, nonzero exits, malformed JSON, validation failures, and other command failures
- updated `cq.eval.component_eval` to report `scenario_errors` and score errored scenarios as zero predictions rather than excluding them
- changed component matching so extra predictions for an event count as false positives while a valid same-event prediction is still used for claim/scope/canonicalization scoring
- added prediction fan-out metrics (`predictions_per_event_p50`, `predictions_per_event_p95`, max, and extra same-event count) so best-match scoring cannot hide models that emit many guesses per event
- moved model command stdout/stderr capture to capped temporary files so oversized output becomes a per-scenario `output_too_large` error instead of unbounded in-memory buffering
- kept `weak` and `positive_control` modes unchanged

### Why it matters

- Phase 4 can now plug in Ollama, llama.cpp, MLX, or another local wrapper without adding model-runtime dependencies to the repo
- extractor crashes and malformed model output are now diagnosable separately from deliberate abstention
- the matcher change is a benchmark-contract change: current gold still has one candidate per observation event, so genuinely multi-claim transcript turns can be penalized with FP extras until the gold schema supports them
- prediction fan-out metrics make the lenient best-matching choice auditable in noisy-mode artifacts
- policy comparisons remain blocked until noisy component outputs are saved, scored, and inspected separately

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_local_extractor -q` passes with 16 tests
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_eval -q` passes with 29 tests
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q` passes with 213 tests
- oracle upper-bound regression coverage confirms all applicable gates remain `1.00` across the current family/template matrix
- no real noisy model artifact was generated in this slice; fake command wrappers cover transport and validation behavior only

### Open issues / next

- choose the first deterministic local model command and prompt template for a forced-contradiction noisy smoke run
- score the saved model-mode predictions with `cq.eval.component_eval` before any extracted-candidate policy run
- add per-component failure examples once non-oracle predictions exist

## 2026-05-06 — Phase 3 reference matrix and transcript-only bridge added

### What shipped

- saved the Phase 3 oracle upper-bound component-evaluation reference matrix across the current calibrated family/split set
- added event-aligned `contradicts_event_ids` scoring so extractor outputs no longer need oracle candidate ids for contradiction edges
- kept legacy `candidate_id` / `contradicts` scoring for oracle and backcompat prediction JSON
- added contradiction-gate applicability metadata: no-edge scenario sets are `not_applicable`, while missed gold edges and false-positive predicted edges still fail measured gates
- added a transcript-only local extractor bridge under `cq/pipeline/` with sanitized input, weak negative-control mode, and forced-contradiction positive-control mode
- added regression coverage for event-edge direction normalization, self/unknown/question event false positives, generator candidate-to-event invariants, input isolation, weak extractor failure, and positive-control extractor pass

### Why it matters

- Phase 4 extractor outputs can now be scored without leaking oracle candidate ids, gold labels, lifecycle expectations, metrics, or policy traces into the extractor input
- the positive-control extractor proves the bridge can round-trip valid transcript-derived predictions, while the weak extractor proves failures are surfaced as measured component failures
- oracle upper-bound artifacts are reference artifacts only; they validate labels, scorer wiring, and saved output shape by construction, not noisy pipeline quality
- false-corroboration and any future no-contradiction clean-only sweep no longer get fake red contradiction gates when there are no gold or predicted contradiction edges

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_eval -q` passes with 24 tests
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_local_extractor -q` passes with 6 tests
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q` passes with 198 tests
- oracle upper-bound artifacts were written to `data/results/*_component_eval_oracle_upper_bound_*.json` plus `data/results/mechanism_diverse_heldout_component_eval_oracle_upper_bound.json`
- weak extractor smoke:
  - `data/results/forced_contradiction_local_extractor_weak_predictions.json`
  - `data/results/forced_contradiction_local_extractor_weak_component_eval.json`
  - reports `candidate_detection_f1=0.00`, `claim_type_accuracy=NA`, `contradiction_applicability=measured`, and `contradiction_f1=0.00`
- positive-control extractor smoke:
  - `data/results/forced_contradiction_local_extractor_positive_control_predictions.json`
  - `data/results/forced_contradiction_local_extractor_positive_control_component_eval.json`
  - reports all applicable forced-contradiction gates at `1.00`

### Open issues / next

- wire the first real local-model extractor behind the transcript-only bridge
- score noisy component outputs before any extracted-candidate policy run
- add per-component failure examples once non-oracle predictions exist

## 2026-05-05 — Frozen Phase 2.5 oracle sweep recorded and Phase 3 harness started

### What shipped

- ran the locked `mechanism_diverse_heldout` frozen oracle sweep with `--policy-set phase2_5`
- wrote frozen sweep artifacts to `data/runs/mechanism_diverse_heldout_oracle_frozen_phase2_5.json` and `data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_metrics.csv`
- rendered the static trace dashboard at `data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_dashboard.html`
- added `docs/predictions_vs_results.md` with every preregistered frozen oracle delta next to the observed delta
- added the Phase 3 component-evaluation harness with candidate detection, claim type, scope level/key, canonicalization B-cubed, contradiction precision/recall/F1, and quality-gate reporting
- added a saved-prediction JSON input path for later noisy extractor outputs and an oracle upper-bound CLI mode
- hardened component quality gates so no-data metrics are reported as undefined and fail instead of passing on empty extractor output

### Why it matters

- Phase 2.5 is now recorded before any noisy-pipeline work, preserving the preregistered evaluation contract
- all 108 preregistered oracle-mode deltas matched observed deltas
- CQ ties `Mem0Lite` on frozen aggregate false assertion, answer correctness, poison promotion, clean durable displacement, and scope leakage, while improving premature promotion by 33 percentage points
- under the preregistered 5 percentage point rule, CQ is not disconfirmed against `Mem0Lite` in oracle mode, but the support is narrow: reduced premature durable promotion, not broad answer-quality superiority
- Phase 3 can now measure component quality separately from policy quality before any noisy-mode claims

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.preregistration_lock --check` passes
- pre-sweep `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q` passed with 168 tests
- frozen aggregate:
  - `consolidation_queue_lite`: `false_assertion=0.33`, `correctness=0.67`, `premature_promotion=0.33`, `poison_promotion=0.33`
  - `mem0_lite`: `false_assertion=0.33`, `correctness=0.67`, `premature_promotion=0.67`, `poison_promotion=0.33`
  - `reflection_eager_write_lite`: `false_assertion=1.00`, `correctness=0.00`, `premature_promotion=0.67`, `poison_promotion=0.33`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m cq.eval.component_eval --family mechanism_diverse_heldout --scenarios 3 --template-mix frozen --output-json data/results/mechanism_diverse_heldout_component_eval_oracle_upper_bound.json` reports all component upper-bound quality metrics at `1.00`
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_component_eval -q` passes with 14 tests
- final `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q` passes with 182 tests
- follow-up component-evaluation coverage exercises zero predictions, canonicalization coverage below threshold, hand-computed B-cubed, duplicate event IDs, strict prediction JSON shape, artifact mode labeling, and frozen-family lock validation

### Open issues / next

- run and record component-evaluation oracle upper-bound artifacts across the remaining benchmark families
- wire the first local extractor to write `scenario_predictions` JSON for the component harness
- start Phase 4 only after noisy component outputs are scored separately from policy outcomes

## 2026-05-05 — Phase 2.5 ablations and frozen preregistration lock added

### What shipped

- added the four named CQ ablation policies: `cq_no_contestation_demotion`, `cq_no_wider_scope_pending_override`, `cq_no_pending_lookup_use`, and `cq_no_source_independence_gate`
- wired the ablations into `--policy-set phase2_5` alongside `Mem0Lite`, while preserving the default policy set
- added ablation metadata to runner artifacts so Phase 2.5 outputs label disabled CQ behavior explicitly
- added frozen mechanism-diverse contracts for adversarial mixed-source corroboration, scope-laundered poisoning, and long-horizon preference corrections
- added `docs/preregistration.md` with numeric predictions and a verified `frozen_eval_lock_sha256`
- added a runner guard so `mechanism_diverse_heldout` execution fails unless the preregistration lock matches the current frozen contracts and predictions block
- added a `python3 -m cq.eval.preregistration_lock --recompute` helper for lock maintenance

### Why it matters

- CQ ablations are now policy-only contrasts over the same candidate stream, storage substrate, source counting, lifecycle logging, and scope matching
- `cq_no_source_independence_gate` is a real ablation rather than a no-op: it leaves substrate source counts untouched but uses raw support edges for CQ promotion
- pending use is split into two interpretable ablations: wider-scope override lookup and no-durable pending fallback
- the frozen mechanism-diverse set is now protected by a mechanical lock instead of a convention, so first execution is tied to preregistered predictions
- existing-family ablation observations remain calibrated commitments; only the frozen mechanism-diverse sweep carries blind disconfirmation weight

### Evidence

- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q` passes with 166 tests
- existing-family mixed calibration with `--policy-set phase2_5`, writing artifacts to `/tmp`, shows:
  - forced contradiction: full CQ remains at `false_assertion=0.00`, `correctness=1.00`; `cq_no_contestation_demotion` falls to `false_assertion=0.67`, `correctness=0.33`; `cq_no_pending_lookup_use` falls to `correctness=0.33`
  - scope contamination: full CQ remains at `leakage=0.00`, `correctness=1.00`; `cq_no_wider_scope_pending_override` exposes the workspace-parent failure with overall `leakage=0.25`, `correctness=0.75`
  - useful pending memory: full CQ remains at `correctness=1.00`, `pending_use=1.00`; `cq_no_pending_lookup_use` drops to `correctness=0.00`, `pending_use=0.00`
  - false corroboration: full CQ remains at `false_assertion=0.00`; `cq_no_source_independence_gate` reaches dirty-template `false_assertion=1.00` and `premature_promotion=0.20`
  - memory poisoning: full CQ remains at `false_assertion=0.60`, `clean_displacement=0.40`; `cq_no_contestation_demotion` removes clean displacement but still has `false_assertion=0.40`; `cq_no_pending_lookup_use` reduces false assertion to `0.20` while preserving the displacement failure

### Open issues / next

- the frozen mechanism-diverse contracts have not been executed against any policy yet
- next step is the locked frozen oracle sweep with `--family mechanism_diverse_heldout --template-mix frozen --policy-set phase2_5`
- record frozen results against preregistered predictions before starting Phase 3 component evaluation

### 2026-05-05 relock note

- before any frozen sweep, recalibrated `false_corroboration_adversarial_mixed_source` above the `Mem0Lite` write threshold so it tests durable false-stack promotion instead of low-confidence NOOP behavior
- corrected the `memory_poisoning_scope_laundered` CQ-vs-`Mem0Lite` prediction to zero delta because `Mem0Lite` is expected to recover via no-margin UPDATE while CQ recovers via wider-scope pending override
- changed frozen-family generation to ignore the requested scenario count and always use the fixed frozen contract set
- corrected the `preference_drift_long_horizon_corrections` `cq_no_pending_lookup_use` false-assertion prediction to zero delta because the ablation abstains rather than asserting a forbidden stale preference
- clarified that the 5 percentage point `Mem0Lite` disconfirmation rule is evaluated per primary metric, not by averaging the metric bundle

## 2026-05-04 — Mem0Lite opt-in Phase 2.5 baseline added

### What shipped

- added `Mem0Lite`, a rule-based partial Mem0-family baseline over the shared oracle candidate and storage substrate
- wired `--policy-set phase2_5` through the runner and `build_run_artifact`, preserving the default policy set unchanged
- included runner artifact metadata documenting that `Mem0Lite` is not a faithful full Mem0 reproduction and that DELETE is reserved until the schema has explicit delete/retraction events
- added focused tests for ADD, low-confidence NOOP, contradiction UPDATE without overwrite margin, matching reinforcement, no pending answers, and runner policy-set membership

### Why it matters

- Phase 2.5 now has its first external published-family comparison target without changing default benchmark behavior
- oracle-mode `Mem0Lite` is interpretable: it differs from Reflection by thresholded ADD, no pending lookup, and no overwrite-margin check on contradictory UPDATE
- Mem0Lite follows Reflection's durable-update bookkeeping surface rather than CQ's candidate-vs-candidate contestation path, so lifecycle differences are attributable to the write policy instead of extra candidate-state transitions
- the memory-poisoning override result is the load-bearing Mem0-vs-Reflection divergence in this slice: Mem0Lite displaces clean durables when a qualifying contradictory poison arrives, while Reflection's overwrite margin can preserve them
- useful-pending-memory shows the expected eager-write-with-dedup pattern here: `Mem0Lite` answers correctly but pays `premature_promotion=1.00`, so this is not evidence of staged pending utility
- existing-family calibration numbers can inform preregistration, while frozen mechanism-diverse scenarios remain unimplemented and unexecuted

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 157 tests
- existing-family mixed calibration with `--policy-set phase2_5`, writing artifacts to `/tmp`, shows `mem0_lite`:
  - forced contradiction, 6 scenarios: `false_assertion=0.00`, `recovery=1.00`, `correctness=1.00`
  - scope contamination, 8 scenarios: `false_assertion=0.25`, `correctness=0.75`, `leakage=0.25`, `premature_promotion=0.25`
  - preference drift, 6 scenarios: `false_assertion=0.00`, `correctness=1.00`, `premature_promotion=0.33`
  - useful pending memory, 4 scenarios: `false_assertion=0.00`, `correctness=1.00`, `premature_promotion=1.00`
  - false corroboration, 4 scenarios: `false_assertion=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - memory poisoning, 10 scenarios: `false_assertion=0.60`, `correctness=0.20`, `premature_promotion=0.60`, `poison_promotion=0.60`, `clean_displacement=0.40`

### Open issues / next

- implement the four named CQ ablations as the next Phase 2.5 slice
- add frozen mechanism-diverse scenario contracts only after ablations, and do not execute them before preregistration predictions are committed
- the 5 percentage point disconfirmation rule still needs an explicit oracle/noisy-mode qualifier in `docs/preregistration.md`

## 2026-05-04 — Preregistration and disconfirmation rules sharpened

### What changed

- required predictions to be per scenario family and per primary metric rather than aggregate-only
- set a 5 percentage point disconfirmation threshold for the CQ policy contribution against `Mem0Lite` on mechanism-diverse held-outs
- required `docs/predictions_vs_results.md` in Phase 6 so every committed prediction is auditable against observed results
- clarified that CQ ablations only change policy decision logic; shared substrate counting, logging, and scope matching remain unchanged
- required mechanism-diverse held-out predictions before those scenarios are executed against any policy, including baselines and ablations

### Why it matters

- aggregate wins can hide family-specific failures, so the preregistration now has to expose where each policy does and does not work
- the contribution now has an explicit fail condition: if `Mem0Lite` matches or beats CQ within tolerance on the frozen held-outs, the paper becomes a benchmark and taxonomy contribution rather than a CQ-policy claim
- locking predictions before first held-out execution reduces the chance of accidental tuning through scenario authoring

### Evidence

- documentation-only planning change; no tests were run

### Open issues / next

- implement Phase 2.5 and draft `docs/preregistration.md` before running mechanism-diverse held-out scenarios

## 2026-05-04 — Research roadmap revised for publishability

### What changed

- inserted Phase 2.5 before component evaluation
- made `Mem0Lite` the first external published-family baseline, framed as rule-based ADD/UPDATE/DELETE/NOOP over the shared candidate stream rather than a faithful LLM-classifier reproduction
- named the four required CQ ablations: contestation/demotion, wider-scope pending override, pending lookup use, and source-independence gating
- defined three mechanism-diverse held-out mechanisms: adversarial mixed-source corroboration, scope-laundered poison, and long-horizon corrective drift
- made preregistration prediction-bearing, with numeric deltas required before result sweeps
- demoted 32B/70B routing to optional engineering work and added LongMemEval as the external transfer check after noisy mode

### Why it matters

- the roadmap now commits to disconfirmation tests before noisy-mode work can tune around them
- existing v2 held-outs remain surface-form robustness checks; only the new frozen mechanisms can support mechanism-generalization claims
- `Mem0Lite` gives reviewers an external-policy comparison while preserving the repo invariant that policies receive the same upstream candidates and storage substrate
- Phase 4 is capped so local extraction quality is measured and reported rather than becoming a separate open-ended extractor project

### Evidence

- documentation-only planning change; no tests were run

### Open issues / next

- implement Phase 2.5 before starting Phase 3
- write `docs/preregistration.md` with concrete prediction deltas before Phase 2.5 result sweeps or noisy-mode evaluations

## 2026-05-04 — Memory-poisoning override-attack probes added

### What shipped

- added same-scope override-attack templates to the `memory_poisoning` oracle family, with shadow (`0.58`) and borderline (`0.70`) strength regimes in main and held-out splits
- added `clean_durable_displacement_rate` to scenario/summary metrics, CSV output, runner summaries, dashboard summaries, and failure examples
- added `clean_durable_candidate_ids` lifecycle expectations so durable-survival diagnostics stay separate from answer-gold labels
- added regression coverage for template rotation, exact two-observation/one-probe shape, threshold calibration, Naive confidence-first selection, displacement examples, CSV output, and dashboard rendering

### Why it matters

- existing poisoning probes attacked from a clean slate; override attacks now test whether a clean durable survives later contradictory poisoned evidence
- CQ exposes a distinct failure mode: exact-scope contradiction demotes the clean durable, then CQ answers from pending poison in the shadow regime or durable poison in the borderline regime
- Reflection keeps the clean durable because the poison does not clear its overwrite margin; Naive promotes poison but keeps answering from the stronger clean durable
- held-out v2 templates are surface-form variants of the same override mechanism and strength regimes, not mechanism-diversity evidence

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 148 tests
- mixed memory-poisoning run (`python3 -m cq.eval.runner --family memory_poisoning --scenarios 10 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.40`, `correctness=0.60`, `premature_promotion=0.40`, `poison_promotion=0.40`, `clean_displacement=0.00`
  - `consolidation_queue_lite`: `false_assertion=0.60`, `correctness=0.20`, `premature_promotion=0.20`, `poison_promotion=0.20`, `clean_displacement=0.40`
  - `naive_eager_write_lite`: `false_assertion=0.40`, `correctness=0.60`, `premature_promotion=0.80`, `poison_promotion=0.80`, `clean_displacement=0.00`
  - `no_memory_lite`: `false_assertion=0.00`, `correctness=0.00`, `premature_promotion=0.00`, `poison_promotion=0.00`, `clean_displacement=0.00`
  - `scope_blind_transcript_rag_lite`: `false_assertion=0.80`, `correctness=0.20`, `premature_promotion=0.00`, `poison_promotion=0.00`, `clean_displacement=0.00`
- held-out memory-poisoning run (`python3 -m cq.eval.runner --family memory_poisoning --scenarios 10 --template-mix heldout`) shows the same aggregate pattern on `memory_poisoning_dirty_override_shadow_v2` and `memory_poisoning_dirty_override_borderline_v2`
- override template rows show CQ at `clean_displacement=1.00` for both shadow and borderline regimes; Reflection, Naive, NoMemory, and RAG stay at `clean_displacement=0.00`

### Open issues / next

- shadow and borderline are strength regimes of one same-scope override mechanism, not independent poisoning mechanisms
- adversarial corroboration and scope-laundered poison remain untested
- the next highest-leverage project step is likely `docs/preregistration.md` before adding more mechanism variants

## 2026-05-04 — Memory-poisoning untrusted-injection probes added

### What shipped

- added the `memory_poisoning` oracle family with clean trusted, dirty below-floor injection, and dirty pending-eligible injection templates
- added main and held-out memory-poisoning splits, runner/CSV/dashboard wiring, and `poison_promotion_rate`
- factored the repeated single-probe metric shape used by useful-pending, false-corroboration, and memory-poisoning metrics
- added regression coverage for threshold calibration, CQ pending false assertion, eager durable poison promotion, NoMemory floor behavior, and dashboard/CSV output

### Why it matters

- below-floor dirty probes isolate immediate-write durable poison promotion from low-quality untrusted input
- pending-eligible dirty probes expose the important CQ failure mode: CQ can still false-assert a poisoned pending candidate while avoiding durable poison promotion
- Reflection and Naive receive the same candidate stream and shared storage substrate; the divergence is policy behavior, not richer CQ inputs
- ScopeBlindTranscriptRAG fails dirty probes by recency over the newest poisoned transcript candidate, not by durable promotion

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 145 tests
- mixed memory-poisoning run (`python3 -m cq.eval.runner --family memory_poisoning --scenarios 6 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.67`, `correctness=0.33`, `premature_promotion=0.67`, `poison_promotion=0.67`
  - `consolidation_queue_lite`: `false_assertion=0.33`, `correctness=0.33`, `premature_promotion=0.00`, `poison_promotion=0.00`
  - `naive_eager_write_lite`: `false_assertion=0.67`, `correctness=0.33`, `premature_promotion=0.67`, `poison_promotion=0.67`
  - `no_memory_lite`: `false_assertion=0.00`, `correctness=0.00`, `premature_promotion=0.00`, `poison_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `false_assertion=0.67`, `correctness=0.33`, `premature_promotion=0.00`, `poison_promotion=0.00`
- held-out memory-poisoning run (`python3 -m cq.eval.runner --family memory_poisoning --scenarios 6 --template-mix heldout`) shows the same aggregate pattern on `memory_poisoning_clean_trusted_v2`, `memory_poisoning_dirty_below_floor_injection_v2`, and `memory_poisoning_dirty_pending_eligible_injection_v2`
- dirty template-kind rows show Reflection/Naive at `false_assertion=1.00`, `premature_promotion=1.00`, and `poison_promotion=1.00`; CQ at `false_assertion=0.50`, `premature_promotion=0.00`, and `poison_promotion=0.00`; RAG at `false_assertion=1.00` with no poison promotion

### Open issues / next

- v1 only probes untrusted injection in below-floor and pending-eligible strength bands
- v1 does not show resistance to adversarial corroboration, scope-laundered poison, or override of an existing clean durable
- held-out v2 templates are surface-form variants of the same mechanisms, not mechanism-diversity evidence
- override-attack poisoning against an existing clean durable remains the next poisoning-specific Phase 2 mechanism

## 2026-05-04 — False-corroboration source-independence probes added

### What shipped

- added shared source-independence corroboration counting for supported candidate observations
- added the `false_corroboration` oracle family with clean independent-source and dirty mirrored-source templates
- added main and held-out false-corroboration splits, runner/CSV/dashboard wiring, and failure examples for false-corroboration assertions and promoted false stacks
- added regression coverage for source-id independence rules, mirrored-source discounting, no-gold dirty probes, and dashboard timeline rendering of counted/duplicate/capped source ids

### Why it matters

- this tests a distinct Phase 2 mechanism: whether weak supported observations become durable only when their provenance source ids are independent
- the shared substrate computes corroboration for every policy, so CQ does not receive a richer private memory representation
- dirty mirrored-source templates show staged promotion using the shared independence gate before durable write, while Reflection and Naive still commit the first weak false observation eagerly and reinforce the mirrored copies
- ScopeBlindTranscriptRAG fails dirty probes by recency over the newest false candidate, not by durable promotion

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 127 tests
- mixed false-corroboration run (`python3 -m cq.eval.runner --family false_corroboration --scenarios 4 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `correctness=0.50`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `false_assertion=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `no_memory_lite`: `false_assertion=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `false_assertion=0.50`, `correctness=0.50`, `premature_promotion=0.00`
- held-out false-corroboration run (`python3 -m cq.eval.runner --family false_corroboration --scenarios 4 --template-mix heldout`) shows the same aggregate pattern on `false_corroboration_clean_independent_v2` and `false_corroboration_dirty_mirrored_sources_v2`
- dirty template-kind rows show Reflection/Naive at `false_assertion=1.00` and `premature_promotion=1.00`, CQ at `0.00`/`0.00`, and RAG at `false_assertion=1.00` with `premature_promotion=0.00`

### Open issues / next

- this is explicit oracle source-id independence, not learned semantic source independence
- the held-out v2 templates are surface-form variants of the same mechanism, not mechanism-diversity evidence
- a future false-corroboration variant should test a distinct mechanism, such as mirrored sources interleaved with one legitimate independent source
- memory-poisoning override attacks remain separate from false-corroboration source-independence probes

## 2026-05-04 — Workspace-parent scope override probes added

### What shipped

- added shared `WORKSPACE -> PROJECT` parent-scope matching with explicit match-relation diagnostics
- added main and held-out workspace-parent scope-contamination templates
- updated CQ so exact-scope pending overrides can shadow a wider workspace durable without globally demoting it
- added regression coverage for adversarial scope keys, workspace-query preservation, cross-family summaries, and per-policy workspace-parent behavior

### Why it matters

- this adds a non-`WORLD_GLOBAL` scope probe while keeping CQ and eager baselines on the same storage substrate
- the dirty workspace-parent templates test active wider-scope shadowing: the workspace default is legitimate durable memory, but it should not answer a project query after an explicit project override
- the result should be described as oracle scope-key behavior plus CQ override-on-lookup, not learned semantic scope inference
- Reflection receives the same shared parent matching and keeps eager-write baseline behavior; CQ's pending override lookup is the policy feature under test

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 107 tests
- mixed scope run (`python3 -m cq.eval.runner --family scope_contamination --scenarios 8 --template-mix mixed`) shows `scope_contamination_dirty_workspace_parent_v1`:
  - `reflection_eager_write_lite`: `leakage=1.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `consolidation_queue_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `leakage=1.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.00`
- held-out scope run (`python3 -m cq.eval.runner --family scope_contamination --scenarios 8 --template-mix heldout`) shows the same aggregate pattern on `scope_contamination_dirty_workspace_parent_v2`

### Open issues / next

- poisoning and false-corroboration families remain unimplemented
- broader scope-inference claims still require noisy scope-inference component evaluation
- Reflection's parent-match reinforcement behavior can still reinforce wider durables from non-contradictory narrower evidence; the new templates intentionally avoid that path

## 2026-05-03 — Useful-pending-memory oracle family added

### What shipped

- added the `useful_pending_memory` oracle family with clean, dirty-refinement, mixed, and held-out template splits
- pinned the family contract to `PROJECT_CONVENTION` candidates with strength in `[0.35, 0.70)`, so every candidate is usable as pending memory but below durable-promotion threshold
- added useful-pending metrics, failure-example reasons, CLI/runner wiring, CSV output, and dashboard/template summaries
- included `ScopeBlindTranscriptRAGLite` as a recency baseline, but this family is not a retrieval probe because recency tracks truth in both clean and dirty templates

### Why it matters

- clean templates are calibration: pending utility does not cost CQ answer correctness, while Reflection and Naive incur premature durable commits
- dirty refinement templates show the realized reversibility cost of those eager commits when no claim is durable-eligible
- this factors a useful-pending mechanism out of the contradiction family, making the staged-promotion thesis easier to inspect without changing the shared substrate
- for this family, `useful_recall` and `answer_correctness` are identical by construction; they should diverge only in future families that define partial-recall states

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 92 tests
- mixed useful-pending run (`python3 -m cq.eval.runner --family useful_pending_memory --scenarios 4 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.50`, `correctness=0.50`, `useful_recall=0.50`, `pending_use=0.00`, `premature_promotion=1.00`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `correctness=1.00`, `useful_recall=1.00`, `pending_use=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `false_assertion=0.50`, `correctness=0.50`, `useful_recall=0.50`, `pending_use=0.00`, `premature_promotion=1.00`
  - `no_memory_lite`: `false_assertion=0.00`, `correctness=0.00`, `useful_recall=0.00`, `pending_use=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `false_assertion=0.00`, `correctness=1.00`, `useful_recall=1.00`, `pending_use=0.00`, `premature_promotion=0.00`
- held-out useful-pending run (`python3 -m cq.eval.runner --family useful_pending_memory --scenarios 4 --template-mix heldout`) shows the same aggregate pattern on `useful_pending_clean_v2` and `useful_pending_dirty_refinement_v2`

### Open issues / next

- non-broad-claim scope contamination remains the top scope-specific Phase 2 caveat
- poisoning and false-corroboration families remain unimplemented
- a Naive-recovers refinement template would round out useful-pending coverage beyond the current confidence-first Naive failure shape
- `durable_commit` has family-specific semantics across current metric computers; a future cleanup should document or rename those fields before cross-family comparison
- no noisy-mode or retrieval-quality claim should be made from this family

## 2026-05-03 — Scenario-level failure examples added

### What shipped

- added deterministic `failure_examples` to per-scenario and per-policy oracle JSON artifacts
- extracted `false_assertion`, `scope_leakage`, `premature_promotion`, and `incorrect_answer` examples from the same scenario inputs used by metrics
- kept successful-but-premature cases visible, including Naive scope runs that answer correctly after promoting should-not-promote memory
- added dashboard failure-example tables linked to full scenario traces

### Why it matters

- Phase 2 failures are now inspectable without reading every trace by hand
- premature promotion is visible as a reversibility failure even when answer correctness stays high
- NoMemory misses are marked as `no_memory_floor`, keeping the floor baseline present but distinguishable from governance failures

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 79 tests
- regression coverage pins metric/example consistency, byte-stable JSON artifacts, dashboard anchors, and the successful-but-premature Naive scope case

### Open issues / next

- the next Phase 2 implementation task is a non-broad-claim scope-contamination mechanism
- forced-contradiction failed recovery is still represented through `false_assertion` or `incorrect_answer`, not a dedicated `failed_recovery` example type

## 2026-05-03 — Preference-drift oracle family added

### What shipped

- added the `preference_drift` oracle family with clean, dirty, mixed, and held-out template splits
- added explicit-update, low-strength one-off exception, and held-out drift-back probes for `USER_PREFERENCE` / `USER_GLOBAL` memories
- included `ScopeBlindTranscriptRAGLite` in preference-drift runs so recency wins and failures remain visible
- added asserted-answer candidate handling for false/stale checks without changing existing contradiction or scope template metrics

### Why it matters

- explicit-update drift is intentionally contradiction-like and should be treated as a calibration point
- the one-off and drift-back templates are the distinct preference-drift mechanisms: CQ filters low-strength newest evidence, while recency follows it
- the held-out drift-back case distinguishes CQ from both eager durable write and oracle-id recency in one scenario

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 71 tests
- mixed preference run (`python3 -m cq.eval.runner --family preference_drift --scenarios 6 --template-mix mixed --output-json data/runs/preference_drift_oracle.json --output-csv data/results/preference_drift_oracle_metrics.csv`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.33`, `correctness=0.67`, `premature_promotion=0.33`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `correctness=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `false_assertion=0.33`, `correctness=0.67`, `premature_promotion=0.33`
  - `no_memory_lite`: `false_assertion=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `false_assertion=0.33`, `correctness=0.67`, `premature_promotion=0.00`
- held-out preference run (`python3 -m cq.eval.runner --family preference_drift --scenarios 4 --template-mix heldout --output-json data/runs/preference_drift_oracle_heldout.json --output-csv data/results/preference_drift_oracle_heldout_metrics.csv`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `correctness=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `false_assertion=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `no_memory_lite`: `false_assertion=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `false_assertion=0.50`, `correctness=0.50`, `premature_promotion=0.00`
- per-template held-out result:
  - `preference_drift_clean_stable_v2`: Reflection/CQ/Naive/RAG are correct; NoMemory has no recall
  - `preference_drift_dirty_drift_back_v2`: Reflection and Naive stale-assert and prematurely absorb the one-off; CQ answers from pending current preference; RAG follows the newest one-off and fails
- generated `data/runs/` and `data/results/` artifacts are ignored by git; the commands above record the reproducible artifacts rather than committing generated files

### Open issues / next

- scenario-level failure example extraction is now the next Phase 2 implementation task
- a future non-broad-claim scope mechanism is still needed before making broader scope-inference claims
- additional drift templates should only be added when they introduce a genuinely new mechanism

## 2026-05-02 — Held-out scope-contamination split added

### What shipped

- added `heldout` support for the scope-contamination oracle family
- added `scope_contamination_clean_v2`, a held-out clean project-scope recency probe
- added `scope_contamination_dirty_broad_claim_v3`, a held-out broad-first ordering probe with explicit contradiction provenance
- pinned the dirty held-out calibration inequalities that make Reflection, CQ, and Naive diverge for the intended reasons

### Why it matters

- clean_v2 checks that the scope-blind transcript baseline still leaks under a held-out surface form
- dirty_v3 checks whether a broad global convention can be prematurely promoted and then block a lower-strength project override
- this extends Phase 2 coverage without changing the shared substrate, policy interfaces, or metric definitions

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 53 tests
- held-out scope run (`python3 -m cq.eval.runner --family scope_contamination --scenarios 4 --template-mix heldout --output-json data/runs/scope_contamination_oracle_heldout.json --output-csv data/results/scope_contamination_oracle_heldout_metrics.csv`) shows:
  - `reflection_eager_write_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `consolidation_queue_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `no_memory_lite`: `leakage=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.00`
- per-template held-out result:
  - `scope_contamination_clean_v2`: Reflection/CQ/Naive are correct with no leakage; NoMemory has no recall; ScopeBlindTranscriptRAG leaks by recency
  - `scope_contamination_dirty_broad_claim_v3`: Reflection and Naive leak and prematurely promote; CQ answers from scoped pending memory; ScopeBlindTranscriptRAG answers correctly by recency

### Open issues / next

- this is still a broad-claim premature-promotion result, not evidence that CQ has better semantic scope inference
- preference drift and scenario-level failure example extraction remain next Phase 2 work
- a future non-broad-claim scope mechanism is still needed before making broader held-out scope claims

## 2026-05-02 — Broad-claim premature promotion scope slice added

### What shipped

- added the first scope-contamination oracle family as a broad-claim premature-promotion slice
- added `ScopeBlindTranscriptRAGLite`, an oracle-id recency baseline that intentionally ignores scope
- generalized the runner with `--family forced_contradiction|scope_contamination`
- added generic answer correctness, false assertion, leakage, and premature-promotion metrics while preserving contradiction aliases
- updated CSV/dashboard rendering so non-contradiction metrics are visible

### Why it matters

- this extends Phase 2 without changing the shared substrate or giving CQ richer memory than Reflection
- the dirty template isolates staged-vs-eager behavior: the same broad `WORLD_GLOBAL` contaminant is promoted by Reflection and left pending by CQ
- the clean template is deliberately narrow: it validates that the scope-blind transcript baseline leaks under oracle-id recency, not that CQ has special scope reasoning

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 44 tests
- mixed scope run (`python3 -m cq.eval.runner --family scope_contamination --scenarios 2 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `leakage=0.50`, `correctness=0.50`, `premature_promotion=0.50`
  - `consolidation_queue_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.00`
  - `naive_eager_write_lite`: `leakage=0.00`, `correctness=1.00`, `premature_promotion=0.50`
  - `no_memory_lite`: `leakage=0.00`, `correctness=0.00`, `premature_promotion=0.00`
  - `scope_blind_transcript_rag_lite`: `leakage=1.00`, `correctness=0.00`, `premature_promotion=0.00`

### Open issues / next

- these results are in-distribution only and should not be cited as generalization evidence until held-out scope templates land
- the dirty result should be described as staged promotion resisting a broad contaminant, not as CQ doing better scope-aware reasoning
- preference drift and scenario-level failure example extraction remain next Phase 2 work

## 2026-05-01 — NoMemory floor baseline and correctness metric added

### What shipped

- added `NoMemoryLite` as the zero-history floor baseline on the oracle contradiction slice
- added `answer_correctness_after_contradiction` alongside the existing strict recovery metric
- updated the runner, CSV, and dashboard summaries to show correctness after recovery
- explicitly deferred `TranscriptRAGLite` until the first scope-contamination patch

### Why it matters

- the contradiction slice now separates “answered the post-contradiction question correctly” from “recovered by invalidating prior memory”
- `NoMemoryLite` makes the lower bound explicit without pretending current-session transcript use is “no memory”
- deferring `TranscriptRAGLite` keeps the current contradiction benchmark sharper instead of adding a transcript baseline that would mostly look good because the corrective turn is still adjacent

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` now passes with 34 tests
- mixed oracle run (`python3 -m cq.eval.runner --scenarios 6 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.67`, `recovery=0.33`, `correctness=0.33`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `recovery=1.00`, `correctness=1.00`
  - `naive_eager_write_lite`: `false_assertion=0.33`, `recovery=0.67`, `correctness=0.67`
  - `no_memory_lite`: `false_assertion=0.00`, `recovery=0.00`, `correctness=0.00`
- held-out oracle run (`python3 -m cq.eval.runner --scenarios 4 --template-mix heldout`) shows:
  - `no_memory_lite`: `false_assertion=0.00`, `recovery=0.00`, `correctness=0.00`

### Open issues / next

- the next family should be scope contamination, paired with `TranscriptRAGLite`
- preference drift should follow scope contamination
- the contradiction family still needs more independent held-out mechanisms, but only when they sharpen the result

## 2026-04-26 — Held-out contradiction family diversified

### What shipped

- expanded the held-out contradiction split from `dirty_v3`/`dirty_v4` to `dirty_v3` through `dirty_v6`
- added `dirty_v5`, a two-step correction cascade where Naive also recovers
- added `dirty_v6`, a cautious authoritative contradiction where Naive's confidence-first answer selection still hurts
- updated the held-out regression coverage and regenerated the held-out oracle artifacts

### Why it matters

- the held-out contradiction family no longer tests only “old confidence stays above new confidence”
- the new split now includes both:
  - a held-out case where Naive also recovers, so CQ's advantage is not limited to beating Reflection
  - a held-out case where confidence-first durable selection is itself the failure mode
- this makes the contradiction family a sharper probe of what CQ buys beyond simple confidence ranking
- `dirty_v5` is intentionally subtle: Naive recovers there by reinforcing the newer correction durable above the old claim, not by clean contradiction resolution

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` still passes with 29 tests
- held-out oracle run (`python3 -m cq.eval.runner --scenarios 4 --template-mix heldout`) now shows:
  - `reflection_eager_write_lite`: `false_assertion=1.00`, `recovery=0.00`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `recovery=1.00`
  - `naive_eager_write_lite`: `false_assertion=0.75`, `recovery=0.25`
- per-template held-out result:
  - `dirty_v3`: Reflection fails, CQ recovers, Naive fails
  - `dirty_v4`: Reflection fails, CQ recovers, Naive fails
  - `dirty_v5`: Reflection fails, CQ recovers, Naive recovers via reinforcement into the newer correction durable
  - `dirty_v6`: Reflection fails, CQ recovers via pending memory, Naive fails

### Open issues / next

- the held-out contradiction family is better, but it still needs more independent mechanisms before it should carry strong conclusions by itself
- `NoMemory` and `TranscriptRAG` remain unimplemented
- preference drift and scope contamination are still the next benchmark families to add

## 2026-04-26 — Naive eager baseline added

### What shipped

- added `NaiveEagerWriteLite` as a third oracle-mode baseline on the shared substrate
- updated the default runner to compare `ReflectionEagerWriteLite`, `ConsolidationQueueLite`, and `NaiveEagerWriteLite`
- normalized `forced_contradiction_dirty_v2` so it forbids both old candidate ids, matching `dirty_v4`
- hardened the dashboard timeline by sorting lifecycle events before oracle-turn bucketing
- extended regression coverage to pin Naive behavior by template and verify the demotion event lands in the correct held-out turn bucket

### Why it matters

- the benchmark now separates three policies instead of two: staged promotion, reflected eager write, and append-only eager write
- `NaiveEagerWriteLite` isolates what Reflection's overwrite-margin is buying and where it hurts
- the key result is template-specific: Reflection fails on `dirty_v2`, while Naive recovers because it keeps both durables active and answers from the higher-confidence new durable

### Evidence

- `python3 -m unittest discover -s tests -p 'test_*.py'` passes with 28 tests
- mixed oracle run (`python3 -m cq.eval.runner --scenarios 6 --template-mix mixed`) shows:
  - `reflection_eager_write_lite`: `false_assertion=0.67`, `recovery=0.33`
  - `consolidation_queue_lite`: `false_assertion=0.00`, `recovery=1.00`
  - `naive_eager_write_lite`: `false_assertion=0.33`, `recovery=0.67`
- per-template mixed result:
  - `dirty_v1`: Reflection fails, CQ recovers, Naive fails
  - `dirty_v2`: Reflection fails, CQ recovers, Naive recovers
- held-out oracle run (`python3 -m cq.eval.runner --scenarios 4 --template-mix heldout`) shows Naive matches Reflection and loses on both `dirty_v3` and `dirty_v4`
- saved artifacts:
  - `data/runs/forced_contradiction_oracle.json`
  - `data/runs/forced_contradiction_oracle_heldout.json`
  - `data/results/forced_contradiction_oracle_metrics.csv`
  - `data/results/forced_contradiction_oracle_heldout_metrics.csv`

### Open issues / next

- the held-out contradiction family still needs more independent mechanisms because `dirty_v2` and `dirty_v4` are both corroborated-old/sub-margin contradiction cases
- `NoMemory` and `TranscriptRAG` remain unimplemented
- preference drift and scope contamination are still the next benchmark families to add

## 2026-04-26 — Phase 1 contradiction slice hardened

### What shipped

- expanded the forced-contradiction oracle family from one clean path into multiple dirty variants plus held-out templates
- added per-template-kind, per-template-split, and per-template-id summaries
- added a static dashboard timeline grouped by oracle turn
- tightened regression coverage around dirty-template rotation, held-out behavior, summary slicing, and dashboard rendering

### Why it matters

- the contradiction benchmark stopped being a clean-path demo and became a real policy comparison
- CQ's advantage is now visible on dirty and held-out cases rather than only as “pending use versus early durable commit”
- saved traces make failure modes inspectable instead of hiding them inside aggregate scores

### Evidence

- the current mixed/held-out artifacts still preserve the core two-policy result:
  - Reflection fails on the dirty contradiction templates
  - CQ recovers on all shipped contradiction templates
- dashboard outputs:
  - `data/results/dashboard.html`
  - `data/results/dashboard_heldout.html`

### Open issues / next

- the contradiction family still needs more held-out mechanisms before the held-out split should carry much interpretive weight
- the repo still lacked a simpler eager baseline at this stage, which is why `NaiveEagerWriteLite` was added next
