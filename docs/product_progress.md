# Product Progress

## 2026-05-16 — CQR second abort and CQDated partial preregistered success

### What shipped

- executed the repaired CQR audit against the locked Phase 4 commit
  `98959788` in `--equivalence-mode path_normalized` from a detached replay
  worktree; the audit aborted under Bucket D for
  `locked_run_json_sha_mismatch` (working as designed — the replay-equivalence
  rule fired rather than a code or test failure)
- executed the preregistered `CQDatedContestation` follow-up on
  `adversarial_upstream_noise` with `--policy-set followup --scenarios 300` for
  both `mixed` and `heldout` splits; recorded partial preregistered success:
  base CQ's `temporal_skew` failure is repaired
  (`answer_correctness` `0.00`→`1.00` vs base CQ on both `v1` and `v2`) and
  the four originally won mechanisms do not reverse, but the preregistered
  Reflection win criterion (delta `>= 0.10`, LCB `> 0`) is not cleared
  because both `CQDatedContestation` and `ReflectionEagerWriteLite` land at
  `correctness=1.00` on this lane (delta `+0.00`)
- added `docs/adversarial_upstream_noise_dated_followup_results.md` recording
  the Lane B outcome as partial preregistered success (base-CQ repair with the
  Reflection win criterion not cleared) against the preregistration's three
  success criteria
- appended the 2026-05-16 retry section to
  `docs/canonical_id_resolution_audit_results.md`, preserving the 2026-05-15
  first-abort record verbatim
- tracked the two Lane B metrics CSVs under
  `data/results/adversarial_upstream_noise/`; left the regeneratable 85+ MB
  followup run JSONs untracked (SHA and size recorded in the result doc)

### Why it matters

- the CQR second abort is itself the §4 plan-matrix Bucket-D outcome: the
  path-normalized replay discipline refuses to emit a verdict when the locked
  inputs cannot be reproduced; the abort attempt did not establish a single
  cause for the non-reproducibility and is documented as observed evidence
  rather than causal closure
- the CQDated outcome lets the writeup claim a named post-hoc repair of base
  CQ's dated-evidence failure mode without rewriting the original `phase2_5`
  headline, while honestly recording that the preregistered Reflection win
  criterion was not cleared on this lane (Reflection's eager-overwrite already
  records `correctness=1.00`, so the dated fix raises CQ to parity rather than
  past it)
- both outcomes together unblock methodology-draft promotion: it now lands
  with two recorded results rather than waiting on a CQR Bucket A/B/C readout

### Open issues / next

- promote `docs/benchmark_methodology_draft.md` to the technical-report spine
  per `docs/next_research_plan.md`, framing CQR as a documented second abort
  and CQDated as a named post-hoc repair (neither settles Phase 4 null-row
  attribution)
- Phase 4 null rows on `useful_pending_memory`, `memory_poisoning`,
  `scope_contamination`, and the frozen sentinel remain unattributed; future
  attribution work would require a freshly run Phase 4 baseline (a new
  experiment, not a methodology repair)
- LongMemEval feasibility memo remains future work, gated on the methodology
  draft

## 2026-05-15 — Next original-research plan written

### What shipped

- added `docs/next_research_plan.md` as the active next-phase research plan
- updated `PROJECT_PLAN.md` so immediate next tasks point to that plan before
  the historical task ledger

### Why it matters

- the project now prioritizes a defensible mechanism-local contribution over
  adding benchmark breadth
- the next work stays anchored on CQR replay repair, honest Bucket B
  attribution, and one preregistered follow-up only after the internal story is
  settled

### Open issues / next

- write the narrow CQR path-normalization repair preregistration and tests
- rerun CQR only under the repaired replay-equivalence contract
- update the methodology draft from the CQR outcome or explicitly keep CQR as
  an abort

## 2026-05-15 — Canonical-id resolution audit aborts under locked replay

### What happened

- ran the locked CQR audit command after confirming the worktree was clean and
  `qwen2.5:32b-instruct-q4_K_M` was installed locally
- the first sandboxed attempt stopped before replay because localhost access to
  Ollama was blocked for model digest verification
- after local Ollama access was allowed, the official replay aborted with
  Bucket D: `locked_input_sha_mismatch` on
  `data/runs/noisy_policy_comparison_forced_contradiction_default_manifest.json`
- recorded the abort in `docs/canonical_id_resolution_audit_results.md`

### Why it matters

- CQR did not emit an A/B/C result, so the Phase 4 null rows remain
  unattributed as in `docs/noisy_policy_mechanism_audit.md`
- the methodology draft promotion is blocked by the plan's own Bucket D branch;
  the draft should not claim canonical-id/query-resolution attribution until a
  valid non-abort audit result exists
