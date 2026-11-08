"""PDF and AI (PDF-compatible) via pdftocairo; EPS via ghostscript first.

pdftocairo turns text into outlines, so lettering in a PDF cuts as designed.
Only the first page is used.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from triaina.convert import ConversionError, Design, run_tool


def load_pdf(path: Path, work_dir: Path, eps: bool = False) -> Design:
    from triaina.convert.svg import load_svg

    pdf = path
    if eps:
        pdf = work_dir / "eps.pdf"
        run_tool(
            [
                "gs",
                "-q",
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-dEPSCrop",
                "-sDEVICE=pdfwrite",
                f"-sOutputFile={pdf}",
                str(path),
            ],
            "EPS",
        )
    svg = work_dir / "page.svg"
    try:
        run_tool(["pdftocairo", "-svg", "-f", "1", "-l", "1", str(pdf), str(svg)], "PDF")
    except ConversionError as exc:
        if path.suffix.lower() == ".ai":
            raise ConversionError(
                f"{exc}. Only PDF-compatible .ai files can be read; in Illustrator save"
                " with 'Create PDF Compatible File' or export as SVG"
            ) from exc
        raise
    design = load_svg(svg)
    if not _has_units(svg):
        # Older cairo writes unitless sizes that are PDF points; load_svg read
        # them as CSS px. 1 pt = 96/72 px. Newer cairo writes "pt" itself, and
        # load_svg already converted those.
        k = 96.0 / 72.0
        design.paths = [[(x * k, y * k) for x, y in p] for p in design.paths]
    return design


def _has_units(svg: Path) -> bool:
    """True when the root width carries a unit (for example "200pt")."""
    try:
        width = ET.parse(svg).getroot().get("width", "")
    except ET.ParseError:
        return False
    width = width.strip()
    return bool(width) and re.fullmatch(r"[\d.eE+-]+", width) is None
