# Dashboard service

The triaina service runs on the Raspberry Pi as a systemd unit. It starts on
boot, restarts within 5 s if it crashes, and serves the
[dashboard](../use/dashboard.md) on your LAN:

```text
http://triaina.local:8080/
```

It talks to the printer's Moonraker over the network, like Fluidd does. Nothing
is installed on the printer apart from the [Klipper macros](klipper.md).

## Install

On the Pi, in the triaina clone ([Raspberry Pi setup](pi.md) first):

```bash
scripts/setup_pi.sh --service
sudo nano /etc/triaina/config.toml      # set [printer] host
sudo systemctl restart triaina
```

The script is idempotent. To update after `git pull`, run it again: it
reinstalls the package and restarts the service. It never overwrites an
existing config file.

| What | Where |
|---|---|
| Code and venv | `/opt/triaina/.venv` |
| Config | `/etc/triaina/config.toml` (from [`deploy/config.example.toml`](https://github.com/nikolareljin/triaina/blob/main/deploy/config.example.toml)) |
| Jobs database, uploads, generated G-code | `/var/lib/triaina` |
| Unit | `/etc/systemd/system/triaina.service` (from [`deploy/triaina.service`](https://github.com/nikolareljin/triaina/blob/main/deploy/triaina.service)) |
| Runs as | system user `triaina`, no login shell |
| Logs | `journalctl -u triaina -f` |

## Configuration

| Section | Key | Default | Meaning |
|---|---|---|---|
| `[printer]` | `host` | `neptune4.local` | Printer address or full URL |
| | `port` | `7125` | Moonraker port |
| | `api_key` | none | Only if Moonraker authorization is on |
| | `web_url` | `http://<host>/` | Fluidd link in the dashboard |
| `[server]` | `bind` | `0.0.0.0` | Listen address on the Pi |
| | `port` | `8080` | Dashboard port |
| | `auth_token` | none | Require a token; see below |
| `[paths]` | `data_dir` | `/var/lib/triaina` | Jobs and files |
| `[cut]` | `max_feed`, `default_feed`, `z_threshold` | `1500`, `1500`, `0` | Preprocessor settings for cut jobs |
| `[camera]` | `stream_url` | none | MJPEG stream shown on the dashboard |

An unknown key or section stops the service with a clear error in the journal
instead of being ignored.

## Local only

The service is for your home network. It has no TLS and, by default, no login.
To require a token, set `[server] auth_token` to a long random string
(`openssl rand -hex 24`), restart, and open the dashboard once as
`http://triaina.local:8080/?token=<token>`; the browser remembers it. API
clients send `Authorization: Bearer <token>`.

Do not forward port 8080 from your router. For remote access use a VPN to your
home network.

## Behaviour on restart

| Situation | What happens |
|---|---|
| Pi reboots | Service starts after the network is up; the dashboard is back within about a minute |
| Service crashes | systemd restarts it after 5 s |
| A job was being uploaded | Marked failed ("interrupted by a service restart"); start it again |
| A job was running on the printer | Keeps running on the printer; the dashboard picks it up again from Moonraker |
| Printer offline | Dashboard shows "offline" and keeps polling; nothing is sent |
| Klipper restarts mid-job | The job is marked failed after 15 s ("printer restarted during the job") |

## Uninstall

```bash
sudo systemctl disable --now triaina
sudo rm /etc/systemd/system/triaina.service && sudo systemctl daemon-reload
sudo rm -rf /opt/triaina            # keep /etc/triaina and /var/lib/triaina if you may reinstall
```
