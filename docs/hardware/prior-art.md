# Existing tools

triaina builds on existing open-source tools and only adds what was missing.
Each project link below was checked on 2026-10-01.

## What triaina reuses

| Need | Project | License | How triaina uses it |
|---|---|---|---|
| Klipper, Moonraker, Fluidd on the printer | Stock ELEGOO firmware, or [OpenNept4une](https://github.com/OpenNeptune3D/OpenNept4une) | GPL-3.0 | Runs as is. triaina only adds its macros to `printer.cfg` |
| Printer API | [Moonraker](https://github.com/Arksine/moonraker) | GPL-3.0 | `mode_switch.py` uploads, starts jobs and runs macros over its HTTP API |
| Installing Klipper add-ons (camera) | [KIAUH](https://github.com/dw-0/kiauh) | GPL-3.0 | Optional, for `crowsnest` on the Pi |
| G-code with blade-offset compensation | [Kiri:Moto](https://github.com/GridSpace/grid-apps) drag-knife mode | MIT | Recommended generator, runs in the browser |
| G-code with blade-offset compensation | [DXF2GCODE](https://sourceforge.net/projects/dxf2gcode/) | open source | Alternative: knife offset entered as tool diameter |
| Cutter GUI | [Inkcut](https://github.com/inkcut/inkcut) | GPL-3.0 | Alternative desktop sender; output to file |
| Path cleanup and ordering | [vpype](https://github.com/abey79/vpype) and [vpype-gcode](https://github.com/abey79/vpype-gcode) | MIT | Optional, for scripted pipelines |
| Blade-offset algorithm reference | [psol/drag_knife](https://github.com/psol/drag_knife) | MIT | Reference only (early Python 2.7 code) |

## What triaina adds

No packaged Klipper drag-knife macros or Neptune 4 cutter setup exist that we
could find, so these are triaina's own:

| Part | Why |
|---|---|
| [Klipper macros](../reference/klipper-macros.md) | Mode switch with heaters off, saved and restored limits, knife offset, plunge refused outside cutter mode |
| [gcode_preprocessor.py](../reference/gcode-preprocessor.md) | Makes any generator's output safe for this machine: strips heaters and extruder, maps Z and `M3`/`M5` to the macros, caps feed |
| [Design conversion](../use/designs.md) | SVG, DXF, PDF, AI, EPS, PNG, JPG to cut G-code on the Pi, with blade-offset compensation (method as in Inkcut / psol/drag_knife), containment-aware cut order and a preview. Parsing reuses svgelements, ezdxf, poppler, ghostscript and potrace |
| [mode_switch.py](../reference/mode-switch.md) | One command to switch modes and upload or start a job from the Pi |
| [setup_pi.sh](../reference/setup-pi.md) | Idempotent Pi provisioning |
| [Knife mount](knife-mount.md) | No Neptune 4 drag-knife mount is published; remix a generic holder clamp |

## How they fit together

```text
Kiri:Moto / DXF2GCODE / Inkcut / Inkscape   (blade offset, toolpath)
        |
        v
gcode_preprocessor.py                       (safety: heaters, macros, feed cap)
        |
        v
mode_switch.py upload --start               (Moonraker HTTP API)
        |
        v
Neptune 4: stock Klipper + triaina macros
```
