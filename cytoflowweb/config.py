"""
cytoflowweb.config
-------------------

Central configuration read from environment variables.

All settings have sensible defaults for local development.  In Docker /
production, override them via the ``environment:`` block in
``docker-compose.yml``.

Environment variables
---------------------
CYTOFLOWWEB_HOST
    Interface the uvicorn server binds to. Default ``127.0.0.1`` (localhost
    only).  Set to ``0.0.0.0`` in Docker to accept external connections.

CYTOFLOWWEB_PORT
    TCP port the server listens on. Default ``8000``.

CYTOFLOWWEB_API_BASE
    Base URL for server-side Dash callbacks to reach the FastAPI routers.
    Both Dash and FastAPI run in the same container, so this is always a
    localhost URL.  Default ``http://localhost:8000/api``.

CYTOFLOWWEB_UPLOAD_ROOT
    Directory where uploaded FCS files are stored.
    Default: a ``cytoflowweb_uploads`` sub-directory of the system temp dir.

CYTOFLOWWEB_MAX_SESSIONS
    Maximum number of concurrent sessions held in the in-memory LRU cache.
    Default ``50``.

CYTOFLOWWEB_LOG_LEVEL
    Logging level passed to uvicorn.  Default ``info``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# ── Server binding ─────────────────────────────────────────────────────────

HOST: str = os.environ.get("CYTOFLOWWEB_HOST", "127.0.0.1")
PORT: int = int(os.environ.get("CYTOFLOWWEB_PORT", "8000"))

# ── Inter-service base URL ─────────────────────────────────────────────────

API_BASE: str = os.environ.get(
    "CYTOFLOWWEB_API_BASE",
    f"http://localhost:{PORT}/api",
)

# ── Storage ────────────────────────────────────────────────────────────────

UPLOAD_ROOT: Path = Path(
    os.environ.get(
        "CYTOFLOWWEB_UPLOAD_ROOT",
        str(Path(tempfile.gettempdir()) / "cytoflowweb_uploads"),
    )
)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# ── Session management ─────────────────────────────────────────────────────

MAX_SESSIONS: int = int(os.environ.get("CYTOFLOWWEB_MAX_SESSIONS", "50"))

# ── Logging ────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.environ.get("CYTOFLOWWEB_LOG_LEVEL", "info")
