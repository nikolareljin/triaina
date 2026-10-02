# Safety

| Hazard | Rule |
|---|---|
| Hot nozzle next to a plastic mount and the operator's fingers | Hotend below 50 C before fitting or removing the holder |
| Heater left on in cutter mode | `CUTTER_MODE` runs `M104 S0` and `M140 S0`; the preprocessor removes all heater commands |
| Blade plunging in printer mode | `CUT_PLUNGE` refuses unless `mode` is `cutter` and all axes are homed |
| Nozzle crashing into the mat | Knife tip must sit below the nozzle tip; see [Mounting the knife](../hardware/knife-mount.md) |
| Two 5 V supplies back-feeding over USB | Topology B only: block pin 1, see [Wiring](../hardware/wiring.md#blocking-5-v-on-the-usb-cable) |
| Exposed blade | Retract or cap the blade when the holder is off the machine |
| Printing over a mounted knife | Always remove the holder before printing; `PRINTER_MODE` reminds you |
