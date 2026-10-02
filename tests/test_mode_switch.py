"""Tests for scripts/mode_switch.py. urlopen is mocked; no network."""

import io
import json
import urllib.error

import pytest

import mode_switch


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
