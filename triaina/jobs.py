"""Job store: one SQLite file, one row per job.

States::

    ready -> sending -> running -> done | failed | cancelled
      \\-> failed (preparation error)

`ready` means the file is prepared and waits for the user to confirm the
physical setup (knife fitted or removed) and press start. Nothing is sent to the
printer before that.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

KINDS = {
    # Ready-made print G-code, sent as is.
    "print-gcode": "Print G-code",
    # Cut G-code from Kiri:Moto, Inkcut, Inkscape...; run through the preprocessor.
    "cut-gcode": "Cut G-code",
    # A design file converted to cut G-code here: SVG, DXF, PDF, AI, EPS, PNG, JPG.
    "cut-design": "Cut design",
    # A 2D design extruded into a plate (sign, stamp, logo) and sliced here.
    "print-design": "Print design (3D)",
    # An STL or 3MF model sliced here.
    "print-model": "Print model",
    # The parametric drag-knife clamp, built and sliced here.
    "knife-mount": "Print knife mount",
}
PRINT_KINDS = ("print-gcode", "print-design", "print-model", "knife-mount")
STATES = ("converting", "ready", "sending", "running", "done", "failed", "cancelled")
ACTIVE = ("sending", "running")

#: What the user must confirm before a job of this kind starts.
CONFIRM_TEXT = {
    "print-gcode": "Knife holder removed, bed clear, filament loaded.",
    "cut-gcode": "Knife holder fitted, hotend below 50 C, vinyl on the mat.",
    "cut-design": "Knife holder fitted, hotend below 50 C, vinyl on the mat.",
    "print-design": "Knife holder removed, bed clear, filament loaded.",
    "print-model": "Knife holder removed, bed clear, filament loaded.",
    "knife-mount": "Knife holder removed, bed clear, filament loaded.",
}


@dataclass
class Job:
    id: int
    kind: str
    name: str
    state: str
    source: str
    output: str
    remote_name: str
    error: str
    created: float
    updated: float
    #: JSON: size, cut length, estimate, warnings. Empty for G-code jobs.
    summary: str = ""

    def to_dict(self) -> dict:
        """API view: no server file paths, only whether output exists."""
        d = asdict(self)
        d["has_output"] = bool(d.pop("output"))
        d["summary"] = json.loads(self.summary) if self.summary else None
        d.pop("source")
        d["kind_label"] = KINDS.get(self.kind, self.kind)
        d["confirm_text"] = CONFIRM_TEXT.get(self.kind, "")
        return d


def safe_name(name: str) -> str:
    """File name safe for Moonraker's gcodes root: no paths, no odd characters."""
    stem = Path(name).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "job"
    return stem[:80]


class JobStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                state TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                output TEXT NOT NULL DEFAULT '',
                remote_name TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created REAL NOT NULL,
                updated REAL NOT NULL
            )""")
        # Columns added after the first release; ALTER keeps existing databases.
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(jobs)")}
        if "summary" not in cols:
            self._db.execute("ALTER TABLE jobs ADD COLUMN summary TEXT NOT NULL DEFAULT ''")
        self._db.commit()

    def create(self, kind: str, name: str) -> Job:
        if kind not in KINDS:
            raise ValueError(f"unknown job kind: {kind}")
        now = time.time()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO jobs (kind, name, state, created, updated)"
                " VALUES (?, ?, 'ready', ?, ?)",
                (kind, name, now, now),
            )
            self._db.commit()
            job_id = cur.lastrowid
        return self.get(job_id)

    def get(self, job_id: int) -> Optional[Job]:
        with self._lock:
            row = self._db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return Job(**dict(row)) if row else None

    def list(self, limit: int = 50) -> list[Job]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Job(**dict(r)) for r in rows]

    def update(self, job_id: int, **values) -> Job:
        bad = set(values) - {"state", "source", "output", "remote_name", "error", "summary"}
        if bad:
            raise ValueError(f"cannot update: {sorted(bad)}")
        if "state" in values and values["state"] not in STATES:
            raise ValueError(f"unknown state: {values['state']}")
        values["updated"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in values)
        with self._lock:
            self._db.execute(f"UPDATE jobs SET {cols} WHERE id = ?", (*values.values(), job_id))
            self._db.commit()
        return self.get(job_id)

    def active(self) -> Optional[Job]:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM jobs WHERE state IN ('sending', 'running') ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return Job(**dict(row)) if row else None

    def recover(self) -> int:
        """After a restart, a job caught mid-send or mid-conversion cannot be
        trusted. Returns how many."""
        with self._lock:
            cur = self._db.execute(
                "UPDATE jobs SET state = 'failed', error = 'interrupted by a service restart',"
                " updated = ? WHERE state IN ('sending', 'converting')",
                (time.time(),),
            )
            self._db.commit()
        return cur.rowcount
