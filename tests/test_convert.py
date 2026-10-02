"""Tests for triaina.convert. Fixtures are built in the test, no binary files."""

import shutil

import pytest

from triaina.convert import ConversionError, RasterOptions, load
from triaina.cut.paths import bounds

needs = {
    tool: pytest.mark.skipif(shutil.which(tool) is None, reason=f"{tool} not installed")
    for tool in ("pdftocairo", "gs", "potrace")
}


def write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return p


def size(design):
    b = bounds(design.paths)
    return round(b.width, 1), round(b.height, 1)


# -- SVG -------------------------------------------------------------------

SVG_MM = """<svg xmlns="http://www.w3.org/2000/svg"
  width="100mm" height="50mm" viewBox="0 0 100 50">
  <rect x="10" y="10" width="40" height="20"/>
  <circle cx="75" cy="25" r="10"/>
  <text x="5" y="45">hi</text>
</svg>"""


def test_svg_units_and_shapes(tmp_path):
    d = load(write(tmp_path, "a.svg", SVG_MM), tmp_path / "w")
    assert size(d) == (75.0, 25.0)  # x 10..85 (rect, circle), y 10..35
    assert len(d.paths) == 2
    assert any("text" in w for w in d.warnings)


def test_svg_y_is_flipped(tmp_path):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
        '<path d="M 0 0 L 0 10"/></svg>'
    )
    path = load(write(tmp_path, "y.svg", svg), tmp_path / "w").paths[0]
    # SVG goes down the page; the machine has Y up.
    assert path[0][1] > path[-1][1]


def test_svg_transform_and_curve(tmp_path):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm"'
        ' viewBox="0 0 100 100">'
        '<g transform="scale(2)"><path d="M 0 0 C 10 0 10 10 20 10"/></g></svg>'
    )
    d = load(write(tmp_path, "c.svg", svg), tmp_path / "w")
    assert size(d) == (40.0, 20.0)
    assert len(d.paths[0]) > 10  # flattened, not just the two ends


def test_svg_errors(tmp_path):
    with pytest.raises(ConversionError, match="cannot read SVG"):
        load(write(tmp_path, "bad.svg", "<svg"), tmp_path / "w")
    with pytest.raises(ConversionError, match="text to paths"):
        load(
            write(
                tmp_path, "t.svg", '<svg xmlns="http://www.w3.org/2000/svg"><text>x</text></svg>'
            ),
            tmp_path / "w",
        )


def test_unsupported_type(tmp_path):
    with pytest.raises(ConversionError, match="unsupported file type .docx"):
        load(write(tmp_path, "a.docx", "x"), tmp_path / "w")


# -- DXF -------------------------------------------------------------------


def test_dxf_entities_blocks_and_units(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 1  # inches
    msp = doc.modelspace()
    msp.add_line((0, 0), (2, 0))
    msp.add_circle((1, 1), 0.5)
    blk = doc.blocks.new("TRI")
    blk.add_lwpolyline([(0, 0), (0.5, 0), (0.5, 0.5)], close=True)
    msp.add_blockref("TRI", (3, 0))
    msp.add_text("label")
    path = tmp_path / "a.dxf"
    doc.saveas(path)
    d = load(path, tmp_path / "w")
    assert len(d.paths) == 3
    assert size(d) == (88.9, 38.1)  # 3.5 x 1.5 inches
    assert any("text" in w for w in d.warnings)


def test_dxf_garbage(tmp_path):
    with pytest.raises(ConversionError, match="cannot read DXF"):
        load(write(tmp_path, "x.dxf", "not a dxf"), tmp_path / "w")


# -- PDF / AI / EPS -----------------------------------------------------------


def make_pdf(content: bytes) -> bytes:
    """Minimal one-page vector PDF (points; 72 pt = 25.4 mm)."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


SQUARE_72PT = b"0 0 0 RG 1 w 10 10 m 82 10 l 82 82 l 10 82 l h S"


@needs["pdftocairo"]
@pytest.mark.parametrize("name", ["a.pdf", "a.ai"])
def test_pdf_and_ai(tmp_path, name):
    d = load(write(tmp_path, name, make_pdf(SQUARE_72PT)), tmp_path / "w")
    w, h = size(d)
    assert w == pytest.approx(25.4, abs=0.6) and h == pytest.approx(25.4, abs=0.6)


@needs["pdftocairo"]
def test_ai_not_pdf_compatible(tmp_path):
    with pytest.raises(ConversionError, match="PDF Compatible"):
        load(write(tmp_path, "old.ai", "%!PS-Adobe-3.0\nnot a pdf"), tmp_path / "w")


@needs["gs"]
@needs["pdftocairo"]
def test_eps(tmp_path):
    eps = (
        b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 100 100\n"
        b"newpath 10 10 moveto 82 10 lineto 82 82 lineto closepath stroke\nshowpage\n"
    )
    d = load(write(tmp_path, "a.eps", eps), tmp_path / "w")
    assert size(d)[0] == pytest.approx(25.4, abs=0.6)


# -- PNG / JPG -----------------------------------------------------------------


def make_png(tmp_path, name="a.png", invert=False):
    from PIL import Image, ImageDraw

    bg, fg = (0, 255) if invert else (255, 0)
    img = Image.new("L", (200, 100), bg)
    ImageDraw.Draw(img).rectangle([20, 20, 179, 79], fill=fg)
    p = tmp_path / name
    img.convert("RGB").save(p)
    return p


@needs["potrace"]
@pytest.mark.parametrize("name", ["a.png", "a.jpg"])
def test_raster_traces_shape(tmp_path, name):
    d = load(make_png(tmp_path, name), tmp_path / "w")
    w, h = size(d)
    assert w / h == pytest.approx(160 / 60, rel=0.05)


@needs["potrace"]
def test_raster_invert(tmp_path):
    d = load(make_png(tmp_path, invert=True), tmp_path / "w", RasterOptions(invert=True))
    w, h = size(d)
    assert w / h == pytest.approx(160 / 60, rel=0.05)


def test_raster_blank_image(tmp_path):
    from PIL import Image

    p = tmp_path / "blank.png"
    Image.new("L", (50, 50), 255).save(p)
    with pytest.raises(ConversionError, match="all one colour"):
        load(p, tmp_path / "w")


def test_missing_tool_names_apt_package(tmp_path, monkeypatch):
    monkeypatch.setattr("triaina.convert.shutil.which", lambda _t: None)
    with pytest.raises(ConversionError, match="sudo apt install poppler-utils"):
        load(write(tmp_path, "a.pdf", make_pdf(SQUARE_72PT)), tmp_path / "w")


def test_svg_embedded_image_warns(tmp_path):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
        ' width="10mm" height="10mm" viewBox="0 0 10 10"><rect width="5" height="5"/>'
        '<image width="5" height="5" xlink:href="data:image/png;base64,iVBORw0KGgo="/></svg>'
    )
    d = load(write(tmp_path, "i.svg", svg), tmp_path / "w")
    assert any("embedded image" in w for w in d.warnings)


@needs["potrace"]
def test_raster_needs_width(tmp_path):
    from triaina.cut.paths import LayoutError
    from triaina.cut.pipeline import CutOptions, run

    p = make_png(tmp_path)
    with pytest.raises(LayoutError, match="set a width"):
        run(p, tmp_path / "w", CutOptions())
    assert run(p, tmp_path / "w2", CutOptions(width=80)).summary["width_mm"] == 80.0
