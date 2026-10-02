# Inkcut

[Inkcut](https://github.com/inkcut/inkcut) sends vector files straight to a
cutter, with blade offset compensation that Inkscape exports lack.

Values to enter are in [`config/inkcut_profile.json`](../reference/inkcut-profile.md).

1. **Device > New**. Name `triaina Neptune 4`.
2. **Connection**: Serial, port `/dev/triaina`, baud 250000 (Topology B only).
   For Topology A, choose **Printer / file output** and save to a file, then
   run it through the preprocessor and upload as in
   [Cutting a sticker](workflow.md).
3. **Protocol**: G-code. Header and footer from the profile.
4. **Area**: 225 x 225 mm.
5. **Filters > Blade offset**: 0.25 mm, cutoff 20 deg.
6. **Speed**: 1500 mm/min.

Even with direct serial, keep `CUTTER_MODE` in the header: it is what zeroes the
heaters and applies the knife offset.
