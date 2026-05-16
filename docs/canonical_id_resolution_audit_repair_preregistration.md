# Canonical-Id Resolution Audit Repair Preregistration

Date: 2026-05-15

Status: locked before any repaired replay.

This document preregisters a narrow, methodology-only repair to the official
canonical-id/query-resolution audit (CQR) that aborted on 2026-05-15 under
Bucket D with `reason=locked_input_sha_mismatch`. It does not edit, replace, or
relax the original locked preregistration at
`docs/canonical_id_resolution_audit_preregistration.md`. It is a strict
cross-reference plus a documented equivalence carve-out for path-sensitive
artifact content.

## 1. Cross-Reference And Lock

The original locked preregistration remains the source of truth for scope,
metrics, thesis families, bucket rules, predictions, alias function, locked
input SHAs, and verification commands. Read it first. This repair adds no new
predictions, no new families, no new gates, and no new alias logic.

The locked Phase 4 replay target is the artifact-lock commit whose manifest
SHAs match the original CQR preregistration:

- `98959788f318e84347216aa8b8b5bd52b6a86e1a`

The repair only changes how the CQR runner compares regenerated artifacts
against the committed Phase 4 manifests when the replay is performed in a
detached worktree at that commit with the ignored locked run JSON artifacts
materialized locally. It does not change the locked Phase 4 artifacts
themselves.

## 2. Repair Is Methodology-Only

This repair must not introduce any of the following:

- prompt changes
- schema changes
- threshold changes
- validator changes
- adapter changes
- policy changes
- substrate changes
- alias-function changes
- new predictions
- new families
- new bucket rules
- post-hoc removal of any existing check

If any future need arises that would require one of those changes, it must come
through a separate preregistration update, not through this repair document.

## 3. Repaired Official Command

The repaired official CQR replay command must be invoked from a clean current
repository and against a clean detached worktree checked out at the
artifact-lock commit, with the ignored locked run JSON artifacts present and
matching the committed manifests. The command is exactly:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_canonical_id_resolution_audit.py \
  --primary-model-tag qwen2.5:32b-instruct-q4_K_M \
  --schema-profile default \
  --include-frozen-sentinel \
  --replay-root <path-at-98959788> \
  --equivalence-mode path_normalized
```

All four of these flags are required for the official repaired replay:

- `--include-frozen-sentinel` (already required by the original preregistration)
- `--primary-model-tag qwen2.5:32b-instruct-q4_K_M` (locked Phase 4 cell)
- `--schema-profile default` (locked Phase 4 cell)
- `--replay-root <path-at-98959788>` (non-default; points at a detached
  worktree at the artifact-lock commit)
- `--equivalence-mode path_normalized`

The runner reads replay inputs (run JSON, metrics CSV, manifest, and component
eval artifacts) from the replay root. It still writes CQR outputs (summary,
family CSV, manifest, results doc, stop report) under the current repo.

`--equivalence-mode path_normalized` is rejected with an explicit abort if
`--replay-root` is not set to a non-default value. The repair only applies to
the locked-replay scenario; it must not be used to silently loosen byte-stable
checks for a single-repo replay.

## 4. Abort Conditions

The runner aborts under Bucket D before any CQR metric emission if any of the
following hold:

- The current repository working tree is dirty.
- The replay-root working tree is dirty.
- Any locked-input artifact referenced under
  `<!-- CQR_LOCKED_INPUT_SHAS_START -->` is missing under the replay root.
- Any locked-input SHA does not match its declared value before replay starts.
- Any locked run JSON artifact referenced by a locked manifest is missing
  before replay starts or does not match the locked manifest's raw SHA before
  replay starts.
- A regenerated manifested artifact is missing.
- The newly written replay manifest mismatches the locked manifest on any of
  the stable manifest fields enumerated in Section 5.
- The newly written metrics CSV mismatches the locked metrics CSV SHA.
- The path-normalized run JSON SHA mismatches between the locked and
  regenerated artifacts.
- The regenerated run JSON contains the current repo path string or the
  replay-root path string in any field other than the approved
  path-normalized fields listed in Section 6.
- The locked Phase 4 component-eval artifact for any family is missing or
  drifts on its locked-input SHA.
- The shelled-out `scripts/run_noisy_policy_comparison.py` command exits
  non-zero.

The first matching condition wins. Adapter drift, model digest drift, prompt
SHA drift, schema profile drift, preregistration lock drift, predictions SHA
drift, and adapter-drop count or rate drift each constitute a Bucket D abort
via the stable-field mismatch rule.

## 5. Stable Manifest Fields Compared Exactly

In path-normalized mode the runner still compares these fields between the
locked manifest and the regenerated replay manifest, byte-exact:

- `candidate_stream_sha256` (whole list of per-scenario stream entries,
  including their `adapter_drop_count` and `adapter_drop_rate` values)
- `candidate_adapter_sha256`
- `primary_model_digest`
- `prompt_sha256`
- `schema_profile`
- `preregistration_lock_sha256`
- `predictions_sha256`

These names are the field names that the locked manifests actually use under
`data/runs/noisy_policy_comparison_*_default_manifest.json`. Any drift on any
of these fields aborts Bucket D.

## 6. Approved Path-Normalized Fields

The only approved path-sensitive normalization in this repair is the
**top-level `predictions_path`** field of the regenerated run JSON artifact.
Its raw value is replaced with the fixed placeholder string
`<NORMALIZED_PREDICTIONS_PATH>` before SHA computation, in both the locked and
the regenerated payloads.

No other field is normalized. The runner additionally enforces an explicit
**path-leak guard**: if any field anywhere in the run JSON tree, other than
the approved fields listed here, contains the current repo path string or the
replay-root path string and differs between expected and observed, the audit
aborts with a clear reason. This makes the carve-out auditable.

Any future expansion of this approved set (for example, normalizing
`runner_command`, `git_commit`, or absolute paths inside policy artifacts)
must come through a separate preregistration update. It is not permitted to
add fields to the approved set by code change alone.

## 7. Out Of Scope

This repair does not, and is not allowed to:

- rerun or change the Phase 4 noisy policy comparison outcome
- claim a CQR Bucket A/B/C result on its own; only the repaired official
  replay against the locked Phase 4 commit may emit a non-abort result
- integrate CQR into `cq/memory/*`, `cq/eval/extracted_candidate_runner.py`,
  or `cq/eval/component_eval.py`
- change `MemoryStore` lookup semantics
- alter the alias function or its preregistration lock
- rescue a component threshold or Phase 4 Bucket B gate

## 8. References

- `docs/canonical_id_resolution_audit_preregistration.md`: original locked
  preregistration (do not edit)
- `docs/canonical_id_resolution_audit_results.md`: the 2026-05-15 Bucket D
  abort record
- `scripts/run_canonical_id_resolution_audit.py`: implementation
- `tests/test_canonical_id_resolution_audit.py`: regression coverage for the
  repair
