# Commissioning checklist

Everything in triaina is tested against a fake printer and the real converters
and slicer, but not yet on a Neptune 4 and a Pi 3. Work through this once, in
order, when the hardware is set up. Each step says what you should see, what
to record, and where to look when it is not that.

The same steps are tracked as issues in the project backlog (epic E92, "R-006 triaina:
hardware commissioning"); record results there.

## 1. Pi service and network

Prerequisites: [Wiring](../hardware/wiring.md) (switch, both on Ethernet),
[Raspberry Pi setup](../setup/pi.md), `scripts/setup_pi.sh --service`, and
`[printer] host` set to the printer's IP in `/etc/triaina/config.toml`.

| Do | Expect | Record | If not |
|---|---|---|---|
| `sudo reboot` the Pi, start a stopwatch | `http://triaina.local:8080` loads within 60 s, badge **online**, Klipper **ready** | Time to dashboard | `journalctl -u triaina -n 50`; `curl http://<printer-ip>:7125/server/info` from the Pi |
| `getent hosts mkspi.local` on the Pi | An address, or nothing | Whether it resolves | If nothing, keep the IP in the config (and reserve it in the router) |
| `curl -s localhost:8080/api/status` | `axis_minimum` and `axis_maximum` lists | Both lists | Missing: Klipper not ready; check Fluidd |

## 2. Klipper macros

Prerequisite: [Klipper macros](../setup/klipper.md) included and restarted.

| Do | Expect | If not |
|---|---|---|
| Fluidd console: `CUT_PLUNGE` (fresh restart, printer mode) | Refused: `run CUTTER_MODE first` | Macros not included; check `printer.cfg` |
| Dashboard: **Cutter mode** | Mode field shows `cutter` | Look for the error in the Fluidd console |
| Fluidd console: `SET_VELOCITY_LIMIT` (no args) before and after **Printer mode** | Acceleration back to the value before cutter mode | Report the two values |

## 3. Cutting

Prerequisites: [Mounting the knife](../hardware/knife-mount.md) (knife tip below
the nozzle, `offset_z` set), then [Calibrating the knife](../setup/calibration.md).

| Do | Expect | Record |
|---|---|---|
| Calibrate offset X/Y with the cross test | Error under 0.2 mm | Final `offset_x`, `offset_y` |
| Calibrate depth with the square test | Vinyl cut, backing not | Final `z_cut` |
| Dashboard: **Cut design**, a 20 mm square SVG, weeding border 3 | Sharp corners, closed ends, border inside the margin | Photo, any warnings |
| Dashboard: **Cut design**, a black-on-white PNG logo, width 60 | Clean outline, weeds well | Threshold used |

If corners are rounded, raise `[cut] blade_offset` (0.25 is a standard 45 degree
blade); if ends do not meet, raise `overcut`. If a design is refused as out of
reach, the axis limits recorded in step 1 explain the area.

## 4. Printing

Remove the knife holder first.

| Do | Expect | If not |
|---|---|---|
| Dashboard: **Print knife mount** with your holder's measured diameter | Prints without supports; holder fits the bore; clamp screw grips | Adjust holder diameter / clearance and print again |
| Dashboard: **Print model**, a small calibration cube | Good first layer; nozzle 215 / bed 60 C on the first layer | Edit `triaina/data/prusaslicer_neptune4.ini`; check the saved `default` bed mesh |
| Switch to **Cutter mode**, then start a print job | The printer switches to printer mode before printing | Report it: this is a safety check |

## 5. Slicing on the Pi 3

| Do | Expect | Record |
|---|---|---|
| `prusa-slicer --version` on the Pi | A version | The version (2.7.2 is the one tested) |
| **Print model** with an STL larger than the bed | Scaled to fit, with a warning; slices | Slicing time on the Pi 3 |

If the profile fails to load on that PrusaSlicer version, the job fails with the
slicer's message; open an issue in triaina with it.

## 6. Console cable (optional)

Only if you use the USB-C console cable ([Wiring](../hardware/wiring.md#optional-usb-c-console-cable)).

| Do | Expect |
|---|---|
| Measure and tape pin 1; printer off, Pi on | Printer stays dark |
| `scripts/setup_pi.sh --udev`, replug, `screen /dev/triaina 1500000` | A login prompt from the printer's Linux host |
