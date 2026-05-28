# Publication-Hardening Step 3 Precondition Skip

Date: 2026-05-26

## Verdict

The Step 3 precondition skip is documented under the publication-hardening
preregistration Section 5 carve-out before execution. Step 3 does not make the
broken repair verification green; it substitutes a new canonical record.

## Why The Original CQR Audit Cannot Pass

The two recorded CQR repair attempts both stopped before emitting a CQR
Bucket A/B/C result because the historical locked Phase 4 payloads could not
be byte-reproduced from the current committed artifact graph.

| Date | Equivalence mode | Failing family | SHA check that stopped |
| --- | --- | --- | --- |
| 2026-05-15 | strict SHA | inferred from `data/runs/noisy_policy_comparison_forced_contradiction_default_manifest.json` | locked input manifest SHA mismatch |
| 2026-05-16 | path-normalized | `forced_contradiction` | locked run JSON SHA mismatch |

Stop reports:

- `data/results/canonical_id_resolution_audit_stop_2026-05-15.json`
- `data/results/canonical_id_resolution_audit_stop_2026-05-16.json`

Those reports are preserved as historical evidence. They establish that the
original repair-verification branch cannot pass against the archived 2026-05
locked Phase 4 run JSONs.

## Scope Of Step 3

Step 3 is a fresh archived replay. New run JSONs and manifests become the new
canonical record for the Step 3 cross-tab. It is not a byte-reproduction of
the pre-2026-05 locked artifacts.

Step 3 does not re-run byte-replay against locked Phase 4 JSONs from
2026-05-15/16; it establishes a new archived replay whose manifests become the
auditable source for the cross-tab.

## Bundled-Replay Note

Step 3 intentionally refreshes the full Phase 4 artifact set as a bundled
replay; only the four families named in prereg Section 5 gate Claim 2 - the
two thesis families (`useful_pending_memory`, `memory_poisoning`) plus the
descriptive companion (`false_corroboration`) and the frozen sentinel
`mechanism_diverse_heldout`, also as a descriptive companion.

## Carve-Out Invocation

Publication-hardening preregistration Section 5 says: "the existing CQR repair
verification is green, or the skip is documented before execution."

This document invokes the "skip is documented" branch. The existing CQR repair
verification is not made green and is not retroactively amended.
