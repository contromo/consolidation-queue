# Benchmark Methodology Draft

This draft consolidates the contribution the repo can defend today: a
preregistered memory-governance benchmark, a gate methodology for noisy-mode
claims, and an inspectable failure taxonomy. It is not a noisy-mode policy
result.

## 1. Framing

The project asks whether staged memory promotion improves reversibility over a
strong immediate-write baseline. The current answer is mode-specific:

- in oracle mode, CQ has narrow policy support over `Mem0Lite` on the frozen
  Phase 2.5 set and a full-support internal abstention-axis result in Phase 2.6
- in adversarial upstream-noise oracle mode, CQ clears four of five mechanisms
  but exposes a named `temporal_skew` weakness
- in noisy local-model mode, the component gate remains locked, so no
  extracted-candidate policy comparison is publishable

Primary sources: `PROJECT_PLAN.md`, `docs/predictions_vs_results.md`,
`docs/adversarial_upstream_noise_results.md`,
`docs/abstention_quality_results.md`, and
`docs/component_gate_followup_benchmark_memo.md`.

## 2. Shared Substrate And Fair Comparison

The load-bearing invariants are the experiment, not implementation details:

- policies compare on the same upstream candidate stream
- CQ and ReflectionEagerWrite share the same storage substrate
- oracle-mode claims and noisy-mode claims stay separate
- noisy-mode claims require component-quality gates first
- saved artifacts and traces remain inspectable

These rules come from `AGENTS.md` and `PROJECT_PLAN.md`. Without them, CQ could
appear to win because it received better inputs, richer storage, or easier
scenarios than the eager baseline.

## 3. Preregistration Discipline

The strongest reusable contribution is the evaluation discipline:

- `docs/preregistered_memory_governance_evaluation_template.md` defines the
  reusable pattern: fixed scope, mechanism rows, win rules, outcome framings,
  ablation attribution, and artifact expectations
- `docs/preregistration.md` locks the Phase 2.5 mechanism-diverse oracle
  predictions before frozen policy execution
- `docs/adversarial_upstream_noise_preregistration.md` locks the adversarial
  upstream-noise mechanism family and surprise-lane framing
- `docs/abstention_quality_preregistration.md` locks the Phase 2.6 abstention
  assay, including the pre-run artifact policy and outcome precedence amendment

The point is not to make positive results inevitable. The point is to make
positive, mixed, and negative results all reportable without changing the
contract after seeing the numbers.

## 4. Phase 2.5 Frozen Oracle Readout

`docs/predictions_vs_results.md` records that all 108 preregistered oracle-mode
deltas matched the observed deltas on the frozen mechanism-diverse sweep.

The policy read is intentionally narrow:

- CQ and `Mem0Lite` tie on aggregate answer correctness and false assertion
- CQ improves aggregate premature promotion by 33 percentage points
- oracle-mode support over `Mem0Lite` is therefore about reduced premature
  durable promotion, not broad answer-quality superiority

This keeps the published-family comparison useful without inflating it beyond
what the frozen artifact supports.

## 5. Adversarial Upstream-Noise Readout

`docs/adversarial_upstream_noise_results.md` lands in Bucket D:

- CQ wins `retraction`, `witness_conflict`, `scope_narrowing`, and
  `pending_competition`
- CQ loses only `temporal_skew`
- held-out does not reverse any mechanism direction
- the unique CQ advantage versus `Mem0Lite`-style baselines is
  witness-conflict abstention

This supports a mechanism-level oracle result at the candidate-stream locus of
noise. It does not support the broad claim that CQ fully governs adversarial
upstream noise, because the dated-evidence weakness is still open.

## 6. Abstention-Calibration Readout

`docs/abstention_quality_results.md` records **full support** for the Phase 2.6
oracle-only abstention axis:

- mixed and held-out pass useful `conflict_moderate`
- mixed and held-out pass useful `conflict_witness`
- mixed and held-out pass the single harmful bucket over `conflict_zero`,
  `conflict_mild`, and `conflict_polluted`

This result sharpens the witness-conflict claim from the adversarial family:
CQ's abstention behavior separates from `Mem0Lite` where the designed evidence
state is genuinely conflicted, without over-abstaining on commit-required rows.

This is a designed mechanism assay, not external validation. It is evidence
that the abstention axis is internally coherent under oracle candidates; it is
not transfer evidence to noisy extraction, LongMemEval, or real user histories.

## 7. Component Gate And Failure Taxonomy

`docs/component_gate_failure_taxonomy.md` and
`docs/component_gate_followup_benchmark_memo.md` explain why Phase 4 remains on
hold:

- the locked 7B `general_v1` gate passed Phase A, determinism, and aggregate
  gates
- unlock still failed because per-family and frozen-sentinel checks caught
  concentrated scenario errors and observed gate failures
- schema-rescue removed primary scenario errors but did not unlock the 7B path
- descriptive 32B rows cleared the selected common-surface measured failures,
  which supports a capacity/schema decomposition rather than a noisy-policy
  claim

The methodology finding is that aggregate gates were insufficient. Per-family
and frozen-sentinel checks prevented a false noisy-mode unlock.

## 8. Limits

The project does not yet show:

- noisy-mode end-to-end CQ superiority
- extracted-candidate policy comparison under the current 7B gate
- LongMemEval or other external benchmark transfer
- real-user long-horizon helpfulness
- learned semantic scope inference
- resolution of the `temporal_skew` weakness
- spectrum-family evidence as external validation

`CQDatedContestation` remains a separately preregistered follow-up. It must not
retrofit the original `phase2_5` adversarial headline result.

## 9. Open Follow-Ups

Next work should stay sequenced:

1. Keep Phase 4 on hold until a component gate explicitly unlocks policy
   comparison.
2. Treat `CQDatedContestation` as an optional, separately preregistered
   dated-evidence repair.
3. Use LongMemEval later as an external transfer check, not as a current claim.
4. Add broader noisy pipeline evidence only after component outputs satisfy the
   preregistered quality gates.

The current shareable package is therefore a benchmark and methodology draft
with honest oracle-policy results, not a completed persistent-agent memory
system claim.
