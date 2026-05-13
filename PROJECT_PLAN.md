# Consolidation Queue Project Plan

Last updated: 2026-05-13

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

- `Mem0Lite`, a rule-based ADD/UPDATE/NOOP write-time policy over the same CQ oracle/noisy candidates; DELETE is reserved until the schema has explicit delete/retraction events

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
- `Mem0Lite` as an opt-in Phase 2.5 external published-family baseline over the shared substrate
- four named CQ ablation policy variants over the same shared substrate
- oracle-only `adversarial_upstream_noise` family with retraction, witness-conflict, temporal-skew, scope-narrowing, and pending-competition mechanisms
- oracle-only `evidence_conflict_spectrum` family implementation for the Phase 2.6 abstention-calibration benchmark, with structure summaries and non-degeneracy probe artifacts recorded before full sweeps
- denominator-aware abstention replay and primary CQ-vs-`Mem0Lite` abstention comparison plumbing
- recorded `adversarial_upstream_noise` headline artifacts plus result readout, with Bucket D triggered because CQ loses only the dated-evidence `temporal_skew` lane while clearing the four dedicated component lanes
- a separate post-hoc follow-up preregistration for `CQDatedContestation`, kept out of the original `phase2_5` headline policy set
- fixed-seed paired-bootstrap helper for preregistered per-mechanism CQ-versus-Reflection comparisons
- `docs/preregistered_memory_governance_evaluation_template.md` as a reusable preregistration-and-readout discipline template
- `docs/abstention_quality_preregistration.md` as the Phase 2.6 abstention-calibration preregistration
- explicit component-eval and local-extractor family allowlists so oracle-only adversarial families do not auto-enroll in the locked Phase 3 path
- mechanism-diverse frozen held-out scenario contracts behind a verified preregistration lock
- `docs/preregistration.md` with numeric Phase 2.5 predictions and a frozen contract hash
- `docs/predictions_vs_results.md` with the Phase 2.5 frozen oracle predictions and observed results
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
- Phase 3 component-evaluation harness for candidate detection, claim type, scope level/key, canonicalization, and contradiction detection, including oracle upper-bound mode and quality-gate reporting
- Phase 3 oracle upper-bound reference artifact matrix across current benchmark families and calibrated splits
- event-aligned `contradicts_event_ids` component scoring for extractor outputs, with legacy candidate-id contradiction scoring preserved for oracle/backcompat paths
- contradiction-gate applicability metadata so no-edge families are marked not applicable rather than failed
- transcript-only local extractor bridge with hard input isolation, weak negative-control mode, and forced-contradiction positive-control mode
- transcript-only command-adapter extractor transport for user-provided local model commands, with reproducibility metadata and per-scenario error reporting
- first forced-contradiction local-model smoke artifacts through the transcript-only bridge, using matched Qwen 2.5 `Q4_K_M` 7B floor and 32B headroom runs with scored component outputs
- CI-aware component gate-decision runner with 60-scenario held-out primary rows, Wilson event-assumption lower bounds, conservative F1 composites, observed-only B-cubed labeling, and pairwise canonicalization CI support
- running product progress notes in `docs/product_progress.md`
- regression coverage for contradiction branches, scope matching, and metric edge cases

Not implemented yet:

- lexical or embedding-based `TranscriptRAG`
- broader scored local-model noisy pipeline beyond the forced-contradiction smoke sample
- full `evidence_conflict_spectrum` mixed/held-out oracle sweeps and `docs/abstention_quality_results.md`
- optional 32B/70B routing
- LongMemEval transfer check
- final writeup docs

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

Status: frozen oracle sweep recorded; `Mem0Lite`, CQ ablations, frozen mechanism-diverse contracts, preregistration lock, dashboard artifact, and prediction-vs-result comparison now exist.

This phase must happen before Phase 3 component evaluation and before preregistering noisy-mode predictions. The point is to commit to comparison targets and disconfirmation tests before more pipeline work can tune around them.

Add:

- `Mem0Lite`, implemented as a rule-based ADD/UPDATE/NOOP policy over the shared candidate and storage substrate
- four named CQ ablation variants
- a mechanism-diverse held-out set with net-new mechanisms
- `docs/preregistration.md` with prediction-bearing quantitative commitments

