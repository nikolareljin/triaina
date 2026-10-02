# Development

```bash
git clone --recursive https://github.com/nikolareljin/triaina.git
cd triaina
./dev install      # submodules, git hooks, .venv with test tools
./dev test         # pytest
./dev preflight    # everything CI runs, plus docs build
```

`./dev` is the shared CLI from
[script-helpers](https://github.com/nikolareljin/script-helpers); repo-specific
behaviour is in `scripts/project.sh`. `make` targets do the same things for
anyone without the submodule: `make install test lint format docs dist clean`.

## Layout

| Path | What |
|---|---|
| `config/klipper_cutter_macros.cfg` | Klipper macros |
| `config/inkcut_profile.json` | Inkcut reference values |
| `triaina/preprocess.py`, `triaina/printer.py` | G-code rewriter and Moonraker / OctoPrint client (stdlib only) |
| `triaina/config.py`, `jobs.py`, `monitor.py`, `web/` | The service: config, SQLite job store, printer poller, FastAPI app and page |
| `scripts/gcode_preprocessor.py`, `scripts/mode_switch.py` | CLI wrappers, run without installing |
| `deploy/` | systemd unit and example config |
| `scripts/setup_pi.sh` | Pi provisioning |
| `scripts/cli.sh`, `scripts/_bootstrap.sh`, `dev` | Shared `./dev` CLI from script-helpers |
| `scripts/preflight.sh`, `scripts/check-*.sh` | Local and CI gates |
| `tests/` | pytest, no network |
| `docs/`, `mkdocs.yml` | This site |

## Rules

- `preprocess` and `printer` use the standard library only, so the CLIs run on a fresh Pi.
- `./dev run` starts the dashboard with auto-reload; `python tests/fake_moonraker.py 7125`
  gives it a fake printer to talk to.
- Tests never touch the network; `urlopen` is mocked.
- Format with `black` (line length 100); `flake8` must be clean.
- Every pull request adds a line under `## Unreleased` in `CHANGELOG.md`.

## CI

All workflows call [ci-helpers](https://github.com/nikolareljin/ci-helpers)
presets at `@production`:

| Workflow | Runs |
|---|---|
| `pr-gate.yml` | Every pull request: lint, tests, shell checks, release-tag check |
| `ci.yml` | Push to main: same checks |
| `pages.yml` | Builds this site on PRs, deploys from main |
| `gitleaks.yml` | Secret scan on every push and PR |
| `release-tag-gate.yml` | Blocks a release PR whose tag exists |
| `auto-tag.yml` | Tags `X.Y.Z` on a merged `release/X.Y.Z` PR (ci-helpers `auto-tag.yml`), then builds and attaches the archive (ci-helpers `release-build.yml`) |
