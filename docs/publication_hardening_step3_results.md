# Publication-Hardening Step 3 Results

Date: 2026-05-26

## Verdict

Bucket: `B_inconclusive_min_n`.

## Scope

Publication-hardening preregistration Section 5 scopes this fresh archived CQR replay to four families.

| Family | Role |
| --- | --- |
| `useful_pending_memory` | thesis |
| `memory_poisoning` | thesis |
| `false_corroboration` | descriptive |
| `mechanism_diverse_heldout` | descriptive |

## Preconditions

- publication-hardening lock: `05671290ae8ebcc665c915521128c18c48b13be075ace55472b5931874672590`
- CQR audit preregistration lock: `5293b5577616c00a31065ddfe30e7f10c0d196dc458ad4481cb89595e97620f0`
- noisy comparison preregistration lock: `4bd2bbe64a542c6d8479c2c7c4b40b12c3c601fd35256a60b85bd1e30bfa9bff`
- alias function SHA256: `8176c5a93ffbdbfd99d48f73836b954aa27aee4ab08de567ca47ec63d7896de0`
- Ollama backend version: `0.23.1`
- pre-run worktree status: ``
- git commit: `3b611311e18a689924c2a3dcad138d1e21869304`
- skip document: `docs/publication_hardening_step3_precondition_skip.md`

## Fresh Run Summary

| Family | Scenario count | Run JSON | Run JSON SHA256 | Metrics CSV SHA256 |
| --- | ---: | --- | --- | --- |
| `useful_pending_memory` | 60 | `data/runs/noisy_policy_comparison_useful_pending_memory_default.json` | `0f83d886f2785b7d2fce66830c36596efa2282384e19ba6519a22d62a168e865` | `918b653f2f9821cb860d7efeec34235a61db3e68930b501a23b8ed36c0eb64b2` |
| `memory_poisoning` | 60 | `data/runs/noisy_policy_comparison_memory_poisoning_default.json` | `0c7cbec3ca53d7e7dce55a483ebbdf0c0bcbaaa0b4edb1be0a3997874b9611b1` | `23b49a5216319c1645fb8df1131f11cf9fb20b37a10338c066e5ce697de4dcd5` |
| `false_corroboration` | 60 | `data/runs/noisy_policy_comparison_false_corroboration_default.json` | `e1c0c0e3bc9fe0b30f0a70f86bf61aa3077e946348cc8a22ed5adf3bca4d0c98` | `1323b3539bef15dec702a031944c6d636855b39936a9a9f2c8142f43c1cf6e4b` |
| `mechanism_diverse_heldout` | 3 | `data/runs/noisy_policy_comparison_mechanism_diverse_heldout_default.json` | `b425dad4956ccd8caadd03d866dd9886163a37aa8f478af6dbabcd0cd0674f8e` | `bd8514419d083ee71be50da33f0c372675458e842288078ef07a74e4d827aa5a` |

## Per-Family Cross-Tab

| Family | Role | Hits | Misses | P(success given hit) | P(success given miss) | Lift | Alias FPR | Min N | Miss evaluable |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `useful_pending_memory` | thesis | 0 | 60 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | False | True |
| `memory_poisoning` | thesis | 0 | 60 | 0.000000 | 0.600000 | -0.600000 | 0.000000 | False | True |
| `false_corroboration` | descriptive | 0 | 60 | 0.000000 | 1.000000 | -1.000000 | 0.000000 | False | True |
| `mechanism_diverse_heldout` | descriptive | 0 | 4 | 0.000000 | 0.250000 | -0.250000 | 0.000000 | False | True |

## False-Positive Negative Control

- `useful_pending_memory`: alias false-positive rate `0.000000` (`0` / `0` pairs).
- `memory_poisoning`: alias false-positive rate `0.000000` (`0` / `0` pairs).
- `false_corroboration`: alias false-positive rate `0.000000` (`0` / `0` pairs).
- `mechanism_diverse_heldout`: alias false-positive rate `0.000000` (`0` / `0` pairs).

## Outcome

- The cross-tab is not evaluable under the preregistered thesis-family gates.

## Limitation Text

Step 3 did not emit a cross-tab verdict on useful_pending_memory because the alias-CQR hit denominator was below the preregistered minimum of 5 (observed: 0). Prior PFLC null rows for useful_pending_memory are preserved as unattributed.

Step 3 did not emit a cross-tab verdict on memory_poisoning because the alias-CQR hit denominator was below the preregistered minimum of 5 (observed: 0). Prior PFLC null rows for memory_poisoning are preserved as unattributed.

## What This Means For Claim 2

Claim 2 null rows remain unchanged because the Step 3 cross-tab is not evaluable.

## Archival Semantics

The publication-hardening preregistration Section 5 says the replay "must
archive raw component outputs, candidate streams, policy outputs, lookup
handles, answer traces, manifests, and hashes." Per the repository's artifact
policy (see `reproducibility.tex` and `PROJECT_PLAN.md`), large per-scenario
payloads — the noisy-comparison run JSONs, the component-eval predictions, and
the per-family component-eval payloads — are not committed to git; only their
content hashes and accompanying manifests are. Step 3's archival surface is:

- the four noisy-comparison run manifests (committed) referenced from
  `source_run_artifacts.<family>.run_manifest_path` in the Step 3 manifest;
- per-family SHA256 hashes for the run JSON, run manifest, metrics CSV,
  predictions, and component-eval payloads (`source_run_artifacts.<family>.*_sha256`);
- the regeneration metadata (primary model digest, prompt SHA, candidate
  adapter SHA, Ollama server version) copied from one fresh noisy-comparison
  manifest into `regeneration_metadata`;
- the Step 3 summary, family-rows CSV, and this results document, with their
  own hashes recorded in the Step 3 manifest's `artifacts[]` list.

The replay is reproducible from the committed component-gate caches plus the
runner command captured in the Step 3 manifest's `runner_command` field. The
content hashes pin every regeneratable input so any future replay can be
verified byte-for-byte against this archival record without committing the
underlying payloads.

## References

- preregistration: `docs/publication_hardening_preregistration.md`
- skip document: `docs/publication_hardening_step3_precondition_skip.md`
- manifest: `data/runs/publication_hardening_step3_manifest.json`
