"""
cytoflowweb.dash_app.layout.main
----------------------------------

Top-level three-column layout:

  ┌──────────┬──────────────────────┬──────────────┐
  │ Sidebar  │      Canvas          │ Right Panel  │
  │ (pipeline│  (dcc.Graph plot)    │ (import /    │
  │  steps)  │                      │  params /    │
  │  ~220px  │      flex-grow       │  experiment) │
  │          │                      │  ~280px      │
  └──────────┴──────────────────────┴──────────────┘
"""

import dash_bootstrap_components as dbc
from dash import html, dcc

from cytoflowweb.dash_app.layout.sidebar import make_sidebar
from cytoflowweb.dash_app.layout.canvas import make_canvas
from cytoflowweb.dash_app.layout.right_panel import make_right_panel


def make_layout() -> html.Div:
    return html.Div(
        id="app-root",
        className="d-flex flex-column vh-100",
        children=[

            # ── Top navigation bar ─────────────────────────────────────────────
            dbc.Navbar(
                dbc.Container(
                    fluid=True,
                    children=[
                        dbc.NavbarBrand(
                            [html.Img(src="/assets/logo.png", height="28px", className="me-2"),
                             "cytoflow"],
                            className="fw-bold",
                        ),
                        dbc.Nav([
                            dbc.NavItem(dbc.NavLink(
                                [html.I(className="bi bi-question-circle me-1"), "Help"],
                                id="btn-help",
                                href="#",
                                className="nav-link",
                            )),
                        ], navbar=True, className="ms-auto"),
                    ],
                ),
                color="dark",
                dark=True,
                className="py-1",
            ),

            # ── Three-column body ─────────────────────────────────────────────
            html.Div(
                className="d-flex flex-row flex-grow-1 overflow-hidden",
                children=[
                    # Left sidebar
                    html.Div(
                        make_sidebar(),
                        style={"width": "220px", "minWidth": "220px"},
                        className="border-end bg-light h-100 overflow-hidden",
                    ),
                    # Central canvas
                    html.Div(
                        make_canvas(),
                        className="flex-grow-1 h-100 overflow-hidden",
                    ),
                    # Right panel
                    html.Div(
                        make_right_panel(),
                        style={"width": "280px", "minWidth": "280px"},
                        className="border-start bg-light h-100 overflow-hidden overflow-y-auto",
                    ),
                ],
            ),

            # ── Help offcanvas ────────────────────────────────────────────────
            dbc.Offcanvas(
                id="help-offcanvas",
                title="Help",
                is_open=False,
                placement="end",
                style={"width": "420px"},
                children=html.Div(id="help-content", className="p-2"),
            ),

            # ── Shared state stores ───────────────────────────────────────────
            dcc.Store(id="store-session-id",    storage_type="session"),
            dcc.Store(id="store-workflow",       storage_type="memory"),
            dcc.Store(id="store-selected-step",  storage_type="memory", data=-1),
            dcc.Store(id="store-uploaded-files", storage_type="memory", data=[]),

            # Poll for step status updates every 2 s while any step is running
            dcc.Interval(id="interval-status-poll", interval=2000, disabled=True),

            # Toast notifications
            html.Div(id="toast-container", className="position-fixed bottom-0 end-0 p-3",
                     style={"zIndex": 9999}),
        ],
    )
