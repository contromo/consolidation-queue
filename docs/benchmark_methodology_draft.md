# Benchmark Methodology Draft

Target format: arXiv technical report first, with a workshop submission as a
follow-up only if the narrative tightens after the noisy policy-comparison
preregistration lands.

This draft consolidates the contribution the repo can defend today:

1. a preregistered fair memory-policy benchmark,
2. a component-gated noisy-mode discipline that prevents false policy unlocks,
3. an inspectable failure taxonomy for local extractor limits, and
4. a narrow positive oracle-policy claim around witness-conflict abstention,
5. a mixed preregistered noisy policy comparison with mechanism-local support,
6. a mechanism audit that separates attributable survival from unattributed
   noisy nulls.

The 2026-05-15 noisy policy comparison fired Bucket B. That is a completed
noisy-mode policy result, but it is not broad CQ superiority: CQ wins versus
Reflection on forced contradiction and preference drift, ties the other
countable rows, and does not separate from `Mem0Lite` on the frozen sentinel.
The follow-on mechanism audit narrows the claim further: forced contradiction
is the clean survival row; preference drift is partial survival; the remaining
ties should not be promoted into extractor-floor convergence claims unless the
32B artifacts directly support that attribution.

## 1. Contributions

The central methodological contribution is the gate structure:

- aggregate CI-supported gates are necessary but not sufficient
- per-family observed gates catch concentrated family failures
- a frozen mechanism-diverse sentinel catches failures on the exact scenarios
  used for mechanism-generalization claims
- Phase A prompt regression and deterministic replay block unstable extractor
  rows before broader scoring

The locked 7B `general_v1` run is the clearest evidence that the design matters:
`phase_a_passed=true`, `determinism_passed=true`,
`aggregate_ci_gate_failure_count=0`, and
`aggregate_observed_gate_failure_count=0`, but the gate still stayed locked
because it found `45` primary scenario errors, `8` per-family observed failures,
and `3` frozen-sentinel observed failures. An aggregate-only rule would have
unlocked Phase 4 incorrectly.

Primary artifact: `data/results/component_gate_decision_general_v1_summary.json`.
Interpretation note: `docs/component_gate_failure_taxonomy.md`.

## 2. Fair Policy Comparison

The benchmark isolates memory governance rather than extraction advantage:

- policies receive the same upstream candidate stream
- CQ and ReflectionEagerWrite share the same scoped storage substrate
- oracle-mode claims and noisy-mode claims are separated
- noisy-mode policy claims require component-quality gates first
- saved artifacts expose traces, lifecycle events, examples, and manifests

These invariants are load-bearing. Without them, CQ could appear to win because
it received better inputs, richer storage, or easier scenarios than the eager
baseline.

## 3. Related Work Positioning

This work should not be pitched as simply another memory system or another
memory benchmark.

LongMemEval, MemoryAgentBench, and MemBench occupy the external benchmark lane:
they stress long-horizon memory behavior and are useful future transfer checks,
but they do not by themselves enforce this repo's fair same-candidate-stream
policy comparison. Mem0 and A-MEM occupy the memory-system or write-policy
lane: they motivate comparison targets, but the publishable claim here is not
that CQ is a full replacement system.

The lane for this project is narrower and more auditable:
preregistered fair policy comparison plus component-gated noisy-mode discipline.
LongMemEval belongs later as a transfer check only after a Bucket B follow-up
justifies the mechanism-local bridge, not as a current empirical claim.

## 4. Preregistration Discipline

The reusable discipline is spread across four locked documents:

- `docs/preregistered_memory_governance_evaluation_template.md` defines the
  general structure for mechanism rows, win rules, ablation attribution,
  outcome buckets, and artifact expectations.
- `docs/preregistration.md` locks the Phase 2.5 mechanism-diverse oracle
  predictions before frozen policy execution.
- `docs/adversarial_upstream_noise_preregistration.md` locks the adversarial
  upstream-noise family and the surprise-lane framing.
- `docs/abstention_quality_preregistration.md` locks the Phase 2.6 abstention
  assay, including artifact policy and outcome precedence.

