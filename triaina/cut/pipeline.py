"""Design file -> safe cut G-code + preview SVG + summary.

load (convert) -> place on the bed -> optional weed border -> order ->
blade-offset compensation -> G-code with the knife macros -> preprocessor
(adds CUTTER_MODE / PRINTER_MODE, caps feed).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from triaina.convert import RasterOptions, load
from triaina.cut.knife import compensate
from triaina.cut.paths import (
    LayoutError,
    Polyline,
    bounds,
    dist,
    length,
    order,
    place,
    weed_border,
)
from triaina.preprocess import Options as PreOptions
from triaina.preprocess import process_lines


@dataclass
class CutOptions:
    #: Final design width, mm. None keeps the file's own size.
    width: Optional[float] = None
    #: Shrink to the bed when the design is larger (never enlarges).
    fit: bool = False
    margin: float = 5.0
    bed_x: float = 225.0
    bed_y: float = 225.0
    #: Where the knife can cut, machine coordinates (min_x, min_y, max_x, max_y).
    #: None = the whole bed. The service narrows it by the printer's axis
    #: limits and the knife offset, so the nozzle never leaves its range.
    area: Optional[tuple[float, float, float, float]] = None
    #: Weeding border gap, mm. 0 = no border.
    weed: float = 0.0
    blade_offset: float = 0.25
    cutoff_deg: float = 20.0
    overcut: float = 1.0
    cut_feed: float = 1200.0
    travel_feed: float = 3000.0
    #: Cap applied by the preprocessor to every F word.
    max_feed: float = 1500.0
    threshold: int = 128
    invert: bool = False
    #: Warnings from the caller (e.g. area not checked), shown with the job.
    extra_warnings: list[str] = field(default_factory=list)


@dataclass
class CutResult:
    gcode: list[str]
    preview_svg: str
    summary: dict
    warnings: list[str]


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def to_gcode(axis_paths: list[Polyline], cut_feed: float, travel_feed: float) -> list[str]:
    lines = ["G90", "G21"]
    for path in axis_paths:
        x, y = path[0]
        lines.append(f"G0 X{_fmt(x)} Y{_fmt(y)} F{_fmt(travel_feed)}")
        lines.append("CUT_PLUNGE")
        first = True
        for x, y in path[1:]:
            lines.append(f"G1 X{_fmt(x)} Y{_fmt(y)}" + (f" F{_fmt(cut_feed)}" if first else ""))
            first = False
        lines.append("CUT_RETRACT")
    return lines


def preview(design: list[Polyline], axis: list[Polyline], opts: CutOptions) -> str:
    """Bed, design (what you get) and travel moves, Y flipped for screen."""
    w, h = opts.bed_x, opts.bed_y
    ax0, ay0, ax1, ay1 = opts.area or (0.0, 0.0, w, h)

    def pts(path):
        return " ".join(f"{x:.2f},{h - y:.2f}" for x, y in path)

    travel = []
    pos = (0.0, 0.0)
    for path in axis:
        travel.append([pos, path[0]])
        pos = path[-1]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 {w + 4} {h + 4}" '
        f'width="{w}mm" height="{h}mm">',
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="#f8fafc" stroke="#94a3b8"'
        ' stroke-width="0.5"/>',
        f'<rect x="{ax0 + opts.margin}" y="{h - ay1 + opts.margin}" '
        f'width="{ax1 - ax0 - 2 * opts.margin}" height="{ay1 - ay0 - 2 * opts.margin}" '
        'fill="none" stroke="#cbd5e1" stroke-width="0.3" stroke-dasharray="2 2"/>',
    ]
    for t in travel:
        parts.append(
            f'<polyline points="{pts(t)}" fill="none" stroke="#f59e0b" stroke-width="0.25" '
            'stroke-dasharray="1 1"/>'
        )
    for path in design:
        parts.append(
            f'<polyline points="{pts(path)}" fill="none" stroke="#0284c7" stroke-width="0.4"/>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def run(source: Path, work_dir: Path, opts: CutOptions) -> CutResult:
    design = load(source, work_dir, RasterOptions(opts.threshold, opts.invert))
    if design.needs_width and opts.width is None and not opts.fit:
        raise LayoutError("an image has no real size: set a width in mm, or shrink to fit")
    # The weeding border must stay inside the margin too, so reserve it there.
    weed = max(opts.weed, 0.0)
    area = opts.area or (0.0, 0.0, opts.bed_x, opts.bed_y)
    paths = place(design.paths, area, opts.margin + weed, opts.width, opts.fit)
    if weed > 0:
        paths = paths + [weed_border(paths, weed)]
    ordered = order(paths)
    axis = [compensate(p, opts.blade_offset, opts.cutoff_deg, opts.overcut) for p in ordered]
    axis = [a for a in axis if len(a) >= 2]

    # max_feed limits cutting. Travel may be faster: every path's first cut move
    # carries its own F, so a travel F never leaks into a cut (F is modal).
    cut_feed = min(opts.cut_feed, opts.max_feed)
    raw = to_gcode(axis, cut_feed, opts.travel_feed)
    cap = max(cut_feed, opts.travel_feed)
    gcode = process_lines(raw, PreOptions(max_feed=cap, default_feed=cut_feed))

    b = bounds(paths)
    cut_mm = sum(length(p) for p in axis)
    travel_mm, pos = 0.0, (0.0, 0.0)
    for p in axis:
        travel_mm += dist(pos, p[0])
        pos = p[-1]
    feed, travel = cut_feed, opts.travel_feed
    summary = {
        "paths": len(axis),
        "width_mm": round(b.width, 1),
        "height_mm": round(b.height, 1),
        "cut_mm": round(cut_mm),
        "travel_mm": round(travel_mm),
        # Lower bound: ignores acceleration and the plunge/retract moves.
        "estimate_s": round(60 * (cut_mm / feed + travel_mm / travel) + 2 * len(axis)),
        "options": asdict(opts),
    }
    return CutResult(gcode, preview(paths, axis, opts), summary, design.warnings)
