"""Production web entrypoint serving the API and compiled frontend together."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import create_app


def create_web_app(static_dir: str | Path) -> FastAPI:
    """Create the production app with the API mounted before frontend assets."""
    directory = Path(static_dir)
    if not directory.is_dir():
        raise RuntimeError(f"Frontend build directory does not exist: {directory}")
    app = create_app()
    app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
    return app


_static_dir = os.environ.get("SCINAPSE_FRONTEND_DIST", "/app/frontend/dist")
app = create_web_app(_static_dir) if Path(_static_dir).is_dir() else create_app()
