"""Tests for triaina.cut.paths and triaina.cut.knife.

The knife test simulates a real swivel blade: the tip is dragged behind the
axis at distance r. Compensation is right when that simulated tip retraces the
design.
"""

import math

import pytest

from triaina.cut.knife import compensate
from triaina.cut.paths import (
    LayoutError,
    bounds,
    clean,
    flip_y,
    is_closed,
    order,
    place,
    weed_border,
)

SQUARE = [(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)]


def drag(axis, r, step=0.005):
    """Trailing-tip simulation: the tip is pulled toward the axis, keeping distance <= r."""
    dense = []
    for a, b in zip(axis, axis[1:]):
        n = max(1, int(math.dist(a, b) / step))
        dense += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    dense.append(axis[-1])
    d0 = ((axis[1][0] - axis[0][0]), (axis[1][1] - axis[0][1]))
    n0 = math.hypot(*d0)
    tip = (axis[0][0] - r * d0[0] / n0, axis[0][1] - r * d0[1] / n0)
    trail = [tip]
    for c in dense:
        vx, vy = c[0] - tip[0], c[1] - tip[1]
        d = math.hypot(vx, vy)
        if d > r:
            tip = (c[0] - r * vx / d, c[1] - r * vy / d)
            trail.append(tip)
    return trail


def dist_to_polyline(p, path):
    best = math.inf
    for a, b in zip(path, path[1:]):
        ax, ay, bx, by = *a, *b
        L2 = (bx - ax) ** 2 + (by - ay) ** 2
        t = (
            0
            if L2 == 0
            else max(0, min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / L2))
        )
        best = min(best, math.dist(p, (ax + t * (bx - ax), ay + t * (by - ay))))
    return best


@pytest.mark.parametrize("r", [0.25, 0.5])
def test_compensated_square_has_sharp_corners(r):
    axis = compensate(SQUARE, r, cutoff_deg=20, overcut=1.0)
    tip = drag(axis, r)
    # The tip never strays from the design...
    assert max(dist_to_polyline(p, SQUARE) for p in tip) < 0.02
    # ...and reaches every corner (an uncompensated knife cuts them short).
    for corner in SQUARE[:-1]:
        assert min(math.dist(corner, p) for p in tip) < 0.02


def test_uncompensated_square_rounds_corners():
    """The failure the compensation exists for: same simulation, no offset."""
    tip = drag(SQUARE, 0.5)
    assert min(math.dist((20, 20), p) for p in tip) > 0.1


def test_zigzag_open_path():
    zig = [(0, 0), (10, 5), (20, 0), (30, 5)]
    tip = drag(compensate(zig, 0.25, cutoff_deg=10), 0.25)
    assert max(dist_to_polyline(p, zig) for p in tip) < 0.02
    assert min(math.dist((20, 0), p) for p in tip) < 0.02


def test_small_turns_skip_the_swivel():
    gentle = [(0, 0), (10, 0), (20, 1)]  # ~5.7 degree turn
    axis = compensate(gentle, 0.25, cutoff_deg=20)
    assert len(axis) == 4  # start, corner end, corner restart, end: no arc points


def test_overcut_extends_closed_paths_only():
    closed = compensate(SQUARE, 0, overcut=2.0)
    assert closed[-1] == pytest.approx((2.0, 0.0))
    opened = compensate([(0, 0), (10, 0)], 0, overcut=2.0)
    assert opened[-1] == (10.0, 0.0)


def test_zero_offset_is_identity_for_open_path():
    assert compensate([(0, 0), (5, 0), (5, 5)], 0) == [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0)]


def test_clean_merges_and_drops():
    assert clean([[(0, 0), (0, 0.001), (5, 0)], [(1, 1), (1, 1)]]) == [[(0.0, 0.0), (5.0, 0.0)]]


def test_place_scales_to_width_and_margin():
    placed = place([SQUARE], bed=(225, 225), margin=5, width=50)
    b = bounds(placed)
    assert (b.min_x, b.min_y, b.width, b.height) == pytest.approx((5, 5, 50, 50))


def test_place_refuses_too_big_unless_fit():
    big = [[(0, 0), (500, 0), (500, 100)]]
    with pytest.raises(LayoutError, match="bed allows"):
        place(big, bed=(225, 225), margin=5)
    b = bounds(place(big, bed=(225, 225), margin=5, fit=True))
    assert b.width == pytest.approx(215)


def test_place_rejects_empty():
    with pytest.raises(LayoutError):
        place([], bed=(225, 225), margin=5)


def test_flip_y_and_weed_border():
    assert flip_y([[(1, 2)]]) == [[(1, -2)]]
    border = weed_border([SQUARE], 3)
    assert is_closed(border) and bounds([border]).width == pytest.approx(26)


def test_order_cuts_inner_before_outer():
    outer = [(0, 0), (50, 0), (50, 50), (0, 50), (0, 0)]
    inner = [(20, 20), (30, 20), (30, 30), (20, 30), (20, 20)]
    far = [(100, 100), (110, 100)]
    out = order([outer, far, inner])
    assert out.index(next(p for p in out if bounds([p]).width == 10)) < out.index(
        next(p for p in out if bounds([p]).width == 50)
    )


def test_order_reverses_open_path_to_shorten_travel():
    out = order([[(10, 0), (0, 0)]], start=(0, 0))
    assert out[0][0] == (0, 0)
