"""Turn a design file into polylines in millimetres (machine orientation, Y up).

| Format | How |
|---|---|
| SVG | svgelements: shapes, paths, transforms and units, curves flattened |
| DXF | ezdxf: lines, polylines, arcs, circles, splines, ellipses, blocks; $INSUNITS |
| PDF, AI | `pdftocairo -svg` (poppler-utils), then SVG. Text becomes outlines |
| EPS | ghostscript to PDF, then as PDF |
| PNG, JPG | threshold with Pillow, trace with `potrace`, then SVG |

External programs are optional: a missing one fails that format with the apt
package to install, never the others.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from triaina.cut.paths import Polyline

#: Curves are flattened into chords of at most this length, mm. On a 1 mm
#: radius that deviates 0.03 mm from the curve, below the blade's own play.
CHORD_MM = 0.5
#: Seconds an external converter may run (a Pi 3 is slow, a huge PDF slower).
TOOL_TIMEOUT_S = 180

FORMATS = {
    ".svg": "svg",
    ".dxf": "dxf",
    ".pdf": "pdf",
    ".ai": "pdf",
    ".eps": "eps",
    ".png": "raster",
    ".jpg": "raster",
    ".jpeg": "raster",
}

APT_PACKAGE = {"pdftocairo": "poppler-utils", "gs": "ghostscript", "potrace": "potrace"}


class ConversionError(ValueError):
    """The design could not be read; the message says why and what to do."""


@dataclass
class Design:
    paths: list[Polyline]
    warnings: list[str] = field(default_factory=list)


@dataclass
class RasterOptions:
    #: 0-255; darker than this is ink.
    threshold: int = 128
    #: Trace light shapes on a dark background instead.
    invert: bool = False


def run_tool(args: list[str], what: str) -> None:
    tool = args[0]
    if shutil.which(tool) is None:
        raise ConversionError(
            f"{what} needs `{tool}`: sudo apt install {APT_PACKAGE.get(tool, tool)}"
        )
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=TOOL_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise ConversionError(f"{tool} took longer than {TOOL_TIMEOUT_S} s") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        raise ConversionError(f"{tool} failed: {detail[0]}")


def load(path: Path, work_dir: Path, raster: RasterOptions | None = None) -> Design:
    """Read any supported design file. `work_dir` receives intermediate files."""
    kind = FORMATS.get(path.suffix.lower())
    if kind is None:
        raise ConversionError(
            f"unsupported file type {path.suffix or '(none)'}; use {', '.join(sorted(FORMATS))}"
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    if kind == "svg":
        from triaina.convert.svg import load_svg

        return load_svg(path)
    if kind == "dxf":
        from triaina.convert.dxf import load_dxf

        return load_dxf(path)
    if kind in ("pdf", "eps"):
        from triaina.convert.pdf import load_pdf

        return load_pdf(path, work_dir, eps=kind == "eps")
    from triaina.convert.raster import load_raster

    return load_raster(path, work_dir, raster or RasterOptions())
