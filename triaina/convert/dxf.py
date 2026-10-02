"""DXF to polylines with ezdxf. Blocks are exploded; $INSUNITS sets the scale."""

from __future__ import annotations

from pathlib import Path

from triaina.convert import ConversionError, Design
from triaina.cut.paths import Polyline

#: $INSUNITS code -> millimetres per drawing unit. 0 (unitless) is read as mm.
UNIT_MM = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0000254, 9: 0.0254}
TEXT_TYPES = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}


def _entities(layout, depth=0):
    for e in layout:
        if e.dxftype() == "INSERT" and depth < 8:
            yield from _entities(e.virtual_entities(), depth + 1)
        else:
            yield e


def load_dxf(path: Path) -> Design:
    try:
        import ezdxf
        from ezdxf import path as dxfpath
    except ImportError as exc:  # pragma: no cover - dependency of the package
        raise ConversionError("ezdxf is not installed") from exc
    try:
        doc = ezdxf.readfile(str(path))
    except (OSError, ezdxf.DXFError) as exc:
        raise ConversionError(f"cannot read DXF: {exc}") from exc

    units = doc.header.get("$INSUNITS", 0)
    scale = UNIT_MM.get(units)
    warnings = []
    if scale is None:
        scale = 1.0
        warnings.append(f"unknown DXF units code {units}; read as millimetres")
    # Max deviation between curve and polyline: 0.05 mm, in drawing units.
    deviation = 0.05 / scale

    paths: list[Polyline] = []
    skipped: dict[str, int] = {}
    for e in _entities(doc.modelspace()):
        kind = e.dxftype()
        if kind in TEXT_TYPES:
            skipped["text"] = skipped.get("text", 0) + 1
            continue
        try:
            p = dxfpath.make_path(e)
        except (TypeError, ValueError, ezdxf.DXFError):
            skipped[kind] = skipped.get(kind, 0) + 1
            continue
        for sub in p.sub_paths():
            pts = [
                (v.x * scale, v.y * scale) for v in sub.flattening(distance=deviation, segments=4)
            ]
            if len(pts) >= 2:
                paths.append(pts)

    for kind, n in sorted(skipped.items()):
        hint = "; explode text to outlines in your CAD program" if kind == "text" else ""
        warnings.append(f"{n} {kind} entit{'y' if n == 1 else 'ies'} skipped{hint}")
    if not paths:
        raise ConversionError("no lines, arcs or curves found in the DXF")
    # DXF is already Y up.
    return Design(paths, warnings)