Slice order:

1. Implement `Mem0Lite`, wire it through an opt-in policy set, test it on existing families, and record calibration numbers. Done.
2. Implement the named CQ ablations with targeted tests. Done.
3. Add frozen mechanism-diverse scenario contracts and contract tests, but do not execute them against any policy. Done.
4. Write `docs/preregistration.md` with numeric predictions, including the 5 percentage point disconfirmation mode, before frozen sweeps run. Done.
5. Run the locked frozen mechanism-diverse oracle sweep and compare results against preregistered predictions. Done.

`Mem0Lite` design call:

- Do not put a Mem0-style LLM operation classifier into the oracle comparison.
- Do not claim this is a faithful reproduction of Mem0's full system.
- Frame it as testing whether the ADD/UPDATE/NOOP write discipline beats staged promotion when both policies receive the same oracle candidates, scopes, strengths, and contradiction/support metadata.
- In oracle mode, ADD promotes candidates that clear `minimum_write_confidence`, UPDATE demotes and overwrites contradictory active durables without Reflection's overwrite margin, matching/supporting observations reinforce through the shared substrate, and NOOP leaves below-threshold candidates non-durable without pending lookup.
- DELETE is reserved because the current oracle schema has no explicit negation, deletion, or retraction primitive; revisit it for noisy mode or future deletion scenarios.
- Treat oracle-mode `Mem0Lite` as a partial baseline result because it is likely close to eager write with deduplication. The headline `Mem0Lite` comparison belongs after Phase 4, where noisy extraction and update decisions can matter.

Required CQ ablations:

- `cq_no_contestation_demotion`: disables the contestation/demotion path for contradictory candidates and active durables.
- `cq_no_wider_scope_pending_override`: disables the narrower pending override exception for active wider-scope durables.
- `cq_no_pending_lookup_use`: disables answering from pending candidates on lookup.
- `cq_no_source_independence_gate`: disables source-independence corroboration gating for CQ promotion decisions while keeping the candidate stream and substrate fields visible.

Ablation rules:

- Ablations modify policy decision logic only. The shared substrate's corroboration counting, lifecycle logging, and scope matching remain unchanged.
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
- Predictions for this mechanism-diverse held-out set must be in `docs/preregistration.md` before these scenarios are executed against any policy, including baselines and ablations.
- Existing-family `Mem0Lite` and ablation observations may inform preregistration because those families are already in-repo; frozen mechanism-diverse scenarios must not be executed against any policy before predictions are committed.
- Use this set as the only basis for mechanism-generalization claims.
- Continue reporting existing v2 held-outs as surface-form robustness checks, not mechanism-diversity evidence.

Preregistration requirements:

- `docs/preregistration.md` must contain predictions, not only task lists.
- Predictions must include numeric deltas for CQ vs `Mem0Lite`, CQ vs ReflectionEagerWrite, and full CQ vs each named CQ ablation.
- Predictions must be specified per scenario family per primary metric: `false_assertion_rate`, `answer_correctness`, `poison_promotion_rate`, `premature_promotion_rate`, `clean_durable_displacement_rate`, and `scope_leakage_rate`.
- Aggregate deltas may be reported, but they cannot replace per-family commitments.
- Predictions must include oracle-mode and noisy-mode expectations, including expected oracle-vs-noisy gaps by policy.
- If results contradict the predictions, report the contradiction directly in the final writeup.
- If `Mem0Lite` matches or exceeds CQ within 5 percentage points on the primary metrics across the mechanism-diverse held-out set, CQ is not supported as a policy contribution. In that case, reframe the writeup as a benchmark and failure-taxonomy contribution rather than a CQ policy contribution.

Required outcome:

- reviewers can see that external comparison, ablation, and mechanism-generalization tests were specified before noisy-mode work
- the project can produce negative, mixed, or CQ-favorable results without changing the evaluation contract
- the frozen mechanism-diverse set cannot be executed through the runner unless `docs/preregistration.md` matches the verified lock
- observed frozen oracle deltas matched preregistered predictions; CQ tied `Mem0Lite` on answer correctness and false assertions while improving premature promotion, so oracle-mode support over `Mem0Lite` is narrow and should not be framed as broad answer-quality superiority

