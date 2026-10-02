"""A tiny Moonraker stand-in on loopback, for end-to-end tests and local demos.

Implements only what triaina calls. Uploads are parsed with the stdlib email
parser, independent of triaina's encoder, so a malformed body fails here.

    python tests/fake_moonraker.py 7125     # demo: point the dashboard at it
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from email.parser import BytesParser
from email.policy import default


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.files: dict[str, bytes] = {}
        self.form: dict[str, str] = {}
        self.print_state = "standby"
        self.filename = ""
        self.mode = "printer"
        self.scripts: list[str] = []


def parse_multipart(body: bytes, content_type: str) -> tuple[dict, dict]:
    """Parse multipart/form-data with the stdlib email parser (independent of the encoder)."""
    msg = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body
    )
    if not msg.is_multipart():
        raise ValueError("not multipart")
    fields, files = {}, {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        filename = part.get_param("filename", header="content-disposition")
        data = part.get_payload(decode=True)
        if filename is not None:
            files[name] = (filename, data)
        else:
            fields[name] = data.decode()
    return fields, files


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def reply(self, code: int, obj) -> None:
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/printer/objects/query":
                with state.lock:
                    status = {
                        "webhooks": {"state": "ready", "state_message": "Printer is ready"},
                        "print_stats": {
                            "state": state.print_state,
                            "filename": state.filename,
                            "print_duration": 0.0,
                            "message": "",
                        },
                        "virtual_sdcard": {
                            "progress": 0.42 if state.print_state == "printing" else 0.0
                        },
                        "display_status": {"progress": 0.0, "message": None},
                        "extruder": {"temperature": 24.6, "target": 0.0},
                        "heater_bed": {"temperature": 23.9, "target": 0.0},
                        "toolhead": {
                            "homed_axes": "xyz",
                            "position": [0, 0, 3, 0],
                            "axis_minimum": [-2, -3, -2, 0],
                            "axis_maximum": [235, 230, 265, 0],
                        },
                        "gcode_macro _TRIAINA_VARS": {
                            "mode": state.mode,
                            "blade_down": False,
                            "offset_x": 32.0,
                            "offset_y": -5.0,
                        },
                    }
                wanted = parse_qs(url.query, keep_blank_values=True)
                self.reply(
                    200, {"result": {"status": {k: v for k, v in status.items() if k in wanted}}}
                )
            elif url.path == "/server/info":
                self.reply(200, {"result": {"klippy_state": "ready"}})
            else:
                self.reply(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            with state.lock:
                if url.path == "/server/files/upload":
                    fields, files = parse_multipart(body, self.headers["Content-Type"])
                    name, data = files["file"]
                    state.files[name] = data
                    state.form = fields
                    if fields.get("print") == "true":
                        state.print_state, state.filename = "printing", name
                    self.reply(201, {"result": {"item": {"path": name}}})
                elif url.path == "/printer/gcode/script":
                    script = json.loads(body)["script"]
                    state.scripts.append(script)
                    state.mode = {"CUTTER_MODE": "cutter", "PRINTER_MODE": "printer"}.get(
                        script, state.mode
                    )
                    self.reply(200, {"result": "ok"})
                elif url.path.startswith("/printer/print/"):
                    action = url.path.rsplit("/", 1)[-1]
                    state.print_state = {
                        "pause": "paused",
                        "resume": "printing",
                        "cancel": "cancelled",
                    }.get(action, state.print_state)
                    self.reply(200, {"result": "ok"})
                elif url.path == "/printer/emergency_stop":
                    state.scripts.append("M112")
                    self.reply(200, {"result": "ok"})
                else:
                    self.reply(404, {"error": "not found"})

    return Handler


def serve(port: int = 0) -> tuple[ThreadingHTTPServer, State]:
    state = State()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, state


if __name__ == "__main__":
    srv, _ = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 7125)
    print(f"fake Moonraker on http://127.0.0.1:{srv.server_address[1]}")
    threading.Event().wait()
