"""Replacement matplotlib figures for the quantitative/status visuals.

Replaces ``longmemeval_x4_cells.png`` with a compact sensitivity-status
matrix, and ``phase4_mechanism_audit.png`` with a quantitative audit chart.
Every number is read from a committed artifact so the figures cannot drift
from the result documents.

Run from the repo root::

    python3 paper/repro/render_charts.py

Requires ``matplotlib``. The five conceptual diagrams (CQ lifecycle, evidence
ledger, externalization protocol, PFLC formal gap, phase Y cardinality control)
ship as TikZ source compiled inline by PDFLaTeX; see the matching ``.tex``
files under ``paper/figures/``.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path

_mpl_config = Path(tempfile.gettempdir()) / "cq-paper-matplotlib"
_mpl_config.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_config))

import matplotlib

matplotlib.use("Agg")  # headless backend: no display required

import matplotlib.pyplot as plt  # noqa: E402  (must follow backend selection)
from matplotlib.patches import Patch, Rectangle  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "paper" / "figures"


# ---------------------------------------------------------------------------
# Figure 5: LongMemEval X.4 sensitivity status
# ---------------------------------------------------------------------------

def _load_x4_pairwise() -> dict[str, dict[str, float]]:
    """Return per-cell CQ-vs-Reflection deltas for both X.4 PFLC metrics.

    Source: ``data/external/longmemeval/transfer_summary.json`` for
    ``all_hit_at_50``, and per-policy ``cell_summaries`` rows for
    ``any_hit_at_50`` (which is always 0.0 because both policies tie at 1.0
    on that metric in every cell).
    """
    summary_path = ROOT / "data/external/longmemeval/transfer_summary.json"
    with open(summary_path) as handle:
        summary = json.load(handle)

    all_hit: dict[str, float] = {}
    for cell, comparisons in summary["pairwise_comparisons"].items():
        cq_vs_ref = comparisons["cq_vs_reflection"]
        assert cq_vs_ref["metric_name"] == "all_hit_at_50"
        all_hit[cell] = float(cq_vs_ref["point_estimate_delta"])

    # any_hit_at_50 is implicit from the cell summaries: every CQ case scores
    # 1.0 and every Reflection case scores 1.0, so the delta is 0.0. Verify by
    # reading per-case rows so the figure cannot lie.
    rows_path = ROOT / "data/external/longmemeval/transfer_per_case_rows.csv"
    any_hit: dict[str, float] = {}
    cq_any: dict[str, list[int]] = {}
    ref_any: dict[str, list[int]] = {}
    with open(rows_path) as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cell = row["cell_id"]
            value = 1 if row["any_hit_at_50"] == "True" else 0
            if row["policy_name"] == "consolidation_queue_lite":
                cq_any.setdefault(cell, []).append(value)
            elif row["policy_name"] == "reflection_eager_write_lite":
                ref_any.setdefault(cell, []).append(value)
    for cell in cq_any:
        cq_mean = sum(cq_any[cell]) / len(cq_any[cell])
        ref_mean = sum(ref_any[cell]) / len(ref_any[cell])
        any_hit[cell] = cq_mean - ref_mean

    return {"all_hit_at_50": all_hit, "any_hit_at_50": any_hit}


def _x4_cell_counts() -> dict[str, int]:
    summary_path = ROOT / "data/external/longmemeval/transfer_summary.json"
    with open(summary_path) as handle:
        summary = json.load(handle)
    return {cell["cell_id"]: cell["scenario_count"] for cell in summary["cell_summaries"]}


def render_x4() -> None:
    deltas = _load_x4_pairwise()
    counts = _x4_cell_counts()

    cell_order = ["primary_contract", "path_a_only_denominator", "path_b_only_denominator"]
    metric_order = ["all_hit_at_50", "any_hit_at_50"]
    metric_label = {
        "all_hit_at_50": "all_hit_at_50",
        "any_hit_at_50": "any_hit_at_50",
    }

    fig, ax = plt.subplots(figsize=(8.4, 3.1))
    ax.set_xlim(-1.25, 3.35)
    ax.set_ylim(-0.3, 2.85)
    ax.axis("off")
    ax.set_title(
        "LongMemEval X.4 sensitivity status",
        fontsize=12,
        fontweight="bold",
        loc="left",
    )
    ax.text(
        -1.18,
        2.48,
        "CQ − Reflection delta is invariant across the primary and denominator-sensitivity cells.",
        fontsize=8.5,
        color="#555555",
    )

    cell_label = {
        "primary_contract": "primary_contract",
        "path_a_only_denominator": "path_a_only_\ndenominator",
        "path_b_only_denominator": "path_b_only_\ndenominator",
    }
    for col, cell in enumerate(cell_order):
        ax.text(
            col + 0.5,
            2.03,
            f"{cell_label[cell]}\n(n={counts[cell]})",
            ha="center",
            va="bottom",
            fontsize=8.4,
            fontweight="bold",
        )

    row_y = {"all_hit_at_50": 1.05, "any_hit_at_50": 0.15}
    row_summary = {
        "all_hit_at_50": "stable completeness loss",
        "any_hit_at_50": "stable exposure tie",
    }
    fill_color = {
        "all_hit_at_50": "#f0cdcd",
        "any_hit_at_50": "#d9e8f5",
    }
    edge_color = {
        "all_hit_at_50": "#9d3030",
        "any_hit_at_50": "#3f6f96",
    }
    status_label = {
        "all_hit_at_50": "loss",
        "any_hit_at_50": "tie",
    }

    for metric in metric_order:
        y = row_y[metric]
        ax.text(
            -0.12,
            y + 0.32,
            metric_label[metric],
            ha="right",
            va="center",
            fontsize=9.2,
            fontfamily="monospace",
            fontweight="bold",
        )
        ax.text(
            -0.12,
            y + 0.08,
            "CQ − Reflection",
            ha="right",
            va="center",
            fontsize=8,
            color="#555555",
        )
        for col, cell in enumerate(cell_order):
            value = deltas[metric][cell]
            rect = Rectangle(
                (col + 0.04, y),
                0.92,
                0.62,
                facecolor=fill_color[metric],
                edgecolor=edge_color[metric],
                linewidth=1.1,
            )
            ax.add_patch(rect)
            ax.text(
                col + 0.5,
                y + 0.39,
                f"{value:+.1f}",
                ha="center",
                va="center",
                fontsize=11,
                fontweight="bold",
                color="#222222",
            )
            ax.text(
                col + 0.5,
                y + 0.16,
                status_label[metric],
                ha="center",
                va="center",
                fontsize=8.2,
                color="#444444",
            )
        ax.text(
            3.12,
            y + 0.32,
            row_summary[metric],
            ha="left",
            va="center",
            fontsize=8.8,
            color="#333333",
        )

    ax.plot([0.0, 3.0], [0.92, 0.92], color="#d0d0d0", linewidth=0.8)
    ax.text(
        3.12,
        2.07,
        "interpretation",
        ha="left",
        va="bottom",
        fontsize=8.8,
        fontweight="bold",
    )
    plt.tight_layout()
    fig.savefig(FIGURES / "longmemeval_x4_cells.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIGURES / "longmemeval_x4_cells.pdf", bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5: Phase 4 mechanism audit
# ---------------------------------------------------------------------------

# Attribution labels and colors are sourced from
# docs/noisy_policy_mechanism_audit.md per-family attribution call.
# Three semantic classes: survival (green/gold), null (grey),
# descriptive-only (muted red).
COLOR_SURVIVAL = "#5aa469"
COLOR_PARTIAL = "#d4a93a"
COLOR_NULL = "#9aa0a6"
COLOR_DESCRIPTIVE = "#c08484"

ATTRIBUTION = {
    "forced_contradiction": ("clean survival", COLOR_SURVIVAL),
    "preference_drift": ("partial survival", COLOR_PARTIAL),
    "scope_contamination": ("unattributed null", COLOR_NULL),
    "useful_pending_memory": ("unattributed null", COLOR_NULL),
    "memory_poisoning": ("unattributed null", COLOR_NULL),
    "false_corroboration": ("descriptive-only (source proxy)", COLOR_DESCRIPTIVE),
    "mechanism_diverse_heldout": ("unattributed null", COLOR_NULL),
}

# Per-row notes used as in-figure annotations alongside the legend so the
# reader can tell the grey-bar rows apart at a glance.
ROW_NOTE = {
    "scope_contamination": "32B defects",
    "useful_pending_memory": "PFLC failure",
    "memory_poisoning": "PFLC failure",
    "mechanism_diverse_heldout": "frozen sentinel",
}


def _phase4_rows() -> list[tuple[str, float, float, float]]:
    """Return ``(family, delta, lcb, ucb)`` from the noisy comparison summary.

    Per-family rows are read from ``primary_metric_comparisons``. The frozen
    sentinel aggregate is read from ``frozen_primary_comparisons`` and we
    assert that every CQ-vs-Reflection delta on every frozen primary metric is
    exactly zero (the audit's recorded result), then surface that as a single
    summary row at 0.0 — no value is hard-coded.
    """
    summary_path = ROOT / "data/results/noisy_policy_comparison_summary.json"
    with open(summary_path) as handle:
        summary = json.load(handle)
    schema = summary["schema_profiles"]["default"]
    primary = schema["primary_metric_comparisons"]
    out: list[tuple[str, float, float, float]] = []
    for family in [
        "forced_contradiction",
        "preference_drift",
        "scope_contamination",
        "useful_pending_memory",
        "memory_poisoning",
        "false_corroboration",
    ]:
        row = primary[family]["reflection_eager_write_lite"]
        out.append((
            family,
            float(row["improvement_delta"]),
            float(row["one_sided_95_lcb"]),
            float(row["one_sided_95_ucb"]),
        ))
    # Frozen sentinel: read the actual CQ-vs-Reflection cells and assert the
    # all-zero pattern recorded in docs/noisy_policy_comparison_results.md.
    frozen = schema["frozen_primary_comparisons"]
    frozen_deltas: list[tuple[float, float, float]] = []
    for metric_name, comparators in frozen.items():
        row = comparators["reflection_eager_write_lite"]
        frozen_deltas.append((
            float(row["improvement_delta"]),
            float(row["one_sided_95_lcb"]),
            float(row["one_sided_95_ucb"]),
        ))
    if not all(d == 0.0 and lcb == 0.0 and ucb == 0.0 for d, lcb, ucb in frozen_deltas):
        raise ValueError(
            "Frozen sentinel CQ-vs-Reflection cells are no longer all zero; "
            "the figure assumes the recorded null pattern. Got: "
            + repr(frozen_deltas)
        )
    out.append(("mechanism_diverse_heldout", 0.0, 0.0, 0.0))
    return out


def render_phase4() -> None:
    rows = _phase4_rows()

    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    families = [row[0] for row in rows]
    deltas = [row[1] for row in rows]
    lcbs = [row[2] for row in rows]
    ucbs = [row[3] for row in rows]
    colors = [ATTRIBUTION[fam][1] for fam in families]

    y = list(range(len(families)))
    # Symmetric error around the point estimate; the bounds from the summary are
    # already one-sided 95% intervals so we draw them as-is.
    err_left = [delta - lcb for delta, lcb in zip(deltas, lcbs)]
    err_right = [ucb - delta for delta, ucb in zip(deltas, ucbs)]

    ax.barh(y, deltas, color=colors, edgecolor="black", linewidth=0.6, height=0.62)
    ax.errorbar(
        deltas,
        y,
        xerr=[err_left, err_right],
        fmt="none",
        ecolor="black",
        elinewidth=1.0,
        capsize=3,
    )
    # Draw a small visible chip at x=0 for zero-delta rows so the attribution
    # color (null/grey vs descriptive-only/red) is readable even when the bar
    # has zero width.
    ZERO_CHIP_WIDTH = 0.012
    for yi, delta, fam, color in zip(y, deltas, families, colors):
        if delta < 0.05:
            ax.barh(yi, ZERO_CHIP_WIDTH, color=color, edgecolor="black",
                    linewidth=0.6, height=0.62)
    for yi, delta, ucb, fam in zip(y, deltas, ucbs, families):
        if delta >= 0.05:
            # Place the label past the UCB whisker so it never overlaps the cap.
            ax.text(ucb + 0.02, yi, f"{delta:+.2f}", va="center", ha="left",
                    fontsize=9, fontweight="bold")
        else:
            note = ROW_NOTE.get(fam)
            if note is None and fam == "false_corroboration":
                note = "source proxy"
            text = "+0.00 (tie)" + (f"  —  {note}" if note else "")
            ax.text(ZERO_CHIP_WIDTH + 0.02, yi, text, va="center", ha="left",
                    fontsize=9, color="#555555")

    ax.set_yticks(y)
    ax.set_yticklabels(families, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(-0.05, 1.05)
    ax.set_xlabel("CQ − Reflection delta on primary metric (95% LCB/UCB)", fontsize=10)
    # Short title + subtitle, matching the X.4 chart layout. The single-line
    # form previously overflowed the figure width and rendered as "five boun..."
    ax.set_title(
        "Phase 4 mechanism audit",
        fontsize=12,
        fontweight="bold",
        loc="left",
        pad=22,
    )
    # Subtitle in axes-relative coords so it sits just under the title,
    # independent of the inverted y-axis used for the bar rows.
    ax.text(
        0.0, 1.02,
        "One clean survival, one partial, five bounded/descriptive rows.",
        transform=ax.transAxes,
        fontsize=8.8,
        color="#555555",
        va="bottom",
    )
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(axis="x", linestyle=":", linewidth=0.5, color="#bbbbbb")
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    # Legend keyed to attribution classes used in the paper.
    seen: dict[str, str] = {}
    for fam in families:
        label, color = ATTRIBUTION[fam]
        seen.setdefault(label, color)
    handles = [Patch(facecolor=color, edgecolor="black", linewidth=0.6, label=label)
               for label, color in seen.items()]
    ax.legend(handles=handles, loc="lower right", fontsize=8.5, frameon=False)

    plt.tight_layout()
    fig.savefig(FIGURES / "phase4_mechanism_audit.png", dpi=200)
    fig.savefig(FIGURES / "phase4_mechanism_audit.pdf")
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    render_x4()
    render_phase4()


if __name__ == "__main__":
    main()
