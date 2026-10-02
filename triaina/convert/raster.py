"""PNG and JPG: threshold with Pillow, trace outlines with potrace.

The traced size is meaningless (pixels), so the job's width option sets the
real size. A logo on a white background works best; photos do not.
"""

from __future__ import annotations

from pathlib import Path

from triaina.convert import ConversionError, Design, RasterOptions, run_tool

#: Images larger than this are downscaled before tracing (a Pi 3 has 1 GB).
MAX_PIXELS = 4_000_000


def load_raster(path: Path, work_dir: Path, opts: RasterOptions) -> Design:
    from PIL import Image, ImageOps, UnidentifiedImageError

    from triaina.convert.svg import load_svg

    if not 0 <= opts.threshold <= 255:
        raise ConversionError("threshold must be 0-255")
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                # Transparent pixels are background, not ink.
                rgba = img.convert("RGBA")
                bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                img = Image.alpha_composite(bg, rgba)
            gray = img.convert("L")
    except (OSError, UnidentifiedImageError) as exc:
        raise ConversionError(f"cannot read image: {exc}") from exc

    if gray.width * gray.height > MAX_PIXELS:
        f = (MAX_PIXELS / (gray.width * gray.height)) ** 0.5
        gray = gray.resize((max(1, int(gray.width * f)), max(1, int(gray.height * f))))

    # potrace traces black; "1" mode maps ink to 0 (black).
    def ink(v: int) -> int:
        dark = v < opts.threshold
        return 0 if dark != opts.invert else 255

    bitmap = gray.point(ink).convert("1")
    black = bitmap.histogram()[0]
    if black == 0 or black == bitmap.width * bitmap.height:
        raise ConversionError(
            "the image is all one colour at this threshold; try another threshold or invert"
        )
    pbm = work_dir / "trace.pbm"
    svg = work_dir / "trace.svg"
    bitmap.save(pbm)
    run_tool(
        ["potrace", "--svg", "--turdsize", "4", "--alphamax", "1.0", "-o", str(svg), str(pbm)],
        "PNG/JPG",
    )
    return load_svg(svg)
