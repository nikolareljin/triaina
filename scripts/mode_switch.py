#!/usr/bin/env python3
"""CLI wrapper for triaina.printer. Runs from a clone or a release archive, no install needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from triaina.printer import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
