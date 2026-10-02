# Cutting a sticker

## 1. Design (Inkscape)

1. Document size: up to 225 x 225 mm (Neptune 4 bed), units mm.
2. Text: **Path > Object to Path**. Fills do not cut; only outlines do.
3. Remove overlaps: **Path > Union** for touching letters.
4. Add a weeding border: a rectangle 5 mm larger than the design.

## 2. Export G-code

Pick one:

| Tool | How | Blade signal |
|---|---|---|
| Inkscape + Gcodetools (Extensions > Gcodetools) | Orientation points, Tools library (cylinder), Path to G-code | Z moves |
| Inkcut | See [Inkcut](inkcut.md) | Z moves or macros |
| LightBurn (GRBL device) | Line mode, power irrelevant | `M3` / `M5` |

Any of them works: the preprocessor turns Z moves and `M3`/`M5` into the same
macros.

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
curl -F "file=@sticker.cut.gcode" "http://$TRIAINA_HOST:7125/server/files/upload"
```

Then start it from Fluidd, or:

```bash
curl -X POST "http://$TRIAINA_HOST:7125/printer/print/start?filename=sticker.cut.gcode"
```

The file switches to `CUTTER_MODE` itself and back to `PRINTER_MODE` at the
end.

## 6. Weed

Lift the mat off the bed, peel the border, then the inside pieces with a hook.
Apply transfer tape.
