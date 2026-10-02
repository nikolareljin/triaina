#!/usr/bin/env bash
# Set up a Raspberry Pi (Raspberry Pi OS / OctoPi) as the triaina companion host.
#
# Idempotent: safe to run again after a pull or a board swap. It
#   1. installs python3, python3-venv and usbutils if missing (apt),
#   2. creates or reuses .venv and installs requirements.txt into it,
#   3. writes /etc/udev/rules.d/99-triaina.rules so the mainboard is /dev/triaina,
#      only when the rule content changed, then reloads udev.
#
# Usage: scripts/setup_pi.sh [--vid XXXX --pid XXXX] [--skip-apt] [--skip-udev] [--dry-run]
# Docs:  docs/setup/pi.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
UDEV_RULE="/etc/udev/rules.d/99-triaina.rules"
APT_PACKAGES=(python3 python3-venv python3-pip usbutils)

# USB IDs seen on Neptune 4 MKS boards. Order matters: first match wins.
#   1d50:614e  Klipper USB firmware on the STM32 (native USB)
#   1a86:7523  CH340 USB-serial bridge
KNOWN_IDS=("1d50:614e" "1a86:7523")

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
  sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

VID=""
PID=""
SKIP_APT=false
SKIP_UDEV=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vid) VID="${2:?--vid needs a value}"; shift 2 ;;
    --pid) PID="${2:?--pid needs a value}"; shift 2 ;;
    --skip-apt) SKIP_APT=true; shift ;;
    --skip-udev) SKIP_UDEV=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) log_error "unknown argument: $1"; usage; exit 2 ;;
  esac
done

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
      log_error "no known mainboard on USB. Connect it, or pass --vid/--pid (see: lsusb)"
      return 1
    fi
    VID="${found%%:*}"
    PID="${found##*:}"
    log_info "detected mainboard $VID:$PID"
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

main() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    log_error "setup_pi.sh targets Linux (Raspberry Pi OS); got $(uname -s)"
    exit 1
  fi
  $SKIP_APT || install_apt_packages
  setup_venv
  if ! $SKIP_UDEV; then
    install_udev_rule
    ensure_dialout
  fi
  log_info "done. Mainboard: /dev/triaina (after replug). Next: docs/setup/klipper.md"
}

main
