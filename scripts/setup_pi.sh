#!/usr/bin/env bash
# Set up a Raspberry Pi (Raspberry Pi OS / OctoPi) as the triaina companion host.
#
# Idempotent: safe to run again after a pull or a board swap. It
#   1. installs python3, python3-venv and usbutils if missing (apt),
#   2. creates or reuses .venv and installs requirements.txt into it,
#   3. with --udev only: writes /etc/udev/rules.d/99-triaina.rules so a USB
#      cable to the printer's USB-C port appears as /dev/triaina, then reloads
#      udev. That port is the built-in Linux host's serial console (1500000
#      baud), useful for recovery. It is NOT a link to the MCU, and normal use
#      (Moonraker over the network) needs no cable at all.
#   4. with --service: installs the dashboard to /opt/triaina as a systemd
#      service that starts on boot and restarts on failure (user `triaina`,
#      config /etc/triaina/config.toml, data /var/lib/triaina), then checks
#      http://127.0.0.1:<port>/healthz. Re-run after `git pull` to update.
#
# Usage: scripts/setup_pi.sh [--service] [--udev [--vid XXXX --pid XXXX]] [--skip-apt] [--dry-run]
# Docs:  docs/setup/pi.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
UDEV_RULE="/etc/udev/rules.d/99-triaina.rules"
SERVICE_USER="triaina"
INSTALL_DIR="/opt/triaina"
CONFIG_FILE="/etc/triaina/config.toml"
UNIT_FILE="/etc/systemd/system/triaina.service"
APT_PACKAGES=(python3 python3-venv python3-pip usbutils curl)

# USB-serial bridges seen behind the Neptune 4 USB-C console port. Order
# matters: first match wins. Pass --vid/--pid if lsusb shows something else.
#   1a86:7523  CH340
#   10c4:ea60  CP210x
KNOWN_IDS=("1a86:7523" "10c4:ea60")

# Prefer script-helpers (submodule at scripts/script-helpers). Fall back to
# minimal local functions so a clone without --recursive still works.
if [[ -f "$SCRIPT_DIR/script-helpers/helpers.sh" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/script-helpers/helpers.sh"
  shlib_import logging os python
else
  log_info()  { printf '\033[0;32m[INFO]\033[0m %s\n' "$*" >&2; }
  log_warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
  log_error() { printf '\033[0;31m[ERROR]\033[0m %s\n' "$*" >&2; }
  log_warn "script-helpers not found; run: git submodule update --init"
fi

usage() {
  sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

VID=""
PID=""
SKIP_APT=false
WITH_UDEV=false
WITH_SERVICE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vid) VID="${2:?--vid needs a value}"; shift 2 ;;
    --pid) PID="${2:?--pid needs a value}"; shift 2 ;;
    --skip-apt) SKIP_APT=true; shift ;;
    --udev) WITH_UDEV=true; shift ;;
    --service) WITH_SERVICE=true; shift ;;
    --skip-udev) log_warn "--skip-udev is now the default; flag ignored"; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) log_error "unknown argument: $1"; usage; exit 2 ;;
  esac
done

if [[ -n "$VID" || -n "$PID" ]] && ! $WITH_UDEV; then
  log_error "--vid/--pid only apply with --udev"
  exit 2
fi
if [[ -n "$VID" || -n "$PID" ]] && [[ -z "$VID" || -z "$PID" ]]; then
  log_error "--vid and --pid must be given together"
  exit 2
fi
for id in "$VID" "$PID"; do
  if [[ -n "$id" && ! "$id" =~ ^[0-9a-fA-F]{4}$ ]]; then
    log_error "USB ids are 4 hex digits, got: $id"
    exit 2
  fi
done

# Run a command, or print it under --dry-run.
run() {
  if $DRY_RUN; then
    printf '[dry-run] %s\n' "$*" >&2
  else
    "$@"
  fi
}

SUDO=""
if [[ $EUID -ne 0 ]]; then
  SUDO="sudo"
fi
# Read-only checks: no sudo under --dry-run, so a preview never asks for a password.
CHECK_SUDO="$SUDO"
$DRY_RUN && CHECK_SUDO=""

