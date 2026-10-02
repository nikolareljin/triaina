"""2D design -> solid: closed outlines become a plate `height` mm thick.

Holes are decided by nesting, not by a fill rule: a shape inside an odd number
of other shapes is a hole, inside an even number it is solid, and shapes at the
same depth are joined. So the counter of an O stays open whatever direction it
was drawn in (even-odd would also do that), and two overlapping circles in a
logo merge instead of the overlap becoming a hole (even-odd's failure). Open
lines have no inside and are skipped with a warning.
"""

from __future__ import annotations

from triaina.cut.paths import Polyline, bounds, is_closed
from triaina.model import ModelError

MAX_HEIGHT_MM = 100.0


def _inside(p, ring) -> bool:
    """Point-in-polygon, even-odd ray cast."""
    x, y = p
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def _by_nesting(m, rings: list[Polyline]):
    """Union shapes level by level, alternately adding and cutting."""
    boxes = [bounds([r]) for r in rings]

    def contains(a: int, b: int) -> bool:
        ba, bb = boxes[a], boxes[b]
        if (
            not (
                ba.min_x <= bb.min_x
                and ba.min_y <= bb.min_y
                and ba.max_x >= bb.max_x
                and ba.max_y >= bb.max_y
            )
            or a == b
        ):
            return False
        # A ring inside another has every vertex inside; three spread vertices
        # are enough for outlines that do not cross (crossing ones overlap and
        # stay at the same depth, which is the point).
        r = rings[b]
        probes = [r[0], r[len(r) // 3], r[2 * len(r) // 3]]
        return all(_inside(p, rings[a]) for p in probes)

    depth = [sum(contains(a, b) for a in range(len(rings))) for b in range(len(rings))]
    result = m.CrossSection()
    for d in range(max(depth) + 1):
        level = [rings[i] for i in range(len(rings)) if depth[i] == d]
        if not level:
            continue
        # All rings turned counter-clockwise, then "positive" fill = their
        # union: overlapping shapes on one level merge, whatever their winding.
        shapes = m.CrossSection([_ccw(r) for r in level], m.FillRule.Positive)
        result = result + shapes if d % 2 == 0 else result - shapes
    return result


def _ccw(ring: Polyline) -> Polyline:
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]))
    return ring if area > 0 else list(reversed(ring))


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
    section = _by_nesting(m, closed)
    if section.area() <= 0:
        raise ModelError("the closed shapes enclose no area")
    solid = section.extrude(height)
    b = bounds(paths)
    if solid.volume() <= 0 or b.width <= 0:
        raise ModelError("extrusion produced an empty solid")
    return solid, warnings
