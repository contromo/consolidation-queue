"""Render LaTeX-ready PNG figure assets.

The SVG files in paper/figures are editable design references. This script
generates the high-resolution PNGs used by PDFLaTeX without depending on a
system SVG renderer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"


COLORS = {
    "blue": "#2f67b2",
    "blue_fill": "#e8f1ff",
    "green": "#5aa469",
    "green_fill": "#eef7ed",
    "orange": "#b76e00",
    "orange_fill": "#fff4df",
    "purple": "#7550b8",
    "purple_fill": "#f4efff",
    "red": "#c64545",
    "red_fill": "#fdecec",
    "gray": "#666666",
    "gray_fill": "#eeeeee",
    "black": "#222222",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if not Path(candidate).exists():
            continue
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


TITLE = font(56, bold=True)
SUBTITLE = font(30)
BODY = font(28)
BODY_BOLD = font(32, bold=True)
SMALL = font(24)
SMALL_BOLD = font(24, bold=True)


def canvas(width: int, height: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (width, height), "white")
    return image, ImageDraw.Draw(image)


def text_center(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fnt, fill=COLORS["black"]) -> None:
    x, y = xy
    box = draw.textbbox((0, 0), text, font=fnt)
    draw.text((x - (box[2] - box[0]) / 2, y - (box[3] - box[1]) / 2), text, font=fnt, fill=fill)


def box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    title: str,
    lines: Iterable[str] = (),
    *,
    outline: str,
    fill: str,
    title_font=BODY_BOLD,
    line_font=BODY,
) -> None:
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=5)
    x0, y0, x1, y1 = xy
    labels = [title, *lines]
    spacing = 48
    center_y = (y0 + y1) // 2
    start_y = center_y - spacing * (len(labels) - 1) / 2
    for index, line in enumerate(labels):
        text_center(
            draw,
            ((x0 + x1) // 2, int(start_y + spacing * index)),
            line,
            title_font if index == 0 else line_font,
        )


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill=COLORS["black"], width: int = 7) -> None:
    draw.line([start, end], fill=fill, width=width)
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length = max((dx * dx + dy * dy) ** 0.5, 1.0)
    ux = dx / length
    uy = dy / length
    px = -uy
    py = ux
    size = 26
    back = 38
    points = [
        (ex, ey),
        (ex - ux * back + px * size / 2, ey - uy * back + py * size / 2),
        (ex - ux * back - px * size / 2, ey - uy * back - py * size / 2),
    ]
    draw.polygon(points, fill=fill)


def save(image: Image.Image, name: str) -> None:
    image.save(FIGURES / name)


def render_pflc() -> None:
    image, draw = canvas(1800, 760)
    draw.text((50, 36), "PFLC formal gap", font=TITLE, fill="black")
    draw.text((50, 112), "Same partition, different policy-facing labels.", font=SUBTITLE, fill="#333333")
    draw.rounded_rectangle((80, 220, 690, 540), radius=18, fill=COLORS["blue_fill"], outline=COLORS["blue"], width=5)
    draw.rounded_rectangle((1110, 220, 1720, 540), radius=18, fill=COLORS["orange_fill"], outline=COLORS["orange"], width=5)
    text_center(draw, (385, 275), "Gold partition", BODY_BOLD)
    text_center(draw, (1415, 275), "Predicted partition", BODY_BOLD)
    for x, label, color in [(200, "g*", COLORS["blue"]), (330, "g1", COLORS["blue"]), (460, "g2", COLORS["green"])]:
        draw.ellipse((x - 45, 355 - 45, x + 45, 355 + 45), fill=color)
        text_center(draw, (x, 358), label, BODY_BOLD, "white")
    for x, label, color in [(1230, "a0", COLORS["blue"]), (1360, "a1", COLORS["blue"]), (1490, "a2", COLORS["green"])]:
        draw.ellipse((x - 45, 355 - 45, x + 45, 355 + 45), fill=color)
        text_center(draw, (x, 358), label, BODY_BOLD, "white")
    text_center(draw, (385, 475), "Queried id: g*", BODY)
    text_center(draw, (1415, 475), "g* not in predicted label set", BODY)
    text_center(draw, (900, 310), "injective relabeling rho", BODY)
    arrow(draw, (740, 360), (1060, 360))
    box(draw, (300, 620, 800, 710), "Cluster metric = 1.00", outline=COLORS["green"], fill=COLORS["green_fill"], title_font=BODY)
    box(draw, (1030, 620, 1600, 710), "Set-membership PFLC = 0", outline=COLORS["red"], fill=COLORS["red_fill"], title_font=BODY)
    save(image, "pflc_formal_gap.png")


def render_protocol() -> None:
    image, draw = canvas(1900, 840)
    draw.text((50, 36), "Controlled externalization protocol", font=TITLE, fill="black")
    box(draw, (60, 200, 320, 330), "LongMemEval", ("v1 source",), outline=COLORS["blue"], fill=COLORS["blue_fill"])
    box(draw, (470, 135, 760, 265), "Annotator", ("Path A",), outline="#5c8f35", fill="#f2f7ed")
    box(draw, (470, 335, 760, 465), "Annotator", ("Path B",), outline="#5c8f35", fill="#f2f7ed")
    box(draw, (930, 235, 1200, 365), "Agreement", ("Verifier",), outline=COLORS["orange"], fill=COLORS["orange_fill"])
    box(draw, (1320, 235, 1590, 365), "Redacted", ("Adapter",), outline=COLORS["purple"], fill=COLORS["purple_fill"])
    box(draw, (1690, 95, 1840, 180), "CQ", outline=COLORS["blue"], fill=COLORS["blue_fill"], title_font=SMALL_BOLD)
    box(draw, (1690, 220, 1840, 305), "Reflection", outline=COLORS["blue"], fill=COLORS["blue_fill"], title_font=SMALL_BOLD)
    box(draw, (1690, 345, 1840, 430), "Mem0Lite", outline=COLORS["blue"], fill=COLORS["blue_fill"], title_font=SMALL_BOLD)
    box(draw, (520, 650, 850, 760), "Judge calibration", ("gate",), outline=COLORS["gray"], fill=COLORS["gray_fill"], title_font=BODY)
    box(draw, (1060, 650, 1390, 760), "PFLC scorer", ("and buckets",), outline=COLORS["gray"], fill=COLORS["gray_fill"], title_font=BODY)
    for start, end in [
        ((320, 260), (470, 205)),
        ((320, 270), (470, 400)),
        ((760, 200), (930, 285)),
        ((760, 400), (930, 320)),
        ((1200, 300), (1320, 300)),
        ((1590, 300), (1690, 140)),
        ((1590, 300), (1690, 265)),
        ((1590, 300), (1690, 390)),
        ((850, 705), (1060, 705)),
        ((1690, 430), (1390, 705)),
    ]:
        arrow(draw, start, end)
    save(image, "externalization_protocol.png")


def render_phase4() -> None:
    image, draw = canvas(1800, 780)
    draw.text((50, 36), "Phase 4 mechanism audit", font=TITLE, fill="black")
    draw.text((50, 112), "CQ vs Reflection: mechanism-local noisy support, nulls kept bounded.", font=SUBTITLE, fill="#333333")
    rows = [
        ("forced_contradiction", 1060, COLORS["green_fill"], COLORS["green"], "clean survival"),
        ("preference_drift", 520, "#f1e9c8", "#b5952f", "partial survival"),
        ("scope_contamination", 260, COLORS["gray_fill"], COLORS["gray"], "residual defects + contract pressure"),
        ("useful_pending_memory", 170, COLORS["gray_fill"], COLORS["gray"], "PFLC failure, no policy win"),
        ("memory_poisoning", 170, COLORS["gray_fill"], COLORS["gray"], "PFLC failure, no policy win"),
        ("false_corroboration", 120, "#f6dede", "#b84a4a", "descriptive-only: source identity absent"),
    ]
    y = 175
    for label, width, fill, outline, note in rows:
        draw.text((90, y), label, font=SMALL, fill=COLORS["black"])
        draw.rounded_rectangle((470, y - 14, 470 + width, y + 26), radius=8, fill=fill, outline=outline, width=3)
        draw.text((500 + width, y - 2), note, font=SMALL, fill=COLORS["black"])
        y += 88
    save(image, "phase4_mechanism_audit.png")


def render_x4() -> None:
    image, draw = canvas(1800, 780)
    draw.text((50, 36), "LongMemEval X.4 cell pattern", font=TITLE, fill="black")
    draw.text((50, 112), "Base CQ ties evidence exposure but loses evidence completeness.", font=SUBTITLE, fill="#333333")
    groups = [("primary_contract", 180), ("path_a_only_denominator", 700), ("path_b_only_denominator", 1220)]
    for title, x in groups:
        text_center(draw, (x + 190, 190), title, SMALL_BOLD)
        draw.rounded_rectangle((x, 260, x + 160, 580), radius=12, fill="#f6dede", outline="#b84a4a", width=4)
        draw.rounded_rectangle((x + 220, 260, x + 380, 580), radius=12, fill=COLORS["green_fill"], outline=COLORS["green"], width=4)
        text_center(draw, (x + 80, 240), "-1.0", BODY_BOLD, "#b84a4a")
        text_center(draw, (x + 300, 240), "0.0", BODY_BOLD, COLORS["green"])
        text_center(draw, (x + 80, 625), "all", BODY)
        text_center(draw, (x + 300, 625), "any", BODY)
    save(image, "longmemeval_x4_cells.png")


def render_phase_y() -> None:
    image, draw = canvas(1800, 660)
    draw.text((50, 36), "Phase Y cardinality control", font=TITLE, fill="black")
    draw.text((50, 112), "Plural CQ readout closes the gap; capped Reflection recreates it.", font=SUBTITLE, fill="#333333")
    box(draw, (70, 220, 360, 360), "Base CQ", ("0/71 all-hit",), outline="#b84a4a", fill="#f6dede")
    box(draw, (520, 220, 850, 360), "Plural pending CQ", ("71/71 all-hit",), outline=COLORS["green"], fill=COLORS["green_fill"])
    box(draw, (1030, 220, 1320, 360), "Reflection", ("71/71 all-hit",), outline=COLORS["green"], fill=COLORS["green_fill"])
    box(draw, (1470, 220, 1760, 360), "Capped Reflection", ("0/71 all-hit",), outline="#b84a4a", fill="#f6dede")
    arrow(draw, (360, 290), (520, 290))
    arrow(draw, (1320, 290), (1470, 290))
    text_center(draw, (900, 480), "Mechanism isolated: answer-time evidence cardinality", BODY_BOLD)
    text_center(draw, (900, 540), "No storage change, no adapter change, no judge change, no headline metric change.", BODY)
    save(image, "phase_y_cardinality_control.png")


def render_ledger() -> None:
    image, draw = canvas(1800, 800)
    draw.text((50, 36), "Evidence ledger summary", font=TITLE, fill="black")
    cols = [
        ("Claim 1", "Fair-stream\nevaluation", ["Oracle locks", "Component gate", "Noisy Bucket B"], COLORS["blue_fill"], COLORS["blue"]),
        ("Claim 2", "Policy-facing\nlookup contracts", ["QR-canon", "PFLC proposition", "Anchor survey"], COLORS["purple_fill"], COLORS["purple"]),
        ("Claim 3", "Controlled\nexternal transfer", ["LongMemEval X.4", "stable negative", "result preserved"], COLORS["orange_fill"], COLORS["orange"]),
        ("Claim 4", "Cardinality-\ncontrolled repair", ["Plural CQ", "Capped Reflection", "no X.4 rewrite"], COLORS["green_fill"], COLORS["green"]),
    ]
    x = 70
    for claim, title, lines, fill, outline in cols:
        draw.rounded_rectangle((x, 150, x + 385, 700), radius=20, fill=fill, outline=outline, width=5)
        text_center(draw, (x + 192, 210), claim, BODY_BOLD)
        for idx, line in enumerate(title.split("\n")):
            text_center(draw, (x + 192, 280 + idx * 42), line, BODY_BOLD)
        for idx, line in enumerate(lines):
            text_center(draw, (x + 192, 450 + idx * 45), line, BODY)
        x += 430
    save(image, "evidence_ledger_summary.png")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    render_pflc()
    render_protocol()
    render_phase4()
    render_x4()
    render_phase_y()
    render_ledger()


if __name__ == "__main__":
    main()
