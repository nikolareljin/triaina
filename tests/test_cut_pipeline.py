"""Tests for triaina.cut.pipeline (SVG input, no external tools)."""

import pytest

from triaina.cut.paths import LayoutError
from triaina.cut.pipeline import CutOptions, run

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="20mm" viewBox="0 0 40 20">'
    '<rect x="0" y="0" width="40" height="20"/><rect x="10" y="5" width="20" height="10"/></svg>'
)


@pytest.fixture
def src(tmp_path):
    p = tmp_path / "d.svg"
    p.write_text(SVG)
    return p


def test_weed_border_stays_inside_margin(src, tmp_path):
    res = run(src, tmp_path / "w", CutOptions(margin=5, weed=4))
    xs = [float(t[1:]) for line in res.gcode for t in line.split() if t.startswith("X")]
    ys = [float(t[1:]) for line in res.gcode for t in line.split() if t.startswith("Y")]
    # Blade offset can push the axis 0.25 mm past a line; the cut itself is inside.
    assert min(xs) >= 5 - 0.3 and min(ys) >= 5 - 0.3
    assert res.summary["width_mm"] == 48.0


def test_weed_border_counts_against_bed(src, tmp_path):
    with pytest.raises(LayoutError):
        run(src, tmp_path / "w", CutOptions(width=210, margin=5, weed=4))


def test_inner_cut_first_and_feeds(src, tmp_path):
    res = run(src, tmp_path / "w", CutOptions(cut_feed=900, travel_feed=3000, max_feed=1500))
    g = [ln for ln in res.gcode if ln.startswith(("G0", "G1"))]
    first_cut = next(ln for ln in g if ln.startswith("G1"))
    assert "F900" in first_cut
    assert any("F3000" in ln for ln in g if ln.startswith("G0"))
    # The first path cut is the inner rectangle (20 mm wide, starts x >= 15).
    first_travel = next(ln for ln in g if ln.startswith("G0"))
    assert float(first_travel.split()[1][1:]) >= 14


def test_cut_feed_capped_by_max_feed(src, tmp_path):
    res = run(src, tmp_path / "w", CutOptions(cut_feed=5000, max_feed=1500))
    feeds = [ln for ln in res.gcode if ln.startswith("G1") and " F" in ln]
    assert feeds and all("F1500" in ln for ln in feeds)


def test_wrapped_for_cutter_mode(src, tmp_path):
    res = run(src, tmp_path / "w", CutOptions())
    assert "CUTTER_MODE" in res.gcode and res.gcode[-1] == "PRINTER_MODE"
    assert res.gcode.count("CUT_PLUNGE") == 2
