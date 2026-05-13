# Benchmark Methodology Draft

Target format: arXiv technical report first, with a workshop submission as a
follow-up only if the narrative tightens after the local unlock probe lands.

This draft consolidates the contribution the repo can defend today:

1. a preregistered fair memory-policy benchmark,
2. a component-gated noisy-mode discipline that prevents false policy unlocks,
3. an inspectable failure taxonomy for local extractor limits, and
4. a narrow positive oracle-policy claim around witness-conflict abstention.

It is not yet a noisy-mode policy result.

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
LongMemEval belongs later as a transfer check after a noisy policy comparison
unlocks, not as a current empirical claim.

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

The new `docs/local_unlock_probe_preregistration.md` does not change any oracle
contract. It only preregisters a minimal 32B component-gate unlock probe before
any 32B primary unlock cell is scored.

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
  `clean_durable_displacement_rate`, and `scope_leakage_rate`
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
- `docs/component_gate_failure_taxonomy.md`
- `docs/component_gate_followup_benchmark_memo.md`

Locked 7B default-schema readout:

- Phase A and determinism pass
- aggregate CI and aggregate observed gates pass
- unlock remains false because of `45` primary scenario errors, `8`
  per-family observed failures, and `3` frozen-sentinel observed failures

Follow-up decomposition:

- 7B `scenario_conditioned` schema rescue removes primary scenario errors
  (`45` to `0`) but remains locked with `5` primary observed failures and `2`
  frozen-sentinel observed failures
- descriptive 32B default-schema rows clear the same common-surface measured
  failures, supporting a capacity/schema decomposition rather than a noisy
  policy claim

Supported claim: the gate discipline prevents a false noisy-mode unlock.
Unsupported claim: extracted-candidate CQ policy superiority.

## 6. Local Unlock Probe

The minimal empirical lift is now preregistered in
`docs/local_unlock_probe_preregistration.md`.

It tests `qwen2.5:32b-instruct-q4_K_M` as the primary unlocking model on the
same held-out per-family rows plus frozen sentinel used by the locked 7B
baseline, under both code-level schema profiles: `default` and
`scenario_conditioned`.

The probe has two allowed outcomes:

- Bucket A: 32B unlocks under at least one schema profile, which triggers a new
  preregistration for a noisy CQ-vs-Reflection-vs-`Mem0Lite` policy comparison.
- Bucket C: 32B stays locked under both schema profiles, which strengthens the
  gate-methodology result but does not retire the oracle-only policy objection.

The draft does not wait for this probe. The probe only determines whether the
paper can add a future noisy-policy-comparison section.

## 7. Limits

Current unsupported claims:

- noisy-mode end-to-end CQ superiority
- extracted-candidate policy comparison under the current locked gate
- LongMemEval or other external benchmark transfer
- real-user long-horizon helpfulness
- learned semantic scope inference
- repaired `temporal_skew`
- spectrum-family evidence as external validation

`CQDatedContestation` remains a separately preregistered follow-up. It must not
retrofit the original `phase2_5` adversarial headline result.

## 8. Next Work

1. Run the 7B anchor from `docs/local_unlock_probe_preregistration.md` on a
   clean worktree and abort if exact locked counts do not reproduce.
2. If the anchor passes, run the two 32B primary unlock cells and classify the
   result as Bucket A or Bucket C.
3. Keep Phase 4 policy comparisons on hold unless Bucket A fires and a separate
   noisy-policy preregistration is written.
4. Treat LongMemEval as future transfer work, not a current claim.

The current shareable package is therefore a benchmark and methodology draft
with honest oracle-policy results and a clear noisy-mode gate, not a completed
persistent-agent memory-system claim.
