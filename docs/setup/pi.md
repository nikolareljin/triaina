# Raspberry Pi setup

Wire the Pi first: [Wiring the Raspberry Pi](../hardware/wiring.md).

## 1. Operating system

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on
   your laptop.
2. Choose **Raspberry Pi 3**, **Raspberry Pi OS Lite (64-bit)** (Bookworm or
   newer), and your microSD card.
3. In the settings dialog: host name `triaina`, user name and password, Wi-Fi
   (if not using Ethernet), locale, and **Enable SSH**.
4. Write, insert the card, power the Pi, wait about a minute, then:

    ```bash
    ssh <user>@triaina.local
    ```

OctoPi also works; the steps below are the same.

## 2. Clone triaina

```bash
sudo apt-get update && sudo apt-get install -y git
git clone --recursive https://github.com/nikolareljin/triaina.git
cd triaina
```

`--recursive` fetches [script-helpers](https://github.com/nikolareljin/script-helpers)
into `scripts/script-helpers`. If you forgot it: `git submodule update --init`.

## 3. Run the setup script

```bash
scripts/setup_pi.sh
```

It installs the apt packages and the Python venv. Add `--udev` only if you
connect the optional [console cable](../hardware/wiring.md#optional-usb-c-console-cable).
Preview what it would do with `--dry-run`. Every option is in
[setup_pi.sh reference](../reference/setup-pi.md).

## 4. Point the scripts at the printer

```bash
echo 'export TRIAINA_HOST=mkspi.local' >> ~/.bashrc
source ~/.bashrc
.venv/bin/python scripts/mode_switch.py status
```

Expected before the macros are installed:

```text
state      standby
filename   n/a
mode       n/a
blade_down n/a
```

`mode n/a` means Klipper has no `_TRIAINA_VARS` yet. Next:
[Klipper macros](klipper.md).

## 5. Dashboard service

`scripts/setup_pi.sh --service` installs the dashboard as a service that
starts on boot. See [Dashboard service](service.md).

## 6. Optional camera

Connect the Camera Module ribbon with the contacts facing the HDMI port, then
install `crowsnest` with [KIAUH](https://github.com/dw-0/kiauh) (or use OctoPi's built-in streamer) and add the stream URL
to Fluidd under Settings > Cameras.
