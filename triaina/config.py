"""Service configuration, read from TOML.

Lookup order: the path given on the command line, then $TRIAINA_CONFIG, then
/etc/triaina/config.toml. A missing file means defaults, so a fresh install
starts and the dashboard can say what is not configured yet.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path("/etc/triaina/config.toml")


@dataclass
class PrinterConfig:
    host: str = "neptune4.local"
    port: int = 7125
    api_key: Optional[str] = None
    timeout: float = 10.0
    #: Fluidd on the printer, linked from the dashboard.
    web_url: str = ""


@dataclass
class ServerConfig:
    bind: str = "0.0.0.0"
    port: int = 8080
    #: When set, every API call needs `Authorization: Bearer <token>` or
    #: `?token=<token>`. Off by default: the service is meant for a home LAN.
    auth_token: Optional[str] = None


@dataclass
class PathsConfig:
    #: Uploaded designs, generated files and the job database.
    data_dir: Path = Path("/var/lib/triaina")


@dataclass
class CutConfig:
    max_feed: float = 1500.0
    default_feed: float = 1500.0
    z_threshold: float = 0.0


@dataclass
class CameraConfig:
    #: MJPEG stream, e.g. crowsnest's http://<host>/webcam/?action=stream
    stream_url: str = ""


@dataclass
class Config:
    printer: PrinterConfig = field(default_factory=PrinterConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    cut: CutConfig = field(default_factory=CutConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    source: Optional[Path] = None

    @property
    def printer_url(self) -> str:
        host = self.printer.host
        if "://" in host:
            return host.rstrip("/")
        return f"http://{host}:{self.printer.port}"


class ConfigError(ValueError):
    """Raised for an unreadable file or an unknown key."""


def _apply(section: object, values: dict, name: str) -> None:
    known = {f.name: f for f in fields(section)}
    for key, value in values.items():
        if key not in known:
            # A typo in a key would otherwise be ignored silently.
            raise ConfigError(f"[{name}] unknown key: {key}")
        if known[key].type in ("Path", Path) or isinstance(getattr(section, key), Path):
            value = Path(value)
        setattr(section, key, value)


def load(path: Optional[Path] = None) -> Config:
    """Load the config. Raises ConfigError on bad TOML or unknown keys."""
    if path is None and os.environ.get("TRIAINA_CONFIG"):
        path = Path(os.environ["TRIAINA_CONFIG"])
    if path is None:
        path = DEFAULT_PATH
    cfg = Config()
    if not path.is_file():
        return cfg
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    for name, values in data.items():
        section = getattr(cfg, name, None)
        if section is None or name == "source" or not isinstance(values, dict):
            raise ConfigError(f"{path}: unknown section [{name}]")
        _apply(section, values, name)
    cfg.source = path
    return cfg
