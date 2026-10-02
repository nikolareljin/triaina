"""SVG to polylines with svgelements (units, viewBox and transforms resolved)."""

from __future__ import annotations

import math
from pathlib import Path

from triaina.convert import CHORD_MM, ConversionError, Design
from triaina.cut.paths import Polyline, flip_y

#: svgelements works in CSS pixels at 96 per inch.
PX_TO_MM = 25.4 / 96.0


def _flatten(path, chord_px: float) -> list[Polyline]:
    from svgelements import Close, Line, Move

    out: list[Polyline] = []
    for sub in path.as_subpaths():
        pts: Polyline = []
        for seg in sub:
            if isinstance(seg, Move):
                if len(pts) >= 2:
                    out.append(pts)
                pts = [(seg.end.x, seg.end.y)]
                continue
            if seg.start is None or seg.end is None:
                continue
            if not pts:
                pts = [(seg.start.x, seg.start.y)]
            if isinstance(seg, (Line, Close)):
                pts.append((seg.end.x, seg.end.y))
                continue
            try:
                seg_len = seg.length(error=1e-3)
            except Exception:  # noqa: BLE001 - degenerate curve: sample a little
                seg_len = 0.0
            n = max(2, math.ceil(seg_len / chord_px))
            for k in range(1, n + 1):
                p = seg.point(k / n)
                pts.append((p.x, p.y))
        if len(pts) >= 2:
            out.append(pts)
    return out


def load_svg(path: Path) -> Design:
    try:
        from svgelements import SVG, Image, Path as SvgPath, Shape, Text
    except ImportError as exc:  # pragma: no cover - dependency of the package
        raise ConversionError("svgelements is not installed") from exc

    try:
        svg = SVG.parse(str(path), reify=True, ppi=96.0)
    except Exception as exc:  # noqa: BLE001 - malformed XML, bad attributes, ...
        raise ConversionError(f"cannot read SVG: {exc}") from exc

    chord_px = CHORD_MM / PX_TO_MM
    paths: list[Polyline] = []
    texts = images = 0
    for element in svg.elements():
        if isinstance(element, Text):
            texts += 1
            continue
        if isinstance(element, Image):
            images += 1
            continue
        if not isinstance(element, Shape):
            continue
        if element.values.get("visibility") == "hidden" or element.values.get("display") == "none":
            continue
        shape = SvgPath(element)
        for poly in _flatten(shape, chord_px):
            paths.append([(x * PX_TO_MM, y * PX_TO_MM) for x, y in poly])

    warnings = []
    if texts:
        warnings.append(
            f"{texts} text element(s) skipped: convert text to paths"
            " (Inkscape: Path > Object to Path)"
        )
    if images:
        warnings.append(
            f"{images} embedded image(s) skipped: trace them to paths first, or upload the"
            " image itself as PNG/JPG"
        )
    if not paths:
        raise ConversionError(
            "no shapes found in the SVG" + (f" ({warnings[0]})" if warnings else "")
        )
    return Design(flip_y(paths), warnings)
