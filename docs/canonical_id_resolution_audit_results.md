# Canonical-Id Resolution Audit Results

Date: 2026-05-15

Result: **Bucket D - abort**.

The locked CQR audit did not emit CQR metrics, the family CSV, or a valid
non-abort summary. The methodology draft must therefore remain anchored on
`docs/noisy_policy_mechanism_audit.md` and must not promote
`useful_pending_memory` or `memory_poisoning` from unattributed nulls to
canonical-id/query-resolution findings.

## Abort Reason

The official replay command was:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_canonical_id_resolution_audit.py --primary-model-tag qwen2.5:32b-instruct-q4_K_M --schema-profile default --include-frozen-sentinel
```

After local Ollama access was allowed, the run aborted before metric emission:

| Field | Value |
| --- | --- |
| Bucket | `D` |
| Reason | `locked_input_sha_mismatch` |
| Path | `data/runs/noisy_policy_comparison_forced_contradiction_default_manifest.json` |
| Expected SHA256 | `03d9715cae2e34ab639a9c17f638787aff3128ce56cb4eb21846c63c7ee5f8af` |
| Observed SHA256 | `1a2dbd7c1c9e65121f2a2482e57e78c1ca9541de18038ca9da91bd9fcadc76b2` |
| Stop report | `data/results/canonical_id_resolution_audit_stop.json` |

The earlier sandboxed attempt failed before replay because localhost access to
Ollama was blocked:
`model_digest_verification_failed` with `Operation not permitted` for
`http://127.0.0.1:11434`. That was an environment permission failure, not an
audit result.

## Investigation

The first approved replay from current `main` regenerated the forced
contradiction manifest with a different `git_commit` and
`candidate_adapter_sha256` from the locked Phase 4 manifests. This is a real
locked-input mismatch under the preregistered Bucket D rule.

A supplemental detached-worktree check was run at the locked Phase 4 commit
`7583d3cdbb9db84e5875157931df35beb666dd8a`, with only ignored 32B component
prediction/eval artifacts copied in. That check preserved the locked adapter
SHA, candidate-stream hashes, metrics CSV hash, model digest, and clean
worktree status, but still produced a different manifest SHA because the
regenerated run JSON artifact hash differed:

| Check | Expected / committed | Detached-worktree replay |
| --- | ---: | ---: |
| Metrics CSV SHA | `a8aaa7dbbbceef4273c38468acb74ce130c2efc5384ad99ea25016ba82587e1e` | `a8aaa7dbbbceef4273c38468acb74ce130c2efc5384ad99ea25016ba82587e1e` |
| Candidate adapter SHA | `4f1fc0f8f67ea6246268933f14fb0f20b514475b37153b4af0d29a8178c34de9` | `4f1fc0f8f67ea6246268933f14fb0f20b514475b37153b4af0d29a8178c34de9` |
| Run JSON SHA | `342fc97d15c51f315347597a0f278de089e5961a2f7e3f32d06be71147a7f479` | `1ba32e009b1903b94989d4c1ef05d82575499fb40dcd44ce5d016c3992e7cbd9` |
| Manifest SHA | `03d9715cae2e34ab639a9c17f638787aff3128ce56cb4eb21846c63c7ee5f8af` | `552b3c82fcc3073cfe98f6e1457d0bcfbb7d0b78a7d17731b1c0c8015618ec42` |

The root cause of the detached-worktree run JSON drift is path-sensitive
artifact content: the run JSON embeds an absolute `predictions_path`. Replaying
twice from the same detached path produced byte-identical forced-contradiction
run JSONs, but the byte size differed from the committed manifest by the exact
length difference between the original repository path and the detached
worktree path. This explains the locked-worktree run JSON SHA mismatch. The
current-`main` replay adds a separate mismatch source because the live adapter
SHA and `git_commit` differ from the locked Phase 4 manifests.

Under the locked audit rules, either mismatch remains Bucket D rather than a
recoverable metric readout.

## Interpretation Boundary

- No CQR bucket A/B/C claim is available.
- The Phase 4 null rows remain as recorded in
  `docs/noisy_policy_mechanism_audit.md`: unattributed unless directly
  supported by 32B artifact evidence.
- Do not update the methodology draft's Discussion or Limits as if CQR settled
  attribution.
- Any future CQR attempt needs a separately documented path-normalization or
  manifest-normalization fix before rerunning. The repair should normalize or
  exclude absolute `predictions_path` from byte-stability checks while
  preserving stable checks for metrics, candidate-stream hashes, adapter
  identity, model digest, prompts, and preregistration locks. It must not relock
  thresholds, prompts, validators, adapters, policies, or the shared substrate.