- investigation showed the current `main` replay changes locked adapter/git
  metadata, while a detached locked-Phase-4 worktree preserves the adapter,
  metric, and candidate-stream hashes but still differs on the regenerated run
  JSON hash because the artifact embeds an absolute `predictions_path`

### Evidence

- lock check:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_canonical_id_resolution_audit.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --check-lock-only`
- official stop report:
  `data/results/canonical_id_resolution_audit_stop.json`
- abort report:
  `docs/canonical_id_resolution_audit_results.md`

### Open issues / next

- do not promote `docs/benchmark_methodology_draft.md` to arXiv-report form
  until CQR emits Bucket A/B/C or the report explicitly treats CQR as an abort
- preregister or narrowly document a path-normalization repair for CQR that
  separates stable policy artifacts from absolute-path-sensitive run JSON fields
- keep prompt, threshold, validator, adapter, policy, and substrate changes out
  of this repair unless they are separately preregistered as a new experiment

## 2026-05-15 — Canonical-id resolution audit locks CQR follow-up

### What shipped

- added `docs/canonical_id_resolution_audit_preregistration.md` with locked
  Section B/C predictions, pre-lock disclosure, locked input SHAs, and the
  byte-identical audit-time alias source
- added `scripts/run_canonical_id_resolution_audit.py`, a standalone replay
  runner that checks the preregistration lock, invokes the Phase 4 noisy policy
  comparison, verifies regenerated artifacts against their manifests, computes
  exact/scope/alias CQR, and emits summary/CSV/manifest/results artifacts
- added `tests/test_canonical_id_resolution_audit.py` for alias-source lock
  identity, exact-vs-scope-vs-alias CQR, negative-control false positives,
  cross-tab marginals, manifest SHA aborts, and lock-only CLI behavior

### Why it matters

- the Bucket B null-row follow-up now stays in the allowed
  canonical-id/query-resolution lane instead of reopening prompts, thresholds,
  validators, or adapter semantics
- the audit distinguishes cluster-oriented B-cubed F1 from exact lookup
  evaluability, with `useful_pending_memory` and `memory_poisoning` as the only
  thesis-gating families
- the runner preserves preregistration discipline: full replay aborts from a
  dirty pre-run worktree and must be run after the implementation is committed

### Evidence

- targeted tests:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_canonical_id_resolution_audit -q`
- lock check:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_canonical_id_resolution_audit.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --check-lock-only`
- preregistration:
  `docs/canonical_id_resolution_audit_preregistration.md`

### Open issues / next

- superseded by the later 2026-05-15 Bucket D abort entry above
- do not treat the preregistered CQR follow-up as executed successfully until
  the deterministic-replay issue is resolved and a non-abort result is emitted

## 2026-05-15 — Bucket B mechanism audit locks attribution

### What shipped

- added `docs/noisy_policy_mechanism_audit_hypothesis.md` and committed it
  before writing the audit body
- added `docs/noisy_policy_mechanism_audit.md` with per-family attribution rows
  for the five countable families, descriptive `false_corroboration`, and the
  frozen sentinel
- added `data/results/noisy_policy_mechanism_audit_evidence.json`, a compact
  evidence extract generated from existing Phase 4 summary, metrics, run, and
  32B component-eval artifacts
- added `scripts/generate_noisy_policy_mechanism_audit.py` so the compact
  evidence and focused traces can be regenerated from saved primary artifacts
- added focused dashboard traces for `forced_contradiction_001`,
  `scope_contamination_001`, and `useful_pending_001`
- fixed dashboard timestamp sorting for noisy traces that mix naive oracle
  question timestamps with timezone-aware extracted candidate timestamps
- updated `docs/benchmark_methodology_draft.md` and `PROJECT_PLAN.md` so the
  next writeup step starts from the audit result rather than the older follow-up
  placeholder

### Why it matters

- the audit narrows Bucket B to a defensible mechanism-local thesis:
  `forced_contradiction` is clean contestation/demotion survival, and
  `preference_drift` is partial survival under residual claim-type/scope drift
- the tied rows are not all extractor-floor convergence findings:
  `useful_pending_memory` and `memory_poisoning` have perfect recorded 32B
  component metrics in the audited artifacts, so their exact policy ties are
  recorded as unattributed nulls rather than forced into the hypothesis
- `scope_contamination` and the frozen sentinel retain real 32B residual defect
  evidence, but the audit also names exact canonical-id/query-resolution
  mismatch as a policy-facing failure mode that the current component gate does
  not fully capture

### Evidence

- hypothesis commit:
  `aa7219e`
- audit:
  `docs/noisy_policy_mechanism_audit.md`
- compact evidence:
  `data/results/noisy_policy_mechanism_audit_evidence.json`
- rendered traces:
  `data/results/audit_trace_forced_contradiction_default.html`,
  `data/results/audit_trace_scope_contamination_default.html`, and
  `data/results/audit_trace_useful_pending_memory_default.html`

### Open issues / next

- do not retune, rerun, or threshold-sweep Bucket B to rescue null rows
- if null-row work is needed, preregister it as a canonical-id/query-resolution
  or adapter-contract audit
- LongMemEval remains future transfer work and should start only from the
  contradiction-like mechanism that survived the audit

## 2026-05-15 — Phase 4 noisy policy comparison lands Bucket B

### What shipped

- ran the locked Phase 4 noisy policy-comparison primary cell:
  `qwen2.5:32b-instruct-q4_K_M` / `default`
- ran the locked robustness replicate:
  `qwen2.5:32b-instruct-q4_K_M` / `scenario_conditioned`
- recorded `data/results/noisy_policy_comparison_summary.json`, 14
  per-family metrics CSVs, and 14 per-family manifests
- added `docs/noisy_policy_comparison_results.md` with the preregistered
  Bucket B readout, audit trail, countable-family table, ablation attribution,
  replicate check, frozen sentinel table, and frozen oracle-vs-noisy gap table
- updated `docs/benchmark_methodology_draft.md`,
  `docs/predictions_vs_results.md`, and `PROJECT_PLAN.md` so Phase 4 is no
  longer described as unexecuted
- updated `.gitignore` to track the small noisy-comparison summary, metrics,
  and manifests while keeping large per-scenario run JSONs regeneratable

### Why it matters

- the repo now has a completed noisy-mode memory-policy result under the
  same-candidate-stream, same-substrate, component-gated isolation contract
- the result is mixed rather than broadly positive: CQ wins versus Reflection
  on forced contradiction and preference drift only
- the forced-contradiction win is stark because Reflection false-asserts on
  `56/60` noisy held-out scenarios while CQ records `0/60`
- the null rows are themselves informative: scope contamination, useful
  pending memory, memory poisoning, and the frozen sentinel collapse to exact
  primary-metric ties under the current extracted candidate stream
- CQ records no countable directional losses and the replicate contradicts no
  primary win, but frozen sentinel superiority over `Mem0Lite` does not appear
- Bucket B routes follow-up work toward mechanism-local analysis and
  extraction-floor diagnosis instead of external transfer or new benchmark
  families

### Evidence

- full pre-run suite:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q`
- primary run:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_noisy_policy_comparison.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --policy-set phase2_5`
- robustness replicate:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_noisy_policy_comparison.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile scenario_conditioned --include-frozen-sentinel --policy-set phase2_5`
- summary:
  `data/results/noisy_policy_comparison_summary.json`
