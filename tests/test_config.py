"""Tests for triaina.config."""

from pathlib import Path

import pytest

from triaina.config import ConfigError, load


def test_missing_file_gives_defaults(tmp_path):
    cfg = load(tmp_path / "none.toml")
    assert cfg.source is None
    assert cfg.printer_url == "http://neptune4.local:7125"
    assert cfg.server.port == 8080


def test_values_and_paths(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[printer]\nhost = "n4.local"\nport = 7126\n[paths]\ndata_dir = "/tmp/x"\n')
    cfg = load(f)
    assert cfg.printer_url == "http://n4.local:7126"
    assert cfg.paths.data_dir == Path("/tmp/x")
    assert cfg.source == f


def test_host_as_url(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[printer]\nhost = "https://printer.example/"\n')
    assert load(f).printer_url == "https://printer.example"


def test_env_var(tmp_path, monkeypatch):
    f = tmp_path / "c.toml"
    f.write_text("[server]\nport = 9000\n")
    monkeypatch.setenv("TRIAINA_CONFIG", str(f))
    assert load().server.port == 9000


@pytest.mark.parametrize(
    "text, match",
    [
        ("[printer]\nhots = 'x'\n", "unknown key: hots"),
        ("[nope]\na = 1\n", "unknown section"),
        ("[printer\n", "c.toml"),
    ],
)
def test_errors(tmp_path, text, match):
    f = tmp_path / "c.toml"
    f.write_text(text)
    with pytest.raises(ConfigError, match=match):
        load(f)


def test_example_config_loads():
    example = Path(__file__).resolve().parent.parent / "deploy" / "config.example.toml"
    assert load(example).printer.host == "neptune4.local"
