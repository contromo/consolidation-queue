# Local 32B Unlock Probe Preregistration

Date: 2026-05-13

This preregistration defines one minimal noisy component-gate unlock probe. It
does not run extracted-candidate policy comparisons. It only asks whether the
existing Phase 3 component gate unlocks on the largest dense local `Q4_K_M`
Qwen cell under either supported schema profile.

## Purpose

The methodology draft can already defend a preregistered oracle-policy result
and a noisy-mode gate discipline. Its remaining reviewer-visible gap is that
every policy-comparison row is oracle-mode. This probe either:

- unlocks a separately preregistered noisy policy comparison at 32B, or
- records that the gate blocks noisy-policy claims even at the largest local
  dense `Q4_K_M` cell tested here.

Both outcomes are reportable. Only an unlock supports a future noisy-mode
policy-comparison claim.

## Locked Cell

Primary model tag allowlist:

| Role | Ollama tag | Expected resolved digest |
| --- | --- | --- |
| anchor | `qwen2.5:7b-instruct-q4_K_M` | `sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` |
| probe | `qwen2.5:32b-instruct-q4_K_M` | `sha256:9f13ba1299afea09d9a956fc6a85becc99115a6d596fae201a5487a03bdc4368` |

Prompt:

- `prompts/component_extractor_general_v1.txt`
- locked SHA256: `ca9ec418156b4cc12bcf5457683844f023684bbc5cee2b7460a6c5030a475633`

Schema profiles:

- `default`
- `scenario_conditioned`

Rows:

- primary held-out rows only:
  `generate_scenarios(family, 60, "heldout")`
- frozen sentinel:
  `generate_scenarios("mechanism_diverse_heldout", 3, "frozen")`

Not parameterized:

- template mix
- prompt content
- schema content
- thresholds
- scenario contracts
- per-family checks
- frozen-sentinel checks
- Phase A prompt-regression guard
- determinism replay
- aggregate gate logic

Determinism replay is the fixed six-scenario `forced_contradiction` smoke row,
but the row now uses the runner's primary model tag and schema profile. It does
not rerun every held-out primary row for determinism.

## Runtime Guard

Before scoring, `scripts/run_component_gate_decision.py` must query local
Ollama for:

- server version
- resolved digest for the primary model tag

The run aborts if the observed digest differs from the expected digest above.
The abort report uses the `component_gate_decision_stop_*` filename prefix and
records the expected digest, observed digest, Ollama server version when
available, and exact runner command. Ollama tag syntax is used for generation;
`tag@digest` invocation is not assumed.

The runner-level `--schema-profile` argument owns schema selection. Do not pass
`--schema-profile` inside `--model-command`.

## Anchor

Before any 32B scoring, re-run the 7B anchor:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py --primary-model-tag qwen2.5:7b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --force
```

Compare the output to
`data/results/component_gate_decision_general_v1_summary.json`.

Exact-count tolerance applies if the Ollama server version and resolved digest
match this preregistration:

| Unlock check | Required value |
| --- | ---: |
| `primary_scenario_error_count` | `45` |
| `primary_observed_gate_failure_count` | `8` |
| `aggregate_observed_gate_failure_count` | `0` |
| `aggregate_ci_gate_failure_count` | `0` |
| `frozen_sentinel_observed_gate_failure_count` | `3` |
| `policy_comparison_unlocked` | `false` |

If the anchor fails, abort before any 32B scoring and investigate runtime drift.
Do not silently apply a plus-or-minus tolerance.

The runner enforces this mechanically: the 7B anchor summary is compared
against the locked baseline counts after the anchor run, and 32B scoring aborts
if the expected 7B anchor summary is absent, count-mismatched, or was produced
under a different Ollama server version than the live 32B probe backend.

## Probe Commands

Run the two 32B primary cells only after the anchor passes and the pre-run git
status is clean.

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel --force
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_component_gate_decision.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile scenario_conditioned --include-frozen-sentinel --force
```

Expected summary artifacts:

- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_default_summary.json`
- `data/results/component_gate_decision_qwen2_5_32b-instruct-q4_K_M_scenario_conditioned_summary.json`

Each summary must have a neighboring `*_manifest.json` recording:

- exact primary model tag
- expected and resolved digest
- Ollama server version
- prompt SHA256
- schema profile
- pre-run working tree status
- exact runner command
- summary JSON SHA256

## Outcome Buckets

Decision precedence is A, then C. There is no Bucket B in this scope because
the mixed split is not run.

### Bucket A: 32B Unlocks

At least one schema profile produces:

- `phase_a_passed=true`
- `determinism_passed=true`
- `primary_scenario_error_count=0`
- no aggregate CI-supported gate failures
- no aggregate observed gate failures
- no per-family observed gate failures
- no frozen-sentinel observed gate failures
- `policy_comparison_unlocked=true`

If Bucket A fires, open a new preregistration for the noisy
CQ-vs-Reflection-vs-`Mem0Lite` policy comparison at the passing cell. This
preregistration does not run that comparison.

### Bucket C: 32B Stays Locked

Both schema profiles produce `policy_comparison_unlocked=false`.

Report the result as: at the largest locally feasible dense `Q4_K_M` cell on
this benchmark, prompt, and schema set, the per-family plus frozen-sentinel gate
blocked a noisy-policy claim. This supports the gate methodology. It does not
retire the oracle-only objection.

## Conditional Follow-Up

Additional 8B, 14B, Mixtral, or 70B cells are out of scope. Expand only under a
new preregistration if either:

- a peer reviewer asks for capacity-scaling evidence, or
- the paper makes a capacity-boundary claim that requires those cells.

No automatic ladder follows from Bucket C.