- primary bucket:
  Bucket B; CQ wins versus Reflection on `forced_contradiction`
  (`+0.93`, LCB `+0.88`) and `preference_drift` (`+0.13`, LCB `+0.07`)
- convergence rows:
  `scope_contamination`, `useful_pending_memory`, `memory_poisoning`, and all
  frozen sentinel primary metrics have exact `+0.00` CQ-vs-comparator deltas
- adapter audit:
  14 manifests, 726 candidate-stream rows, max scenario adapter drop rate
  `0.00`

### Open issues / next

- write a focused Bucket B follow-up plan around forced contradiction and
  preference drift
- inspect noisy failure examples and frozen oracle-vs-noisy gaps for the tied
  countable rows before proposing any new mechanism work or treating the nulls
  as policy-level negatives
- keep `CQDatedContestation`, Bucket C abstention, and transfer benchmarks out
  of scope until separately preregistered

## 2026-05-14 — Noisy policy-comparison review hardening

### What shipped

- corrected the locked noisy preregistration metric name from
  `scope_leakage_rate` to the actual runner field, `leakage_rate`
- added an adapter drop-rate abort condition with a preregistered `0.05`
  ceiling, backed by per-scenario input/drop counts in the candidate-stream
  audit and manifests
- made the noisy comparison summary emit the promised six-family x six-metric
  descriptive grid with paired-bootstrap LCB/UCB rows
- moved the noisy runner off dynamic imports of the component-gate script by
  adding reusable gate-runtime helpers under `cq/eval/`
- made candidate-stream hash audits self-evidencing by recording the computed
  `candidate_stream_hash_mismatches` list
- added focused tests for bucket aggregation, component-gate rechecks, adapter
  drop aborts, manifest shape, and descriptive-grid output

### Why it matters

- a policy win can no longer mask substantial adapter-level extraction loss
  after the component gate passes
- the readout contract now matches the planned descriptive evidence surface
- external reviewers see the same metric identifiers in the preregistration,
  code, and artifacts

### Evidence

