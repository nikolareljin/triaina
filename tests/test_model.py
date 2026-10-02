"""Tests for triaina.model: extrusion, knife mount, STL writer, slicing."""

import shutil
import struct

import pytest

from triaina.model import ModelError, write_stl
from triaina.model.extrude import extrude
from triaina.model.mount import MountOptions, build
from triaina.model.slice import SliceOptions, parse_stats, slice_model

SQ = [(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)]
HOLE = [(5, 5), (15, 5), (15, 15), (5, 15), (5, 5)]
needs_slicer = pytest.mark.skipif(
    not (shutil.which("prusa-slicer") or shutil.which("PrusaSlicer")),
    reason="prusa-slicer not installed",
)


def read_stl(path):
    data = path.read_bytes()
    (n,) = struct.unpack_from("<I", data, 80)
    assert len(data) == 84 + 50 * n
    tris = [struct.unpack_from("<12f", data, 84 + 50 * i) for i in range(n)]
    zs = [t[k] for t in tris for k in (5, 8, 11)]
    return n, min(zs), max(zs)


def test_extrude_keeps_holes():
    solid, warnings = extrude([SQ, HOLE], 3)
    assert solid.volume() == pytest.approx((400 - 100) * 3)
    assert warnings == []


def test_extrude_skips_open_lines():
    solid, warnings = extrude([SQ, [(30, 0), (40, 0)]], 2)
    assert solid.volume() == pytest.approx(800) and "open line" in warnings[0]


@pytest.mark.parametrize("height", [0, -1, 500])
def test_extrude_height_range(height):
    with pytest.raises(ModelError, match="height"):
        extrude([SQ], height)


def test_extrude_needs_closed_shape():
    with pytest.raises(ModelError, match="no closed shapes"):
        extrude([[(0, 0), (10, 0)]], 2)


def test_stl_roundtrip(tmp_path):
    solid, _ = extrude([SQ], 4)
    n = write_stl(solid, tmp_path / "a.stl")
    count, zmin, zmax = read_stl(tmp_path / "a.stl")
    assert count == n == 12 and (zmin, zmax) == (0, 4)


def test_mount_builds_watertight():
    part = build(MountOptions())
    assert part.volume() > 0 and part.genus() >= 3  # bore, clamp screw, bolt slots
    xmin, ymin, zmin, xmax, ymax, zmax = part.bounding_box()
    assert zmin == pytest.approx(0) and xmax - xmin == pytest.approx(40)


@pytest.mark.parametrize(
    "kw, match",
    [
        ({"holder_diameter": 50}, "holder_diameter"),
        ({"bolt_spacing": 39}, "do not fit"),
        ({"standoff": 5}, "standoff"),
    ],
)
def test_mount_rejects_bad_parameters(kw, match):
    with pytest.raises(ModelError, match=match):
        build(MountOptions(**kw))


def test_mount_bore_follows_holder_diameter():
    small, big = build(MountOptions(holder_diameter=10)), build(MountOptions(holder_diameter=14))
    assert big.volume() < small.volume() + 2000  # larger bore, larger collar: still sane
    assert big.bounding_box()[4] > small.bounding_box()[4]  # collar reaches further


def test_parse_stats(tmp_path):
    g = tmp_path / "x.gcode"
    g.write_text(
        "G1 X1\n; filament used [mm] = 2450.5\n; filament used [g] = 7.36\n"
        "; estimated printing time (normal mode) = 1h 2m 3s\n"
    )
    assert parse_stats(g) == {
        "print_time": "1h 2m 3s",
        "estimate_s": 3723,
        "filament_g": 7.36,
        "filament_m": 2.45,
    }


def test_slice_options_range():
    with pytest.raises(ModelError, match="layer height"):
        SliceOptions(layer_height=0.5).check()
    with pytest.raises(ModelError, match="infill"):
        SliceOptions(infill=150).check()


def test_missing_slicer_names_package(tmp_path, monkeypatch):
    monkeypatch.setattr("triaina.model.slice.shutil.which", lambda _n: None)
    with pytest.raises(ModelError, match="apt install prusa-slicer"):
        slice_model(tmp_path / "a.stl", tmp_path / "a.gcode", SliceOptions())


