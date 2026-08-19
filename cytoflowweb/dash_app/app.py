"""
cytoflowweb.dash_app.app
--------------------------

Dash application factory.

Usage (standalone dev server)::

    python -m cytoflowweb.dash_app.app

In production the app is mounted inside the FastAPI application via
``WSGIMiddleware`` (see ``cytoflowweb.api.main``).
"""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc

from cytoflowweb.dash_app.layout.main import make_layout
from cytoflowweb.dash_app.callbacks import workflow as workflow_cb
from cytoflowweb.dash_app.callbacks import import_cb
from cytoflowweb.dash_app.callbacks import plot as plot_cb


def create_dash_app(requests_pathname_prefix: str = "/") -> dash.Dash:
    """Create and configure the Dash application.

    Parameters
    ----------
    requests_pathname_prefix:
        URL prefix for the app.  Set to ``"/"`` when mounted at the root of
        the FastAPI application.
    """
    app = dash.Dash(
        __name__,
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            dbc.icons.BOOTSTRAP,
        ],
        requests_pathname_prefix=requests_pathname_prefix,
        suppress_callback_exceptions=True,
        title="cytoflow",
        update_title=None,
        meta_tags=[
            {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        ],
    )

    app.layout = make_layout()

    # Register all callback modules
    workflow_cb.register(app)
    import_cb.register(app)
    plot_cb.register(app)

    return app


if __name__ == "__main__":
    # Run a standalone Dash dev server (useful for layout development without
    # needing the FastAPI backend)
    _app = create_dash_app()
    _app.run(debug=True, port=8050)