## 2026-05-16 Retry Under Path-Normalized Mode

Date: 2026-05-16

Result: **Bucket D — second abort.** Reason: `locked_run_json_sha_mismatch`.

The path-normalized replay repair preregistered in
`docs/canonical_id_resolution_audit_repair_preregistration.md` (added in
PR [#39](https://github.com/contromo/consolidation-queue/pull/39)) was
exercised against the locked Phase 4 commit
`98959788f318e84347216aa8b8b5bd52b6a86e1a` from a detached worktree at that
commit. The audit aborted before CQR metric emission.

### Repaired Command

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 scripts/run_canonical_id_resolution_audit.py \
  --primary-model-tag qwen2.5:32b-instruct-q4_K_M \
  --schema-profile default \
  --include-frozen-sentinel \
  --replay-root <path-at-98959788> \
  --equivalence-mode path_normalized
```

### Stop Report

| Field | Value |
| --- | --- |
| Bucket | `D` |
| Reason | `locked_run_json_sha_mismatch` |
| Family | `forced_contradiction` |
| Manifest | `<replay-root>/data/runs/noisy_policy_comparison_forced_contradiction_default_manifest.json` |
| Path | `data/runs/noisy_policy_comparison_forced_contradiction_default.json` |
| Expected SHA256 | `342fc97d15c51f315347597a0f278de089e5961a2f7e3f32d06be71147a7f479` |
| Observed SHA256 | `fa738ab89084b34440305ccb452046f5e343f1bf618f2152b6833a60edc1fb1c` |
| Stop report path | `data/results/canonical_id_resolution_audit_stop.json` |

### Observed Evidence (Not Causal Closure)

The audit recorded these observations during the retry. Each is stated as
observed evidence; the audit did not establish a single cause for the
non-reproducibility, and the bullets below should be read as a boundary rather
than as a settled explanation.

1. The locked Phase 4 manifest at commit `98959788` records
   `git_commit: 7583d3cdbb9db84e5875157931df35beb666dd8a` and a
   `artifacts[run_json].sha256` of
   `342fc97d15c51f315347597a0f278de089e5961a2f7e3f32d06be71147a7f479`. The
   locked manifest therefore references a run JSON generated at the earlier
   commit `7583d3cd` (prior to "Record portable noisy prediction paths").
2. Regenerating `scripts/run_noisy_policy_comparison.py` at commit `98959788`
   from a detached replay worktree produces a run JSON with SHA
   `fa738ab89084b34440305ccb452046f5e343f1bf618f2152b6833a60edc1fb1c`. A direct
   string replacement of the relative `predictions_path` with the corresponding
   absolute path does not reduce the regenerated content to the locked SHA, so
   the remaining difference is not a single-field path encoding. The cause of
   that residual difference is **not established by this audit attempt**:
   candidate causes include inter-commit code changes between `7583d3cd` and
   `98959788`, runner non-determinism, or upstream artifact drift; the audit
   does not distinguish among them.
3. The locked Phase 4 run JSON content is not present in any commit (the
   `data/runs/*` ignore in `.gitignore` keeps run JSONs out of git). Without a
   separately-committed locked payload, the audit has no path-normalized
   expected to compare the regen output against under the preregistered
   equivalence rule, and the strict pre-flight raw-SHA check therefore stops
   the audit before path-normalized comparison can run.

### Mapping To The Plan §4 CQR Matrix

From the approved execution plan §4 CQR × writeup posture matrix:

> **Bucket D: Second abort.** Preserve the current mechanism-audit posture and
> report the replay boundary explicitly. Under the reframed contribution, a
> second Bucket D actually strengthens the methodology claim because it shows
> the replay discipline is strict enough to refuse a methodology-only repair
> when the locked inputs cannot be reproduced.

The observed outcome matches this row. The repair landed, was exercised under
its own contract, and refused to emit a verdict when the locked inputs could
not be reproduced.

### Interpretation Boundary

- No new CQR Bucket A/B/C claim is available.
- The Phase 4 null rows remain as recorded in
  `docs/noisy_policy_mechanism_audit.md`: unattributed unless directly
  supported by 32B artifact evidence.
- Do not update the methodology draft's Discussion or Limits as if CQR
  settled attribution.
- A third CQR attempt would require either (a) materializing the original
  locked run JSON payloads from a separately archived `7583d3cd` environment,
  or (b) restarting the audit chain from a freshly run Phase 4 baseline at the
  current main commit. Option (b) would be a new experiment with its own
  preregistration, not a methodology repair of the original Phase 4 result.
- Do not loosen the pre-flight raw-SHA check on the run JSON, the path-leak
  guard, or any other equivalence rule introduced by the repair. Those checks
  are working as designed.
