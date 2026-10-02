"""VERSION (read by the release tooling) and the package version must agree.

./dev release bumps VERSION only; the package, /healthz and the wheel read
triaina.__version__. A mismatch ships a release that reports the old number.
"""

from pathlib import Path

import triaina


def test_version_file_matches_package():
    version = (Path(__file__).resolve().parent.parent / "VERSION").read_text().strip()
    assert triaina.__version__ == version
