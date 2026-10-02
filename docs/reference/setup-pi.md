# setup_pi.sh

File: [`scripts/setup_pi.sh`](https://github.com/nikolareljin/triaina/blob/main/scripts/setup_pi.sh).
Run on the Raspberry Pi, from the repository root. Idempotent: run it again
after a `git pull` or after swapping the mainboard.

```bash
scripts/setup_pi.sh [--vid XXXX --pid XXXX] [--skip-apt] [--skip-udev] [--dry-run]
```

| Option | Meaning |
|---|---|
| `--vid`, `--pid` | USB vendor and product id of the mainboard (4 hex digits each). Default: detect |
| `--skip-apt` | Do not install apt packages |
| `--skip-udev` | Do not write the udev rule or touch group membership |
| `--dry-run` | Print privileged commands instead of running them |

## Steps

1. Installs `python3 python3-venv python3-pip usbutils` if any are missing.
2. Creates `.venv` (or reuses it) and installs `requirements.txt`.
3. Detects the mainboard with `lsusb`. Known ids, first match wins:

    | VID:PID | Device |
    |---|---|
    | `1d50:614e` | Klipper firmware with native USB on the STM32 |
    | `1a86:7523` | CH340 USB-serial bridge |

    If neither is connected it stops and asks for `--vid/--pid` (read them from
    `lsusb`). It never guesses.
4. Writes `/etc/udev/rules.d/99-triaina.rules` only if the content differs:

    ```
    SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="triaina", MODE="0660", GROUP="dialout"
    ```

    then `udevadm control --reload-rules` and `udevadm trigger`.
5. Adds the user to `dialout` if needed (log out and in to apply).

Uses [script-helpers](https://github.com/nikolareljin/script-helpers) for
logging when the submodule is present, and falls back to local functions when
it is not.
