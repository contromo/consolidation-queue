# Paper Reproducibility Bundle

This directory is the reviewer entry point for the paper in `paper/`.

## Branch And Commit Policy

The release plan allowed either merging `longmemeval-externalization-gate` into
`main` or pinning the paper package to the branch and commit that contain the
cardinality-repair follow-up artifacts and arXiv-readiness edits. The paper
package follows the tag-pinning path so the arXiv source archive, rendered PDF,
and reviewer instructions resolve to the same revision.

The pinned revision is:

- working branch: `paper_revisions`
- source branch: `longmemeval-externalization-gate`
- final pinned tag: [`paper-v3`](https://github.com/contromo/consolidation-queue/tree/paper-v3)

## Verify Artifact Paths

From the repository root:

```bash
sh paper/repro/verify_artifact_paths.sh
```

The script checks every `data/...`, `docs/...`, and `paper/figures/...` path
referenced in the LaTeX source.

Current-code note: the LongMemEval follow-up runner now emits
`policy_set_warning` and per-cell `runtime_candidate_stream_mutation_check`
diagnostics added after the committed follow-up artifacts were generated; these
fields do not change the empirical counts, bucket, or candidate-stream hashes.

## Build The Paper

From the repository root:

```bash
make -C paper
```

This produces `paper/When_Memory_Metrics_Hide_Memory_Policies.pdf` when a
standard LaTeX toolchain is installed.

## Figure Assets

Five conceptual diagrams ship as TikZ source. They are compiled inline by
PDFLaTeX when the paper builds; no separate render step is needed.

- `paper/figures/cq_lifecycle.tex` (CQ pending/durable lifecycle)
- `paper/figures/evidence_ledger_summary.tex` (method-stage diagram)
- `paper/figures/externalization_protocol.tex` (LongMemEval pipeline)
- `paper/figures/pflc_formal_gap.tex` (Proposition 1 worked example)
- `paper/figures/phase_y_cardinality_control.tex` (symmetric swap)

Two matplotlib-rendered visuals ship as output artifacts. Both PNG (200 dpi
for review) and PDF (vector for the final build) are committed.

- `paper/figures/phase4_mechanism_audit.{png,pdf}` (Phase 4 deltas)
- `paper/figures/longmemeval_x4_cells.{png,pdf}` (X.4 sensitivity status)

Regenerate the two visuals from the committed result artifacts:

```bash
python3 paper/repro/render_charts.py
```

The script pulls numbers directly from
`data/results/noisy_policy_comparison_summary.json`,
`data/external/longmemeval/transfer_summary.json`, and
`data/external/longmemeval/transfer_per_case_rows.csv`, so the figures
cannot silently drift from the result documents. Numeric claims should be
checked against the artifact index in `paper/appendices/artifacts.tex`.

## Generated Tables

Two report tables are generated from committed artifacts and checked into the
paper source, so a paper-only build does not need to run these scripts. From the
repository root, regenerate them with:

```bash
python3 scripts/build_cqmulti_per_row_regression_table.py
python3 scripts/compute_all_hit_at_50_random_floor.py
```

The first command reads `data/results/cq_pending_multi_evidence_*_metrics.csv`
and writes `paper/figures/cqmulti_per_row_regression.tex` plus
`data/results/cqmulti_per_row_regression_summary.json`. The second reads
`data/external/longmemeval/transfer_per_case_rows.csv` and writes
`paper/figures/all_hit_random_floor.tex` plus
`data/external/longmemeval/all_hit_random_floor.json`.

## Hosting

The paper source and reproducibility bundle are hosted at the tag
[`paper-v2`](https://github.com/contromo/consolidation-queue/tree/paper-v2)
on this repository. The paper uses the default `article` class; if a target
venue requires a different style, swap it at submission time without
changing the artifact pin.

## Artifact Symlinks

For reviewer convenience, this directory includes symlinks:

- `data -> ../../data`
- `docs -> ../../docs`

They avoid duplicating committed artifacts while keeping the paper bundle's
inputs discoverable from one directory.