- focused tests:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_extracted_candidate_runner tests.test_noisy_policy_comparison_runner -q`

### Open issues / next

- run the default Phase 4 noisy policy-comparison cell from a clean worktree
- run the `scenario_conditioned` robustness replicate and write the
  preregistered results readout

## 2026-05-14 — Phase 4 noisy policy-comparison path locked and staged

### What shipped

- rewrote `docs/noisy_policy_comparison_preregistration.md` from stub to a
  locked Phase 4 contract with:
  - explicit six-family held-out denominator plus frozen sentinel
  - primary/replicate schema-profile rules
  - sign-normalized metric gates and bucket precedence
  - numeric primary-metric predictions
  - the event-source proxy carve-out for noisy false corroboration
- added `cq/eval/extracted_candidate_runner.py`, implementing the locked
  `CandidateComponentPrediction` to `CandidateUpdate` adapter
- pinned the adapter SHA in `docs/noisy_policy_comparison_adapter_pin.json`
- extended `cq/eval/runner.py` with `--mode extracted`
- added `scripts/run_noisy_policy_comparison.py` for the preregistered default
  and `scenario_conditioned` policy-comparison cells
- added focused fairness regression coverage for stream hashes, adapter
  determinism, scenario-error propagation, substrate isolation, digest/pin
  provenance, shared `MemoryStore` class, and corroboration round-trip

### Why it matters

- the comparison can now use cached 32B extracted candidates without giving CQ
  richer inputs or a private storage substrate
- same-stream hashes are recorded per scenario, making the key fairness
  invariant auditable from artifacts
- no policy scoring has been run yet; the script intentionally aborts on dirty
  pre-run state, so the actual noisy policy result must happen after this patch
  is committed

### Evidence

- focused adapter tests:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_extracted_candidate_runner -q`
- full suite:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover -s tests -p 'test_*.py' -q`
- syntax check:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile cq/eval/extracted_candidate_runner.py scripts/run_noisy_policy_comparison.py cq/eval/runner.py`
- dry-run preflight for both 32B schema profiles:
  `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_noisy_policy_comparison.py --dry-run --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --policy-set phase2_5`
  and the same command with `--schema-profile scenario_conditioned`

### Open issues / next

- commit this preregistration/adapter-pin implementation
- run the default Phase 4 noisy policy-comparison cell from a clean worktree
- run the `scenario_conditioned` robustness replicate and write the
  preregistered results readout

## 2026-05-14 — Local unlock probe reaches Bucket A on both 32B cells

### What shipped

- ran the preregistered 7B anchor from
  `docs/local_unlock_probe_preregistration.md`
- ran both 32B primary unlock cells after the anchor reproduced: `default` and
  `scenario_conditioned`
- left the Bucket C cross-family abstention assay unimplemented because the
  32B cells took the preregistered Bucket A branch
- opened `docs/noisy_policy_comparison_preregistration.md` as the next required
  work item before any extracted-candidate CQ-vs-Reflection-vs-`Mem0Lite`
  policy comparison
- updated `PROJECT_PLAN.md` and `docs/benchmark_methodology_draft.md` so the
  repo no longer lists the 7B anchor or 32B unlock cells as future work

### Why it matters

- the 7B anchor reproduced the locked gate baseline exactly, so the 32B cells
  were allowed to run under the preregistered contract
- both 32B primary cells cleared every component gate, which means the local
  unlock probe is Bucket A rather than Bucket C
- Bucket A is not a policy result; it only permits a separately preregistered
  noisy policy comparison

### Evidence

- 7B anchor:
  - summary:
    `data/results/component_gate_decision_qwen2_5_7b-instruct-q4_K_M_default_summary.json`
  - manifest:
    `data/results/component_gate_decision_qwen2_5_7b-instruct-q4_K_M_default_manifest.json`
  - locked-count checks:
    `primary_scenario_error_count=45`,
    `primary_observed_gate_failure_count=8`,
    `aggregate_observed_gate_failure_count=0`,
    `aggregate_ci_gate_failure_count=0`,
    `frozen_sentinel_observed_gate_failure_count=3`,
    `policy_comparison_unlocked=false`
- 32B default:
  - summary:
    `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_summary.json`
  - manifest:
    `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_manifest.json`
  - unlock checks:
    `primary_scenario_error_count=0`,
    `primary_observed_gate_failure_count=0`,
    `aggregate_observed_gate_failure_count=0`,
    `aggregate_ci_gate_failure_count=0`,
    `frozen_sentinel_observed_gate_failure_count=0`,
    `policy_comparison_unlocked=true`
