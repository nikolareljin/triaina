#!/usr/bin/env bash
# Repo-specific overrides for ./dev. Sourced by scripts/cli.sh before dispatch.
#
# triaina is a Python + shell toolkit with no build step and no device app, so
# only install, test, lint, build (the release archive) and preflight differ
# from the shared template.

TRIAINA_PY="$DEV_REPO_ROOT/.venv/bin/python"

triaina_python() {
  [[ -x "$TRIAINA_PY" ]] || { log_error "no .venv; run ./dev install"; return 1; }
  "$TRIAINA_PY" "$@"
}

project_install() {
  log_info "install: submodules"
  git -C "$DEV_REPO_ROOT" submodule update --init --recursive
  dev_install_hooks
  make -C "$DEV_REPO_ROOT" install
}

project_test() {
  triaina_python -m pytest "${DEV_ARGS[@]+"${DEV_ARGS[@]}"}"
}

# The release archive, dist/triaina-<tag>.tar.gz.
project_build() {
  make -C "$DEV_REPO_ROOT" dist
}

project_run() {
  not_applicable run "nothing to start; see docs/use/workflow.md for the cut pipeline"
}

project_deploy() {
  not_applicable deploy "run scripts/setup_pi.sh on the Raspberry Pi instead"
}

project_preflight() {
  bash "$DEV_REPO_ROOT/scripts/preflight.sh" "${DEV_ARGS[@]+"${DEV_ARGS[@]}"}"
}
