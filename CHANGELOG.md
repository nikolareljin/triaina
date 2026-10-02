# Changelog

## [Unreleased]

- Docs: About page (author, grouped project list) and links to the sibling kinect-forge site from the home page and footer.
- Docs: audit against the code: `setup_pi.sh --service` steps, `triaina serve` options, `/api/info`, every job form field, `[printer] timeout`, code layout, the manual release steps and archive contents; Fluidd is on the printer, not the Pi.

## 2026-10-02 — v0.2.0

### Added

- Dashboard service on the Pi (`python -m triaina serve`, systemd unit, `setup_pi.sh --service`): live printer state, mode switch, pause/resume/cancel, emergency stop and firmware restart, camera, optional token. Starts on boot, restarts on failure.
- Cut jobs from design files: SVG, DXF, PDF, AI, EPS, PNG and JPG converted on the Pi with blade-offset compensation, inner-first cut order, optional weeding border, size/fit options and an SVG preview. Designs are placed only where the knife and the nozzle can both reach.
- Print jobs built on the Pi: a 2D design extruded into a plate, STL/3MF models, and a parametric drag-knife clamp; sliced with PrusaSlicer and a shipped Neptune 4 profile. Models are measured and shrunk to fit the printer, with a scale option for unit-less STL.
- `mode_switch.py upload FILE [--start]`.
- Docs: Existing tools page; wired network through a small switch, with a parts list entry; commissioning checklist for the hardware stage.

### Changed

- Code moved into the `triaina` package; `scripts/*.py` are thin CLI wrappers.
- `setup_pi.sh`: the udev rule is opt-in (`--udev`) and targets the printer's USB-C console bridge.
- Default printer host is `mkspi.local` (the Neptune 4's board name).
- Starting a print in cutter mode runs `PRINTER_MODE` first.
- Logo redrawn as a three-pronged trident.

### Fixed

- Docs: the printer's USB-C port is its Linux console, not the MCU; Pi-as-Klipper-host corrected and marked experimental. The printer is wired-only (no built-in Wi-Fi).

## 2026-10-01 — v0.1.0

- Klipper macros `CUTTER_MODE`, `PRINTER_MODE`, `CUT_PLUNGE`, `CUT_RETRACT`.
- `gcode_preprocessor.py`: Inkscape / Inkcut / LightBurn G-code to cutter G-code.
- `mode_switch.py`: switch modes over Moonraker or OctoPrint.
- `setup_pi.sh`: Pi provisioning with a `/dev/triaina` udev rule.
- Inkcut reference profile, `./dev` CLI, CI on ci-helpers presets.
- Documentation site with wiring diagrams and a parts list.