- 32B scenario-conditioned:
  - summary:
    `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_scenario_conditioned_summary.json`
  - manifest:
    `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_scenario_conditioned_manifest.json`
  - unlock checks:
    `primary_scenario_error_count=0`,
    `primary_observed_gate_failure_count=0`,
    `aggregate_observed_gate_failure_count=0`,
    `aggregate_ci_gate_failure_count=0`,
    `frozen_sentinel_observed_gate_failure_count=0`,
    `policy_comparison_unlocked=true`

### Open issues / next

- write and lock the noisy policy-comparison preregistration before any
  extracted-candidate policy run
- do not implement the Bucket C abstention assay unless a future preregistered
  result actually lands in Bucket C

## 2026-05-13 — Local unlock probe preregistered and runner parameterized

### What shipped

- parameterized `scripts/run_component_gate_decision.py` so the primary gate
  model can be either `qwen2.5:7b-instruct-q4_K_M` or
  `qwen2.5:32b-instruct-q4_K_M`
- made schema profile a required runner-level argument (`default` or
  `scenario_conditioned`) and included it in row artifact names, summaries, and
  cache checks
- added preregistered Ollama digest verification before scoring, with abort
  reports on digest mismatch and per-cell summary manifests recording digest,
  server version, prompt SHA, schema profile, pre-run git status, command, and
  summary SHA
- renamed gate stop reports from `component_gate_decision_phase_a_stop_*` to
  `component_gate_decision_stop_*` because stop conditions now include anchor
  and digest failures, not only Phase A
- added `docs/local_unlock_probe_preregistration.md` and tightened
  `docs/benchmark_methodology_draft.md` around the aggregate/per-family/frozen
  sentinel gate contribution, related-work positioning, and arXiv technical
  report target
- follow-up hardening after review added primary-model determinism replay,
  automated 7B anchor-count enforcement before 32B scoring, and model-digest
  cache provenance checks
- second review hardening pass made 32B scoring abort when the required 7B
  anchor summary was produced under a different Ollama server version than the
  live probe backend

### Why it matters

- 32B can now be tested as an actual primary unlock cell rather than only a
  descriptive headroom row
- schema-profile execution is explicit and auditable instead of hidden in the
  model command string
- the preregistration keeps the next noisy-mode step bounded: Bucket A opens a
  separate noisy policy-comparison preregistration, while Bucket C strengthens
  the gate-methodology result without retiring the oracle-only objection

### Evidence

- focused tests:
  - `python3 -m unittest tests.test_component_gate_decision -q`
- dry-run preview:
  - `python3 scripts/run_component_gate_decision.py --dry-run --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile scenario_conditioned --include-frozen-sentinel`
