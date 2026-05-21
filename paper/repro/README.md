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

Draft vector figures live in `paper/figures/`:

- `pflc_formal_gap.svg`
- `externalization_protocol.svg`
- `phase4_mechanism_audit.svg`
- `longmemeval_x4_cells.svg`
- `phase_y_cardinality_control.svg`
- `evidence_ledger_summary.svg`

High-resolution PNG derivatives are also committed for PDFLaTeX-compatible
builds:

- `pflc_formal_gap.png`
- `externalization_protocol.png`
- `phase4_mechanism_audit.png`
- `longmemeval_x4_cells.png`
- `phase_y_cardinality_control.png`
- `evidence_ledger_summary.png`

The SVG files remain the editable sources. Numeric claims should be checked
against the artifact index in `paper/appendices/artifacts.tex`.

Regenerate the PNGs with any Python environment that has Pillow installed:

```bash
python3 paper/repro/render_figures.py
```

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
