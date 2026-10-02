# Inkcut

[Inkcut](https://github.com/inkcut/inkcut) sends vector files straight to a
cutter, with blade offset compensation that Inkscape exports lack.

Values to enter are in [`config/inkcut_profile.json`](../reference/inkcut-profile.md).

1. **Device > New**. Name `triaina Neptune 4`.
2. **Connection**: choose file output and save the job to a file. The printer
   has no serial port for cut jobs (its USB-C is a console); run the file
   through the preprocessor and upload it as in [Cutting a sticker](workflow.md).
3. **Protocol**: G-code. Header and footer from the profile.
4. **Area**: 225 x 225 mm.
5. **Filters > Blade offset**: 0.25 mm, cutoff 20 deg.
6. **Speed**: 1500 mm/min.

The preprocessor adds the `CUTTER_MODE` header that zeroes the heaters and
applies the knife offset.
