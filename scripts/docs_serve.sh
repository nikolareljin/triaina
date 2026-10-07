#!/usr/bin/env bash
# SCRIPT: docs_serve.sh
# DESCRIPTION: Start the MkDocs preview on the first available local port.
# USAGE: bash scripts/docs_serve.sh <python>
#
# EXIT_CODES:
#   0  The server stops normally.
#   1  No preview port was available.
#   2  Bad arguments.
set -euo pipefail

if [[ $# -ne 1 || ! -x $1 ]]; then
  echo "usage: bash scripts/docs_serve.sh <python>" >&2
  exit 2
fi

python="$1"
for port in $(seq 8000 8010); do
  if "$python" -c '
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", port))
' "$port" 2>/dev/null; then
    echo "docs preview: http://127.0.0.1:$port/triaina/"
    exec "$python" -m mkdocs serve --dev-addr "127.0.0.1:$port"
  fi
done

echo "no free documentation preview port found from 8000 through 8010" >&2
exit 1
