# System overview

The Neptune 4 is not a bare mainboard. Its base holds two computers:

| Part | Runs | You reach it at |
|---|---|---|
| Built-in Linux host | Klipper (klippy), Moonraker, Fluidd | `http://<printer>/` (Fluidd), `http://<printer>:7125/` (Moonraker) |
| STM32 MCU | Klipper MCU firmware: steppers, heaters, endstops | Internal serial link from the host |

triaina adds two things: Klipper macros that switch the machine between printing
and cutting, and a Raspberry Pi 3 B that prepares cut files and drives the
switch. There are two ways to connect the Pi.

| | Topology A (recommended) | Topology B (advanced) |
|---|---|---|
| Pi role | Companion on the network | Replaces the built-in host as the Klipper host |
| Link Pi to printer | Wi-Fi or Ethernet, HTTP to Moonraker | USB cable to the MCU, 5 V pin blocked |
| Printer modification | None | Flash MCU firmware for USB, stop the built-in Klipper |
| Where the macros live | Built-in host's `printer.cfg` | Pi's `printer.cfg` |
| Reversible | Yes, unplug | Yes, but needs a reflash |
| Use it when | You want cutting with the stock machine | You want the Pi to own the whole stack (for example a mainline Klipper build) |

Start with Topology A. Everything in triaina (macros, preprocessor, mode
switch, Inkcut profile) works the same on both; only where Klipper runs
changes.

## Data flow for one sticker

```text
Inkscape (laptop)        -> design.svg -> G-code export
gcode_preprocessor.py    -> design.cut.gcode   (Pi or laptop)
Moonraker upload         -> /server/files/upload
mode_switch.py cutter    -> CUTTER_MODE        (heaters off, slow accel, knife offset)
Start print in Fluidd    -> CUT_PLUNGE / G1 ... / CUT_RETRACT
End of file              -> PRINTER_MODE       (limits and offsets restored)
```

Next: [Wiring the Raspberry Pi](wiring.md).
