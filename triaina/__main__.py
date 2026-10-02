"""`python -m triaina serve [--config PATH] [--host H] [--port N] [--reload]`."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from triaina import __version__
from triaina.config import ConfigError, load


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="triaina")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the dashboard and printer monitor")
    serve.add_argument(
        "--config",
        type=Path,
        help="TOML file (default: $TRIAINA_CONFIG or /etc/triaina/config.toml)",
    )
    serve.add_argument("--host", help="bind address (overrides [server].bind)")
    serve.add_argument("--port", type=int, help="port (overrides [server].port)")
    serve.add_argument("--reload", action="store_true", help="development: reload on code change")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        cfg = load(args.config)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    import uvicorn

    from triaina.web.app import create_app

    host = cfg.server.bind if args.host is None else args.host
    # `is None`, not `or`: --port 0 (any free port) is a valid choice.
    port = cfg.server.port if args.port is None else args.port
    logging.getLogger("triaina").info(
        "config %s, printer %s, data %s",
        cfg.source or "(defaults)",
        cfg.printer_url,
        cfg.paths.data_dir,
    )
    if args.reload:
        # Reload needs an import string; the factory re-reads the config.
        import os

        if args.config:
            os.environ["TRIAINA_CONFIG"] = str(args.config)
        uvicorn.run("triaina.web.factory:app", host=host, port=port, reload=True, factory=True)
    else:
        uvicorn.run(create_app(cfg), host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
