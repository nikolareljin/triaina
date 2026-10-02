#!/usr/bin/env python3
"""Switch the Neptune 4 between printer and cutter mode over HTTP.

Talks to Moonraker (Klipper's API server, default) or OctoPrint. Uses only the
standard library so it runs on a fresh Raspberry Pi OS without a venv.

Usage::

    python scripts/mode_switch.py status
    python scripts/mode_switch.py cutter --host neptune4.local
    python scripts/mode_switch.py printer --backend octoprint --host octopi.local

OctoPrint needs an API key: pass ``--api-key`` or set ``OCTOPRINT_API_KEY``.
Moonraker accepts ``--api-key`` too (``X-Api-Key``) when its auth is enabled.

Exit codes: 0 success, 1 HTTP or network failure, 3 refused because the
printer is busy printing, 2 bad arguments (argparse).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

__all__ = ["Client", "MoonrakerClient", "OctoPrintClient", "main"]

MODE_MACROS = {"cutter": "CUTTER_MODE", "printer": "PRINTER_MODE"}
EXIT_HTTP = 1
EXIT_BUSY = 3


class ApiError(RuntimeError):
    """Raised for any HTTP, network or decoding failure."""


class Client:
    """Minimal JSON-over-HTTP client shared by both backends."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("X-Api-Key", self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise ApiError(f"{method} {path}: HTTP {exc.code} {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise ApiError(f"{method} {path}: {reason}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise ApiError(f"{method} {path}: response is not JSON") from exc

    def status(self) -> dict:
        raise NotImplementedError

    def run_gcode(self, script: str) -> None:
        raise NotImplementedError


class MoonrakerClient(Client):
    """Moonraker: https://moonraker.readthedocs.io/en/latest/web_api/"""

    def status(self) -> dict:
        query = urllib.parse.urlencode(
            {"print_stats": "state,filename", "gcode_macro _TRIAINA_VARS": "mode,blade_down"}
        )
        result = self.request("GET", f"/printer/objects/query?{query}")
        status = (result or {}).get("result", {}).get("status", {})
        stats = status.get("print_stats", {})
        macro = status.get("gcode_macro _TRIAINA_VARS")
        return {
            "state": stats.get("state", "unknown"),
            "filename": stats.get("filename") or None,
            # None means the macros are not installed in printer.cfg.
            "mode": macro.get("mode") if macro else None,
            "blade_down": macro.get("blade_down") if macro else None,
        }

    def run_gcode(self, script: str) -> None:
        self.request("POST", "/printer/gcode/script", {"script": script})


class OctoPrintClient(Client):
    """OctoPrint: https://docs.octoprint.org/en/master/api/"""

    def status(self) -> dict:
        job = self.request("GET", "/api/job") or {}
        state = str(job.get("state", "unknown")).lower()
        return {
            # Normalise OctoPrint's "Printing from SD" etc. to Moonraker words.
            "state": "printing" if state.startswith("printing") else state,
            "filename": ((job.get("job") or {}).get("file") or {}).get("name"),
            # OctoPrint cannot read Klipper macro variables.
            "mode": None,
            "blade_down": None,
        }

    def run_gcode(self, script: str) -> None:
        self.request("POST", "/api/printer/command", {"commands": script.splitlines()})


def make_client(
    backend: str, host: str, port: Optional[int], api_key: Optional[str], timeout: float
) -> Client:
    scheme_host = host if "://" in host else f"http://{host}"
    if port:
        scheme_host = f"{scheme_host}:{port}"
    cls = MoonrakerClient if backend == "moonraker" else OctoPrintClient
    return cls(scheme_host, api_key=api_key, timeout=timeout)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mode_switch",
        description="Query or switch triaina printer/cutter mode via Moonraker or OctoPrint.",
    )
    parser.add_argument("action", choices=["status", "cutter", "printer"])
    parser.add_argument("--backend", choices=["moonraker", "octoprint"], default="moonraker")
    parser.add_argument(
        "--host",
        default=os.environ.get("TRIAINA_HOST", "localhost"),
        help="host name or URL (default: $TRIAINA_HOST or localhost)",
    )
    parser.add_argument("--port", type=int, help="override the port (Moonraker: 7125)")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OCTOPRINT_API_KEY"),
        help="API key (default: $OCTOPRINT_API_KEY)",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per request")
    parser.add_argument(
        "--force", action="store_true", help="switch even while a print is running (dangerous)"
    )
    parser.add_argument("--json", action="store_true", help="print status as JSON")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    port = args.port
    if port is None and args.backend == "moonraker" and "://" not in args.host:
        port = 7125
    client = make_client(args.backend, args.host, port, args.api_key, args.timeout)

    try:
        status = client.status()
        if args.action == "status":
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                for key, value in status.items():
                    print(f"{key:<11}{'n/a' if value is None else value}")
            return 0

        if status["state"] == "printing" and not args.force:
            print("refused: printer is printing; pass --force to override", file=sys.stderr)
            return EXIT_BUSY
        client.run_gcode(MODE_MACROS[args.action])
    except ApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_HTTP

    print(f"sent {MODE_MACROS[args.action]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
