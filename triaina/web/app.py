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
from concurrent.futures import ThreadPoolExecutor
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
from triaina.convert import FORMATS, ConversionError
from triaina.cut import pipeline as cut_pipeline
from triaina.cut.paths import LayoutError
from triaina.cut.pipeline import CutOptions
from triaina.jobs import KINDS, JobStore, safe_name
from triaina.monitor import Monitor
from triaina.preprocess import Options, process_lines, xy_extents
from triaina.printer import ApiError, MoonrakerClient

log = logging.getLogger("triaina.web")

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
GCODE_SUFFIXES = {".gcode", ".gco", ".g", ".nc", ".ngc", ".txt"}
DESIGN_SUFFIXES = set(FORMATS)
#: print_stats states in which starting a job or switching mode is safe.
#: Anything else, including "unknown" when the state could not be read, is refused.
IDLE_STATES = ("standby", "complete", "cancelled", "error")


def knife_area(cfg: Config, snap: dict) -> tuple[tuple[float, float, float, float], Optional[str]]:
    """Where the knife can cut: on the bed, with the nozzle inside its axis limits.

    The macros apply SET_GCODE_OFFSET X=offset_x Y=offset_y, so the nozzle is at
    commanded + offset while the knife tip is at the commanded point. Needs the
    live printer; without it the configured bed is used and a warning returned.
    """
    bed = (0.0, 0.0, cfg.cut.bed_x, cfg.cut.bed_y)
    lo, hi, off = snap.get("axis_minimum"), snap.get("axis_maximum"), snap.get("knife_offset")
    if not (snap.get("online") and lo and hi and off):
        return bed, (
            "printer limits or knife offset unknown (printer offline or macros missing):"
            " the cut area was not checked against the knife offset"
        )
    ox, oy = float(off[0]), float(off[1])
    area = (
        max(bed[0], lo[0] - ox),
        max(bed[1], lo[1] - oy),
        min(bed[2], hi[0] - ox),
        min(bed[3], hi[1] - oy),
    )
    return area, None


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
            converter.shutdown(wait=False, cancel_futures=True)
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
    # One conversion at a time: a Pi 3 has four cores and 1 GB.
    converter = ThreadPoolExecutor(max_workers=1, thread_name_prefix="triaina-convert")
    app.state.converter = converter

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
        if snap.get("state") not in IDLE_STATES:
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

    def prepare_gcode(kind: str, source: Path, output: Path) -> Optional[dict]:
        """Write the G-code to send. For cut G-code, also check the knife can
        reach every move; returns a summary, or raises ValueError."""
        if kind != "cut-gcode":
            shutil.copyfile(source, output)
            return None
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        opts = Options(
            max_feed=cfg.cut.max_feed,
            default_feed=cfg.cut.default_feed,
            z_threshold=cfg.cut.z_threshold,
        )
        processed = process_lines(lines, opts)
        area, warning = knife_area(cfg, monitor.poll_once())
        warnings = [warning] if warning else []
        try:
            ext = xy_extents(processed)
        except ValueError as exc:
            ext = None
            warnings.append(str(exc))
        if ext is not None:
            x0, y0, x1, y1 = ext
            ax0, ay0, ax1, ay1 = area
            if x0 < ax0 - 0.01 or y0 < ay0 - 0.01 or x1 > ax1 + 0.01 or y1 > ay1 + 0.01:
                raise ValueError(
                    f"moves span X {x0:.1f}..{x1:.1f}, Y {y0:.1f}..{y1:.1f}; the knife can reach"
                    f" X {ax0:.1f}..{ax1:.1f}, Y {ay0:.1f}..{ay1:.1f} (move the design in your"
                    " CAM program)"
                )
        output.write_text("\n".join(processed) + "\n", encoding="utf-8")
        summary = {"warnings": warnings}
        if ext is not None:
            summary.update(width_mm=round(ext[2] - ext[0], 1), height_mm=round(ext[3] - ext[1], 1))
        return summary

    def convert_design(job_id: int, source: Path, output: Path, opts: CutOptions) -> None:
        """Runs on the converter thread: a PDF or a traced photo takes seconds on a Pi 3."""
        try:
            result = cut_pipeline.run(source, output.parent / "work", opts)
            output.write_text("\n".join(result.gcode) + "\n", encoding="utf-8")
            (output.parent / "preview.svg").write_text(result.preview_svg, encoding="utf-8")
            summary = dict(result.summary, warnings=opts.extra_warnings + result.warnings)
            jobs.update(job_id, state="ready", summary=json.dumps(summary))
        except (ConversionError, LayoutError, ValueError) as exc:
            jobs.update(job_id, state="failed", error=str(exc))
        except Exception as exc:  # noqa: BLE001 - a job must never stay "converting"
            log.exception("converting job %s failed", job_id)
            jobs.update(job_id, state="failed", error=f"conversion failed: {exc}")
        finally:
            # Intermediate files (traced bitmap, PDF page SVG) are not needed
            # afterwards; on a Pi they would fill the SD card job by job.
            shutil.rmtree(output.parent / "work", ignore_errors=True)

    @app.post("/api/jobs", dependencies=auth, status_code=201)
    def create_job(
        kind: str = Form(...),
        file: UploadFile = File(...),
        width: Optional[float] = Form(None),
        fit: bool = Form(False),
        weed: float = Form(0.0),
        blade_offset: Optional[float] = Form(None),
        cut_feed: Optional[float] = Form(None),
        threshold: int = Form(128),
        invert: bool = Form(False),
    ) -> dict:
        if kind not in KINDS:
            raise HTTPException(422, f"kind must be one of {sorted(KINDS)}")
        name = safe_name(file.filename or "upload")
        suffix = Path(name).suffix.lower()
        allowed = DESIGN_SUFFIXES if kind == "cut-design" else GCODE_SUFFIXES
        if suffix not in allowed:
            raise HTTPException(415, f"{KINDS[kind]} takes {', '.join(sorted(allowed))}")
        cut_opts = None
        if kind == "cut-design":
            cut_opts = CutOptions(
                width=width,
                fit=fit,
                margin=cfg.cut.margin,
                bed_x=cfg.cut.bed_x,
                bed_y=cfg.cut.bed_y,
                weed=weed,
                blade_offset=cfg.cut.blade_offset if blade_offset is None else blade_offset,
                cutoff_deg=cfg.cut.cutoff_deg,
                overcut=cfg.cut.overcut,
                cut_feed=cfg.cut.cut_feed if cut_feed is None else cut_feed,
                travel_feed=cfg.cut.travel_feed,
                max_feed=cfg.cut.max_feed,
                threshold=threshold,
                invert=invert,
            )
            # (name, value, low, high): the same ranges as the form fields.
            limits = (
                ("width", width, 1, 1000),
                ("weed", weed, 0, 20),
                ("blade_offset", cut_opts.blade_offset, 0, 2),
                ("cut_feed", cut_opts.cut_feed, 1, 20000),
                ("threshold", threshold, 0, 255),
            )
            bad = [
                f"{n} must be {lo}-{hi}"
                for n, v, lo, hi in limits
                if v is not None and not lo <= v <= hi
            ]
            if bad:
                raise HTTPException(422, "; ".join(bad))

        job = jobs.create(kind, name)
        job_dir = data_dir / "jobs" / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        source = job_dir / f"source{suffix}"
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
        jobs.update(job.id, source=str(source), output=str(output), remote_name=remote)
        if cut_opts is not None:
            cut_opts.area, area_warning = knife_area(cfg, monitor.poll_once())
            if area_warning:
                cut_opts.extra_warnings.append(area_warning)
            jobs.update(job.id, state="converting")
            converter.submit(convert_design, job.id, source, output, cut_opts)
            return jobs.get(job.id).to_dict()
        try:
            summary = prepare_gcode(kind, source, output)
        except ValueError as exc:
            return jobs.update(job.id, state="failed", error=str(exc)).to_dict()
        # Any failure must leave a failed job, never a ready one with no output.
        except Exception as exc:  # noqa: BLE001
            log.exception("preparing job %s failed", job.id)
            return jobs.update(job.id, state="failed", error=f"preparation failed: {exc}").to_dict()
        if summary is not None:
            return jobs.update(job.id, summary=json.dumps(summary)).to_dict()
        return jobs.get(job.id).to_dict()

    @app.get("/api/jobs/{job_id}/preview.svg", dependencies=auth)
    def job_preview(job_id: int):
        job = job_or_404(job_id)
        preview_file = Path(job.output).parent / "preview.svg" if job.output else None
        if preview_file is None or not preview_file.is_file():
            raise HTTPException(404, "no preview for this job")
        return FileResponse(preview_file, media_type="image/svg+xml")

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
        if job.state == "converting":
            raise HTTPException(409, "wait for the conversion to finish")
        if job.state == "ready":
            job = jobs.update(job.id, state="cancelled")
        # Free the space: uploads go up to 50 MB and a Pi runs from an SD card.
        # The row stays as history; its files are gone.
        shutil.rmtree(data_dir / "jobs" / str(job.id), ignore_errors=True)
        return jobs.update(job.id, output="", source="").to_dict()

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