- syntax check:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile scripts/run_component_gate_decision.py tests/test_component_gate_decision.py`

### Open issues / next

- no 32B primary scoring was run in this change
- next, run the preregistered 7B anchor on a clean worktree, then run the two
  32B primary schema-profile cells only if the anchor reproduces exact locked
  counts

## 2026-05-13 — Integrated benchmark/methodology draft added

### What shipped

- added `docs/benchmark_methodology_draft.md`, consolidating the current
  shareable contribution across:
  - Phase 2.5 frozen oracle results
  - adversarial upstream-noise Bucket D readout
  - Phase 2.6 full-support abstention-calibration assay
  - component-gate failure taxonomy and follow-up decomposition
- updated `PROJECT_PLAN.md` Phase 6 framing to point at the draft

### Why it matters

- the project now has a single in-repo methodology draft that can be reviewed
  before any Phase 4 work resumes
- the draft keeps the contribution bounded as benchmark, preregistration/gate
  methodology, and failure taxonomy rather than noisy-mode policy superiority
- `evidence_conflict_spectrum` is explicitly framed as a designed internal
  mechanism assay, not external transfer evidence

### Evidence

- source docs cited by the draft:
  - `docs/predictions_vs_results.md`
  - `docs/adversarial_upstream_noise_results.md`
  - `docs/abstention_quality_results.md`
  - `docs/component_gate_failure_taxonomy.md`
  - `docs/component_gate_followup_benchmark_memo.md`

### Open issues / next

- review the draft for publication style and target-audience fit
- keep Phase 4 on hold while `policy_comparison_unlocked=false`
- handle `CQDatedContestation` only as a separate optional follow-up

## 2026-05-13 — Phase 2.6 abstention-calibration sweeps recorded

### What shipped

- ran the preregistered `evidence_conflict_spectrum` mixed and held-out oracle
  sweeps with `--policy-set phase2_5 --scenarios 600`
- committed the small durable artifact set:
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed_metrics.csv`
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_mixed_manifest.json`
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout_metrics.csv`
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_oracle_phase2_5_heldout_manifest.json`
  - `data/results/abstention/evidence_conflict_spectrum_oracle_phase2_5_mixed_abstention.json`
  - `data/results/abstention/evidence_conflict_spectrum_oracle_phase2_5_heldout_abstention.json`
- wrote `docs/abstention_quality_results.md` from committed CSV, manifest, and
  replay artifacts only

### Why it matters

- the Phase 2.6 readout lands in **full support**: both mixed and held-out pass
  `conflict_moderate` useful abstention, `conflict_witness` useful abstention,
  and the single harmful bucket over `zero`, `mild`, and `polluted`
- this strengthens the witness-conflict finding into a broader oracle-only
  abstention-calibration axis under the designed mechanism assay
- the result remains separated from noisy-mode claims; Phase 3 stays locked and
  Phase 4 remains on hold

### Evidence

- primary CQ-vs-`Mem0Lite` gates on both splits:
  - `conflict_moderate`: delta `+1.00`, one-sided 95% LCB `+1.00`
  - `conflict_witness`: delta `+1.00`, one-sided 95% LCB `+1.00`
  - harmful bucket: delta `+0.00`, one-sided 95% UCB `+0.00`
- large JSON manifests verified against local SHA256 before the JSONs were left
  untracked:
  - mixed JSON: `182838865` bytes
  - held-out JSON: `182869137` bytes

### Open issues / next

- fold the adversarial-upstream-noise result, the full-support abstention
  readout, and the component-gate methodology into
  `docs/benchmark_methodology_draft.md`

## 2026-05-13 — Phase 2.6 artifact policy locked before sweeps

### What shipped

- added a prospective large-artifact policy: small headline artifacts stay in
  git, while new per-scenario sweep JSONs over about `5 MB` are recorded through
  SHA256 manifests and treated as regeneratable unless an actual archive URI is
  present
- added the stdlib-only manifest helper planned for Phase 2.6 sweep artifacts
- extended abstention replay pairwise comparisons to include the four named CQ
  ablations when present, preserving the preregistered secondary table
- amended the Phase 2.6 preregistration with the artifact policy, replay
  extension, and a top-to-bottom outcome precedence list before running the
  full `evidence_conflict_spectrum` sweeps

### Why it matters

- the full sweeps can proceed without forcing large per-scenario JSONs into git
  while still leaving a verifiable SHA256 record and exact regeneration command
- secondary ablation claims in the abstention readout now have a replay-artifact
  source rather than requiring post-hoc hand derivation
- outcome buckets are ordered before any full-sweep numbers are visible, so the
  results doc can apply the preregistration mechanically

### Evidence

- focused pre-sweep bundle:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_abstention tests.test_evidence_conflict_spectrum tests.test_runner_policy_sets tests.test_bootstrap tests.test_metrics tests.test_adversarial_upstream_noise tests.test_component_eval tests.test_local_extractor tests.test_frozen_preregistration tests.test_artifact_manifest -q`
- dry-run replay preflight:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_abstention_replay.py --dry-run`
- ignore-rule checks:
  - spectrum sweep JSONs remain ignored
  - spectrum metrics/manifests and abstention replay outputs are explicitly
    unignored and trackable
  - old root-level generated metrics remain ignored

### Open issues / next

- commit this pre-sweep lock before running the mixed and held-out
  `evidence_conflict_spectrum` sweeps

## 2026-05-13 — Abstention-calibration benchmark implementation staged

### What shipped

- added the oracle-only `evidence_conflict_spectrum` family for the Phase 2.6
  abstention-calibration benchmark
- added denominator-aware abstention replay/scoring, including primary
  CQ-vs-`Mem0Lite` useful-mechanism rows and harmful-bucket comparison rows
- added structure-summary and CQ-vs-`Mem0Lite` non-degeneracy probe scripts
- hardened the preregistration contract and replay plumbing after review:
  generator-owned mechanism-diverse abstention intents now fail fast for new
  templates, witness gets the same structure-variance check as the load-bearing
  mechanisms, and runner artifacts warn when primary abstention comparisons
  cannot be computed because `Mem0Lite` is absent
- wrote the Phase 2.6 preregistration in
  `docs/abstention_quality_preregistration.md`
- generated pre-run artifacts:
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_structure_mixed.json`
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_structure_heldout.json`
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_nondegeneracy_mixed.json`
  - `data/results/evidence_conflict_spectrum/evidence_conflict_spectrum_nondegeneracy_heldout.json`
- replayed recorded abstention metrics into `data/results/abstention/`

### Why it matters

- the witness-conflict finding is now isolated as a stricter abstention-axis
  test rather than being folded into generic answer correctness
- the primary gate requires CQ to win both abstain-required mechanisms and stay
  non-inferior on commit-required mechanisms, so over-abstention cannot pass as
  calibration
- the non-degeneracy probe checks that `conflict_moderate` and
  `conflict_witness` actually exercise different CQ and `Mem0Lite` actions
  before the full sweeps run

