# triaina

<p align="center"><img src="assets/logo.svg" alt="triaina logo" width="160"></p>

Giving your Neptune 4 its proper Greek trident so it can slice vinyl stickers at
1000 mm/s^2.

triaina turns an ELEGOO Neptune 4 into a two-in-one machine: a normal FDM
printer and a drag-knife vinyl cutter. A Raspberry Pi 3 Model B prepares cut
files and switches modes.

| Part | What it does |
|---|---|
| [Klipper macros](reference/klipper-macros.md) | `CUTTER_MODE`, `PRINTER_MODE`, `CUT_PLUNGE`, `CUT_RETRACT` |
| [gcode_preprocessor.py](reference/gcode-preprocessor.md) | Turns Inkscape / Inkcut / LightBurn G-code into safe cutter G-code |
| [mode_switch.py](reference/mode-switch.md) | Switches modes over Moonraker or OctoPrint |
| [setup_pi.sh](reference/setup-pi.md) | Provisions the Pi: packages, venv, and the service |
| [Dashboard](use/dashboard.md) | Service on the Pi: live status, mode switch, cut and print jobs; [cuts SVG, DXF, PDF, AI, EPS, PNG, JPG](use/designs.md) directly |

## Start here

1. [Parts and where to buy](hardware/parts.md)
2. [System overview](hardware/overview.md) and [Existing tools](hardware/prior-art.md)
3. [Wiring the Raspberry Pi](hardware/wiring.md)
4. [Mounting the knife](hardware/knife-mount.md)
5. [Raspberry Pi setup](setup/pi.md), [Klipper macros](setup/klipper.md),
   [Calibrating the knife](setup/calibration.md)
6. [Dashboard service](setup/service.md), then [Cutting a sticker](use/workflow.md)
7. Once, with the hardware: [Commissioning checklist](use/commissioning.md)

<figure class="diagram" markdown>
![Network wiring diagram](assets/img/wiring-network.svg)
<figcaption>Pi and printer on the same network; jobs go through Moonraker.</figcaption>
</figure>
