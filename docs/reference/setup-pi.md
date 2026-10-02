# setup_pi.sh

File: [`scripts/setup_pi.sh`](https://github.com/nikolareljin/triaina/blob/main/scripts/setup_pi.sh).
Run on the Raspberry Pi, from the repository root. Idempotent: run it again
after a `git pull` or after swapping the mainboard.

```bash
scripts/setup_pi.sh [--udev [--vid XXXX --pid XXXX]] [--skip-apt] [--dry-run]
```

| Option | Meaning |
|---|---|
| `--udev` | Also install the udev rule for the optional console cable |
| `--vid`, `--pid` | USB id of the console bridge (4 hex digits each). Only with `--udev`. Default: detect |
| `--skip-apt` | Do not install apt packages |
| `--dry-run` | Print privileged commands instead of running them |
| `--skip-udev` | Accepted for old scripts; ignored, since no rule is written by default |

## Steps

1. Installs `python3 python3-venv python3-pip usbutils` if any are missing.
2. Creates `.venv` (or reuses it) and installs `requirements.txt`.
3. With `--udev` only:
    1. Detects the console bridge behind the printer's USB-C port with `lsusb`.
       Known ids, first match wins:

        | VID:PID | Device |
        |---|---|
        | `1a86:7523` | CH340 |
        | `10c4:ea60` | CP210x |

        If neither is connected it stops and asks for `--vid/--pid`. It never guesses.
    2. Writes `/etc/udev/rules.d/99-triaina.rules` only if the content differs,
       then reloads udev. The console is then `/dev/triaina`
       (`screen /dev/triaina 1500000`).
    3. Adds the user to `dialout` if needed (log out and in to apply).

The printer's USB-C port is a console to its Linux host, not a link to the
MCU, so no rule is needed for normal use.

Uses [script-helpers](https://github.com/nikolareljin/script-helpers) for
logging when the submodule is present, and falls back to local functions when
it is not.