The `docs/local_unlock_probe_preregistration.md` contract did not change any
oracle contract. It preregistered a minimal 32B component-gate unlock probe
before any 32B primary unlock cell was scored. Both 32B cells reached Bucket A
on 2026-05-14.

`docs/noisy_policy_comparison_preregistration.md` locked the extracted-candidate
policy comparison before scoring. It fixed the primary `default` cell, the
`scenario_conditioned` robustness replicate, the six-family held-out
denominator, the frozen sentinel metrics, the extracted-candidate adapter
contract, numeric primary-metric predictions, and the event-source proxy
carve-out for noisy false corroboration. The adapter source is separately
pinned in `docs/noisy_policy_comparison_adapter_pin.json`, and
`scripts/run_noisy_policy_comparison.py` executed both locked cells on
2026-05-15.

## 5. Evidence Ledger

### Phase 2.5 Frozen Oracle Sweep

Source: `docs/predictions_vs_results.md`.

Specific cell:

- frozen aggregate, `phase2_5` policy set,
  `data/results/mechanism_diverse_heldout_oracle_frozen_phase2_5_metrics.csv`

Readout:

- all `108` preregistered oracle-mode deltas matched observed deltas
- CQ and `Mem0Lite` tie on aggregate `answer_correctness`,
  `false_assertion_rate`, `poison_promotion_rate`,
  `clean_durable_displacement_rate`, and `leakage_rate`
- CQ improves aggregate `premature_promotion_rate` by `33` percentage points
  versus `Mem0Lite`, driven by
  `false_corroboration_adversarial_mixed_source`

Supported claim: narrow oracle-mode support for staged promotion reducing
premature durable commitment. Unsupported claim: broad answer-quality
superiority over `Mem0Lite`.

### Adversarial Upstream-Noise Oracle Sweep

Source: `docs/adversarial_upstream_noise_results.md`.

Specific cells:

- `phase2_5`, `mixed`, five preregistered mechanisms,
  `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_mixed_metrics.csv`
- `phase2_5`, `heldout`, direction check,
  `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_phase2_5_heldout_metrics.csv`

Readout:

- Bucket D fires: CQ wins `retraction`, `witness_conflict`,
  `scope_narrowing`, and `pending_competition`
- CQ loses only `temporal_skew`
- held-out does not reverse any mechanism direction
- versus `Mem0Lite`, CQ's unique advantage is witness-conflict abstention

Supported claim: CQ has a named narrow advantage on witness conflict and a
named dated-evidence weakness. Unsupported claim: CQ fully governs adversarial
upstream noise.

### Phase 2.6 Abstention Assay

Source: `docs/abstention_quality_results.md`.

Specific cells:

- mixed primary useful `conflict_moderate`: delta `+1.00`, LCB `+1.00`,
  count `120`
- mixed primary useful `conflict_witness`: delta `+1.00`, LCB `+1.00`,
  count `120`
- mixed harmful bucket over `conflict_zero`, `conflict_mild`,
  `conflict_polluted`: delta `+0.00`, UCB `+0.00`
- held-out repeats the same three primary gate outcomes

Supported claim: full support for the designed oracle-only abstention axis.
Unsupported claim: external validation, noisy transfer, or LongMemEval
performance.

### Phase 3 Component Gate

Sources:

- `data/results/component_gate_decision_general_v1_summary.json`
- `data/results/component_gate_decision_qwen2_5_7b-instruct-q4_K_M_default_summary.json`
- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_summary.json`
- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_scenario_conditioned_summary.json`
- `docs/component_gate_failure_taxonomy.md`
- `docs/component_gate_followup_benchmark_memo.md`

Locked 7B default-schema readout:

- Phase A and determinism pass
- aggregate CI and aggregate observed gates pass
- unlock remains false because of `45` primary scenario errors, `8`
  per-family observed failures, and `3` frozen-sentinel observed failures
- the 2026-05-14 7B anchor is a clean-worktree reproduction of the older
  `general_v1` locked summary under the preregistered primary-model tag, schema
  profile, digest, and Ollama server-version checks

Follow-up decomposition:

- 7B `scenario_conditioned` schema rescue removes primary scenario errors
  (`45` to `0`) but remains locked with `5` primary observed failures and `2`
  frozen-sentinel observed failures
