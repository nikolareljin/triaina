"""2D design -> solid: closed outlines become a plate `height` mm thick.

Holes come from even-odd fill, so the counter of an O or A stays open. Open
lines (a single stroke) have no inside and are skipped with a warning.
"""

from __future__ import annotations

from triaina.cut.paths import Polyline, bounds, is_closed
from triaina.model import ModelError

MAX_HEIGHT_MM = 100.0


def extrude(paths: list[Polyline], height: float):
    """Returns (manifold3d.Manifold, warnings)."""
    import manifold3d as m

    if not 0 < height <= MAX_HEIGHT_MM:
        raise ModelError(f"height must be between 0 and {MAX_HEIGHT_MM:.0f} mm")
    closed = [p[:-1] for p in paths if is_closed(p) and len(p) >= 4]
    open_count = len(paths) - len(closed)
    warnings = []
    if open_count:
        warnings.append(f"{open_count} open line(s) skipped: only closed shapes can be extruded")
    if not closed:
        raise ModelError("no closed shapes to extrude (outlines must be closed)")
    section = m.CrossSection(closed, m.FillRule.EvenOdd)
    if section.area() <= 0:
        raise ModelError("the closed shapes enclose no area")
    solid = section.extrude(height)
    b = bounds(paths)
    if solid.volume() <= 0 or b.width <= 0:
        raise ModelError("extrusion produced an empty solid")
    return solid, warnings