### Evidence

- focused tests:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_abstention tests.test_evidence_conflict_spectrum tests.test_runner_policy_sets -q`
- broader verification:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_abstention tests.test_evidence_conflict_spectrum tests.test_runner_policy_sets tests.test_bootstrap tests.test_metrics tests.test_adversarial_upstream_noise tests.test_component_eval tests.test_local_extractor -q`
- review-hardening verification:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_abstention tests.test_evidence_conflict_spectrum tests.test_runner_policy_sets tests.test_bootstrap tests.test_metrics tests.test_adversarial_upstream_noise tests.test_component_eval tests.test_local_extractor tests.test_frozen_preregistration -q`
- dry-run replay preflight:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_abstention_replay.py --dry-run`
- pre-run structure/probe artifacts listed above

### Open issues / next

- commit the Phase 2.6 preregistration and pre-run artifacts before running the
  full mixed/held-out `evidence_conflict_spectrum` sweeps
- after sweeps, write `docs/abstention_quality_results.md` from saved artifacts
  only

## 2026-05-12 — Adversarial upstream-noise headline runs recorded

### What shipped

- ran the three preregistered headline commands for the oracle-only
  `adversarial_upstream_noise` family:
  - default policy set, `mixed`
  - `phase2_5` policy set, `mixed`
  - `phase2_5` policy set, `heldout`
- regenerated a tracked artifact set under `data/results/adversarial_upstream_noise/`
  so the saved JSON and CSV files include the persisted pairwise bootstrap
  comparison rows required by the preregistered reporting contract
- added `docs/adversarial_upstream_noise_results.md` with the preregistered
  bucket readout, per-mechanism CQ-versus-Reflection deltas and lower bounds,
  ablation attribution labels, held-out direction check, and Mem0 partial
  baseline sub-table
- added `docs/adversarial_upstream_noise_dated_followup_preregistration.md`
  because the preregistered Bucket D surprise-lane trigger fired
- added `docs/preregistered_memory_governance_evaluation_template.md` as the
  reusable methodology artifact for future benchmark families

### Why it matters

- the policy comparison has now moved from preregistration-only to recorded
  empirical evidence at the correct locus of noise: adversarial upstream
  candidate streams with extraction held constant
- CQ clears the mixed win rule on four of five mechanisms and loses only
  `temporal_skew`, exactly the preregistered surprise lane
- because the four dedicated component lanes still clear, the correct read is
  not a generic "3+ wins" headline but the stronger Bucket D mechanism story:
  CQ works on the named lanes and has a dated-evidence weakness
- the held-out `_v2` rows do not reverse any mechanism direction, so the
  robustness split supports the same story
- the methodology contribution is now citable independently of whether the
  follow-up fix succeeds

### Evidence

- focused pre-flight bundle:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_adversarial_upstream_noise tests.test_bootstrap tests.test_cq_ablations tests.test_runner_policy_sets tests.test_metrics -q`
- tracked artifacts:
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_default_mixed.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_default_mixed_metrics.csv`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed_metrics.csv`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout.json`
  - `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout_metrics.csv`
- mixed `phase2_5` CQ-versus-Reflection mechanism deltas with one-sided `95%`
  lower bounds:
  - `adversarial_retraction_v1`: `+1.00`, `+1.00`
  - `adversarial_witness_conflict_v1`: `+1.00`, `+1.00`
  - `adversarial_temporal_skew_v1`: `-1.00`, `-1.00`
  - `adversarial_scope_narrowing_v1`: `+1.00`, `+1.00`
  - `adversarial_pending_competition_v1`: `+1.00`, `+1.00`
- held-out direction check:
  - no mechanism reverses direction between `mixed` and `heldout`

### Open issues / next

- commit the tracked headline artifact set and result-side docs together
- implement `CQDatedContestation` only under the new dated follow-up
  preregistration; do not retrofit the original `phase2_5` headline result
- fold the result doc, methodology template, and later dated follow-up into the
  integrated benchmark/methodology draft

## 2026-05-12 — Oracle-only adversarial upstream-noise family added

### What shipped

- added the `adversarial_upstream_noise` oracle family with five adversarial
  mechanisms: `adversarial_retraction`, `adversarial_witness_conflict`,
  `adversarial_temporal_skew`, `adversarial_scope_narrowing`, and
  `adversarial_pending_competition`, each with held-out `_v2` variants
- wired the family through the oracle runner and Phase 2.5 policy set, including
  per-template summaries, CSV propagation of new diagnostics, and failure-example
  extraction via a single `adversarial_probe` phase
- added fixed-seed paired-bootstrap utilities for the preregistered
  mechanism-level CQ-versus-Reflection comparison rule
