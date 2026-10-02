"""Poll Moonraker in a background thread and keep the latest printer state.

Polling once a second instead of a Moonraker websocket subscription: fewer
moving parts, and it recovers by itself when the printer reboots or drops off
the network. The browser gets updates over the dashboard's own websocket.

The monitor also closes the loop on jobs: when the printer reports the job's
file as complete, cancelled or errored, the job row follows.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from triaina.jobs import JobStore
from triaina.printer import ApiError, MoonrakerClient

log = logging.getLogger("triaina.monitor")

#: print_stats.state -> job state, for the file the active job sent.
FINAL_STATES = {"complete": "done", "cancelled": "cancelled", "error": "failed"}
#: Seconds after a start during which the printer may still show the old file.
START_GRACE_S = 15.0


class Monitor:
    def __init__(self, client: MoonrakerClient, jobs: JobStore, interval: float = 1.0):
        self.client = client
        self.jobs = jobs
        self.interval = interval
        self._lock = threading.Lock()
        self._snapshot: dict = {"online": False, "error": "not polled yet"}
        self._version = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- state ---------------------------------------------------------------

    def snapshot(self) -> tuple[int, dict]:
        with self._lock:
            return self._version, dict(self._snapshot)

    def _set(self, snap: dict) -> None:
        def same(a: dict, b: dict) -> bool:
            # The timestamp changes every poll; only a real change bumps the version.
            return {k: v for k, v in a.items() if k != "updated"} == {
                k: v for k, v in b.items() if k != "updated"
            }

        with self._lock:
            if not same(snap, self._snapshot):
                self._version += 1
            self._snapshot = snap

    # -- polling -------------------------------------------------------------

    def poll_once(self) -> dict:
        try:
            snap = self.client.snapshot()
            snap.update(online=True, error=None)
        except ApiError as exc:
            snap = {"online": False, "error": str(exc)}
        snap["updated"] = time.time()
        if snap["online"]:
            self._reconcile(snap)
        active = self.jobs.active()
        snap["active_job"] = active.to_dict() if active else None
        self._set(snap)
        return snap

    def _reconcile(self, snap: dict) -> None:
        job = self.jobs.active()
        if not job or job.state != "running" or not job.remote_name:
            return
        if snap.get("filename") != job.remote_name:
            # Another file is loaded: the user started something else from
            # Fluidd, so ours is no longer running.
            if snap.get("state") in ("printing", "paused"):
                self.jobs.update(job.id, state="failed", error="replaced by another print")
            elif time.time() - job.updated > START_GRACE_S:
                # Nothing of ours loaded long after the start: the printer
                # restarted or the job was cleared from Fluidd.
                self.jobs.update(
                    job.id, state="failed", error="job no longer loaded on the printer"
                )
            return
        final = FINAL_STATES.get(snap.get("state"))
        if final:
            error = (
                (snap.get("message") or "printer reported an error") if final == "failed" else ""
            )
            self.jobs.update(job.id, state=final, error=error)
            log.info("job %s %s", job.id, final)

    def run(self) -> None:
        log.info("monitor started, polling every %.1fs", self.interval)
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:  # noqa: BLE001 - the loop must survive anything
                log.exception("monitor poll failed")
            self._stop.wait(self.interval)

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name="triaina-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
