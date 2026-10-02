#!/usr/bin/env python3
"""Switch the Neptune 4 between printer and cutter mode over HTTP.

Talks to Moonraker (Klipper's API server, default) or OctoPrint. Uses only the
standard library so it runs on a fresh Raspberry Pi OS without a venv.

Usage::

    python scripts/mode_switch.py status
    python scripts/mode_switch.py cutter --host mkspi.local
    python scripts/mode_switch.py printer --backend octoprint --host octopi.local
    python scripts/mode_switch.py upload sticker.cut.gcode --start

OctoPrint needs an API key: pass ``--api-key`` or set ``OCTOPRINT_API_KEY``.
Moonraker accepts ``--api-key`` too (``X-Api-Key``) when its auth is enabled.

Exit codes: 0 success, 1 HTTP, network or file error, 3 refused because the
printer is busy printing (mode switch or upload --start), 2 bad arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Optional

__all__ = ["ApiError", "Client", "MoonrakerClient", "OctoPrintClient", "main", "make_client"]

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

    def request(
        self,
        method: str,
        path: str,
        body: Optional[dict] = None,
        raw: Optional[bytes] = None,
        content_type: str = "application/json",
    ) -> Any:
        data = raw
        if data is None and body is not None:
            data = json.dumps(body).encode()
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", content_type)
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

    def upload(self, path: Path, start: bool) -> None:
        raise NotImplementedError

    def _post_file(self, url_path: str, path: Path, fields: dict) -> Any:
        body, content_type = multipart(fields, path.name, path.read_bytes())
        return self.request("POST", url_path, raw=body, content_type=content_type)


def multipart(fields: dict, filename: str, content: bytes) -> tuple[bytes, str]:
    """Encode form fields plus one file as multipart/form-data."""
    boundary = uuid.uuid4().hex
    # Quotes or line breaks in the name would end the header early.
    filename = filename.replace("\\", "_").replace('"', "_").replace("\r", "").replace("\n", "")
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        + content
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class MoonrakerClient(Client):
    """Moonraker: https://moonraker.readthedocs.io/en/latest/external_api/introduction/"""

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

    #: Objects the dashboard shows. Field lists keep the response small.
    SNAPSHOT_OBJECTS = {
        "webhooks": "state,state_message",
        "print_stats": "state,filename,print_duration,message",
        "virtual_sdcard": "progress,is_active",
        "display_status": "progress,message",
        "extruder": "temperature,target",
        "heater_bed": "temperature,target",
        "toolhead": "homed_axes,position,axis_minimum,axis_maximum",
        "gcode_macro _TRIAINA_VARS": "mode,blade_down,offset_x,offset_y",
    }

    def snapshot(self) -> dict:
        """One flat dict of everything the dashboard shows."""
        query = urllib.parse.urlencode(self.SNAPSHOT_OBJECTS)
        result = self.request("GET", f"/printer/objects/query?{query}")
        st = (result or {}).get("result", {}).get("status", {})
        stats = st.get("print_stats", {})
        sd = st.get("virtual_sdcard", {})
        macro = st.get("gcode_macro _TRIAINA_VARS")
        return {
            "klippy": st.get("webhooks", {}).get("state", "unknown"),
            "klippy_message": st.get("webhooks", {}).get("state_message", ""),
            "state": stats.get("state", "unknown"),
            "filename": stats.get("filename") or None,
            "print_duration": stats.get("print_duration", 0.0),
            "message": stats.get("message") or st.get("display_status", {}).get("message"),
            "progress": sd.get("progress", 0.0),
            "extruder": st.get("extruder", {}),
            "heater_bed": st.get("heater_bed", {}),
            "homed_axes": st.get("toolhead", {}).get("homed_axes", ""),
            # Axis limits [x, y, z, e] and knife offset: the service derives the
            # area the knife can reach without the nozzle leaving its range.
            "axis_minimum": st.get("toolhead", {}).get("axis_minimum"),
            "axis_maximum": st.get("toolhead", {}).get("axis_maximum"),
            "knife_offset": (
                [macro.get("offset_x"), macro.get("offset_y")]
                if macro and macro.get("offset_x") is not None
                else None
            ),
            "mode": macro.get("mode") if macro else None,
            "blade_down": macro.get("blade_down") if macro else None,
        }

    def start(self, filename: str) -> None:
        query = urllib.parse.urlencode({"filename": filename})
        self.request("POST", f"/printer/print/start?{query}")

    def print_action(self, action: str) -> None:
        """pause, resume or cancel the current job."""
        if action not in ("pause", "resume", "cancel"):
            raise ValueError(f"unknown print action: {action}")
        self.request("POST", f"/printer/print/{action}")

    def emergency_stop(self) -> None:
        self.request("POST", "/printer/emergency_stop")

    def firmware_restart(self) -> None:
        self.request("POST", "/printer/firmware_restart")

    def server_info(self) -> dict:
        """Moonraker's own state. Answers even when Klipper is shut down or
        disconnected, when object queries may fail."""
        result = self.request("GET", "/server/info") or {}
        return result.get("result", {})

    def upload(self, path: Path, start: bool) -> None:
        fields = {"root": "gcodes"}
        if start:
            fields["print"] = "true"
        self._post_file("/server/files/upload", path, fields)


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

    def upload(self, path: Path, start: bool) -> None:
        fields = {"select": "true", "print": "true"} if start else {}
        self._post_file("/api/files/local", path, fields)


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
        prog="mode_switch.py",
        description=(
            "Query or switch triaina printer/cutter mode, or upload a job,"
            " via Moonraker or OctoPrint."
        ),
    )
    parser.add_argument("action", choices=["status", "cutter", "printer", "upload"])
    parser.add_argument("file", nargs="?", type=Path, help="G-code file for upload")
    parser.add_argument(
        "--start", action="store_true", help="upload: start the job after uploading"
    )
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
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.action == "upload":
        if args.file is None:
            parser.error("upload needs a FILE")
        if not args.file.is_file():
            print(f"error: no such file: {args.file}", file=sys.stderr)
            return EXIT_HTTP
    elif args.file is not None or args.start:
        parser.error("FILE and --start only apply to upload")
    port = args.port
    if port is None and args.backend == "moonraker" and "://" not in args.host:
        port = 7125
    client = make_client(args.backend, args.host, port, args.api_key, args.timeout)

    try:
        if args.action == "upload" and not args.start:
            # Uploading never touches a running job, so no status check.
            client.upload(args.file, start=False)
            print(f"uploaded {args.file.name}")
            return 0

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
        if args.action == "upload":
            client.upload(args.file, start=True)
            print(f"uploaded and started {args.file.name}")
            return 0
        client.run_gcode(MODE_MACROS[args.action])
    except (ApiError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_HTTP

    print(f"sent {MODE_MACROS[args.action]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
