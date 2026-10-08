<p align="center"><img src="assets/logo.svg" alt="triaina logo" width="160"></p>

# triaina

triaina — Giving your Neptune 4 its proper Greek trident so it can slice vinyl stickers at 1000 mm/s². 🔱⚔️

## One Neptune 4. Two tools. One Raspberry Pi 3 control host.

<p align="center">
  <img src="docs/assets/img/triaina-product.jpeg" alt="triaina product setup: Neptune 4 with drag-knife holder, Raspberry Pi 3 and Ethernet switch" width="100%">
</p>

Turn an ELEGOO Neptune 4 (Klipper) into both an FDM printer and a drag-knife
vinyl cutter. A Raspberry Pi 3 Model B runs the dashboard, prepares jobs and
talks to the printer over Ethernet.

| You provide | triaina provides |
|---|---|
| ELEGOO Neptune 4 and a Raspberry Pi 3 | Print jobs, vinyl-cut jobs, a browser dashboard, mode-safe Klipper macros and setup guides |

The dashboard makes the active tool explicit before a job starts. A cut job
switches to cutter mode; a print job switches back to printer mode.

<p align="center">
  <img src="docs/assets/img/neptune4.svg" alt="ELEGOO Neptune 4 configured with a printed drag-knife holder" width="48%">
  <img src="docs/assets/img/pi3b.svg" alt="Raspberry Pi 3 Model B that runs the triaina dashboard" width="48%">
</p>

**Full documentation: https://nikolareljin.github.io/triaina/** (wiring
diagrams, parts list with store links, setup and calibration).

## Why "triaina"?

*Triaina* (Greek *τρίαινα*, "TREE-eh-nah") is Greek for **trident**, the
three-pronged spear of Poseidon, god of the sea.

The printer is an ELEGOO **Neptune** 4. Neptune is Poseidon after the Romans
adopted him: same sea, same beard, same trident, new name tag. So the Neptune 4
is named after the Roman edition of a Greek god, and this project gives it the
original Greek spear back.

Three prongs, three jobs: **print**, **cut**, and the **Raspberry Pi** that
decides which of the two is on duty. The longer version, with a table:
https://nikolareljin.github.io/triaina/name/

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
| `docs/assets/img/triaina-product.jpeg` | Product photo shown at the top of this README and the documentation site |

The CLI scripts use only the standard library; the service needs FastAPI and
uvicorn (`pyproject.toml`).

## Hardware

The Neptune 4 already runs Klipper, Moonraker and Fluidd on a built-in Linux
host. The USB-C port is a console to that host, not a link to the MCU.

| | Topology A (supported) | Topology B (experimental) |
|---|---|---|
| Klipper host | Printer's built-in Linux host | Raspberry Pi |
| Link Pi to printer | Ethernet via a small switch (printer is wired-only), HTTP to Moonraker | Pi GPIO UART (3.3 V, TX/RX/GND) wired to the MCU's UART pins inside the base; **not** the USB-C port |
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
export TRIAINA_HOST=mkspi.local
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
sudo nano /etc/triaina/config.toml       # [printer] host = "mkspi.local"
sudo systemctl restart triaina
```

Open `http://triaina.local:8080/`. It starts on boot and restarts on failure.
Drop a design (SVG, DXF, PDF, AI, EPS, PNG, JPG) or G-code, check the preview,
confirm the physical setup, start, and watch it.
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