install_apt_packages() {
  local missing=() pkg
  for pkg in "${APT_PACKAGES[@]}"; do
    dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed" ||
      missing+=("$pkg")
  done
  if [[ ${#missing[@]} -eq 0 ]]; then
    log_info "apt packages present"
    return 0
  fi
  log_info "installing: ${missing[*]}"
  run $SUDO apt-get update
  run $SUDO apt-get install -y "${missing[@]}"
}

setup_venv() {
  local python_bin
  python_bin="$(command -v python3 || true)"
  if [[ -z "$python_bin" ]]; then
    log_error "python3 not found"
    return 1
  fi
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log_info "creating $VENV_DIR"
    run "$python_bin" -m venv "$VENV_DIR"
  else
    log_info "reusing $VENV_DIR"
  fi
  run "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
  run "$VENV_DIR/bin/python" -m pip install --quiet -r "$REPO_ROOT/requirements.txt"
}

# Print "vid:pid" of the first connected known board, or nothing.
detect_board() {
  local id
  command -v lsusb >/dev/null 2>&1 || return 0
  for id in "${KNOWN_IDS[@]}"; do
    if lsusb -d "$id" >/dev/null 2>&1; then
      echo "$id"
      return 0
    fi
  done
}

install_udev_rule() {
  if [[ -z "$VID" ]]; then
    local found
    found="$(detect_board)"
    if [[ -z "$found" ]]; then
      log_error "no known console bridge on USB. Connect the printer USB-C port, or pass --vid/--pid (see: lsusb)"
      return 1
    fi
    VID="${found%%:*}"
    PID="${found##*:}"
    log_info "detected console bridge $VID:$PID"
  fi

  local rule
  rule="SUBSYSTEM==\"tty\", ATTRS{idVendor}==\"${VID,,}\", ATTRS{idProduct}==\"${PID,,}\", SYMLINK+=\"triaina\", MODE=\"0660\", GROUP=\"dialout\""

  if [[ -f "$UDEV_RULE" ]] && [[ "$(cat "$UDEV_RULE")" == "$rule" ]]; then
    log_info "udev rule unchanged: $UDEV_RULE"
    return 0
  fi
  log_info "writing $UDEV_RULE"
  if $DRY_RUN; then
    printf '[dry-run] %s <- %s\n' "$UDEV_RULE" "$rule" >&2
  else
    printf '%s\n' "$rule" | $SUDO tee "$UDEV_RULE" >/dev/null
  fi
  run $SUDO udevadm control --reload-rules
  run $SUDO udevadm trigger --subsystem-match=tty
}

ensure_dialout() {
  local user="${SUDO_USER:-$USER}"
  if id -nG "$user" | tr ' ' '\n' | grep -qx dialout; then
    return 0
  fi
  log_info "adding $user to dialout (log out and back in to apply)"
  run $SUDO usermod -aG dialout "$user"
}

# Copy a file into place only when the content differs. Returns 0 if it changed.
install_if_changed() {
  local src="$1" dest="$2" mode="$3" owner="$4"
  if $CHECK_SUDO test -f "$dest" && $CHECK_SUDO cmp -s "$src" "$dest"; then
    return 1
  fi
  run $SUDO install -D -m "$mode" -o "${owner%%:*}" -g "${owner##*:}" "$src" "$dest"
  return 0
}

install_service() {
  local port unit_changed=false
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    log_info "creating system user $SERVICE_USER"
    run $SUDO useradd --system --home-dir /var/lib/triaina --shell /usr/sbin/nologin "$SERVICE_USER"
  fi

  if [[ ! -x "$INSTALL_DIR/.venv/bin/python" ]]; then
    log_info "creating $INSTALL_DIR/.venv"
    run $SUDO mkdir -p "$INSTALL_DIR"
    run $SUDO python3 -m venv "$INSTALL_DIR/.venv"
  fi
  # Build the wheel as the invoking user, then install only the wheel as root.
  # `sudo pip install <clone>` would build inside the clone and leave
  # root-owned build/ and *.egg-info behind in the user's working copy.
  local wheel_dir builder
  builder="$VENV_DIR/bin/python"
  [[ -x "$builder" ]] || builder="python3"
  wheel_dir="$(mktemp -d)"
  log_info "building triaina wheel"
  run "$builder" -m pip wheel --quiet --no-deps --wheel-dir "$wheel_dir" "$REPO_ROOT"
  log_info "installing triaina into $INSTALL_DIR/.venv"
  run $SUDO "$INSTALL_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
  # --force-reinstall --no-deps first: the version stays 0.1.0 between commits,
  # so pip would otherwise keep the old code after `git pull`. Then resolve deps.
  run $SUDO "$INSTALL_DIR/.venv/bin/python" -m pip install --quiet --force-reinstall --no-deps "$wheel_dir"/triaina-*.whl
  run $SUDO "$INSTALL_DIR/.venv/bin/python" -m pip install --quiet "$wheel_dir"/triaina-*.whl
  rm -rf "$wheel_dir"

  # Never overwrite a config the user has edited.
  if $CHECK_SUDO test -f "$CONFIG_FILE"; then
    log_info "keeping existing $CONFIG_FILE"
  else
    log_info "writing default $CONFIG_FILE (edit [printer] host)"
    install_if_changed "$REPO_ROOT/deploy/config.example.toml" "$CONFIG_FILE" 0640 "root:$SERVICE_USER" || true
  fi

  if install_if_changed "$REPO_ROOT/deploy/triaina.service" "$UNIT_FILE" 0644 "root:root"; then
    unit_changed=true
    run $SUDO systemctl daemon-reload
  fi
  run $SUDO systemctl enable triaina.service
  # Restart every time: the package may have changed even when the unit did not.
  run $SUDO systemctl restart triaina.service
  $unit_changed && log_info "installed $UNIT_FILE"

  $DRY_RUN && return 0
  # Read the port the way the service does, so [printer] port is never mistaken for it.
  port="$($SUDO "$INSTALL_DIR/.venv/bin/python" -c \
    "from pathlib import Path; from triaina.config import load; print(load(Path('$CONFIG_FILE')).server.port)")"
  local _
  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$port/healthz" >/dev/null 2>&1; then
      log_info "dashboard up: http://$(hostname).local:$port/"
      return 0
    fi
    sleep 1
  done
  log_error "service did not answer on port $port within 30 s; see: journalctl -u triaina -n 50"
  return 1
}

main() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "setup_pi.sh targets Linux (Raspberry Pi OS); got $(uname -s)"
    exit 1
  fi
  $SKIP_APT || install_apt_packages
  setup_venv
  if $WITH_UDEV; then
    install_udev_rule
    ensure_dialout
  fi
  if $WITH_SERVICE; then
    install_service
  fi
  log_info "done. Next: docs/setup/klipper.md"
  $WITH_UDEV && log_info "printer console: screen /dev/triaina 1500000 (after replug)"
  return 0
}

main
