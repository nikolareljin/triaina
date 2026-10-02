"""App factory for `uvicorn --factory` (development reload)."""

from triaina.config import load
from triaina.web.app import create_app


def app():
    return create_app(load())
