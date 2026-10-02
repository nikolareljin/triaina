# Switching modes

| From | To | Command |
|---|---|---|
| Printer | Cutter | `CUTTER_MODE` in the console, or `mode_switch.py cutter` |
| Cutter | Printer | `PRINTER_MODE`, or `mode_switch.py printer` |

Files from `gcode_preprocessor.py` switch by themselves unless built with
`--no-wrap`.

## From the Pi

```bash
.venv/bin/python scripts/mode_switch.py status
.venv/bin/python scripts/mode_switch.py cutter
.venv/bin/python scripts/mode_switch.py printer
```

The switch is refused (exit code 3) while a job is printing. `--force`
overrides it; do not use it while a hot nozzle is moving.

## Physical changeover

Software mode does not move hardware. Every changeover is:

| To cutter | To printer |
|---|---|
| Wait for hotend below 50 C | `PRINTER_MODE` |
| Fit knife holder | Remove knife holder |
| Mat on bed | Mat off; clean PEI |
| `G28`, `CUTTER_MODE` | `G28` |
