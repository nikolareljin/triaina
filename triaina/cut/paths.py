"""Polylines in millimetres, machine orientation (X right, Y back/up).

A design is a list of polylines. These helpers size and place it on the bed,
add a weeding border and choose the cut order. Pure Python, no dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]
Polyline = list[Point]

#: Points closer than this are merged, mm.
MERGE_MM = 0.01
#: A polyline whose ends are this close is treated as closed, mm.
CLOSED_MM = 0.05


class LayoutError(ValueError):
    """The design cannot be placed as asked (too big, empty)."""


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def contains(self, other: "Bounds") -> bool:
        return (
            self.min_x <= other.min_x
            and self.min_y <= other.min_y
            and self.max_x >= other.max_x
            and self.max_y >= other.max_y
            and (self.width * self.height) > (other.width * other.height)
        )


def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def is_closed(path: Polyline) -> bool:
    return len(path) > 2 and dist(path[0], path[-1]) <= CLOSED_MM


def clean(paths: list[Polyline]) -> list[Polyline]:
    """Merge near-duplicate points; drop paths with no length."""
    out = []
    for path in paths:
        pts: Polyline = []
        for p in path:
            p = (float(p[0]), float(p[1]))
            if not pts or dist(pts[-1], p) > MERGE_MM:
                pts.append(p)
        if len(pts) >= 2 and length(pts) > MERGE_MM:
            out.append(pts)
    return out


def length(path: Polyline) -> float:
    return sum(dist(a, b) for a, b in zip(path, path[1:]))


def bounds(paths: list[Polyline]) -> Bounds:
    xs = [p[0] for path in paths for p in path]
    ys = [p[1] for path in paths for p in path]
    if not xs:
        raise LayoutError("the design has no cut lines")
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def transform(paths: list[Polyline], scale: float, dx: float, dy: float) -> list[Polyline]:
    return [[(x * scale + dx, y * scale + dy) for x, y in path] for path in paths]


def flip_y(paths: list[Polyline]) -> list[Polyline]:
    """SVG and images have Y down; the machine has Y up."""
    return [[(x, -y) for x, y in path] for path in paths]


def place(
    paths: list[Polyline],
    bed: tuple[float, float],
    margin: float,
    width: float | None = None,
    fit: bool = False,
) -> list[Polyline]:
    """Scale (to `width`, or down to fit the bed when `fit`) and move the
    design's lower-left corner to (margin, margin).

    Raises LayoutError if the result does not fit the bed: a design is never
    shrunk silently, because a sticker at the wrong size is a wasted sheet.
    """
    paths = clean(paths)
    b = bounds(paths)
    usable_w, usable_h = bed[0] - 2 * margin, bed[1] - 2 * margin
    if usable_w <= 0 or usable_h <= 0:
        raise LayoutError(f"margin {margin} mm leaves no room on a {bed[0]} x {bed[1]} mm bed")
    scale = 1.0
    if width is not None:
        if width <= 0:
            raise LayoutError("width must be positive")
        if b.width <= 0:
            raise LayoutError("the design has no width to scale")
        scale = width / b.width
    elif fit:
        scale = min(
            usable_w / b.width if b.width else math.inf,
            usable_h / b.height if b.height else math.inf,
        )
    w, h = b.width * scale, b.height * scale
    if w > usable_w + 1e-6 or h > usable_h + 1e-6:
        raise LayoutError(
            f"design is {w:.1f} x {h:.1f} mm; the bed allows {usable_w:.1f} x {usable_h:.1f} mm"
            " (set a smaller width, or fit to bed)"
        )
    return transform(paths, scale, margin - b.min_x * scale, margin - b.min_y * scale)


def weed_border(paths: list[Polyline], gap: float) -> Polyline:
    """Closed rectangle `gap` mm outside the design, for peeling the waste."""
    b = bounds(paths)
    x0, y0, x1, y1 = b.min_x - gap, b.min_y - gap, b.max_x + gap, b.max_y + gap
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _rotate_to_nearest(path: Polyline, pos: Point) -> Polyline:
    """Start a closed path at its vertex nearest `pos`."""
    ring = path[:-1]
    i = min(range(len(ring)), key=lambda k: dist(ring[k], pos))
    ring = ring[i:] + ring[:i]
    return ring + [ring[0]]


def order(paths: list[Polyline], start: Point = (0.0, 0.0)) -> list[Polyline]:
    """Cut order: inner shapes before the shapes around them, otherwise
    nearest next.

    Cutting the outline of a letter before its counter (the hole in an O) lets
    the piece shift on the mat, so containment wins over travel distance.
    Open paths may be reversed and closed paths re-started to shorten travel.
    """
    boxes = [bounds([p]) for p in paths]
    inside = [
        {j for j in range(len(paths)) if j != i and boxes[i].contains(boxes[j])}
        for i in range(len(paths))
    ]
    done: set[int] = set()
    out: list[Polyline] = []
    pos = start
    while len(done) < len(paths):
        ready = [i for i in range(len(paths)) if i not in done and inside[i] <= done]
        best, best_path, best_d = None, None, math.inf
        for i in ready:
            path = paths[i]
            if is_closed(path):
                cand = [_rotate_to_nearest(path, pos)]
            else:
                cand = [path, list(reversed(path))]
            for c in cand:
                d = dist(pos, c[0])
                if d < best_d:
                    best, best_path, best_d = i, c, d
        done.add(best)
        out.append(best_path)
        pos = best_path[-1]
    return out
