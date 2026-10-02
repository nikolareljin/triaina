"""Tests for the dashboard API. FakePrinter stands in for Moonraker."""

import pytest
from fastapi.testclient import TestClient

from fakes import FakePrinter
from triaina.config import Config
from triaina.jobs import JobStore
from triaina.monitor import Monitor
from triaina.web.app import create_app


@pytest.fixture
def env(tmp_path):
    cfg = Config()
    cfg.paths.data_dir = tmp_path
    printer = FakePrinter()
    app = create_app(cfg, client=printer, start_monitor=False)
    client = TestClient(app)
    app.state.monitor.poll_once()
    return cfg, printer, client, app


def upload(client, kind, text="G1 X1 Y1 F600\n", name="job.gcode", **kw):
    return client.post("/api/jobs", data={"kind": kind}, files={"file": (name, text)}, **kw)


def test_page_and_health(env):
    _, _, client, _ = env
    assert "triaina" in client.get("/").text
    assert client.get("/healthz").json()["ok"] is True
    assert client.get("/logo.svg").status_code == 200


def test_info_lists_kinds(env):
    info = env[2].get("/api/info").json()
    assert set(info["kinds"]) == {"cut-gcode", "print-gcode"}
    assert info["printer_url"] == "http://neptune4.local:7125"


def test_cut_job_is_preprocessed(env):
    _, printer, client, _ = env
    job = upload(client, "cut-gcode", "M104 S200\nM3\nG1 X10 Y10 E1 F9000\nM5\n").json()
    assert job["state"] == "ready" and job["has_output"] is True and "output" not in job
    out = client.get(f"/api/jobs/{job['id']}/output").text
    assert "CUTTER_MODE" in out and "M104 S" not in out and " E1" not in out and "F1500" in out


def test_print_job_is_unchanged(env):
    job = upload(env[2], "print-gcode", "M104 S200\nG1 X1 E1\n").json()
    assert env[2].get(f"/api/jobs/{job['id']}/output").text == "M104 S200\nG1 X1 E1\n"


def test_upload_rejects_wrong_type_and_kind(env):
    client = env[2]
    assert upload(client, "print-gcode", name="cat.png").status_code == 415
    assert upload(client, "laser").status_code == 422


def test_start_needs_confirmation(env):
    _, printer, client, _ = env
    job = upload(client, "print-gcode").json()
    r = client.post(f"/api/jobs/{job['id']}/start", json={})
    assert r.status_code == 428
    assert printer.uploads == []


def test_start_uploads_and_runs(env):
    _, printer, client, _ = env
    job = upload(client, "cut-gcode").json()
    r = client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True})
    assert r.status_code == 200 and r.json()["state"] == "running"
    name, text, start = printer.uploads[0]
    assert name == f"triaina-{job['id']}-job.gcode" and start is True and "CUTTER_MODE" in text
    # A second job cannot start while one is active.
    job2 = upload(client, "print-gcode").json()
    assert client.post(f"/api/jobs/{job2['id']}/start", json={"confirm": True}).status_code == 409


def test_start_refused_while_printer_busy(env):
    _, printer, client, app = env
    printer.state = "printing"
    app.state.monitor.poll_once()
    job = upload(client, "print-gcode").json()
    r = client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True})
    assert r.status_code == 409 and "printing" in r.json()["detail"]


def test_failed_upload_marks_job_failed(env):
    _, printer, client, _ = env
    printer.fail_upload = True
    job = upload(client, "print-gcode").json()
    assert client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True}).status_code == 502
    assert client.get(f"/api/jobs/{job['id']}").json()["state"] == "failed"


def test_offline_printer(env):
    _, printer, client, app = env
    printer.online = False
    app.state.monitor.poll_once()
    r = client.post("/api/mode/cutter")
    assert r.status_code == 503


def test_mode_switch(env):
    _, printer, client, _ = env
    assert client.post("/api/mode/cutter").json()["mode"] == "cutter"
    assert ("gcode", "CUTTER_MODE") in printer.calls
    assert client.post("/api/mode/laser").status_code == 404


def test_print_actions_and_estop(env):
    _, printer, client, _ = env
    assert client.post("/api/print/pause").status_code == 200
    assert client.post("/api/print/explode").status_code == 404
    assert client.post("/api/estop").status_code == 200
    assert ("estop",) in printer.calls


def test_discard(env):
    client = env[2]
    job = upload(client, "print-gcode").json()
    assert client.delete(f"/api/jobs/{job['id']}").json()["state"] == "cancelled"
    assert client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True}).status_code == 409


def test_websocket_pushes_state(env):
    client = env[2]
    upload(client, "print-gcode")
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
    assert msg["status"]["online"] is True and len(msg["jobs"]) == 1


