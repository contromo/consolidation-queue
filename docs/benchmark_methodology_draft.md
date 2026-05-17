# Benchmark Methodology Draft

Target format: arXiv technical report first, with a workshop submission as a
follow-up only if the narrative tightens after the noisy policy-comparison
preregistration lands.

## Abstract

This work presents a preregistered fair-policy memory-governance benchmark
together with a component-gated noisy-mode discipline and a Bucket B mechanism
audit. Under the same upstream candidate stream and shared scoped substrate,
contradiction-edge-driven contestation/demotion survives cleanly on
`forced_contradiction` and partially on `preference_drift`; the remaining ties
are unattributed or uninformative under the current noisy stream unless
directly supported by 32B artifact evidence. A path-normalized canonical-id
resolution (CQR) replay repair refused to emit a verdict under a second Bucket
D abort on locked-input non-reproducibility, which strengthens rather than
weakens the replay-discipline claim because the audit refuses methodology-only
fixes when locked inputs cannot be reproduced. A named post-hoc CQ variant
(`CQDatedContestation`) repairs base CQ's dated-evidence failure mode on
`adversarial_temporal_skew` without retrofitting the original `phase2_5`
adversarial headline; it does not clear the preregistered CQ-vs-Reflection
win criterion because Reflection's eager-overwrite already lands the lane at
the correctness ceiling. The shareable contribution is therefore mechanism-
local: a preregistered benchmark plus attribution discipline that exposes
when a memory-governance policy remains scientifically evaluable under shared
noisy inputs, not a claim of broad noisy CQ superiority or a replacement
persistent-agent memory system.

## Draft Scope

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

### Adversarial Upstream-Noise Dated Follow-Up

Source: `docs/adversarial_upstream_noise_dated_followup_results.md`.

Specific cells:

- `followup`, `mixed` (`adversarial_temporal_skew_v1`),
  `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_mixed_metrics.csv`
- `followup`, `heldout` (`adversarial_temporal_skew_v2`),
  `data/results/adversarial_upstream_noise/adversarial_upstream_noise_oracle_followup_heldout_metrics.csv`

Readout:

- Outcome: **partial preregistered success** on both splits.
- Per-policy `answer_correctness` on the `temporal_skew` lane (mixed `v1` /
  heldout `v2`):

  | Policy | `mixed` | `heldout` |
  | --- | ---: | ---: |
  | `reflection_eager_write_lite` | `1.00` | `1.00` |
  | `cq_dated_contestation` | `1.00` | `1.00` |
  | `consolidation_queue_lite` (base) | `0.00` | `0.00` |
  | `mem0_lite` | `0.00` | `0.00` |

- Preregistered primary criterion (`CQDatedContestation` vs
  `ReflectionEagerWriteLite` mechanism win, point-estimate delta `>= 0.10` AND
  one-sided 95% LCB `> 0`): **NOT cleared** — delta is `+0.00` on both splits
  because Reflection's eager-overwrite already lands `correctness=1.00`. The
  fixed-seed paired bootstrap is uninformative on a unanimous `(1, 1)` row
  and is omitted to avoid implying CI precision the data does not support.
- Secondary descriptive criterion (`CQDatedContestation` improves on base
  `ConsolidationQueueLite`): **MET** — delta `+1.00` on both splits.
- Four-mechanism preservation criterion (no direction reversal on
  `retraction`, `witness_conflict`, `scope_narrowing`, `pending_competition`):
  **MET** on both splits, with mechanism-aligned outcome rates
  (`retraction_demotion_rate`, `narrow_scope_override_success_rate`,
  `pending_competition_resolution_rate`) matching base CQ at `1.00`.
- The base-CQ "loss" on `temporal_skew` is mechanically abstention rather than
  stale assertion (`false_assertion_rate=0.00`); `CQDatedContestation` upgrades
  that to a correct answer from the fresher dated evidence.
- `mem0_lite` records `false_assertion_rate=1.00` and
  `stale_evidence_promotion_rate=1.00` on both `temporal_skew` rows — the
  documented Mem0-family weakness on dated contradiction.

