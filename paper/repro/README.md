# Paper Reproducibility Bundle

This directory is the reviewer entry point for the draft in `paper/`.

## Branch And Commit Policy

The Phase Z plan allowed either merging `longmemeval-externalization-gate` into
`main` or pinning the paper package to the branch and commit that contain the
Phase Y artifacts. A fast-forward merge into `main` was not possible from this
worktree because the branches had diverged after the earlier LongMemEval merge.

This draft therefore follows the accepted pinning path:

- working branch: `paper/ship-paper-draft`
- source branch: `longmemeval-externalization-gate`
- source branch head when drafting began: `cf949f9`

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

## Build The Draft

From the repository root:

```bash
make -C paper
```

This produces `paper/main.pdf` when a standard LaTeX toolchain is installed.

## Figure Assets

Four conceptual diagrams ship as TikZ source. They are compiled inline by
PDFLaTeX when the paper builds; no separate render step is needed.

- `paper/figures/evidence_ledger_summary.tex` (claim dependency DAG)
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

## Venue And Hosting Placeholders

The current draft uses the default `article` class for arXiv technical-report
iteration. Before submission, replace it with the chosen venue style if needed
and set the final reproducibility URL in the abstract/front matter. The
expected hosting target is one of:

- GitHub release attached to a tagged repo state
- Zenodo DOI
- both GitHub release and Zenodo DOI

## Artifact Symlinks

For reviewer convenience, this directory includes symlinks:

- `data -> ../../data`
- `docs -> ../../docs`

They avoid duplicating committed artifacts while keeping the paper bundle's
inputs discoverable from one directory.
