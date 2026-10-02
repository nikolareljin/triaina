<p align="center"><img src="assets/logo.svg" alt="triaina logo" width="160"></p>

# triaina

triaina — Giving your Neptune 4 its proper Greek trident so it can slice vinyl stickers at 1000 mm/s². 🔱⚔️

Run an ELEGOO Neptune 4 (Klipper) as both an FDM printer and a drag-knife vinyl
cutter, with a Raspberry Pi 3 Model B as the companion host.

**Full documentation: https://nikolareljin.github.io/triaina/** (wiring
diagrams, parts list with store links, setup and calibration).

## What is in the box

| Path | What |
|---|---|
| `config/klipper_cutter_macros.cfg` | `CUTTER_MODE`, `PRINTER_MODE`, `CUT_PLUNGE`, `CUT_RETRACT` |
| `config/inkcut_profile.json` | Inkcut device settings |
| `scripts/gcode_preprocessor.py` | Inkscape / Inkcut / LightBurn G-code to safe cutter G-code |
| `scripts/mode_switch.py` | Switch modes over Moonraker or OctoPrint |
| `scripts/setup_pi.sh` | Pi provisioning: venv, udev rule for `/dev/triaina` |
| `assets/logo.svg` | Logo |

The Python scripts use only the standard library.

## Hardware

The Neptune 4 already runs Klipper, Moonraker and Fluidd on a built-in Linux
host. The Pi can join it two ways:

| | Topology A (recommended) | Topology B (advanced) |
|---|---|---|
| Link | Wi-Fi or Ethernet, HTTP to the printer's Moonraker | USB to the MCU; Pi becomes the Klipper host |
| Printer changes | None | Reflash MCU for USB, stop built-in Klipper |
| USB 5 V | n/a | **Block pin 1 (VBUS) with Kapton tape** or a 5 V blocker, so the two supplies do not back-feed |

Diagrams, pinout and step-by-step wiring:
[Wiring the Raspberry Pi](https://nikolareljin.github.io/triaina/hardware/wiring/).
Parts with store links:
[Parts and where to buy](https://nikolareljin.github.io/triaina/hardware/parts/).

## Quick start

On the Pi:

```bash
git clone --recursive https://github.com/nikolareljin/triaina.git
cd triaina
scripts/setup_pi.sh --skip-udev          # Topology A; drop the flag for B
export TRIAINA_HOST=neptune4.local
```

Upload `config/klipper_cutter_macros.cfg` next to `printer.cfg` (Fluidd >
Configuration) and add:

```ini
[include klipper_cutter_macros.cfg]
```

Save & Restart. Then measure and set `offset_x`, `offset_y`, `offset_z`,
`z_cut` in `_TRIAINA_VARS`
([calibration](https://nikolareljin.github.io/triaina/setup/calibration/)).

## Cutting a sticker

```bash
# 1. Inkscape: Object to Path, export G-code (Gcodetools), or LightBurn/Inkcut
# 2. Preprocess
.venv/bin/python scripts/gcode_preprocessor.py sticker.gcode --max-feed 1500
# 3. Upload and start
curl -F "file=@sticker.cut.gcode" "http://$TRIAINA_HOST:7125/server/files/upload"
curl -X POST "http://$TRIAINA_HOST:7125/printer/print/start?filename=sticker.cut.gcode"
```

The output file runs `CUTTER_MODE` (heaters and fans off, accel 1000 mm/s^2,
knife offset) at the start and `PRINTER_MODE` at the end. Switch by hand with:

```bash
.venv/bin/python scripts/mode_switch.py status|cutter|printer
```

Remove the knife holder before printing, and let the hotend cool below 50 C
before fitting it.

## Development

```bash
./dev install && ./dev test && ./dev preflight
```

`./dev` comes from [script-helpers](https://github.com/nikolareljin/script-helpers);
CI uses [ci-helpers](https://github.com/nikolareljin/ci-helpers) presets. `make
install test lint format docs dist clean` work without the submodule. See
[Development](https://nikolareljin.github.io/triaina/develop/development/).

## License

[MIT](LICENSE)
