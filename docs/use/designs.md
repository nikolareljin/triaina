# Cutting a design file

The dashboard turns a design file into cut G-code on the Pi: no Kiri:Moto,
Inkcut or Inkscape export needed. Choose **Cut design** as the job type and drop
the file.

## Formats

| Format | Read with | Notes |
|---|---|---|
| SVG | svgelements | Units, viewBox and transforms honoured. **Text must be converted to paths** (Inkscape: Path > Object to Path); text elements are skipped with a warning |
| DXF | ezdxf | Lines, polylines, arcs, circles, splines, ellipses, blocks. `$INSUNITS` sets the scale; unitless is read as mm. Text is skipped |
| PDF | `pdftocairo` (poppler-utils) | First page only. Text is converted to outlines automatically |
| AI | `pdftocairo` | Only PDF-compatible files ("Create PDF Compatible File" in Illustrator) |
| EPS | ghostscript, then as PDF | |
| PNG, JPG | Pillow + `potrace` | Black-on-white logos trace well; photos do not. Set the width, since pixels have no real size |

`setup_pi.sh --service` installs the three programs. A missing one makes only
its format fail, with the `apt install` line in the error.

## Options

| Option | Default | Meaning |
|---|---|---|
| Width | the file's own size | Final width in mm; height follows the aspect ratio |
| Shrink to fit | off | Scale down to the bed if the design is larger. A design is never shrunk silently: without this, too big is an error |
| Weeding border | 0 (none) | Rectangle this many mm around the design, for peeling the waste |
| Blade offset | `[cut] blade_offset` (0.25) | Tip offset of your blade; 0 disables compensation |
| Image threshold | 128 | PNG/JPG: pixels darker than this are the design |
| Light on dark | off | PNG/JPG: trace light shapes on a dark background |

Bed size, margin, corner cutoff, overcut and feeds come from the
[service config](../setup/service.md#configuration).

## What happens

```text
file -> polylines (mm) -> size and place on the bed (lower-left at the margin)
     -> optional weeding border -> cut order -> blade-offset compensation
     -> G-code with CUT_PLUNGE / CUT_RETRACT -> preprocessor (CUTTER_MODE ... PRINTER_MODE)
```

**Cut order.** Inner shapes are cut before the shapes around them (the hole of
an O before its outline), so pieces cannot shift on the mat. Otherwise the
nearest next shape is cut, and open lines may be reversed to save travel.

**Blade offset.** A swivel blade's tip trails the holder by about 0.25 mm, so an
uncompensated knife rounds every corner. The holder is driven ahead of the
design by that offset, and at corners sharper than `cutoff_deg` it swings on a
small arc around the corner so the tip pivots in place. Closed shapes are cut
`overcut` mm past their start so the ends meet. The tests check this by
simulating the dragged tip: it stays within 0.02 mm of the design and reaches
every corner.

## Preview and checks

The job is **converting** while this runs (seconds; a large PDF or photo on a
Pi 3 can take a minute), then **ready**. Before starting:

- open **Preview**: the bed, the margin, the cut lines (blue) and travel moves
  (orange, dashed);
- read the details column: size in mm, number of paths, a time estimate (a lower
  bound: acceleration and plunges are not counted), and any warnings such as
  skipped text;
- download the G-code if you want to inspect it.
