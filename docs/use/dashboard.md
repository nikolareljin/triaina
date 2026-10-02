# Dashboard

Open `http://triaina.local:8080/` from any device on your network. The service
must be installed first: [Dashboard service](../setup/service.md).

## Printer panel

Live, once a second: Klipper state, print state, triaina mode (printer or
cutter), blade up or down, nozzle and bed temperature, homed axes, current file
and progress.

| Button | Does | Allowed when |
|---|---|---|
| Cutter mode | Runs `CUTTER_MODE` | Printer online and idle |
| Printer mode | Runs `PRINTER_MODE` | Printer online and idle |
| Pause / Resume / Cancel | Moonraker print controls | A job is printing or paused |
| Emergency stop | Moonraker `emergency_stop`; Klipper halts and needs a firmware restart | Always (asks first) |
| Firmware restart | Moonraker `firmware_restart`; brings Klipper back | Shown only while Klipper is not ready (after an emergency stop or an error) |

When Klipper is shut down or in error but Moonraker answers, the panel says
`Klipper shutdown: <reason>` rather than "offline". "Offline" means the
printer does not answer at all.

"macros not installed" in the Mode field means `printer.cfg` does not include
the [triaina macros](../setup/klipper.md).

## Jobs

1. **New job**: choose the type and drop a file.

    | Type | Accepts | What happens |
    |---|---|---|
    | Cut design | SVG, DXF, PDF, AI, EPS, PNG, JPG | Converted on the Pi with blade-offset compensation and a preview; see [Cutting a design file](designs.md) |
    | Cut G-code | G-code from Kiri:Moto, Inkcut, Inkscape, LightBurn | Run through the [preprocessor](../reference/gcode-preprocessor.md): heaters and extruder removed, knife macros added, feed capped |
    | Print G-code | Sliced G-code | Sent unchanged |

    The job is now **ready** (a design is **converting** first). Nothing has
    been sent to the printer. Check the preview and details, or download the
    generated G-code from the job row.
2. **Start**: confirm the physical setup shown in the dialog (knife holder
    fitted and hotend cold for a cut; holder removed for a print). The service
    cannot see the toolhead, so this is your check.
3. The file is uploaded to the printer as `triaina-<id>-<name>.gcode` and
    started. The job follows the printer: **running**, then **done**,
    **cancelled** or **failed**.

A job will not start while the printer is printing or paused, while another
triaina job is active, or while Klipper is not ready.

## Camera

Set `[camera] stream_url` to an MJPEG stream (crowsnest on the printer or the
Pi) and the camera panel appears.

## API

The dashboard is a client of the service's REST API. Interactive docs are at
`http://triaina.local:8080/api/docs`.

| Method | Path | Does |
|---|---|---|
| GET | `/api/status` | Printer snapshot |
| GET | `/api/jobs` | Recent jobs |
| POST | `/api/jobs` | Upload: `kind`, `file`; design options `width`, `fit`, `weed`, `blade_offset`, `cut_feed`, `threshold`, `invert` (multipart) |
| POST | `/api/jobs/{id}/start` | `{"confirm": true}` |
| DELETE | `/api/jobs/{id}` | Discard a ready job |
| GET | `/api/jobs/{id}/output` | Generated G-code |
| GET | `/api/jobs/{id}/preview.svg` | Cut preview (design jobs) |
| POST | `/api/mode/{cutter,printer}` | Mode switch |
| POST | `/api/print/{pause,resume,cancel}` | Print control |
| POST | `/api/estop` | Emergency stop |
| POST | `/api/firmware-restart` | Firmware restart |
| WS | `/ws` | Live status and jobs |
| GET | `/healthz` | Liveness (no token needed) |