Supported claim: a named post-hoc CQ variant repairs base CQ's
dated-evidence failure mode on `temporal_skew` and preserves the four
originally won mechanisms in oracle mode, without retrofitting the original
`phase2_5` adversarial headline. Unsupported claim: that
`CQDatedContestation` clears the preregistered CQ-vs-Reflection win
criterion on this lane, that it produces a noisy-mode repair, that it
transfers to LongMemEval, or that it would repair the Phase 4 null rows.

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
- representative perfect-component null trace:
  `data/results/audit_trace_useful_pending_memory_default.html`
- generator:
  `scripts/generate_noisy_policy_mechanism_audit.py`

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
  the exact policy tie is also consistent with adapter-contract or
  query-resolution failure
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

### Canonical-Id Resolution Audit (Repair Attempt)

Source: `docs/canonical_id_resolution_audit_results.md`.

Specific cells:

- canonical, latest abort:
  `data/results/canonical_id_resolution_audit_stop.json`
- date-suffixed snapshot of first abort (2026-05-15):
  `data/results/canonical_id_resolution_audit_stop_2026-05-15.json`
- date-suffixed snapshot of second abort (2026-05-16):
  `data/results/canonical_id_resolution_audit_stop_2026-05-16.json`
- repair preregistration:
  `docs/canonical_id_resolution_audit_repair_preregistration.md`

Readout:

- The canonical-id/query-resolution (CQR) audit was first preregistered as a
  standalone replay-only follow-up against the Phase 4 null rows. The
  2026-05-15 official replay aborted under **Bucket D** with
  `locked_input_sha_mismatch` on the locked forced-contradiction manifest
  before any CQR metric could be emitted.
- A narrow, repair-only preregistration (`--replay-root`,
  `--equivalence-mode path_normalized`) was added to separate path-sensitive
  run JSON content from stable policy artifacts while preserving stable checks
  for metrics, candidate-stream hashes, adapter identity, model digest,
  prompts, and preregistration locks. The repair did not change prompts,
  thresholds, validators, adapters, policies, or the shared substrate.
- The 2026-05-16 retry from a detached worktree at the locked Phase 4 commit
  `98959788` aborted again under **Bucket D** with
  `locked_run_json_sha_mismatch`. Direct path substitution did not reduce the
  regenerated content to the locked SHA, and the locked run JSON payload is
  not present in any commit, so the strict pre-flight raw-SHA check stops the
  audit before path-normalized comparison can run. The audit recorded this as
  observed evidence rather than causal closure: the residual non-reproducibility
  was not attributed to a single cause among candidate inter-commit code
  changes, runner non-determinism, or upstream artifact drift.
- Per the §4 CQR × writeup posture matrix, a second Bucket D **strengthens**
  the replay-discipline methodology claim: it shows that the replay rule is
  strict enough to refuse a methodology-only repair when the locked inputs
  cannot be reproduced.

Supported claim: the path-normalized CQR audit is the contrastive evidence
that the replay discipline is enforced — under the repair contract, the audit
still refused to emit a verdict and recorded a second Bucket D. Unsupported
claim: any CQR Bucket A/B/C readout, any change to the Phase 4 null-row
attribution beyond what is already recorded in `docs/noisy_policy_mechanism_audit.md`,
or that a third CQR attempt is licensed without first re-establishing a freshly
run Phase 4 baseline with separately archived run-JSON payloads.

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
perfect while exact canonical-id/query-resolution alignment fails. That pattern
is consistent with adapter-contract or query-resolution failure, but remains an
open attribution until a follow-up audit tests it directly.

The central claim for a memory-community writeup is therefore mechanism-local:
same-candidate-stream evaluation can show when policy architecture remains
visible after noisy extraction, and it can also identify when the noisy stream
has stopped exposing the policy distinction. That makes the contribution a
preregistered benchmark plus attribution discipline, not a replacement memory
system or a claim of broad noisy CQ superiority.

