# gcode_preprocessor.py

CLI: [`scripts/gcode_preprocessor.py`](https://github.com/nikolareljin/triaina/blob/main/scripts/gcode_preprocessor.py), code in
[`triaina/preprocess.py`](https://github.com/nikolareljin/triaina/blob/main/triaina/preprocess.py) (also used by the service).
Standard library only; Python 3.9 or newer.

```bash
python3 scripts/gcode_preprocessor.py INPUT [-o OUTPUT] [options]
```

## Options

| Option | Default | Meaning |
|---|---|---|
| `-o, --output PATH` | `INPUT` with `.cut.gcode` suffix | Output file. `-` writes to stdout |
| `--max-feed MM_MIN` | `1500` | Every `F` word is capped at this |
| `--default-feed MM_MIN` | `1500` | `F` added to the first XY move if the job never sets one |
| `--z-threshold MM` | `0.0` | Z at or below this means "cutting" |
| `--no-wrap` | off | Omit the `CUTTER_MODE` header and `PRINTER_MODE` footer |
| `--home` | off | Emit `G28` before `CUTTER_MODE` |

Exit codes: `0` success, `1` cannot read input or write output, `2` bad
arguments.

## What it changes

| Input | Output | Why |
|---|---|---|
| `M3`, `M4` (spindle / laser on) | `CUT_PLUNGE` | LightBurn and laser posts signal "tool on" this way |
| `M5` (spindle / laser off) | `CUT_RETRACT` | |
| `G0/G1 Z<=threshold` | `CUT_PLUNGE`, Z word removed | Real cut depth comes from `z_cut` on the printer |
| `G0/G1 Z>threshold` | `CUT_RETRACT`, Z word removed | |
| `T<n>` (tool change) | `CUT_RETRACT` | Lift before any pause; Klipper has no tool table by default |
| `E` words | removed | No extruder in cutter mode |
| `M82 M83 M104 M106 M107 M109 M140 M190 G10 G11` | removed | Heaters, fans, extruder mode, firmware retract |
| `F` above `--max-feed` | clamped | |
| `N` line numbers, `*` checksums | removed | Meaningless after rewriting |
| Comments, macro lines, other G/M codes | kept | |

Plunge and retract are only emitted on a change of blade state, so a
multi-pass job that steps from `Z-0.1` to `Z-0.2` keeps the blade down and
does not emit a second plunge.

Relative Z (`G91`) is tracked. If a file starts in `G91` with no known Z, the
sign of the move decides.

## Output layout

```gcode
; processed by triaina gcode_preprocessor
; removed: E x120, M104 x1
G21
G90
CUTTER_MODE
CUT_RETRACT
... body ...
CUT_RETRACT      ; only if the job left the blade down
PRINTER_MODE
```

## Python API

```python
from triaina.preprocess import Options, process_lines

out = process_lines(open("job.gcode").read().splitlines(), Options(max_feed=1200))
```

`process_lines` is pure (no I/O) and returns lines without newlines.
`classify_z_move(new_z, z_threshold, blade_down)` returns `"CUT_PLUNGE"`,
`"CUT_RETRACT"` or `None`.