### Phase 2.6: Abstention-Calibrated Memory Governance Axis

Status: implementation and pre-run artifacts exist; full oracle sweeps are pending and must not be run until the preregistration plus pre-run artifacts are committed.

This is a separate oracle-only benchmark-strengthening step. It does not reopen the Phase 2.5 frozen contract, the Phase 3 component gate, or Phase 4 noisy policy comparison.

Add:

- `evidence_conflict_spectrum`, with zero, mild, moderate, witness, and polluted conflict-intensity mechanisms
- denominator-aware abstention replay metrics:
  - `useful_abstention_rate`
  - `harmful_abstention_rate`
  - unweighted mechanism-bucket comparisons for the primary gate
- a structure-only summary script for scenario design audit
- a CQ-vs-`Mem0Lite` non-degeneracy probe that confirms abstain-required mechanisms exercise different policy actions before Section B predictions are locked
- `docs/abstention_quality_preregistration.md`, separating partial post-hoc replay from strict spectrum-family pre-run predictions

Primary gate:

- CQ vs `Mem0Lite` on `evidence_conflict_spectrum`, mixed split
- `conflict_moderate` useful abstention clears `delta >= 0.10` and one-sided 95% LCB `> 0`
- `conflict_witness` useful abstention clears the same rule
- harmful abstention over `conflict_zero`, `conflict_mild`, and `conflict_polluted` is non-inferior: CQ-Mem0 delta `<= 0.05` and UCB `<= 0.05`
- held-out must pass the same gate for full support; otherwise downgrade to narrow support

Required outcome:

- the unique witness-conflict finding is either strengthened into an abstention-calibration axis or honestly narrowed to witness-only support
- commit-required rows prevent an over-abstaining CQ from passing through useful-side gains alone
- all numeric claims trace to saved replay, structure, probe, and runner artifacts

### Phase 3: Component Evaluation Harness

Status: in progress; oracle upper-bound reference artifacts, event-aligned contradiction scoring, gate applicability metadata, a transcript-only extractor bridge, and a backend-neutral command-adapter transport now exist. The real 7B `general_v1` CI-aware gate run with required frozen sentinel stayed locked on 2026-05-11, and the 2026-05-12 follow-up evidence block completed: the 7B schema-rescue path removed all primary scenario errors but still stayed gate-locked on observed per-family/frozen failures, while the descriptive 32B blocker-surface sweep cleared the same common-surface failures.

Implemented:

