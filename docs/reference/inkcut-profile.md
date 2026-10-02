# Inkcut profile

File: [`config/inkcut_profile.json`](https://github.com/nikolareljin/triaina/blob/main/config/inkcut_profile.json)

Inkcut stores devices in its own settings and has no stable import format, so
this file is a reference: copy the values into Inkcut's device dialog. See
[Inkcut](../use/inkcut.md) for where each field goes.

| Key | Value | Meaning |
|---|---|---|
| `connection.transport` | `file` | Inkcut writes G-code to a file; upload it with `mode_switch.py upload` |
| `protocol` | `gcode` | |
| `area` | 225 x 225 mm | Neptune 4 bed |
| `blade.offset_mm` | `0.25` | Tip offset of a standard 45 deg Roland blade |
| `blade.cutoff_deg` | `20` | Corners sharper than this get a swivel move |
| `speeds.cut_feed_mm_min` | `1500` | Matches the preprocessor default cap |
| `gcode.header` | `G21 G90 G28 CUTTER_MODE CUT_RETRACT` | |
| `gcode.footer` | `CUT_RETRACT PRINTER_MODE` | |
