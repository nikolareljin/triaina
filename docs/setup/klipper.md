# Klipper macros

The macros go on whichever machine runs Klipper: the printer's built-in host
(Topology A) or the Pi (experimental Topology B).

## 1. Upload the file

=== "Fluidd (both topologies)"

    1. Open Fluidd (`http://mkspi.local/` or `http://triaina.local/`).
    2. **Configuration** (the `{}` icon) > upload
       `config/klipper_cutter_macros.cfg` into the root next to `printer.cfg`.

=== "Command line (from the Pi)"

    ```bash
    curl -F "root=config" -F "file=@config/klipper_cutter_macros.cfg" \
      "http://$TRIAINA_HOST:7125/server/files/upload"
    ```

## 2. Include it

Add this line to `printer.cfg`, above the `#*# <---------------------- SAVE_CONFIG` block:

```ini
[include klipper_cutter_macros.cfg]
```

If you keep it in a subfolder, use the path relative to `printer.cfg`, for
example `[include config/klipper_cutter_macros.cfg]`.

## 3. Restart and check

Click **Save & Restart**, then in the Fluidd console:

```text
CUTTER_MODE
PRINTER_MODE
```

Each prints a `triaina:` line. `mode_switch.py status` now shows
`mode printer`.

## 4. Tune

Edit the `variable_` lines in `_TRIAINA_VARS` (offsets, `z_cut`,
`z_travel`, accel). Each one is described in the
[macro reference](../reference/klipper-macros.md). Restart after every change.

!!! note "1000 mm/s^2"
    Stock Neptune 4 limits are far above what a swivel blade tolerates. At
    1000 mm/s^2 and a 2 mm/s square corner velocity the blade has time to
    rotate before the next segment starts.
