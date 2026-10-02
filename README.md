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
| `triaina/` (service) | Dashboard on the Pi at `http://triaina.local:8080`: live printer state, mode switch, cut and print jobs, camera. Runs as a systemd service |
| `scripts/gcode_preprocessor.py` | Inkscape / Inkcut / LightBurn G-code to safe cutter G-code |
| `scripts/mode_switch.py` | Switch modes over Moonraker or OctoPrint |
| `scripts/setup_pi.sh` | Pi provisioning: packages and venv |
| `assets/logo.svg` | Logo |

The CLI scripts use only the standard library; the service needs FastAPI and
uvicorn (`pyproject.toml`).

## Hardware

The Neptune 4 already runs Klipper, Moonraker and Fluidd on a built-in Linux
host. The USB-C port is a console to that host, not a link to the MCU.

| | Topology A (supported) | Topology B (experimental) |
|---|---|---|
| Klipper host | Printer's built-in Linux host | Raspberry Pi |
| Link Pi to printer | Wi-Fi or Ethernet, HTTP to Moonraker | Pi GPIO UART (3.3 V, TX/RX/GND) wired to the MCU's UART pins inside the base; **not** the USB-C port |
| Printer changes | None | Open the base, wire to MCU pins, build and flash Klipper MCU firmware for that UART, stop the built-in Klipper |
| USB 5 V | Optional console cable: **block pin 1 (VBUS) with Kapton tape** or a 5 V blocker | No 5 V between boards; share GND only |
| Verified | Yes | No: MCU UART pins on the ZNP-K1 not confirmed on any board revision |

Diagrams, pinout and step-by-step wiring:
[Wiring the Raspberry Pi](https://nikolareljin.github.io/triaina/hardware/wiring/).
Parts with store links:
[Parts and where to buy](https://nikolareljin.github.io/triaina/hardware/parts/).
What triaina reuses (Kiri:Moto, Moonraker, OpenNept4une, KIAUH) and what it
adds: [Existing tools](https://nikolareljin.github.io/triaina/hardware/prior-art/).

## Quick start

On the Pi:

```bash
git clone --recursive https://github.com/nikolareljin/triaina.git
cd triaina
scripts/setup_pi.sh
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

## Dashboard service

```bash
scripts/setup_pi.sh --service            # installs, enables, starts; re-run to update
sudo nano /etc/triaina/config.toml       # [printer] host = "neptune4.local"
sudo systemctl restart triaina
```

Open `http://triaina.local:8080/`. It starts on boot and restarts on failure.
Upload cut or print G-code, confirm the physical setup, start, and watch it.
See [Dashboard service](https://nikolareljin.github.io/triaina/setup/service/).

## Cutting a sticker

```bash
# 1. Generate G-code with blade offset: Kiri:Moto drag-knife mode, DXF2GCODE or Inkcut
# 2. Make it safe for this machine
.venv/bin/python scripts/gcode_preprocessor.py sticker.gcode --max-feed 1500
# 3. Upload and start through Moonraker
.venv/bin/python scripts/mode_switch.py upload sticker.cut.gcode --start
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
