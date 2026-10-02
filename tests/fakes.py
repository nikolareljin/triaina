"""A stand-in for MoonrakerClient that records calls and never touches the network."""

from pathlib import Path

from triaina.printer import ApiError


class FakePrinter:
    def __init__(self):
        self.state = "standby"
        self.filename = ""
        self.online = True
        self.mode = "printer"
        self.calls = []
        self.uploads = []
        self.fail_upload = False

    def snapshot(self):
        if not self.online:
            raise ApiError("GET /printer/objects/query: connection refused")
        return {
            "klippy": "ready",
            "klippy_message": "",
            "state": self.state,
            "filename": self.filename or None,
            "print_duration": 0.0,
            "message": None,
            "progress": 0.0,
            "extruder": {"temperature": 25.0, "target": 0.0},
            "heater_bed": {"temperature": 24.0, "target": 0.0},
            "homed_axes": "xyz",
            "mode": self.mode,
            "blade_down": False,
        }

    def run_gcode(self, script):
        self.calls.append(("gcode", script))
        if script == "CUTTER_MODE":
            self.mode = "cutter"
        elif script == "PRINTER_MODE":
            self.mode = "printer"

    def upload(self, path: Path, start: bool):
        if self.fail_upload:
            raise ApiError("POST /server/files/upload: HTTP 500")
        self.uploads.append((path.name, path.read_text(), start))
        if start:
            self.state, self.filename = "printing", path.name

    def print_action(self, action):
        self.calls.append(("print", action))
        if action == "cancel":
            self.state = "cancelled"

    def emergency_stop(self):
        self.calls.append(("estop",))
