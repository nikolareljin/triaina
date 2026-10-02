"""Tests for the `python -m triaina` entry point."""

import pytest

import triaina.__main__ as entry


@pytest.fixture
def captured(monkeypatch, tmp_path):
    seen = {}
    # main() sets TRIAINA_CONFIG for --reload; setenv here makes monkeypatch undo it.
    monkeypatch.setenv("TRIAINA_CONFIG", "")
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: seen.update(kw))
    cfg = tmp_path / "c.toml"
    cfg.write_text(f'[server]\nport = 9999\nbind = "127.0.0.1"\n[paths]\ndata_dir = "{tmp_path}"\n')
    return seen, cfg


def test_port_zero_is_honoured(captured):
    seen, cfg = captured
    assert entry.main(["serve", "--config", str(cfg), "--port", "0"]) == 0
    assert seen["port"] == 0


def test_config_port_used_by_default(captured):
    seen, cfg = captured
    entry.main(["serve", "--config", str(cfg)])
    assert seen["port"] == 9999 and seen["host"] == "127.0.0.1"


def test_bad_config_exits_2(tmp_path, capsys):
    bad = tmp_path / "b.toml"
    bad.write_text("[printer]\nhots = 1\n")
    assert entry.main(["serve", "--config", str(bad)]) == 2
    assert "unknown key" in capsys.readouterr().err


def test_reload_uses_factory(captured):
    seen, cfg = captured
    entry.main(["serve", "--config", str(cfg), "--reload"])
    assert seen["factory"] is True and seen["reload"] is True
