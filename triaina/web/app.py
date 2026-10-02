"""The dashboard: REST API, a websocket for live state, and the static page.

Endpoints are plain `def` so FastAPI runs them in its thread pool; the
Moonraker client is synchronous on purpose (it is the same stdlib client the
CLI uses).
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from triaina import __version__
from triaina.config import Config
from triaina.jobs import KINDS, JobStore, safe_name
from triaina.monitor import Monitor
from triaina.preprocess import Options, process_lines
from triaina.printer import ApiError, MoonrakerClient

log = logging.getLogger("triaina.web")

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
GCODE_SUFFIXES = {".gcode", ".gco", ".g", ".nc", ".ngc", ".txt"}
BUSY_STATES = ("printing", "paused")


def fluidd_url(host: str) -> str:
    """Fluidd runs on port 80 of the printer, whatever port Moonraker uses."""
    hostname = urlparse(host if "://" in host else f"http://{host}").hostname or host
    return f"http://{hostname}/"


class StartRequest(BaseModel):
    #: The user ticked the physical-setup box shown for this job kind.
    confirm: bool = False


def create_app(
    cfg: Config,
    client: Optional[MoonrakerClient] = None,
    monitor: Optional[Monitor] = None,
    start_monitor: bool = True,
) -> FastAPI:
    data_dir = cfg.paths.data_dir
    jobs = JobStore(data_dir / "jobs.db")
    recovered = jobs.recover()
    if recovered:
        log.warning("marked %d interrupted job(s) as failed", recovered)
    client = client or MoonrakerClient(
        cfg.printer_url, api_key=cfg.printer.api_key, timeout=cfg.printer.timeout
    )
    monitor = monitor or Monitor(client, jobs)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if start_monitor:
            monitor.start()
        try:
            yield
        finally:
            if start_monitor:
                monitor.stop()

    app = FastAPI(
        title="triaina",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.cfg, app.state.jobs, app.state.client, app.state.monitor = cfg, jobs, client, monitor

    # -- auth ----------------------------------------------------------------

    def token_ok(supplied: Optional[str]) -> bool:
        want = cfg.server.auth_token
        return not want or (supplied is not None and secrets.compare_digest(supplied, want))

    def require_token(request: Request) -> None:
        header = request.headers.get("authorization", "")
        supplied = header[7:] if header.lower().startswith("bearer ") else None
        supplied = supplied or request.query_params.get("token")
        if not token_ok(supplied):
            raise HTTPException(401, "missing or wrong token")

    auth = [Depends(require_token)]
    start_lock = threading.Lock()

    # -- helpers -------------------------------------------------------------

    def printer_idle() -> None:
        """Raise 409 unless the printer is online and not running a job.

        Polls now rather than trusting the last snapshot: a print started from
        Fluidd a moment ago must not be missed."""
        snap = monitor.poll_once()
        if not snap.get("online"):
            raise HTTPException(503, f"printer offline: {snap.get('error')}")
        if snap.get("klippy") not in (None, "ready"):
            raise HTTPException(
                409, f"Klipper is {snap.get('klippy')}: {snap.get('klippy_message')}"
            )
        if snap.get("state") in BUSY_STATES:
            raise HTTPException(409, f"printer is {snap.get('state')}")

    def api_call(fn, *args) -> None:
        try:
            fn(*args)
        except ApiError as exc:
            raise HTTPException(502, str(exc)) from exc

    def job_or_404(job_id: int):
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "no such job")
        return job

    # -- read ----------------------------------------------------------------

    @app.get("/api/info", dependencies=auth)
    def info() -> dict:
        return {
            "version": __version__,
            "printer_url": cfg.printer_url,
            "printer_web_url": cfg.printer.web_url or fluidd_url(cfg.printer.host),
            "camera_url": cfg.camera.stream_url or None,
            "config_file": str(cfg.source) if cfg.source else None,
            "kinds": KINDS,
        }

    @app.get("/api/status", dependencies=auth)
    def status() -> dict:
        return monitor.snapshot()[1]

    @app.get("/api/jobs", dependencies=auth)
    def list_jobs() -> list[dict]:
        return [j.to_dict() for j in jobs.list()]

    @app.get("/api/jobs/{job_id}", dependencies=auth)
    def get_job(job_id: int) -> dict:
        return job_or_404(job_id).to_dict()

    @app.get("/api/jobs/{job_id}/output", dependencies=auth)
    def job_output(job_id: int):
        job = job_or_404(job_id)
        if not job.output or not Path(job.output).is_file():
            raise HTTPException(404, "no output file")
        return FileResponse(job.output, filename=Path(job.output).name)

    # -- jobs ----------------------------------------------------------------

    @app.post("/api/jobs", dependencies=auth, status_code=201)
    def create_job(kind: str = Form(...), file: UploadFile = File(...)) -> dict:
        if kind not in KINDS:
            raise HTTPException(422, f"kind must be one of {sorted(KINDS)}")
        name = safe_name(file.filename or "upload.gcode")
        if Path(name).suffix.lower() not in GCODE_SUFFIXES:
            raise HTTPException(415, f"expected G-code ({', '.join(sorted(GCODE_SUFFIXES))})")
        job = jobs.create(kind, name)
        job_dir = data_dir / "jobs" / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        source = job_dir / f"source{Path(name).suffix.lower()}"
        with source.open("wb") as out:
            copied = 0
            while chunk := file.file.read(1024 * 1024):
                copied += len(chunk)
                if copied > MAX_UPLOAD_BYTES:
                    out.close()
                    shutil.rmtree(job_dir, ignore_errors=True)
                    jobs.update(job.id, state="failed", error="file too large")
                    raise HTTPException(413, f"file larger than {MAX_UPLOAD_BYTES} bytes")
                out.write(chunk)

        # The output is named as it will appear on the printer, so the
        # multipart upload carries the right name.
        remote = f"triaina-{job.id}-{Path(name).stem}.gcode"
        output = job_dir / remote
        try:
            if kind == "cut-gcode":
                lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
                opts = Options(
                    max_feed=cfg.cut.max_feed,
                    default_feed=cfg.cut.default_feed,
                    z_threshold=cfg.cut.z_threshold,
                )
                output.write_text("\n".join(process_lines(lines, opts)) + "\n", encoding="utf-8")
            else:
                shutil.copyfile(source, output)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - any failure must leave a failed job, not a ready one
            log.exception("preparing job %s failed", job.id)
            return jobs.update(job.id, state="failed", error=f"preparation failed: {exc}").to_dict()
        return jobs.update(
            job.id, source=str(source), output=str(output), remote_name=remote
        ).to_dict()

    @app.post("/api/jobs/{job_id}/start", dependencies=auth)
    def start_job(job_id: int, body: StartRequest) -> dict:
        job = job_or_404(job_id)
        if job.state != "ready":
            raise HTTPException(409, f"job is {job.state}")
        if not body.confirm:
            raise HTTPException(428, "confirm the physical setup first")
        # Check and claim under one lock: two clicks must not both start.
        with start_lock:
            if jobs.get(job.id).state != "ready":
                raise HTTPException(409, "job already started")
            if jobs.active():
                raise HTTPException(409, "another job is active")
            printer_idle()
            jobs.update(job.id, state="sending")
        try:
            client.upload(Path(job.output), start=True)
        except Exception as exc:  # noqa: BLE001 - never leave a job stuck in "sending"
            jobs.update(job.id, state="failed", error=str(exc))
            if not isinstance(exc, (ApiError, OSError)):
                log.exception("starting job %s failed", job.id)
            raise HTTPException(502, str(exc)) from exc
        job = jobs.update(job.id, state="running")
        monitor.poll_once()
        return job.to_dict()

    @app.delete("/api/jobs/{job_id}", dependencies=auth)
    def discard_job(job_id: int) -> dict:
        job = job_or_404(job_id)
        if job.state in ("sending", "running"):
            raise HTTPException(409, "cancel the print first")
        if job.state == "ready":
            job = jobs.update(job.id, state="cancelled")
        return job.to_dict()

    # -- printer control -----------------------------------------------------

    @app.post("/api/mode/{mode}", dependencies=auth)
    def set_mode(mode: str) -> dict:
        macros = {"cutter": "CUTTER_MODE", "printer": "PRINTER_MODE"}
        if mode not in macros:
            raise HTTPException(404, "mode is cutter or printer")
        printer_idle()
        api_call(client.run_gcode, macros[mode])
        return monitor.poll_once()

    @app.post("/api/print/{action}", dependencies=auth)
    def print_action(action: str) -> dict:
        if action not in ("pause", "resume", "cancel"):
            raise HTTPException(404, "action is pause, resume or cancel")
        api_call(client.print_action, action)
        return monitor.poll_once()

    @app.post("/api/firmware-restart", dependencies=auth)
    def firmware_restart() -> dict:
        """The way back after an emergency stop or a Klipper error."""
        api_call(client.firmware_restart)
        return monitor.poll_once()

    @app.post("/api/estop", dependencies=auth)
    def estop() -> dict:
        api_call(client.emergency_stop)
        return monitor.poll_once()

    # -- live ----------------------------------------------------------------

    @app.websocket("/ws")
    async def live(ws: WebSocket) -> None:
        if not token_ok(ws.query_params.get("token")):
            await ws.close(code=4401)
            return
        await ws.accept()
        last: Optional[str] = None
        try:
            while True:
                _, snap = monitor.snapshot()
                payload = json.dumps(
                    {"status": snap, "jobs": [j.to_dict() for j in jobs.list(20)]},
                    default=str,
                    sort_keys=True,
                )
                if payload != last:
                    await ws.send_text(payload)
                    last = payload
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    # -- page ----------------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "version": __version__}

    app.mount("/", StaticFiles(directory=STATIC, html=True, follow_symlink=True), name="static")
    return app
