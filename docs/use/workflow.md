# Cutting a sticker

## 1. Design (Inkscape)

1. Document size: up to 225 x 225 mm (Neptune 4 bed), units mm.
2. Text: **Path > Object to Path**. Fills do not cut; only outlines do.
3. Remove overlaps: **Path > Union** for touching letters.
4. Add a weeding border: a rectangle 5 mm larger than the design.

!!! tip "Easier: the dashboard"
    With the [dashboard service](../setup/service.md) installed, drop the SVG,
    DXF, PDF or PNG on the dashboard as a **Cut design** job and skip steps 2-5.
    See [Cutting a design file](designs.md).

## 2. Generate G-code

Drag knives need blade-offset compensation: the tip trails the holder axis by
about 0.25 mm, so corners need small swivel moves. Use a generator that does it.

| Tool | How | Blade offset |
|---|---|---|
| [Kiri:Moto](https://grid.space/kiri/) (recommended, in the browser) | Laser mode, drag-knife option; bed 225 x 225 mm; export G-code | yes |
| [DXF2GCODE](https://sourceforge.net/projects/dxf2gcode/) | Export DXF from Inkscape; knife offset as tool diameter | yes (swivel moves) |
| [Inkcut](inkcut.md) | Blade offset filter; output to file | yes |
| Inkscape + Gcodetools | Path to G-code | no; corners round slightly |
| LightBurn (GRBL device) | Line mode | via `M3`/`M5`, no offset |

Any of them works: the preprocessor turns Z moves and `M3`/`M5` into the same
macros. See [Existing tools](../hardware/prior-art.md).

## 3. Preprocess

```bash
.venv/bin/python scripts/gcode_preprocessor.py sticker.gcode --max-feed 1500
# wrote sticker.cut.gcode
```

Read the first lines of the output: `; removed:` lists what was dropped. If it
mentions `M109` or many `E` words, the source was exported for a printer, not a
cutter; check the export settings.

## 4. Prepare the machine

1. Hotend cold (below 50 C). Fit the knife holder.
2. Stick the vinyl on the cutting mat, shiny side up; place the mat on the bed,
   aligned to the front-left corner.
3. `G28`.

## 5. Send and run

```bash
.venv/bin/python scripts/mode_switch.py upload sticker.cut.gcode --start
```

Without `--start` the file is only uploaded; start it from Fluidd. The file
switches to `CUTTER_MODE` itself and back to `PRINTER_MODE` at the end.

## 6. Weed

Lift the mat off the bed, peel the border, then the inside pieces with a hook.
Apply transfer tape.
