# System overview

The Neptune 4 is not a bare mainboard. Its base holds two computers:

| Part | Runs | You reach it at |
|---|---|---|
| Built-in Linux host | Klipper (klippy), Moonraker, Fluidd | `http://<printer>/` (Fluidd), `http://<printer>:7125/` (Moonraker) |
| STM32 MCU | Klipper MCU firmware: steppers, heaters, endstops | Internal serial link from the host only |

The USB-C port on the printer is the built-in host's **serial console**
(1500000 baud), not a link to the MCU
([OpenNept4une wiki](https://github.com/OpenNeptune3D/OpenNept4une/wiki)).
So the Raspberry Pi cannot simply take over as the Klipper host over USB.

## How triaina connects

The Pi joins the printer over the network and drives it through Moonraker's
HTTP API, the same API Fluidd uses. Nothing on the printer is modified apart
from adding the triaina macros to `printer.cfg`.

| Link | Required | Purpose |
|---|---|---|
| Ethernet (printer is wired-only; Pi wired or Wi-Fi), same LAN, through a small switch | yes | Upload jobs, switch modes, read status |
| USB-C cable, Pi to printer | no | Recovery console when the printer's network is down |

## Topologies

| | Topology A (supported) | Topology B (experimental) |
|---|---|---|
| Klipper host | Printer's built-in Linux host | Raspberry Pi |
| Link Pi to printer | Ethernet via a switch (Pi may use Wi-Fi), HTTP to Moonraker | Pi GPIO UART (3.3 V, TX/RX/GND) wired to the MCU's UART pins inside the base; **not** the USB-C port |
| Printer changes | None | Open the base, wire to MCU pins, build and flash Klipper MCU firmware for that UART, stop the built-in Klipper |
| USB 5 V | Optional console cable: **block pin 1 (VBUS) with Kapton tape** or a 5 V blocker | No 5 V between boards; share GND only |
| Verified | Yes | No: MCU UART pins on the ZNP-K1 not confirmed on any board revision |

Use Topology A. Topology B is documented for people who want the Pi to own the
whole Klipper stack and are willing to open the printer; see
[Wiring, Topology B](wiring.md#topology-b-pi-as-klipper-host-experimental).

## Data flow for one sticker

```text
Design (laptop): Inkscape, Kiri:Moto, DXF2GCODE or Inkcut -> G-code
gcode_preprocessor.py (Pi)      -> design.cut.gcode
mode_switch.py upload --start   -> Moonraker /server/files/upload (print=true)
File header                     -> CUTTER_MODE (heaters off, slow accel, knife offset)
Cut                             -> CUT_PLUNGE / G1 ... / CUT_RETRACT
File footer                     -> PRINTER_MODE (limits and offsets restored)
```

See [Existing tools](prior-art.md) for what triaina reuses and what is its own.

Next: [Wiring the Raspberry Pi](wiring.md).
