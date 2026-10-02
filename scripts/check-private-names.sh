#!/usr/bin/env bash
# SCRIPT: check-private-names.sh
# DESCRIPTION: Fail if anything that must not be in a public repository has been
#              committed — a private project name, a private-range IP literal, a
#              tooling co-authorship trailer, or a signing key. Runs in preflight
#              and in CI.
# USAGE: bash scripts/check-private-names.sh [--staged]
#
# PARAMETERS:
#   --staged  Scan the staged diff instead of the whole tracked tree.
#   -h        Show this help message.
#
# EXIT_CODES:
#   0  Clean.
#   1  A forbidden pattern was found. The offending file and line are printed.
#   2  Bad arguments.
#
# NOTES:
#   The private-name wordlist lives in .private-names at the repository root and
#   is gitignored — the list of private project names must not itself be
#   published. One name per line, '#' comments allowed. When the file is absent
#   (a fresh clone, or CI) that half of the check is skipped with a warning; the
#   pattern checks below always run.
# ----------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SCRIPT_HELPERS_DIR="${SCRIPT_HELPERS_DIR:-$SCRIPT_DIR/script-helpers}"
if [[ -f "$SCRIPT_HELPERS_DIR/helpers.sh" ]]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_HELPERS_DIR/helpers.sh"
  shlib_import logging help >/dev/null 2>&1 || true
fi
type log_info  >/dev/null 2>&1 || log_info()  { echo "[boundary] $*"; }
type log_warn  >/dev/null 2>&1 || log_warn()  { echo "[boundary][WARN] $*" >&2; }
type log_error >/dev/null 2>&1 || log_error() { echo "[boundary][ERROR] $*" >&2; }

STAGED=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --staged) STAGED=true; shift ;;
    -h|--help) sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) log_error "unknown argument: $1"; exit 2 ;;
  esac
done

cd "$ROOT_DIR"

# This script necessarily contains the patterns it looks for. Excluding it here
# is why the check does not trip over itself.
SELF="scripts/check-private-names.sh"

files() {
  if [[ "$STAGED" == "true" ]]; then
    git diff --cached --name-only --diff-filter=ACMR
  else
    # Tracked *and* not-yet-staged files. Scanning only the index would let a
    # leak sit in the working tree until the moment it is committed, which is
    # exactly when nobody is looking.
    git ls-files --cached --others --exclude-standard
  fi | grep -v "^scripts/script-helpers/" | grep -v "^${SELF}$" || true
}

mapfile -t FILES < <(files)
if [[ ${#FILES[@]} -eq 0 ]]; then
  log_info "nothing to scan"
  exit 0
fi

FOUND=0
report() {
  local label="$1" hits="$2"
  [[ -z "$hits" ]] && return 0
  log_error "$label"
  printf '%s\n' "$hits" | sed 's/^/    /'
  FOUND=1
}

scan() {
  # scan <label> <extended-regex>
  local label="$1" pattern="$2" hits
  hits="$(grep -nIE --binary-files=without-match "$pattern" "${FILES[@]}" 2>/dev/null || true)"
  report "$label" "$hits"
}

# --- 1. Private project names (wordlist is gitignored) ------------------------

WORDLIST="$ROOT_DIR/.private-names"
if [[ -f "$WORDLIST" ]]; then
  mapfile -t NAMES < <(grep -vE '^\s*(#|$)' "$WORDLIST" || true)
  if [[ ${#NAMES[@]} -gt 0 ]]; then
    joined="$(printf '%s|' "${NAMES[@]}")"
    scan "private project name referenced" "\\b(${joined%|})\\b"
  fi
else
  log_warn "no .private-names wordlist — name check skipped (see the header of this script)"
fi

# --- 1b. Any sibling repository referenced by URL ------------------------------
# Catches what the wordlist cannot: names that are also ordinary English words
# ("anchor", "notifications") are left out of .private-names to avoid constant
# false positives, so a reference to one is caught here, where the surrounding
# owner/repo form makes the intent unambiguous. Only the public dependencies of
# this repository are allowed. `stats` is nikolareljin/stats, the public
# chart-assets repository the clone-traffic badge in README.md renders from;
# it is public by design, so naming it leaks nothing.

OWNER_REFS="$(grep -nIoE --binary-files=without-match \
  '(github\.com[/:]|\b)nikolareljin/[A-Za-z0-9._-]+' "${FILES[@]}" 2>/dev/null \
  | grep -vE '/(triaina|ci-helpers|script-helpers|stats)(\.git)?\.?([^A-Za-z0-9._-]|$)' || true)"
report "reference to another repository under the same owner" "$OWNER_REFS"

# --- 2. Private-range IP literals ---------------------------------------------
# Documentation must use the RFC 5737 ranges (192.0.2.x, 198.51.100.x,
# 203.0.113.x), an mDNS .local name, or loopback. A real LAN address in a public
# repo describes someone's actual network.

scan "private-range IP literal (use RFC 5737 documentation ranges)" \
  '(^|[^0-9.])(192\.168\.[0-9]{1,3}\.[0-9]{1,3}|10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9.]|$)'

# --- 3. Tooling co-authorship trailers ----------------------------------------

scan "co-authorship trailer for a tool or model" \
  '^(Co-Authored-By|Signed-off-by):.*(Claude|Anthropic|Copilot|GPT|Gemini|AI)'

# --- 4. Credentials and signing material --------------------------------------

scan "private key material" '-----BEGIN [A-Z ]*PRIVATE KEY-----'

KEYSTORES="$(printf '%s\n' "${FILES[@]}" | grep -E '\.(jks|keystore|p12|pfx|pem|key)$' || true)"
report "signing material committed" "$KEYSTORES"

ENVFILES="$(printf '%s\n' "${FILES[@]}" | grep -E '(^|/)\.env(\.|$)' | grep -vE '\.example$' || true)"
report "environment file committed" "$ENVFILES"

# --- Verdict ------------------------------------------------------------------

if [[ $FOUND -ne 0 ]]; then
  log_error "public-boundary scan failed; cite private repositories by code, never by name"
  exit 1
fi
log_info "public-boundary scan clean (${#FILES[@]} files)"
