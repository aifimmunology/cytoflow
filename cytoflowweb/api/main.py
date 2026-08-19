"""
cytoflowweb.api.main
---------------------

FastAPI application factory and entry point.

The Dash front end is mounted at ``/`` via Starlette's ``WSGIMiddleware``,
so all ``/api/`` prefixed routes are served by FastAPI and everything else
falls through to Dash.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

from cytoflowweb.api.workers.executor import init_executor, shutdown_executor
from cytoflowweb.api.routers import sessions, workflow, operations, files, views

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_executor()
    logger.info("cytoflowweb API started")
    yield
    shutdown_executor()
    logger.info("cytoflowweb API shut down")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="cytoflowweb",
        description="Browser-native front end for cytoflow flow cytometry analysis",
        version="0.1.0",
        lifespan=lifespan,
        # Mount API under /api so it doesn't conflict with Dash routes
        root_path="",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # tighten in production behind auth proxy
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routers ───────────────────────────────────────────────────────────
    api_prefix = "/api"
    app.include_router(sessions.router,   prefix=api_prefix)
    app.include_router(workflow.router,   prefix=api_prefix)
    app.include_router(operations.router, prefix=api_prefix)
    app.include_router(files.router,      prefix=api_prefix)
    app.include_router(views.router,      prefix=api_prefix)

    # ── Mount the Dash WSGI app at root ───────────────────────────────────────
    # Import here to avoid circular imports at module load time
    from cytoflowweb.dash_app.app import create_dash_app
    dash_app = create_dash_app(requests_pathname_prefix="/")
    app.mount("/", WSGIMiddleware(dash_app.server))

    return app


# Module-level instance used by uvicorn
app = create_app()
