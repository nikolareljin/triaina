# Klipper macros

File: [`config/klipper_cutter_macros.cfg`](https://github.com/nikolareljin/triaina/blob/main/config/klipper_cutter_macros.cfg)

Include it from `printer.cfg` (see [Klipper macros setup](../setup/klipper.md)):

```ini
[include klipper_cutter_macros.cfg]
```

## Settings: `_TRIAINA_VARS`

Every number the macros use lives here. Edit the `variable_` lines, then
`FIRMWARE_RESTART`.

| Variable | Default | Unit | Meaning |
|---|---|---|---|
| `offset_x` | `32.0` | mm | Nozzle X minus knife X (positive: knife left of nozzle) |
| `offset_y` | `-5.0` | mm | Nozzle Y minus knife Y (negative: knife behind nozzle) |
| `offset_z` | `0.0` | mm | How far the knife tip sits below the nozzle tip |
| `z_cut` | `0.1` | mm | Z at which the blade cuts vinyl but not the backing |
| `z_travel` | `3.0` | mm | Z for travel moves between cuts |
| `plunge_feed` | `300` | mm/min | Z speed going down |
| `retract_feed` | `600` | mm/min | Z speed going up |
| `cutter_accel` | `1000` | mm/s^2 | Acceleration while cutting |
| `cutter_velocity` | `100` | mm/s | Max velocity while cutting |
| `cutter_scv` | `2.0` | mm/s | Square corner velocity while cutting |

Runtime state (written by the macros, read by `mode_switch.py status`):

| Variable | Meaning |
|---|---|
| `mode` | `'printer'` or `'cutter'` |
| `blade_down` | `True` after `CUT_PLUNGE`, `False` after `CUT_RETRACT` |
| `saved_accel`, `saved_velocity`, `saved_scv` | Limits in force when `CUTTER_MODE` ran |

## `CUTTER_MODE`

1. If not already in cutter mode, saves the current `max_accel`, `max_velocity`
   and `square_corner_velocity`.
2. `M104 S0`, `M140 S0`: hotend and bed heaters off.
3. `M107`: part cooling fan off.
4. `SET_VELOCITY_LIMIT` to the cutter values.
5. `SET_GCODE_OFFSET X=offset_x Y=offset_y Z=offset_z`.
6. Sets `mode = 'cutter'`.

Running it twice is safe: the second run does not overwrite the saved limits.

## `PRINTER_MODE`

1. Runs `CUT_RETRACT` if the blade is down.
2. Restores the limits saved by `CUTTER_MODE` (no hard-coded "factory" values,
   so it restores whatever your `printer.cfg` set).
3. `SET_GCODE_OFFSET X=0 Y=0 Z=0`.
4. Sets `mode = 'printer'`, which makes `CUT_PLUNGE` refuse to run.

## `CUT_PLUNGE`

Moves Z to `z_cut` at `plunge_feed`, in absolute mode, then restores the caller's
G90/G91 state. Refuses with an error when:

- `mode` is not `'cutter'` (`CUT_PLUNGE refused: run CUTTER_MODE first`), or
- X, Y and Z are not all homed (`CUT_PLUNGE refused: home all axes (G28) first`).

An error in Klipper aborts the running print, so a cut file sent in printer mode
stops before the blade touches anything.

## `CUT_RETRACT`

Moves Z to `z_travel` at `retract_feed` if Z is homed, and marks the blade up.
Never refuses: lifting is always the safe direction.
