"""Blade-offset compensation for a swivel drag knife.

The blade tip trails the holder's axis by the tip offset `r` (about 0.25 mm on a
45 degree Roland blade). The machine moves the axis; the tip follows behind and
turns towards the direction of travel. Uncompensated, every corner comes out
rounded and short.

Compensation, per segment a->b with unit direction d:

- the axis runs a + r*d -> b + r*d, so the trailing tip runs a -> b;
- at a corner b where the direction turns from d1 to d2 by more than
  `cutoff_deg`, the axis swings on an arc of radius r around b from b + r*d1
  to b + r*d2. The tip stays at b and pivots, so the corner stays sharp;
- smaller turns are taken directly: the error is below the blade's own play.

Closed paths are cut `overcut` mm past their start so the ends meet.

This is the same method as Inkcut's and DXF2GCODE's blade offset (reference:
psol/drag_knife, MIT). The tests check it by simulating the trailing tip.
"""

from __future__ import annotations

import math

from triaina.cut.paths import Point, Polyline, clean, dist, is_closed

#: Arc resolution for the corner swivel, degrees per segment.
ARC_STEP_DEG = 10.0


def _unit(a: Point, b: Point) -> Point:
    d = dist(a, b)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def _turn(d1: Point, d2: Point) -> float:
    """Signed angle from d1 to d2, radians, in (-pi, pi]."""
    return math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1[0] * d2[0] + d1[1] * d2[1])


def _extend(path: Polyline, extra: float) -> Polyline:
    """Continue a closed path past its start by `extra` mm along its first segments."""
    out = list(path)
    left = extra
    for a, b in zip(path, path[1:]):
        seg = dist(a, b)
        if seg >= left:
            t = left / seg
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            return out
        out.append(b)
        left -= seg
    return out


def compensate(
    path: Polyline, offset: float, cutoff_deg: float = 20.0, overcut: float = 1.0
) -> Polyline:
    """Return the axis path that makes the trailing tip follow `path`."""
    cleaned = clean([path])
    if not cleaned:
        # No length at all (every point the same): nothing to cut.
        return []
    path = cleaned[0]
    if is_closed(path) and overcut > 0:
        path = _extend(path, overcut)
    if offset <= 0:
        return list(path)

    dirs = [_unit(a, b) for a, b in zip(path, path[1:])]
    cutoff = math.radians(cutoff_deg)
    out: Polyline = [(path[0][0] + offset * dirs[0][0], path[0][1] + offset * dirs[0][1])]
    for i, d1 in enumerate(dirs):
        b = path[i + 1]
        out.append((b[0] + offset * d1[0], b[1] + offset * d1[1]))
        if i + 1 == len(dirs):
            break
        d2 = dirs[i + 1]
        turn = _turn(d1, d2)
        if abs(turn) > cutoff:
            start = math.atan2(d1[1], d1[0])
            steps = max(2, math.ceil(abs(math.degrees(turn)) / ARC_STEP_DEG))
            for k in range(1, steps):
                ang = start + turn * k / steps
                out.append((b[0] + offset * math.cos(ang), b[1] + offset * math.sin(ang)))
        out.append((b[0] + offset * d2[0], b[1] + offset * d2[1]))
    return clean([out])[0] if len(out) >= 2 else out