def test_recovery_on_restart(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    job = store.create("print-gcode", "a")
    store.update(job.id, state="sending")
    cfg = Config()
    cfg.paths.data_dir = tmp_path
    create_app(cfg, client=FakePrinter(), start_monitor=False)
    assert JobStore(tmp_path / "jobs.db").get(job.id).state == "failed"


class TestAuth:
    @pytest.fixture
    def client(self, tmp_path):
        cfg = Config()
        cfg.paths.data_dir = tmp_path
        cfg.server.auth_token = "s3cret"
        printer = FakePrinter()
        app = create_app(
            cfg,
            client=printer,
            monitor=Monitor(printer, JobStore(tmp_path / "m.db")),
            start_monitor=False,
        )
        return TestClient(app)

    def test_api_needs_token(self, client):
        assert client.get("/api/status").status_code == 401
        assert (
            client.get("/api/status", headers={"Authorization": "Bearer nope"}).status_code == 401
        )
        assert (
            client.get("/api/status", headers={"Authorization": "Bearer s3cret"}).status_code == 200
        )
        assert client.get("/api/status?token=s3cret").status_code == 200

    def test_page_and_health_stay_open(self, client):
        assert client.get("/").status_code == 200
        assert client.get("/healthz").status_code == 200

    def test_websocket_needs_token(self, client):
        from starlette.websockets import WebSocketDisconnect

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws") as ws:
                ws.receive_json()
        with client.websocket_connect("/ws?token=s3cret") as ws:
            assert "status" in ws.receive_json()


def test_lifespan_starts_and_stops_monitor(tmp_path):
    """The real startup path: the monitor thread polls without anyone calling poll_once."""
    import time

    cfg = Config()
    cfg.paths.data_dir = tmp_path
    printer = FakePrinter()
    monitor = Monitor(printer, JobStore(tmp_path / "jobs.db"), interval=0.05)
    app = create_app(cfg, client=printer, monitor=monitor)
    with TestClient(app) as client:
        deadline = time.time() + 2
        while not client.get("/api/status").json().get("online") and time.time() < deadline:
            time.sleep(0.05)
        assert client.get("/api/status").json()["online"] is True
        assert monitor._thread.is_alive()
    assert not monitor._thread.is_alive()


def test_fluidd_url_drops_moonraker_port():
    from triaina.web.app import fluidd_url

    assert fluidd_url("neptune4.local") == "http://neptune4.local/"
    assert fluidd_url("http://198.51.100.7:7125") == "http://198.51.100.7/"


def test_concurrent_starts_send_once(env):
    import threading
    import time as _time

    _, printer, client, _ = env
    job = upload(client, "print-gcode").json()
    real_upload = printer.upload

    def slow_upload(path, start):
        _time.sleep(0.2)
        real_upload(path, start)

    printer.upload = slow_upload
    codes = []

    def go():
        codes.append(
            client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True}).status_code
        )

    threads = [threading.Thread(target=go) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200, 409, 409]
    assert len(printer.uploads) == 1


def test_start_sees_print_started_elsewhere(env):
    _, printer, client, _ = env
    job = upload(client, "print-gcode").json()
    printer.state = "printing"  # started from Fluidd after the last poll
    assert client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True}).status_code == 409


def test_estop_then_firmware_restart(env):
    _, printer, client, _ = env
    snap = client.post("/api/estop").json()
    # Moonraker answers, Klipper is down: reachable, not "offline".
    assert snap["online"] is True and snap["klippy"] == "shutdown"
    assert client.post("/api/mode/cutter").status_code == 409
    assert client.post("/api/firmware-restart").json()["klippy"] == "ready"
    assert ("firmware_restart",) in printer.calls


def test_preparation_error_fails_job(env, monkeypatch):
    def boom(*_a, **_k):
        raise ValueError("bad G-code")

    monkeypatch.setattr("triaina.web.app.process_lines", boom)
    r = upload(env[2], "cut-gcode")
    assert r.status_code == 201
    assert r.json()["state"] == "failed" and "bad G-code" in r.json()["error"]


def test_unexpected_upload_error_does_not_leave_job_sending(env):
    _, printer, client, _ = env

    def boom(path, start):
        raise RuntimeError("surprise")

    printer.upload = boom
    job = upload(client, "print-gcode").json()
    assert client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True}).status_code == 502
    assert client.get(f"/api/jobs/{job['id']}").json()["state"] == "failed"
    job2 = upload(client, "print-gcode").json()
    # Not blocked by a stuck "sending" job.
    printer.upload = lambda path, start: None
    assert client.post(f"/api/jobs/{job2['id']}/start", json={"confirm": True}).status_code == 200