- descriptive 32B default-schema rows clear the same common-surface measured
  failures, supporting a capacity/schema decomposition rather than a noisy
  policy claim
- preregistered 7B anchor rerun on 2026-05-14 reproduced the locked counts
  exactly under the same Ollama server version and preregistered digest
- preregistered 32B default primary cell cleared the gate with `0` primary
  scenario errors, `0` primary observed failures, `0` aggregate observed
  failures, `0` aggregate CI failures, `0` frozen-sentinel observed failures,
  and `policy_comparison_unlocked=true`
- preregistered 32B scenario-conditioned primary cell cleared the same unlock
  checks and also recorded `policy_comparison_unlocked=true`

Supported claim: the gate discipline prevents a false noisy-mode unlock. The
32B local extractor path was eligible for the separately preregistered noisy
policy comparison reported below. Unsupported claim from the gate alone:
extracted-candidate CQ policy superiority.

### Phase 4 Noisy Policy Comparison

Source: `docs/noisy_policy_comparison_results.md`.

Specific cells:

- primary `default` profile:
  `data/results/noisy_policy_comparison_summary.json` and
  `data/results/noisy_policy_comparison_*_default_metrics.csv`
- robustness `scenario_conditioned` profile:
  `data/results/noisy_policy_comparison_*_scenario_conditioned_metrics.csv`
- per-family manifests:
  `data/runs/noisy_policy_comparison_*_manifest.json`

Readout:

- Bucket B fires under the preregistered precedence rules
- CQ wins versus Reflection on `forced_contradiction` with delta `+0.93`,
  LCB `+0.88`, and on `preference_drift` with delta `+0.13`, LCB `+0.07`
- the forced-contradiction headline reflects a stark mechanism split:
  Reflection false-asserts on `56/60` noisy held-out scenarios while CQ records
  `0/60` false assertions through contestation/demotion
- CQ records no directional losses versus Reflection on the five countable
  primary metrics
- `scope_contamination`, `useful_pending_memory`, `memory_poisoning`, and the
  frozen sentinel collapse to exact policy ties on the primary metrics,
  suggesting current-extraction convergence where the noisy candidate stream
  stops exposing policy differences
- CQ is non-inferior to `Mem0Lite` on the frozen sentinel primary metrics, but
  has no frozen superiority row because every CQ-vs-`Mem0Lite` frozen primary
  delta is `+0.00`
- the `scenario_conditioned` replicate contradicts none of the primary wins
- all adapter drop rates are `0.00`, preserving the same-candidate-stream
  fairness surface

Supported claim: same-candidate-stream, same-substrate, component-gated policy
isolation produces mechanism-local noisy support for CQ on forced contradiction
and preference drift. Secondary methodological claim: the null rows expose an
extraction-floor convergence mode that makes some policy comparisons
uninformative under the current noisy stream. Unsupported claim: broad noisy CQ
superiority or noisy separation from `Mem0Lite` on the frozen sentinel.

### Bucket B Mechanism Audit

Source: `docs/noisy_policy_mechanism_audit.md`.

Specific cells:

- compact audit evidence:
  `data/results/noisy_policy_mechanism_audit_evidence.json`
- representative survival trace:
  `data/results/audit_trace_forced_contradiction_default.html`
- representative null/convergence-pressure trace:
  `data/results/audit_trace_scope_contamination_default.html`

Readout:

- `forced_contradiction` is a clean mechanism-survival row: the 32B default
  component artifact has perfect contradiction, scope, claim-type, and
  canonicalization scores, and the noisy ablation identifies
  `cq_no_contestation_demotion` as the carrying component
- `preference_drift` is partial survival: the noisy CQ-vs-Reflection win
  remains, but absolute CQ answer correctness drops by `0.67` from oracle and
  32B artifacts show residual claim-type/scope/canonicalization drift
- `scope_contamination` has real 32B residual defects, including
  canonicalization splits, scope mismatches, and missed contradiction edges, but
  the exact policy tie is also dominated by canonical-id/query-resolution
  mismatch
- `useful_pending_memory` and `memory_poisoning` should be recorded as
  unattributed nulls, not extractor-floor convergence rows, because their 32B
  component artifacts are perfect across the audited dimensions while exact
  policy-query canonical-id alignment is `0/60`
