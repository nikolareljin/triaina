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
        # Shrink only: a small design keeps its size (fitting must not enlarge).
        scale = min(
            1.0,
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


def _box_dist(b: "Bounds", p: Point) -> float:
    """Distance from p to a bounding box (0 inside). O(1), used to rank candidates."""
    dx = max(b.min_x - p[0], 0.0, p[0] - b.max_x)
    dy = max(b.min_y - p[1], 0.0, p[1] - b.max_y)
    return math.hypot(dx, dy)


class _Grid:
    """Ready shapes bucketed by box centre, for nearest-next without a full scan.

    pop_nearest searches rings of cells outward and stops once no unvisited
    ring can hold anything nearer. Distance is to the box, so a large box (a
    weeding border) whose centre is far away is still found when the search
    reaches its centre's ring; with few large boxes that is the right trade.
    """

    CELL_MM = 10.0

    def __init__(self, boxes: list["Bounds"]):
        self.boxes = boxes
        self.cells: dict[tuple[int, int], set[int]] = {}
        self.count = 0

    def _key(self, i: int) -> tuple[int, int]:
        b = self.boxes[i]
        return (
            int(math.floor((b.min_x + b.max_x) / 2 / self.CELL_MM)),
            int(math.floor((b.min_y + b.max_y) / 2 / self.CELL_MM)),
        )

    def __bool__(self) -> bool:
        return self.count > 0

    def add(self, i: int) -> None:
        self.cells.setdefault(self._key(i), set()).add(i)
        self.count += 1

    def pop_nearest(self, p: Point) -> int:
        cx, cy = int(math.floor(p[0] / self.CELL_MM)), int(math.floor(p[1] / self.CELL_MM))
        keys = list(self.cells)
        max_ring = max(max(abs(kx - cx), abs(ky - cy)) for kx, ky in keys)
        best, best_d = None, math.inf
        for r in range(max_ring + 1):
            # Nothing in ring r or beyond has its centre closer than (r - 1) cells.
            if best is not None and (r - 1) * self.CELL_MM > best_d:
                break
            for kx in range(cx - r, cx + r + 1):
                for ky in (cy - r, cy + r) if abs(kx - cx) != r else range(cy - r, cy + r + 1):
                    for i in self.cells.get((kx, ky), ()):
                        d = _box_dist(self.boxes[i], p)
                        if d < best_d or (d == best_d and best is not None and i < best):
                            best, best_d = i, d
        cell = self.cells[self._key(best)]
        cell.discard(best)
        if not cell:
            del self.cells[self._key(best)]
        self.count -= 1
        return best


def order(paths: list[Polyline], start: Point = (0.0, 0.0)) -> list[Polyline]:
    """Cut order: inner shapes before the shapes around them, otherwise
    nearest next.

    Cutting the outline of a letter before its counter (the hole in an O) lets
    the piece shift on the mat, so containment wins over travel distance.
    Open paths may be reversed and closed paths re-started to shorten travel.

    Roughly O(n^2) in the number of paths with O(1) work per pair, so a traced
    image with thousands of shapes still orders in seconds on a Pi 3.
    """
    n = len(paths)
    boxes = [bounds([p]) for p in paths]
    # waiting[i]: how many shapes inside i are not cut yet; outer[j]: shapes around j.
    waiting = [0] * n
    outer: list[list[int]] = [[] for _ in range(n)]
    by_area = sorted(range(n), key=lambda k: boxes[k].width * boxes[k].height)
    for a, j in enumerate(by_area):
        for i in by_area[a + 1 :]:
            if boxes[i].contains(boxes[j]):
                waiting[i] += 1
                outer[j].append(i)
    grid = _Grid(boxes)
    for i in range(n):
        if waiting[i] == 0:
            grid.add(i)
    out: list[Polyline] = []
    pos = start
    while grid:
        best = grid.pop_nearest(pos)
        path = paths[best]
        if is_closed(path):
            path = _rotate_to_nearest(path, pos)
        elif dist(pos, path[-1]) < dist(pos, path[0]):
            path = list(reversed(path))
        out.append(path)
        pos = path[-1]
        for i in outer[best]:
            waiting[i] -= 1
            if waiting[i] == 0:
                grid.add(i)
    return out
