# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `CUT_PLUNGE refused: run CUTTER_MODE first` | File built with `--no-wrap`, or mode reset by a restart | Run `CUTTER_MODE` or rebuild without `--no-wrap` |
| `CUT_PLUNGE refused: home all axes` | Klipper restarted since the last `G28` | `G28` |
| `Unknown command: "CUTTER_MODE"` | Macros not included | [Klipper macros](../setup/klipper.md) step 2 |
| `mode_switch.py` exit 1, `Connection refused` | Wrong host, or port 7125 blocked | `curl http://<host>:7125/server/info`; check `TRIAINA_HOST` |
| `mode_switch.py upload` exit 1, `no such file` | Wrong path | Check the path; it is relative to where you run it |
| `mode_switch.py` exit 1, `HTTP 401` | Moonraker or OctoPrint auth on | Pass `--api-key` |
| `/dev/triaina` missing (console cable) | Rule not installed, or other USB bridge | Replug; `lsusb`; `setup_pi.sh --udev --vid XXXX --pid XXXX` |
| Pi shows a lightning bolt / undervoltage | Weak supply, or back-feed over the console cable | Official PSU; check the Kapton tape |
| Printer LEDs on with printer switched off | 5 V back-feed | Tape slipped; redo it or use a blocker |
| Cut shifted by a constant amount | Offset wrong | [Calibrating the knife](../setup/calibration.md) step 1 |
| Rounded or open corners | Too fast, or no blade-offset compensation | Lower `--max-feed`; use Inkcut's blade offset filter |