- candidate extraction eval
- claim type eval
- scope inference eval
- canonicalization eval
- contradiction detection eval
- oracle upper-bound reference artifact matrix across current families and splits
- event-id contradiction edge scoring for extractor outputs, with undirected edge normalization
- generator invariant coverage for one observation event per gold candidate id and resolvable contradiction targets
- transcript-only extractor input contract and local extractor smoke CLI
- weak negative-control and forced-contradiction positive-control extractor modes
- command-adapter `model` mode with required model id, prompt metadata, decoding metadata, and per-scenario `scenario_errors`
- component-eval handling for `scenario_errors` and extra same-event predictions
- per-component failure examples for non-oracle predictions, including candidate, claim/scope, canonicalization, contradiction, and scenario-error diagnostics
- first deterministic local Ollama command and forced-contradiction prompt, with Qwen 2.5 7B floor and 32B headroom artifacts scored before any policy run
- diagnostic-only local-model component scoring matrix runner, with `general_v1` prompt regression checks, deterministic JSON checks, collision-resistant artifact naming, and descriptive-only framing
- first attempted diagnostic matrix run, stopped by the Phase A prompt-regression guard before broader rows because 32B `general_v1` missed one forced-contradiction corroborating observation
- family-neutral `general_v1` prompt revision for per-observation extraction and support-vs-contradiction guidance
- completed diagnostic matrix run after the prompt revision, with final prompt-hash-matching diagnostic artifacts and no statistical gate verdict issued
- `docs/component_diagnostic_matrix.md`, interpreting the completed diagnostic matrix with a fixed failure taxonomy and selecting prompt/schema diagnostics as the next active task
- `prompt_schema_diagnostic` row-set support in `scripts/run_component_scoring_matrix.py`, with prompt path/label overrides, `general_v2` prompt artifact naming, and boundary-adjusted diagnostic summaries that keep policy comparisons locked
- `prompts/component_extractor_general_v2.txt`, a single prompt-only diagnostic candidate focused on non-empty required fields, canonical slot reuse, full scope-key preservation, and explicit treatment of one-off preference constraints as benchmark-boundary scope cases
- completed targeted `general_v2` diagnostic run; Phase A passed and 11 targeted rows were written, but the branch did not resolve because adjusted 32B scope drift was `5`, adjusted 32B canonical split/merge was `7`, and 7B still had six validation-error scenario failures
- the only accepted boundary carve-outs for that summary are 32B `preference_drift_002-event-4` and `preference_drift_004-event-4` `scope_key`/`scope_level` mismatches from `docs/component_diagnostic_matrix.md`; the branch-resolution criterion still requires zero targeted-row scenario errors
- `scripts/run_component_gate_decision.py`, a separate CI-aware gate-decision runner that reuses Phase A prompt regression and determinism checks, runs 7B `general_v1` over 60 held-out scenarios per benchmark family, keeps 32B headroom descriptive, and emits `policy_comparison_unlocked` only from the 7B primary gate
- the real 7B `general_v1` gate run completed with required frozen sentinel and no 32B headroom; `phase_a_passed=true` and `determinism_passed=true`, but `policy_comparison_unlocked=false` because the run recorded `45` primary scenario errors, `8` primary observed gate failures, and `3` frozen-sentinel observed gate failures
- completed follow-up evidence under `docs/component_gate_followup_preregistration.md`: the descriptive 32B default-schema sweep over `scope_contamination`, `preference_drift`, `memory_poisoning`, and the frozen sentinel, plus the full 7B `general_v1_dynamic_schema` run with frozen sentinel
- the 7B schema-rescue run recorded `phase_a_passed=true`, `determinism_passed=true`, `primary_scenario_error_count=0`, `primary_observed_gate_failure_count=5`, `frozen_sentinel_observed_gate_failure_count=2`, and `policy_comparison_unlocked=false`
- `docs/component_gate_followup_benchmark_memo.md`, recording the completed follow-up comparison, the common-surface burden reductions, the no-quadrant decision, and the draft-versus-expansion recommendation

Status notes:

- do not treat Phase A clearance as cross-family prompt safety; it only guards the forced-contradiction smoke row, so scope, drift, poisoning, false-corroboration, useful-pending, and mechanism-diverse regressions require direct artifact inspection
- the locked 7B baseline is dominated by invalid model outputs rather than aggregate CI math: empty `scope_key`, empty `canonical_id`, and invalid `contradicts_event_ids` targets drive the scenario-error burden across `scope_contamination`, `preference_drift`, `useful_pending_memory`, `false_corroboration`, `memory_poisoning`, and the frozen sentinel
- the completed follow-up now splits that baseline burden into two effects: a stricter structured interface removes the schema-shaped blocker class on 7B without vacuous placeholder substitution, while larger-model capacity removes the remaining common-surface measured failures in the descriptive 32B rows
- do not reopen `general_v2`, add prompt-only retries, loosen validators, lower thresholds, or otherwise make the component gate easier to pass; those are model-quality workarounds, not code fixes
- do not make Phase 4 noisy policy-comparison claims from the current 7B path; the follow-up supports a benchmark/gate-methodology/failure-taxonomy writeup, not a noisy-policy unlock

Required outcome:

- explicit quality gates before noisy-mode claims
- gold labels attached to scenarios
- no noisy-mode claim unless component outputs are scored through the transcript-only bridge

### Phase 4: Noisy Local-Model Pipeline

Status: on hold. The 2026-05-11 real 7B `general_v1` component gate run stayed locked, so extracted-candidate policy comparison does not start under the current contract.

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
- `docs/predictions_vs_results.md`, with every committed numeric prediction next to the observed value and interpretation
- final paper/report structure

LongMemEval positioning:

- Use LongMemEval as an external task-design transfer check after Phase 4.
- Do not frame the claim as "beating LongMemEval".
- Frame the claim as whether the CQ-vs-baseline policy comparison transfers to a benchmark the project did not design.
- Keep real-user, weeks-long helpfulness as an explicit limitation and future-work item.

Current framing note:

