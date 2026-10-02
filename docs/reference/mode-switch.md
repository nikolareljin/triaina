# mode_switch.py

CLI: [`scripts/mode_switch.py`](https://github.com/nikolareljin/triaina/blob/main/scripts/mode_switch.py), code in
[`triaina/printer.py`](https://github.com/nikolareljin/triaina/blob/main/triaina/printer.py) (also used by the service).
Standard library only. Runs from the Pi or from any machine on the same network.

```bash
python3 scripts/mode_switch.py {status,cutter,printer} [options]
python3 scripts/mode_switch.py upload FILE [--start] [options]
```

## Options

| Option | Default | Meaning |
|---|---|---|
| `--backend` | `moonraker` | `moonraker` or `octoprint` |
| `--host` | `$TRIAINA_HOST` or `localhost` | Host name or full URL |
| `--port` | `7125` for Moonraker, none for OctoPrint | Port override |
| `--api-key` | `$OCTOPRINT_API_KEY` | Sent as `X-Api-Key`. Required by OctoPrint |
| `--timeout` | `10` | Seconds per request |
| `--force` | off | Switch even while a print is running |
| `--json` | off | `status` as JSON |
| `FILE` | | G-code to upload (`upload` only) |
| `--start` | off | Start the job after uploading (`upload` only) |

Exit codes: `0` success, `1` HTTP, network or file error, `2` bad arguments,
`3` refused because the printer is printing (mode switch, or `upload --start`).
A plain `upload` without `--start` is allowed while printing.

## Endpoints used

| Backend | Status | Send command |
|---|---|---|
| Moonraker | `GET /printer/objects/query?print_stats&gcode_macro _TRIAINA_VARS` | `POST /printer/gcode/script` `{"script": "CUTTER_MODE"}` |
| OctoPrint | `GET /api/job` | `POST /api/printer/command` `{"commands": ["CUTTER_MODE"]}` |

Uploads are `multipart/form-data`: Moonraker `POST /server/files/upload`
(`root=gcodes`, plus `print=true` with `--start`); OctoPrint
`POST /api/files/local` (plus `select=true`, `print=true` with `--start`).

OctoPrint cannot read Klipper macro variables, so `mode` and `blade_down`
show `n/a` there. With Moonraker, `mode: n/a` means the macros are not
included in `printer.cfg`.

## Examples

```bash
python3 scripts/mode_switch.py status --host neptune4.local
python3 scripts/mode_switch.py cutter --host neptune4.local
python3 scripts/mode_switch.py upload sticker.cut.gcode --start --host neptune4.local
OCTOPRINT_API_KEY=... python3 scripts/mode_switch.py printer --backend octoprint --host octopi.local
```

Never put an API key in a shell history you share; prefer the environment
variable.
