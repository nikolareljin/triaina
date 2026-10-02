#!/usr/bin/env bash
# SCRIPT: check-changelog.sh
# DESCRIPTION: Verify the newest CHANGELOG release header parses. Release notes
#              are generated from it, and a malformed header does not fail
#              anything by itself — it silently falls back to an auto-generated
#              commit list, which nobody notices until they read a release page.
# USAGE: bash scripts/check-changelog.sh
#
# EXIT_CODES:
#   0  The header is well formed.
#   1  The header does not parse, or script-helpers is missing.
#
# NOTES:
#   Canonical form is `## YYYY-MM-DD — vX.Y.Z` with an em-dash. An ASCII hyphen
#   is rejected. `## [Unreleased]` at the top is allowed and skipped.
#
#   Its own script rather than a line inside preflight, because CI runs it
#   without running preflight and both must mean the same thing.
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
shlib_import logging changelog

changelog_check_header "$ROOT_DIR/CHANGELOG.md"
