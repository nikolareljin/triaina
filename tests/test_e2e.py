"""End to end: dashboard API -> real MoonrakerClient -> fake Moonraker over loopback HTTP."""

import pytest
from fastapi.testclient import TestClient

from fake_moonraker import serve
from triaina.config import Config
from triaina.web.app import create_app


@pytest.fixture
def stack(tmp_path):
    server, state = serve()
    cfg = Config()
    cfg.printer.host = f"http://127.0.0.1:{server.server_address[1]}"
    cfg.paths.data_dir = tmp_path
    app = create_app(cfg, start_monitor=False)
    yield TestClient(app), state, app
    server.shutdown()


def test_cut_job_end_to_end(stack):
    client, state, app = stack
    app.state.monitor.poll_once()
    job = client.post(
        "/api/jobs",
        data={"kind": "cut-gcode"},
        files={"file": ('my "sticker".gcode', "M3\nG1 X5 Y5 F600\nM5\n")},
    ).json()
    assert job["state"] == "ready"

    r = client.post(f"/api/jobs/{job['id']}/start", json={"confirm": True})
    assert r.status_code == 200, r.text
    # The multipart body parsed on the server side, with the right name and fields.
    name = job["remote_name"]
    assert name in state.files and b"CUTTER_MODE" in state.files[name]
    assert state.form == {"root": "gcodes", "print": "true"}

    snap = app.state.monitor.poll_once()
    assert snap["state"] == "printing" and snap["filename"] == name

    state.print_state = "complete"
    app.state.monitor.poll_once()
    assert client.get(f"/api/jobs/{job['id']}").json()["state"] == "done"


def test_mode_switch_end_to_end(stack):
    client, state, app = stack
    app.state.monitor.poll_once()
    assert client.post("/api/mode/cutter").json()["mode"] == "cutter"
    assert state.scripts == ["CUTTER_MODE"]


def test_real_server_websocket(tmp_path):
    """uvicorn + a real websocket client. TestClient alone cannot catch a missing
    websocket library: uvicorn then answers "Unsupported upgrade request"."""
    import socket
    import threading
    import time

    import uvicorn
    from websockets.sync.client import connect

    server, state = serve()
    cfg = Config()
    cfg.printer.host = f"http://127.0.0.1:{server.server_address[1]}"
    cfg.paths.data_dir = tmp_path
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    web = uvicorn.Server(
        uvicorn.Config(create_app(cfg), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=web.run, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 10
        while not web.started and time.time() < deadline:
            time.sleep(0.05)
        assert web.started
        with connect(f"ws://127.0.0.1:{port}/ws", open_timeout=5) as ws:
            import json

            msg = json.loads(ws.recv(timeout=5))
            # The monitor thread may not have polled yet; the shape is what matters.
            assert {"status", "jobs"} <= set(msg)
    finally:
        web.should_exit = True
        thread.join(timeout=10)
        server.shutdown()
