"""Tests for scripts/mode_switch.py. urlopen is mocked; no network."""

import io
import json
import urllib.error

import pytest

import triaina.printer as mode_switch


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def calls(monkeypatch):
    """Record requests; reply with the next queued payload."""
    log = {"requests": [], "replies": []}

    def fake_urlopen(req, timeout):
        log["requests"].append(req)
        reply = log["replies"].pop(0)
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(json.dumps(reply).encode())

    monkeypatch.setattr(mode_switch.urllib.request, "urlopen", fake_urlopen)
    return log


def moonraker_status(state="standby", mode="printer"):
    return {
        "result": {
            "status": {
                "print_stats": {"state": state, "filename": ""},
                "gcode_macro _TRIAINA_VARS": {"mode": mode, "blade_down": False},
            }
        }
    }


def test_status_moonraker(calls, capsys):
    calls["replies"] = [moonraker_status(mode="cutter")]
    assert mode_switch.main(["status", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "cutter"
    assert calls["requests"][0].full_url.startswith("http://localhost:7125/printer/objects/query")


def test_cutter_sends_macro(calls):
    calls["replies"] = [moonraker_status(), {"result": "ok"}]
    assert mode_switch.main(["cutter", "--host", "n4.local"]) == 0
    req = calls["requests"][1]
    assert req.full_url == "http://n4.local:7125/printer/gcode/script"
    assert json.loads(req.data) == {"script": "CUTTER_MODE"}


def test_refuses_while_printing(calls, capsys):
    calls["replies"] = [moonraker_status(state="printing")]
    assert mode_switch.main(["cutter"]) == mode_switch.EXIT_BUSY
    assert len(calls["requests"]) == 1


def test_force_while_printing(calls):
    calls["replies"] = [moonraker_status(state="printing"), {}]
    assert mode_switch.main(["printer", "--force"]) == 0


def test_octoprint_uses_key_and_command_endpoint(calls):
    calls["replies"] = [{"state": "Operational"}, {}]
    assert (
        mode_switch.main(
            ["printer", "--backend", "octoprint", "--host", "octopi", "--api-key", "k"]
        )
        == 0
    )
    req = calls["requests"][1]
    assert req.full_url == "http://octopi/api/printer/command"
    assert req.get_header("X-api-key") == "k"
    assert json.loads(req.data) == {"commands": ["PRINTER_MODE"]}


def test_octoprint_printing_from_sd_is_busy(calls):
    calls["replies"] = [{"state": "Printing from SD"}]
    assert mode_switch.main(["cutter", "--backend", "octoprint"]) == mode_switch.EXIT_BUSY


def test_network_error(calls, capsys):
    calls["replies"] = [urllib.error.URLError("refused")]
    assert mode_switch.main(["status"]) == mode_switch.EXIT_HTTP
    assert "refused" in capsys.readouterr().err


def test_http_error(calls, capsys):
    calls["replies"] = [urllib.error.HTTPError("u", 401, "no", {}, io.BytesIO(b"denied"))]
    assert mode_switch.main(["status"]) == mode_switch.EXIT_HTTP
    assert "HTTP 401" in capsys.readouterr().err


def test_missing_macros_reported_as_none(calls, capsys):
    calls["replies"] = [{"result": {"status": {"print_stats": {"state": "ready"}}}}]
    assert mode_switch.main(["status"]) == 0
    assert "n/a" in capsys.readouterr().out


def test_upload_moonraker_multipart(calls, tmp_path):
    job = tmp_path / "sticker.cut.gcode"
    job.write_text("CUTTER_MODE\n")
    calls["replies"] = [moonraker_status(), {"result": {}}]
    assert mode_switch.main(["upload", str(job), "--start"]) == 0
    req = calls["requests"][1]
    assert req.full_url == "http://localhost:7125/server/files/upload"
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert b'name="print"\r\n\r\ntrue' in req.data
    assert b'filename="sticker.cut.gcode"' in req.data and b"CUTTER_MODE" in req.data


def test_upload_without_start_skips_busy_check(calls, tmp_path):
    job = tmp_path / "a.gcode"
    job.write_text("G1 X1\n")
    calls["replies"] = [{}]
    assert mode_switch.main(["upload", str(job)]) == 0
    assert len(calls["requests"]) == 1
    assert b'name="print"' not in calls["requests"][0].data


def test_upload_start_refused_while_printing(calls, tmp_path):
    job = tmp_path / "a.gcode"
    job.write_text("G1 X1\n")
    calls["replies"] = [moonraker_status(state="printing")]
    assert mode_switch.main(["upload", str(job), "--start"]) == mode_switch.EXIT_BUSY


def test_upload_octoprint_endpoint(calls, tmp_path):
    job = tmp_path / "a.gcode"
    job.write_text("G1 X1\n")
    calls["replies"] = [{"state": "Operational"}, {}]
    assert mode_switch.main(["upload", str(job), "--backend", "octoprint", "--start"]) == 0
    assert calls["requests"][1].full_url == "http://localhost/api/files/local"


def test_upload_missing_file(calls, tmp_path, capsys):
    assert mode_switch.main(["upload", str(tmp_path / "nope.gcode")]) == mode_switch.EXIT_HTTP
    assert "no such file" in capsys.readouterr().err


def test_upload_needs_file():
    with pytest.raises(SystemExit) as exc:
        mode_switch.main(["upload"])
    assert exc.value.code == 2


def test_start_rejected_for_mode_switch():
    with pytest.raises(SystemExit) as exc:
        mode_switch.main(["cutter", "--start"])
    assert exc.value.code == 2


def test_multipart_filename_cannot_break_header():
    body, _ = mode_switch.multipart({}, 'a"b\r\nX-Evil: 1.gcode', b"G1")
    assert b'filename="a_bX-Evil: 1.gcode"' in body
    assert b"\r\nX-Evil" not in body