@needs_slicer
def test_real_slice_of_mount(tmp_path):
    stl = tmp_path / "m.stl"
    write_stl(build(MountOptions()), stl)
    stats = slice_model(stl, tmp_path / "m.gcode", SliceOptions(layer_height=0.3, infill=10))
    assert stats["estimate_s"] > 60 and stats["filament_g"] > 1
    text = (tmp_path / "m.gcode").read_text()
    assert "M190 S60" in text and "M109 S215" in text and ";LAYER:1" in text


class TestFit:
    def test_fits_unchanged(self):
        factor, warnings = SliceOptionsFactory.fit([40, 30, 20])
        assert factor == 1.0 and warnings == []

    def test_too_big_scales_down_uniformly(self):
        factor, warnings = SliceOptionsFactory.fit([406, 100, 50])
        # 225 bed - 2 x (5 margin + 6 skirt) = 203 mm usable.
        assert factor == pytest.approx(203 / 406) and "scaled to 50.0%" in warnings[0]

    def test_too_tall(self):
        factor, _ = SliceOptionsFactory.fit([50, 50, 530])
        assert factor == pytest.approx(0.5)

    def test_keep_size_refuses(self):
        with pytest.raises(ModelError, match="printer takes 203 x 203 x 265"):
            SliceOptionsFactory.fit([300, 10, 10], autofit=False)

    def test_user_scale_then_fit(self):
        # 10 x 10 x 1 inch model: 2540% makes it 254 mm, then fit shrinks it.
        factor, warnings = SliceOptionsFactory.fit([10, 10, 1], scale_percent=2540)
        assert factor * 10 == pytest.approx(203) and any("scaled" in w for w in warnings)

    def test_tiny_model_warns_about_units(self):
        _, warnings = SliceOptionsFactory.fit([0.2, 0.1, 0.05])
        assert "no units" in warnings[0]


class SliceOptionsFactory:
    @staticmethod
    def fit(size, **kw):
        from triaina.model.slice import fit_plan

        return fit_plan(size, SliceOptions(**kw))


@needs_slicer
def test_real_slice_scales_oversized_model(tmp_path):
    big = [(0, 0), (300, 0), (300, 40), (0, 40), (0, 0)]
    solid, _ = extrude([big], 5)
    stl = tmp_path / "big.stl"
    write_stl(solid, stl)
    stats = slice_model(stl, tmp_path / "big.gcode", SliceOptions(layer_height=0.3, infill=5))
    assert stats["model_mm"] == [300.0, 40.0, 5.0]
    assert stats["final_mm"][0] == pytest.approx(203, abs=0.1)
    assert any("scaled to" in w for w in stats["warnings"])
    from triaina.preprocess import xy_extents

    lines = (tmp_path / "big.gcode").read_text().splitlines()
    x0, _, x1, _ = xy_extents([ln for ln in lines if not ln.startswith("G91")])
    assert x0 >= 0 and x1 <= 225  # every move, skirt included, on the bed


def test_clean_slicer_message(tmp_path):
    from triaina.model.slice import _clean

    model = tmp_path / "part.stl"
    line = f"[2026-10-01 23:35:06.150404] [0x00007c8be1552180] [error]   empty file: {model}"
    assert _clean(line, model) == "empty file: part.stl"


@needs_slicer
def test_real_broken_stl_message(tmp_path):
    bad = tmp_path / "bad.stl"
    bad.write_bytes(b"\x00" * 300)
    with pytest.raises(ModelError) as exc:
        slice_model(bad, tmp_path / "bad.gcode", SliceOptions())
    msg = str(exc.value)
    assert (
        msg.startswith("cannot read the model:") and str(tmp_path) not in msg and "[0x" not in msg
    )


@needs_slicer
def test_real_3mf_input(tmp_path):
    import subprocess

    from triaina.model.slice import find_slicer

    stl = tmp_path / "m.stl"
    write_stl(build(MountOptions()), stl)
    mf = tmp_path / "m.3mf"
    subprocess.run(
        [find_slicer(None), "--export-3mf", "-o", str(mf), str(stl)],
        check=True,
        capture_output=True,
    )
    stats = slice_model(mf, tmp_path / "m.gcode", SliceOptions(layer_height=0.3))
    assert stats["final_mm"] == [40.0, 26.9, 20.0]
    text = (tmp_path / "m.gcode").read_text()
    assert "G92 E0" in text and "M73 P" in text
