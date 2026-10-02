# Changelog

## [Unreleased]

- Cut designs from the dashboard: SVG, DXF, PDF, AI, EPS, PNG and JPG are converted on the Pi with blade-offset compensation, inner-first cut order, optional weeding border, size/fit options and an SVG preview. `setup_pi.sh --service` installs poppler-utils, ghostscript and potrace.

- Dashboard service (`python -m triaina serve`): live printer state, mode switch, cut and print G-code jobs with a physical-setup confirmation, pause/resume/cancel, emergency stop, camera. systemd unit, `setup_pi.sh --service`, optional token.
- Code moved into the `triaina` package (`preprocess`, `printer`); `scripts/*.py` are thin CLI wrappers.
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
