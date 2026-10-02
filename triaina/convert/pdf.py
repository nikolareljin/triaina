"""PDF and AI (PDF-compatible) via pdftocairo; EPS via ghostscript first.

pdftocairo turns text into outlines, so lettering in a PDF cuts as designed.
Only the first page is used.
"""

from __future__ import annotations

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
    # pdftocairo writes unitless sizes that are PDF points (cairo convention);
    # load_svg read them as CSS px. 1 pt = 96/72 px.
    k = 96.0 / 72.0
    design.paths = [[(x * k, y * k) for x, y in p] for p in design.paths]
    return design
