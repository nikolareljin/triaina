# Changelog

## [Unreleased]

- `mode_switch.py upload FILE [--start]`: upload a job to Moonraker or OctoPrint, optionally start it.
- `setup_pi.sh`: udev rule is opt-in (`--udev`) and targets the USB-C console bridge; the port is the printer host's console, not the MCU.
- Docs: Pi-as-Klipper-host (Topology B) corrected and marked experimental: it needs the MCU UART inside the base, not USB-C; new Existing tools page (Kiri:Moto, DXF2GCODE, Inkcut, Moonraker, OpenNept4une, KIAUH); Inkcut profile writes to a file.
- Logo redrawn as a three-pronged trident; cut line now renders.

## 2026-10-01 — v0.1.0

- Klipper macros `CUTTER_MODE`, `PRINTER_MODE`, `CUT_PLUNGE`, `CUT_RETRACT`.
- `gcode_preprocessor.py`: Inkscape / Inkcut / LightBurn G-code to cutter G-code.
- `mode_switch.py`: switch modes over Moonraker or OctoPrint.
- `setup_pi.sh`: Pi provisioning with a `/dev/triaina` udev rule.
- Inkcut reference profile, `./dev` CLI, CI on ci-helpers presets.
- Documentation site with wiring diagrams and a parts list.