- split runner family registration from Phase 3 component-eval / local-extractor
  eligibility so the new oracle-only family cannot auto-enroll in the locked
  noisy harness
- added focused regressions for scenario structure, abstention scoring,
  bootstrap determinism, policy-set wiring, component-eval exclusion,
  local-extractor exclusion, and adversarial ablation behavior

### Why it matters

- this restores the policy comparison at the correct locus of noise: adversarial
  upstream candidate streams with extraction held constant at oracle
- the new family exercises all four named CQ ablations directly, giving the
  oracle comparison a mechanism-attribution story instead of only another family
  row
- the temporal-skew lane is explicitly a weakness probe rather than a hidden
  calibration failure, because it now lives in its own preregisterable mechanism
- the locked Phase 3 / Phase 4 path remains unchanged: the new family is
  runner-eligible but not component-eval-eligible and not local-extractor-eligible

### Evidence

- focused test bundle:
  - `python3 -m unittest tests.test_adversarial_upstream_noise tests.test_bootstrap tests.test_runner_policy_sets tests.test_cq_ablations tests.test_metrics tests.test_component_eval tests.test_local_extractor -q`

### Open issues / next

- commit `docs/adversarial_upstream_noise_preregistration.md` before any run
- inspect a tiny dirty sample and then run the `mixed` / `heldout` sweeps at
  counts that deliver `60` scenarios per mechanism
- report per-mechanism CQ-versus-Reflection deltas, bootstrap lower bounds, and
  ablation drops exactly as preregistered

## 2026-05-12 — Schema-rescue follow-up completed and quadrant ruled out

### What shipped

- replaced the rejected `oneOf` scenario-conditioned Ollama schema with a flat
  event-id-enum schema and preserved `schema_profile` through
  `cq.pipeline.local_extractor` aggregation
- committed the follow-up preregistration amendment first, then completed the
  blocker-surface smoke sweep and the full 7B schema-rescue gate run with frozen
  sentinel
- added `docs/component_gate_followup_benchmark_memo.md` to record the follow-up
  readout, the quadrant decision, and the next-step recommendation

### Why it matters

- the 7B schema-rescue path removed all `45` primary scenario errors from the
  locked 7B baseline without introducing preregistered vacuous placeholder
  values on the common blocker surface
- the preregistered common-surface schema-shaped burden fell from `26` in the
  locked 7B baseline to `0` in both the 7B schema-rescue run and the descriptive
  32B default-schema sweep
- the 7B run still stayed gate-locked because measured per-family and
  frozen-sentinel failures remained (`5` primary observed gate failures and `2`
  frozen-sentinel observed gate failures), which localizes the remaining 7B
  problem to semantic extraction quality rather than output-contract breakage
- the descriptive 32B rows clear the same common-surface measured failures, so
  the follow-up now supports a capacity-versus-structure methodology result
- the symmetric `32B + schema` quadrant was not run because both mandatory runs
  already achieved a `100%` reduction in the preregistered common-surface burden

### Evidence

- preregistration amendment commit: `aef1619` (`Amend schema-rescue preregistration`)
- unit tests:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest tests.test_ollama_component_extractor tests.test_local_extractor`
- smoke artifacts:
  - `data/results/schema_smoke/scope_contamination_predictions.json`
  - `data/results/schema_smoke/preference_drift_predictions.json`
  - `data/results/schema_smoke/memory_poisoning_predictions.json`
  - `data/results/schema_smoke/mechanism_diverse_heldout_frozen_predictions.json`
- full 7B schema-rescue command:
  - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py --model-command "python3 scripts/ollama_component_extractor.py --schema-profile scenario_conditioned" --general-prompt-label general_v1_dynamic_schema --include-frozen-sentinel`
- full 7B schema-rescue runtime: `3481852` ms (`58m 02s`)
- summary artifacts:
  - `data/results/component_gate_decision_general_v1_dynamic_schema_summary.json`
  - `data/results/component_gate_decision_general_v1_followup_32b_default_summary.json`
  - `docs/component_gate_followup_benchmark_memo.md`

### Open issues / next

- keep Phase 4 extracted-candidate policy comparisons on hold while
  `policy_comparison_unlocked=false`
- start the integrated benchmark/methodology draft using the publication
  outline, locked-taxonomy note, and follow-up benchmark memo rather than adding
  the combined quadrant
- treat any future benchmark expansion as a separate preregistered
  benchmark-strengthening step, not as a hidden continuation of the completed
  follow-up

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
- the frozen sentinel miss is substantive rather than just held-out spread: the fixed `frozen_preference_drift_001` scenario itself carries the same empty-`scope_key` and missed-contradiction-edge pattern seen in held-out `preference_drift`
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
- completed run output: `Wrote or reused 11 diagnostic rows in data/results`
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
