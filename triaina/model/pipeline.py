"""Print jobs: 2D design -> extruded STL -> G-code, STL/3MF -> G-code, and the
knife mount -> STL -> G-code. Each returns the files written and a summary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from triaina.convert import RasterOptions, load
from triaina.cut.paths import LayoutError, bounds, place
from triaina.model import ModelError, write_stl
from triaina.model.extrude import extrude
from triaina.model.mount import MountOptions, build
from triaina.model.slice import SKIRT_CLEARANCE_MM, SliceOptions, slice_model

MODEL_SUFFIXES = {".stl", ".3mf"}


@dataclass
class PrintResult:
    stl: Optional[Path]
    gcode: Path
    summary: dict
    warnings: list[str] = field(default_factory=list)


def _finish(stl: Optional[Path], gcode: Path, stats: dict, extra: dict, warnings) -> PrintResult:
    # Slicer warnings (scaled to fit, units, repair) join the job's own.
    slicer_warnings = stats.pop("warnings", [])
    return PrintResult(stl, gcode, {**stats, **extra}, list(warnings) + slicer_warnings)


def print_design(
    source: Path,
    out_dir: Path,
    height: float,
    width: Optional[float],
    fit: bool,
    raster: RasterOptions,
    slicing: SliceOptions,
    bed: tuple[float, float] = (225.0, 225.0),
) -> PrintResult:
    """A logo, sign or stamp: the closed outlines become a plate `height` mm thick."""
    design = load(source, out_dir / "work", raster)
    if design.needs_width and width is None and not fit:
        raise LayoutError("an image has no real size: set a width in mm, or shrink to fit")
    # Same usable area as the slicer's fit (bed minus margin and skirt), so a
    # width the user set is either honoured or refused, never shrunk later.
    edge = slicing.margin + SKIRT_CLEARANCE_MM
    paths = place(design.paths, (0.0, 0.0, bed[0], bed[1]), edge, width, fit)
    solid, warnings = extrude(paths, height)
    stl = out_dir / "model.stl"
    write_stl(solid, stl)
    gcode = out_dir / "model.gcode"
    stats = slice_model(stl, gcode, slicing)
    b = bounds(paths)
    extra = {
        "width_mm": round(b.width, 1),
        "height_mm": round(b.height, 1),
        "thickness_mm": height,
        "volume_cm3": round(solid.volume() / 1000, 2),
    }
    return _finish(stl, gcode, stats, extra, design.warnings + warnings)


def print_model(source: Path, out_dir: Path, slicing: SliceOptions) -> PrintResult:
    if source.suffix.lower() not in MODEL_SUFFIXES:
        raise ModelError("expected an STL or 3MF file")
    gcode = out_dir / "model.gcode"
    return _finish(None, gcode, slice_model(source, gcode, slicing), {}, [])


def knife_mount(opts: MountOptions, out_dir: Path, slicing: SliceOptions) -> PrintResult:
    solid = build(opts)
    stl = out_dir / "knife-mount.stl"
    write_stl(solid, stl)
    gcode = out_dir / "model.gcode"
    stats = slice_model(stl, gcode, slicing)
    warnings = [
        "generic clamp: check the screw spacing and standoff against your toolhead"
        " before printing"
    ]
    return _finish(stl, gcode, stats, {"mount": asdict(opts)}, warnings)
