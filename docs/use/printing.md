# Printing from the dashboard

Besides plain print G-code, the dashboard can make and slice three kinds of
print job on the Pi. They use the same flow as everything else: upload,
**converting** (building and slicing), **ready** with a summary, confirm, start.

| Job type | Input | What happens |
|---|---|---|
| Print design (3D) | SVG, DXF, PDF, AI, EPS, PNG, JPG | The closed outlines become a plate `thickness` mm thick (a sign, stamp, keychain or logo), then it is sliced |
| Print model | STL, 3MF | Sliced as it is, centred on the bed |
| Print knife mount | none: parameters | The [drag-knife clamp](../hardware/knife-mount.md) is generated and sliced |

## Options

| Option | Default | Applies to |
|---|---|---|
| Width, shrink to fit | file size | Print design (as for [cut designs](designs.md)); required for PNG/JPG |
| Thickness | 3 mm | Print design |
| Layer height | 0.2 mm | All (0.05-0.32 for the 0.4 mm nozzle) |
| Infill | 20 % | All |
| Holder diameter, bolt spacing, standoff | 11.5, 30, 12 mm | Knife mount |
| Scale | 100 % | Print model |
| Keep size | off | Print model: refuse instead of shrinking to fit |

The details column shows size, print time and filament from the slicer. **STL**
downloads the generated model (to check it in a viewer); **G-code** the sliced
file.

## Fitting the model to the printer

Every model is measured first (`prusa-slicer --info`), then:

1. **Scale** (default 100 %) is applied. STL has no units: a model drawn in
   inches needs 2540 %, one in metres 100000 %. A model under 2 mm across gets a
   warning that its units are probably wrong.
2. **Fit to the printer** (on unless you tick *Keep size*): a model larger than
   the usable volume is shrunk, uniformly, until it fits. It is never enlarged.
   The usable volume is the bed minus the margin and the skirt on each side,
   203 x 203 mm, by 265 mm tall: a part fitted to the bed edge would otherwise
   put its skirt off the bed. With *Keep size*, a model that does not fit is an
   error instead.
3. It is centred on the bed and sliced.

The details column shows the size as printed (`prints 203 x 27.1 x 3.4 mm`)
and an orange warning when it was scaled.

## Slicing

Slicing runs the `prusa-slicer` command line on the Pi with
[`triaina/data/prusaslicer_neptune4.ini`](https://github.com/nikolareljin/triaina/blob/main/triaina/data/prusaslicer_neptune4.ini):
225 x 225 x 265 mm, 0.4 mm nozzle, Klipper flavour, PLA 215/60 C first layer,
gyroid infill, a purge line at the left edge. PrusaSlicer's own Elegoo profiles
stop at the Neptune 3, so this profile is written from the Neptune 4 specs;
check it against your printer and edit the file to taste.

A Pi 3 slices a small part in a minute or two; a large model can take much
longer (the limit is 30 minutes).

## Printer mode

Starting any print job while the printer is in cutter mode runs
`PRINTER_MODE` first, so the knife's G-code offset cannot shift the print. The
start dialog asks you to confirm the knife holder is removed.

## Extruding a design

Only closed shapes have an inside: open lines are skipped with a warning. Holes
stay holes (even-odd fill), so lettering keeps its counters. For a stamp,
mirror the design before uploading.