- frame the current noisy-mode outcome as a benchmark, gate-methodology, and failure-taxonomy contribution rather than a CQ noisy-policy contribution; the follow-up evidence now supports drafting that methodology story without reopening Phase 4
- the separate oracle-only `adversarial_upstream_noise` comparison has now landed as a recorded policy result at the candidate-stream locus of noise, with extraction held constant and the locked Phase 3 / Phase 4 path unchanged
- that family now carries a two-part story: four mechanism wins plus a named dated-evidence weakness on `temporal_skew`; any repair attempt belongs in the separately preregistered `CQDatedContestation` follow-up rather than the original headline artifact

## Scenario Families

Target families:

1. forced contradiction
2. preference drift
3. scope contamination
4. memory poisoning
5. false corroboration
6. useful pending memory
7. evidence conflict spectrum

For each family:

- include clean templates
- include dirty templates
- split by template, not just instance
- store latent truth, oracle events, transcript, and expected lifecycle

## Metrics That Matter

Primary metrics:

- useful recall
- answer correctness
- false assertion rate
- contradiction recovery rate
- time to demotion
- scope leakage rate
- poison promotion rate
- premature promotion rate
- clean durable displacement rate
- memory precision
- memory recall
- pending utility gain
- useful abstention rate
- harmful abstention rate

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

The first deterministic forced-contradiction local-model command/prompt, component scoring artifacts, and per-component failure examples are complete. The first diagnostic matrix attempt stopped on 2026-05-08 before broader rows because the Phase A prompt-regression guard caught a 32B `general_v1` candidate-detection regression on `forced_contradiction_006`. A family-neutral `general_v1` prompt revision cleared Phase A, and the diagnostic matrix completed with no statistical gate verdict issued. `docs/component_diagnostic_matrix.md` interpreted the completed matrix as diagnostic component evidence only. Its branch rule selected prompt/schema diagnostics first because scope drift and canonical split defects recur across at least two families at both 7B and 32B. The targeted `general_v2` diagnostic run completed, but the branch failed the adjusted acceptance rule (`scope_key_or_level_drift=5`, `canonical_split_or_merge=7`, six 7B scenario errors; branch resolution requires zero targeted-row scenario errors), so `general_v2` should not become the future diagnostic/gate default. The real 7B `general_v1` CI-aware gate run with required frozen sentinel completed on 2026-05-11 and stayed locked (`policy_comparison_unlocked=false`) despite passing Phase A and determinism. The completed 2026-05-12 follow-up evidence block then ran the descriptive 32B blocker-surface sweep and the full 7B schema-rescue run. Both mandatory runs reduced the preregistered common-surface schema-shaped burden from `26` to `0`, so the conditional `32B + schema` quadrant did not trigger. The 7B schema-rescue run still remained locked on observed per-family/frozen failures (`5` primary, `2` frozen), while the 32B descriptive rows cleared the same common-surface measured failures. `docs/component_gate_publication_outline.md` maps the publication package, `docs/component_gate_failure_taxonomy.md` records the locked-gate interpretation, and `docs/component_gate_followup_benchmark_memo.md` records the follow-up decomposition and next-step recommendation. The separate oracle-only `adversarial_upstream_noise` headline runs are now also recorded: CQ clears four of five preregistered mechanisms on `mixed`, loses only `temporal_skew`, and therefore triggers the separately preregistered `CQDatedContestation` follow-up rather than a retrofit of the original `phase2_5` policy set. Phase 4 remains on hold. Next:

1. Keep Phase 4 extracted-candidate policy comparisons on hold while `policy_comparison_unlocked=false`.
2. Commit the Phase 2.6 abstention-calibration implementation, preregistration, replay artifacts, structure summaries, and non-degeneracy probes before running the full `evidence_conflict_spectrum` policy sweeps.
3. Run the preregistered `evidence_conflict_spectrum` mixed and held-out oracle sweeps, then write `docs/abstention_quality_results.md` from saved artifacts only.
4. Fold the recorded `adversarial_upstream_noise` result, the abstention-calibration readout, and the methodology template into the benchmark/methodology draft without upgrading any claim beyond its preregistered bucket.
5. Treat `CQDatedContestation` as a separate optional follow-up; do not retrofit the original `phase2_5` headline result.

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
