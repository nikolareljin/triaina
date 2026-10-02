"""Tests for triaina.jobs and triaina.monitor."""

import time

import pytest

from fakes import FakePrinter
from triaina.jobs import JobStore, safe_name
from triaina.monitor import Monitor


@pytest.fixture
def store(tmp_path):
    return JobStore(tmp_path / "jobs.db")


def test_create_and_update(store):
    job = store.create("cut-gcode", "a.gcode")
    assert job.state == "ready"
    job = store.update(job.id, state="running", remote_name="triaina-1-a.gcode")
    assert store.active().id == job.id
    assert store.list()[0].to_dict()["kind_label"] == "Cut G-code"


def test_rejects_bad_values(store):
    with pytest.raises(ValueError):
        store.create("laser", "a")
    job = store.create("print-gcode", "a")
    with pytest.raises(ValueError):
        store.update(job.id, state="flying")
    with pytest.raises(ValueError):
        store.update(job.id, kind="cut-gcode")


def test_recover_fails_only_sending(store):
    a = store.create("print-gcode", "a")
    b = store.create("print-gcode", "b")
    store.update(a.id, state="sending")
    store.update(b.id, state="running")
    assert store.recover() == 1
    assert store.get(a.id).state == "failed"
    assert store.get(b.id).state == "running"


def test_persists_across_instances(tmp_path):
    JobStore(tmp_path / "j.db").create("print-gcode", "a")
    assert len(JobStore(tmp_path / "j.db").list()) == 1


@pytest.mark.parametrize(
    "raw, want",
    [("../../etc/passwd", "passwd"), ("my file (1).gcode", "my_file_1_.gcode"), ("", "job")],
)
def test_safe_name(raw, want):
    assert safe_name(raw) == want


def running_job(store, name="triaina-1-a.gcode"):
    job = store.create("print-gcode", "a.gcode")
    return store.update(job.id, state="running", remote_name=name)


@pytest.mark.parametrize(
    "printer_state, job_state",
    [("complete", "done"), ("cancelled", "cancelled"), ("error", "failed")],
)
def test_monitor_closes_job(store, printer_state, job_state):
    printer = FakePrinter()
    job = running_job(store)
    printer.state, printer.filename = printer_state, job.remote_name
    Monitor(printer, store).poll_once()
    assert store.get(job.id).state == job_state
    assert (store.get(job.id).error == "") == (job_state != "failed")


def test_monitor_keeps_running_job(store):
    printer = FakePrinter()
    job = running_job(store)
    printer.state, printer.filename = "printing", job.remote_name
    snap = Monitor(printer, store).poll_once()
    assert store.get(job.id).state == "running"
    assert snap["active_job"]["id"] == job.id


def test_monitor_other_print_replaces_job(store):
    printer = FakePrinter()
    job = running_job(store)
    printer.state, printer.filename = "printing", "benchy.gcode"
    Monitor(printer, store).poll_once()
    assert store.get(job.id).error == "replaced by another print"


def test_monitor_grace_then_fail(store, monkeypatch):
    printer = FakePrinter()
    job = running_job(store)
    Monitor(printer, store).poll_once()
    assert store.get(job.id).state == "running"  # within the start grace period
    later = time.time() + 60
    monkeypatch.setattr("triaina.monitor.time.time", lambda: later)
    Monitor(printer, store).poll_once()
    assert store.get(job.id).error == "job no longer loaded on the printer"


def test_monitor_offline(store):
    printer = FakePrinter()
    printer.online = False
    mon = Monitor(printer, store)
    snap = mon.poll_once()
    assert snap["online"] is False and "refused" in snap["error"]


def test_version_ignores_timestamp(store):
    mon = Monitor(FakePrinter(), store)
    mon.poll_once()
    v1, _ = mon.snapshot()
    mon.poll_once()
    assert mon.snapshot()[0] == v1


def test_monitor_standby_with_our_file_fails_after_grace(store, monkeypatch):
    printer = FakePrinter()
    job = running_job(store)
    printer.state, printer.filename = "standby", job.remote_name
    Monitor(printer, store).poll_once()
    assert store.get(job.id).state == "running"
    later = time.time() + 60
    monkeypatch.setattr("triaina.monitor.time.time", lambda: later)
    Monitor(printer, store).poll_once()
    assert store.get(job.id).error == "printer restarted during the job"


def test_monitor_klipper_down_is_online(store):
    printer = FakePrinter()
    printer.klippy_state = "shutdown"
    snap = Monitor(printer, store).poll_once()
    assert snap["online"] is True and snap["klippy"] == "shutdown"
    printer.online = False
    assert Monitor(printer, store).poll_once()["online"] is False
