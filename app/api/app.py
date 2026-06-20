"""FastAPI application factory.

Bind to the Tailscale interface (or 127.0.0.1) in production — never 0.0.0.0.
The API is read-mostly and has no dependency on discovery/scoring being up:
the dashboard renders whatever is already in the DB (graceful degradation).
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app import __version__
from app.api.routes import router
from app.db.connection import apply_schema

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(title="Job Discovery & Application Copilot", version=__version__)
    apply_schema()  # idempotent; ensures tables exist regardless of lifespan
    app.include_router(router)
    return app


app = create_app()
