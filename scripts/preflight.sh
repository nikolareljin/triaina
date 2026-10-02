#!/usr/bin/env bash
# SCRIPT: preflight.sh
# DESCRIPTION: Every check CI runs, plus the public-boundary scan and the
#              CHANGELOG header format. The pre-push hook calls this through
#              `./dev preflight`.
# USAGE: ./dev preflight [--quick]
#
# PARAMETERS:
#   --quick   Skip the docs build (the slowest step).
#   -h        Show this help message.
#
# EXIT_CODES:
#   0  Everything passed.
#   1  A check failed. The failing check names itself.
#   2  Bad arguments.
# ----------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SCRIPT_HELPERS_DIR="${SCRIPT_HELPERS_DIR:-$SCRIPT_DIR/script-helpers}"
if [[ ! -f "$SCRIPT_HELPERS_DIR/helpers.sh" ]]; then
  echo "script-helpers not initialized. Run: git submodule update --init --recursive" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$SCRIPT_HELPERS_DIR/helpers.sh"
shlib_import logging help

QUICK=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) QUICK=true; shift ;;
    -h|--help) show_help "${BASH_SOURCE[0]}"; exit 0 ;;
    *) log_error "unknown argument: $1"; exit 2 ;;
  esac
done

cd "$ROOT_DIR"
PY="$ROOT_DIR/.venv/bin/python"
[[ -x "$PY" ]] || { log_error "no .venv; run ./dev install"; exit 1; }

FAILED=()
run_check() {
  local name="$1"; shift
  log_info "preflight: $name"
  if "$@"; then
    return 0
  fi
  log_error "preflight: $name FAILED"
  FAILED+=("$name")
  return 0
}

run_check "public-boundary scan" bash "$SCRIPT_DIR/check-private-names.sh"
run_check "CHANGELOG header format" bash "$SCRIPT_DIR/check-changelog.sh"
run_check "black" "$PY" -m black --check scripts tests
run_check "flake8" "$PY" -m flake8 scripts tests
run_check "pytest" "$PY" -m pytest -q
run_check "bash -n setup_pi.sh" bash -n scripts/setup_pi.sh

if command -v shellcheck >/dev/null 2>&1; then
  run_check "shellcheck" shellcheck -S warning scripts/setup_pi.sh scripts/preflight.sh \
    scripts/project.sh scripts/check-private-names.sh scripts/check-changelog.sh
else
  log_warn "preflight: shellcheck not installed; CI will run it"
fi

if ! $QUICK; then
  run_check "docs build" bash -c "'$PY' -m pip install --quiet -r requirements-docs.txt && '$PY' -m mkdocs build --strict --quiet"
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  log_error "preflight failed: ${FAILED[*]}"
  exit 1
fi
log_info "preflight: all checks passed"
