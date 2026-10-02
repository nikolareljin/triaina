"""The docs name everything a user can set or call. New code without docs fails here.

Checks names, not prose: config keys, API routes and form fields, CLI options,
Make targets, and that every docs page is in the site navigation.
"""

import dataclasses
import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from triaina import config
from triaina.web import app as webapp

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("section", ["printer", "server", "paths", "cut", "camera", "print"])
def test_every_config_key_documented(section):
    page = text("docs/setup/service.md")
    keys = [f.name for f in dataclasses.fields(getattr(config.Config(), section))]
    assert [k for k in keys if f"`{k}`" not in page] == []


def test_every_api_route_documented(tmp_path):
    cfg = config.Config()
    cfg.paths.data_dir = tmp_path
    page = text("docs/use/dashboard.md")
    missing = []
    for route in webapp.create_app(cfg, start_monitor=False).routes:
        path = getattr(route, "path", "")
        if not path.startswith(("/api", "/ws", "/healthz")) or path.startswith("/api/docs"):
            continue
        if "openapi" in path:
            continue
        # `/api/jobs/{id}` is written as is; `/api/mode/{mode}` as `/api/mode/{cutter,printer}`.
        if f"`{path}`" not in page and f"`{path.split('{')[0]}" not in page:
            missing.append(path)
    assert missing == []


def test_every_job_form_field_documented():
    page = text("docs/use/dashboard.md")
    fields = re.findall(r"(\w+): [^=\n]+= (?:Form|File)\(", inspect.getsource(webapp))
    assert [f for f in fields if f"`{f}`" not in page] == []


@pytest.mark.parametrize(
    "cmd, page",
    [
        ([sys.executable, "scripts/mode_switch.py", "--help"], "docs/reference/mode-switch.md"),
        (
            [sys.executable, "scripts/gcode_preprocessor.py", "--help"],
            "docs/reference/gcode-preprocessor.md",
        ),
        (["bash", "scripts/setup_pi.sh", "--help"], "docs/reference/setup-pi.md"),
        ([sys.executable, "-m", "triaina", "serve", "--help"], "docs/setup/service.md"),
    ],
)
def test_every_cli_option_documented(cmd, page):
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout
    options = set(re.findall(r"(--[a-z][a-z-]+)", out)) - {"--help"}
    assert options, "no options parsed: help output changed?"
    doc = text(page)
    assert (
        sorted(o for o in options if not re.search(rf"(?<![\w-]){re.escape(o)}(?![\w-])", doc))
        == []
    )


def test_every_make_target_documented():
    targets = re.findall(r"^([a-z-]+):.*## ", text("Makefile"), re.M)
    page = text("docs/develop/development.md")
    assert [t for t in targets if t not in page] == []


def test_every_page_in_navigation():
    def flat(items):
        for item in items:
            for value in item.values():
                yield from flat(value) if isinstance(value, list) else [value]

    nav = set(flat(yaml.safe_load(text("mkdocs.yml"))["nav"]))
    pages = {str(p.relative_to(DOCS)) for p in DOCS.rglob("*.md")}
    assert sorted(pages - nav) == [] and sorted(nav - pages) == []
