# Calibrating the knife

Do these in order, with a scrap sheet of vinyl on the mat.

## 1. Offset X/Y

1. Tape a sheet of paper on the mat. `G28`, `CUTTER_MODE`.
2. Cut a small cross centred on `X100 Y100`:

    ```gcode
    G1 X95 Y100 F3000
    CUT_PLUNGE
    G1 X105 F600
    CUT_RETRACT
    G1 X100 Y95
    CUT_PLUNGE
    G1 Y105
    CUT_RETRACT
    ```

3. `PRINTER_MODE`, then `G1 X100 Y100 Z1 F3000`. The cold nozzle now hangs
   over the point the macros think the knife was.
4. Measure from the nozzle centre to the cross centre. Correct `offset_x` /
   `offset_y`: if the cross is to the right of the nozzle, **decrease**
   `offset_x` by the distance; if it is to the left, increase it. Same for Y
   (cross toward the back: decrease `offset_y`). Restart and repeat until the
   error is under 0.2 mm.

## 2. Cut depth

Cut a 20 mm square with `--max-feed 600`:

```gcode
CUTTER_MODE
G1 X50 Y50 F3000
CUT_PLUNGE
G1 X70 F600
G1 Y70
G1 X50
G1 Y50
CUT_RETRACT
PRINTER_MODE
```

| Result | Change |
|---|---|
| Vinyl not cut through | Lower `z_cut` by 0.05 |
| Backing paper cut | Raise `z_cut` by 0.05, or reduce blade exposure |
| Corners not closed | Lower `cutter_scv`, or add blade offset compensation in Inkcut |
| Corners torn | Lower `cutter_accel` and `--max-feed` |

## 3. Speed

Raise `--max-feed` in steps of 300 until corners start to round, then step back.
1500 mm/min is a safe default for Oracal 651.