- `false_corroboration` remains descriptive-only because Phase 4 does not
  extract source identity
- the frozen sentinel contains one real 32B defect trace, but the exact policy
  tie is not enough to support broad noisy mechanism-generalization

Supported claim: contradiction-edge-driven contestation/demotion remains
visible under the current 32B noisy stream. Unsupported claim:
scope-aware pending override, source-independence gating, and poisoning defense
survive noisy extraction in this Phase 4 run.

## 6. Discussion

The audit thesis should lead the writeup: the completed Bucket B result is a
contingency map, not a broad noisy-mode CQ win. Contestation/demotion survives
when 32B noisy extraction preserves contradiction edges, with
`forced_contradiction` as the clean row and `preference_drift` as a partial row.
The remaining countable rows and the frozen sentinel should be treated as
current-stream nulls unless a specific 32B artifact supports a stronger
attribution.

This is where the upstream component gate and downstream mechanism audit meet.
The gate prevented a 7B false unlock by catching concentrated per-family and
frozen-sentinel failures that aggregate gates smoothed over. The audit then
prevents the opposite error after the 32B unlock: it stops the paper from
turning every exact tie into an extractor-floor convergence story. In
particular, `useful_pending_memory` and `memory_poisoning` are unattributed
nulls under the current evidence because the audited 32B component artifacts are
perfect while exact canonical-id/query-resolution alignment fails.

The central claim for a memory-community writeup is therefore mechanism-local:
same-candidate-stream evaluation can show when policy architecture remains
visible after noisy extraction, and it can also identify when the noisy stream
has stopped exposing the policy distinction. That makes the contribution a
preregistered benchmark plus attribution discipline, not a replacement memory
system or a claim of broad noisy CQ superiority.

## 7. Local Unlock Probe

The minimal empirical lift was preregistered in
`docs/local_unlock_probe_preregistration.md` and both 32B cells reached Bucket A
on 2026-05-14.

It tests `qwen2.5:32b-instruct-q4_K_M` as the primary unlocking model on the
same held-out per-family rows plus frozen sentinel used by the locked 7B
baseline, under both code-level schema profiles: `default` and
`scenario_conditioned`.

Recorded cells:

- 7B `default` anchor:
  `data/results/component_gate_decision_qwen2_5_7b-instruct-q4_K_M_default_summary.json`
  and matching manifest. It matched the locked baseline exactly.
- 32B `default` primary:
  `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_summary.json`
  and matching manifest. It unlocked the component gate and triggered Bucket A.
- 32B `scenario_conditioned` primary:
  `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_scenario_conditioned_summary.json`
  and matching manifest. It also unlocked the component gate.

Bucket A does not itself compare memory policies. It only opens the next
preregistration step for a noisy CQ-vs-Reflection-vs-`Mem0Lite` policy
comparison. The Bucket C cross-family abstention assay remains out of scope for
this branch.

## 8. Limits

Current unsupported claims:

- broad noisy-mode end-to-end CQ superiority
- noisy separation from `Mem0Lite` on the frozen sentinel
- LongMemEval or other external benchmark transfer
- real-user long-horizon helpfulness
- learned semantic scope inference
- repaired `temporal_skew`
- spectrum-family evidence as external validation
- extractor-floor convergence for `useful_pending_memory` or
  `memory_poisoning` under the current 32B artifacts

`CQDatedContestation` remains a separately preregistered follow-up. It must not
retrofit the original `phase2_5` adversarial headline result.

## 9. Next Work

1. Treat the Bucket B audit as the writeup anchor: clean survival on forced
   contradiction, partial survival on preference drift, and unattributed nulls
   elsewhere unless directly supported by 32B artifacts.
2. If future work addresses null rows, preregister it as a policy-facing
   canonical-id/query-resolution or adapter-contract audit, not as a threshold
   sweep that rescues Bucket B.
3. Treat LongMemEval as future transfer work, not a current claim, and base any
   transfer hypothesis only on the contradiction-like mechanism that survived.

The current shareable package is therefore a benchmark and methodology draft
with honest oracle-policy results, a clear noisy-mode gate, and a completed
mixed noisy policy comparison, not a completed persistent-agent memory-system
claim.
