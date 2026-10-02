"""Slice STL/3MF with the PrusaSlicer command line.

Uses triaina/data/prusaslicer_neptune4.ini (shipped with triaina; PrusaSlicer's own
Elegoo profiles stop at the Neptune 3). A Pi 3 slices a small part in a minute
or two; a large one can take much longer, hence the generous timeout.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from triaina.model import ModelError

PROFILE = Path(__file__).resolve().parent.parent / "data" / "prusaslicer_neptune4.ini"
SLICE_TIMEOUT_S = 1800
#: The profile's skirt runs `skirt_distance` (5 mm) outside the part, plus the
#: line width. Without this clearance a part fitted to the bed edge puts its
#: skirt off the bed (measured: X -0.43..225.43 on a 225 mm bed).
SKIRT_CLEARANCE_MM = 6.0
SLICER_NAMES = ("prusa-slicer", "PrusaSlicer", "prusaslicer")


@dataclass
class SliceOptions:
    layer_height: float = 0.2
    #: Infill, percent.
    infill: int = 20
    #: Centre of the part on the bed, mm.
    center: tuple[float, float] = (112.5, 112.5)
    profile: Optional[Path] = None
    #: Command to run; None = first of SLICER_NAMES on PATH.
    slicer: Optional[str] = None
    #: Uniform scale applied first, percent. STL has no units: a model drawn
    #: in inches needs 2540, one in metres 100000.
    scale_percent: float = 100.0
    #: Shrink a model that does not fit the build volume (never enlarges).
    autofit: bool = True
    #: Build volume, mm, and the clearance kept from the bed edges.
    bed: tuple[float, float, float] = (225.0, 225.0, 265.0)
    margin: float = 5.0

    def check(self) -> None:
        if not 1 <= self.scale_percent <= 100000:
            raise ModelError("scale must be 1-100000 %")
        if not 0.05 <= self.layer_height <= 0.32:
            raise ModelError("layer height must be 0.05-0.32 mm for a 0.4 mm nozzle")
        if not 0 <= self.infill <= 100:
            raise ModelError("infill must be 0-100 %")


def _clean(line: str, *paths: Path) -> str:
    """PrusaSlicer log line -> message: no '[time] [thread] [level]' prefix,
    no server paths (the user only knows their file's name)."""
    line = re.sub(r"^(\s*\[[^\]]*\])+\s*", "", line).strip()
    for p in paths:
        line = line.replace(str(p), p.name)
    return line


def find_slicer(name: Optional[str]) -> str:
    for candidate in ([name] if name else SLICER_NAMES):
        if candidate and shutil.which(candidate):
            return candidate
    raise ModelError("slicing needs PrusaSlicer: sudo apt install prusa-slicer")


def parse_stats(gcode: Path) -> dict:
    """Time and filament from PrusaSlicer's comments at the end of the file."""
    stats: dict = {}
    with gcode.open("rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 64 * 1024))
        tail = f.read().decode("utf-8", errors="replace")
    if m := re.search(r"^; estimated printing time \(normal mode\) = (.+)$", tail, re.M):
        text = m.group(1).strip()
        stats["print_time"] = text
        secs = 0
        for value, unit in re.findall(r"(\d+)([dhms])", text):
            secs += int(value) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
        stats["estimate_s"] = secs
    if m := re.search(r"^; filament used \[g\] = ([\d.]+)", tail, re.M):
        stats["filament_g"] = float(m.group(1))
    if m := re.search(r"^; filament used \[mm\] = ([\d.]+)", tail, re.M):
        stats["filament_m"] = round(float(m.group(1)) / 1000, 2)
    return stats


def model_info(model: Path, slicer: str) -> dict:
    """Size and mesh facts from `prusa-slicer --info` (works for STL and 3MF)."""
    try:
        proc = subprocess.run(
            [slicer, "--info", str(model)], capture_output=True, text=True, timeout=300
        )
    except subprocess.TimeoutExpired as exc:
        raise ModelError("reading the model took longer than 5 min") from exc
    info: dict = {}
    for key, value in re.findall(r"^(\w+) = (.+)$", proc.stdout, re.M):
        info[key] = value.strip()
    try:
        size = [float(info["size_x"]), float(info["size_y"]), float(info["size_z"])]
    except (KeyError, ValueError) as exc:
        lines = [ln for ln in (proc.stderr + proc.stdout).splitlines() if ln.strip()]
        raise ModelError(
            "cannot read the model: " + (_clean(lines[-1], model) if lines else "no output")
        ) from exc
    return {"size": size, "manifold": info.get("manifold", "yes") == "yes"}


def fit_plan(size: list[float], opts: SliceOptions) -> tuple[float, list[str]]:
    """Total scale factor (user scale x auto-fit) and warnings for a model of `size` mm."""
    warnings = []
    user = opts.scale_percent / 100.0
    scaled = [d * user for d in size]
    edge = opts.margin + SKIRT_CLEARANCE_MM
    limit = [opts.bed[0] - 2 * edge, opts.bed[1] - 2 * edge, opts.bed[2]]
    if max(scaled) < 2.0:
        warnings.append(
            f"the model is only {max(scaled):.2f} mm across: STL has no units, so it may be"
            " in metres or inches; set a scale"
        )
    fit = min([1.0] + [lim / d for lim, d in zip(limit, scaled) if d > 0])
    if fit < 1.0:
        if not opts.autofit:
            raise ModelError(
                "model is {:.0f} x {:.0f} x {:.0f} mm; the printer takes {:.0f} x {:.0f} x"
                " {:.0f} mm (turn on fit to printer, or scale it down)".format(*scaled, *limit)
            )
        warnings.append(
            "scaled to {:.1f}% to fit the printer ({:.0f} x {:.0f} x {:.0f} mm)".format(
                fit * 100, *limit
            )
        )
    return user * fit, warnings


def slice_model(model: Path, output: Path, opts: SliceOptions) -> dict:
    """Measure, fit to the printer, and slice `model` (STL or 3MF) to `output`.

    Returns slicer stats plus `model_mm` (as uploaded), `final_mm` (as printed),
    `scale_percent` and `warnings`.
    """
    opts.check()
    slicer = find_slicer(opts.slicer)
    info = model_info(model, slicer)
    factor, warnings = fit_plan(info["size"], opts)
    if not info["manifold"]:
        warnings.append("the mesh is not watertight; PrusaSlicer will try to repair it")
    profile = opts.profile or PROFILE
    if not profile.is_file():
        raise ModelError(f"slicer profile missing: {profile}")
    args = [
        slicer,
        "--export-gcode",
        "--load",
        str(profile),
        "--layer-height",
        f"{opts.layer_height:g}",
        "--fill-density",
        f"{opts.infill}%",
        "--center",
        f"{opts.center[0]:g},{opts.center[1]:g}",
        "--scale",
        f"{factor * 100:.4f}%",
        "--output",
        str(output),
        str(model),
    ]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=SLICE_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise ModelError(f"slicing took longer than {SLICE_TIMEOUT_S // 60} min") from exc
    if proc.returncode != 0 or not output.is_file():
        lines = [ln for ln in (proc.stderr + proc.stdout).splitlines() if ln.strip()]
        reason = next(
            (ln for ln in reversed(lines) if "error" in ln.lower()),
            lines[-1] if lines else "no output",
        )
        raise ModelError(f"slicing failed: {_clean(reason, model, output)}")
    stats = parse_stats(output)
    stats.update(
        model_mm=[round(d, 1) for d in info["size"]],
        final_mm=[round(d * factor, 1) for d in info["size"]],
        scale_percent=round(factor * 100, 2),
        warnings=warnings,
    )
    return stats