The two 2026-05-16 follow-up outcomes sharpen this thesis on either side. The
`CQDatedContestation` follow-up is an oracle-mode, named post-hoc repair of
base CQ's dated-evidence failure mode on `adversarial_temporal_skew`. It
upgrades base CQ from abstention to a correct answer from the fresher dated
evidence on both `mixed` and `heldout` splits and preserves the four
originally won mechanisms, but it does not clear the preregistered
CQ-vs-Reflection win criterion because Reflection's eager-overwrite already
lands the lane at the correctness ceiling. That outcome is honestly a partial
preregistered success: the mechanism the original headline named — base CQ
losing on dated contradiction — is now repaired by a named CQ variant, and
the methodology refuses to manufacture a CQ-vs-Reflection win where the
eager-write baseline already wins by accident-of-mechanism. The follow-up does
not alter the Phase 4 noisy story or imply any LongMemEval transfer. The
canonical-id resolution (CQR) replay repair is the contrastive evidence on the
audit side: the path-normalized repair tightened the equivalence rule to
separate path-sensitive run JSON content from stable policy artifacts, and the
2026-05-16 retry still aborted under a second Bucket D on
`locked_run_json_sha_mismatch`. Under the §4 plan matrix, a second Bucket D
strengthens the replay-discipline claim rather than weakening it: the rule
refused to emit a verdict when locked inputs cannot be reproduced and did so
without loosening any check. The Phase 4 null rows on `useful_pending_memory`
and `memory_poisoning` therefore stay recorded as unattributed under the
mechanism-audit posture; the methodology does not promote them into
canonical-id/query-resolution findings, and any third CQR attempt would
require a freshly run Phase 4 baseline with separately archived run-JSON
payloads (i.e. a new experiment, not a methodology repair).

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
- spectrum-family evidence as external validation
- extractor-floor convergence for `useful_pending_memory` or
  `memory_poisoning` under the current 32B artifacts

The 2026-05-16 `CQDatedContestation` oracle-mode follow-up repairs base CQ's
failure mode on `adversarial_temporal_skew` (correctness `0.00`→`1.00` on both
`mixed` and `heldout`) and preserves the four originally won mechanisms, but
the following claims are explicitly **not** supported:

- that `CQDatedContestation` clears the preregistered CQ-vs-Reflection win
  criterion on the `temporal_skew` lane (both policies land at
  `correctness=1.00`; delta is `+0.00`)
- that `CQDatedContestation` produces a noisy-mode repair on any family
- that `CQDatedContestation` would repair the Phase 4 null rows
- that `CQDatedContestation` transfers to LongMemEval or any external benchmark

The follow-up must not retrofit the original `phase2_5` adversarial headline
result; it lives in its own `followup` policy-set artifacts.

The 2026-05-16 canonical-id resolution (CQR) replay repair aborted under a
second Bucket D. The following claims are explicitly **not** supported:

- any CQR Bucket A/B/C readout from either the 2026-05-15 or 2026-05-16 attempt
- attribution of `useful_pending_memory` or `memory_poisoning` null rows to
  canonical-id/query-resolution failure (the mechanism audit's adapter-contract
  hypothesis remains an open attribution, not a settled cause)
- any loosening of the pre-flight raw-SHA check, the path-leak guard, or any
  other equivalence rule introduced by the repair
- a third CQR attempt without first re-establishing a freshly run Phase 4
  baseline that includes committed (or separately archived) run-JSON payloads;
  any such re-baseline would be a new experiment with its own preregistration,
  not a methodology repair of the original Phase 4 result

## 9. Next Work

1. Treat the Bucket B audit as the writeup anchor: clean survival on forced
   contradiction, partial survival on preference drift, and unattributed nulls
   elsewhere unless directly supported by 32B artifacts.
2. If future work addresses null rows, preregister it as a policy-facing
   adapter-contract audit (or a fresh Phase 4 baseline with archived run-JSON
   payloads), not as a threshold sweep or a third CQR replay attempt against
   the existing locked Phase 4 manifests.
3. The next named follow-on, gated on this spine landing, is the LongMemEval
   feasibility memo (Workstream D of `docs/next_research_plan.md`). It must be
   preregistered as a transfer probe before any policy is executed against it,
   and it should be framed as descriptive future work if the
   same-candidate-stream fairness invariants cannot be preserved. Any transfer
   hypothesis must be based only on the contradiction-like mechanism that
   survived the Bucket B audit.

The current shareable package is therefore a benchmark and methodology draft
with honest oracle-policy results, a clear noisy-mode gate, a completed mixed
noisy policy comparison, a named post-hoc oracle-mode repair of base CQ's
dated-evidence weakness, and a second Bucket D CQR replay abort that the
methodology refuses to wave away — not a completed persistent-agent
memory-system claim.
