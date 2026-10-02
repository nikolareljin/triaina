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

# The dashboard with auto-reload, against the printer in $TRIAINA_CONFIG (or
# defaults). Data goes to .dev-data/ instead of /var/lib/triaina.
project_run() {
  local cfg="${TRIAINA_CONFIG:-$DEV_REPO_ROOT/.dev-config.toml}"
  if [[ ! -f "$cfg" ]]; then
    printf '[paths]\ndata_dir = "%s"\n[server]\nbind = "127.0.0.1"\n' "$DEV_REPO_ROOT/.dev-data" > "$cfg"
    log_info "run: wrote $cfg (edit [printer] host to point at your printer)"
  fi
  triaina_python -m triaina serve --config "$cfg" --reload "${DEV_ARGS[@]+"${DEV_ARGS[@]}"}"
}

project_deploy() {
  not_applicable deploy "run scripts/setup_pi.sh on the Raspberry Pi instead"
}

project_preflight() {
  bash "$DEV_REPO_ROOT/scripts/preflight.sh" "${DEV_ARGS[@]+"${DEV_ARGS[@]}"}"
}
