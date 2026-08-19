"""
Entry point for the cytoflowweb server.

Usage::

    python -m cytoflowweb
    # or
    uvicorn cytoflowweb.api.main:app --host 0.0.0.0 --port 8000 --reload
"""

import uvicorn
from cytoflowweb.api.main import app  # noqa: F401 — ensures app is importable
from cytoflowweb import config


def main() -> None:
    uvicorn.run(
        "cytoflowweb.api.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level=config.LOG_LEVEL,
    )


if __name__ == "__main__":
    main()
