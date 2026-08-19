"""
cytoflowweb.dash_app.layout.sidebar
-------------------------------------

Left sidebar: pipeline step list (accordion) and the Add Step toolbar.
"""

import dash_bootstrap_components as dbc
from dash import html, dcc


def make_sidebar() -> html.Div:
    return html.Div(
        id="sidebar",
        className="sidebar d-flex flex-column h-100",
        children=[
            # ── Header ────────────────────────────────────────────────────────
            html.Div(
                className="sidebar-header p-2 border-bottom",
                children=[
                    html.H6("Pipeline", className="mb-1 fw-bold"),
                    dbc.Button(
                        [html.I(className="bi bi-plus-lg me-1"), "Add Step"],
                        id="btn-add-step",
                        color="primary",
                        size="sm",
                        className="w-100",
                    ),
                ],
            ),

            # ── Step list ─────────────────────────────────────────────────────
            html.Div(
                id="pipeline-steps",
                className="flex-grow-1 overflow-auto p-2",
                children=[
                    html.P(
                        "Upload FCS files to begin.",
                        className="text-muted small mt-2",
                        id="pipeline-empty-msg",
                    )
                ],
            ),

            # ── Add-step modal ────────────────────────────────────────────────
            dbc.Modal(
                id="modal-add-step",
                is_open=False,
                size="lg",
                children=[
                    dbc.ModalHeader(dbc.ModalTitle("Add Operation")),
                    dbc.ModalBody(
                        dcc.Dropdown(
                            id="dropdown-op-select",
                            placeholder="Choose an operation…",
                            options=[],   # populated by callback from operation registry
                        )
                    ),
                    dbc.ModalFooter([
                        dbc.Button("Add", id="btn-confirm-add-step", color="primary"),
                        dbc.Button("Cancel", id="btn-cancel-add-step", color="secondary", className="ms-2"),
                    ]),
                ],
            ),
        ],
    )


def make_step_card(index: int, friendly_id: str, status: str, selected: bool) -> dbc.Card:
    """Render a single pipeline step card."""
    status_colors = {
        "valid":      "success",
        "applying":   "warning",
        "estimating": "warning",
        "invalid":    "secondary",
        "waiting":    "secondary",
        "error":      "danger",
    }
    color = status_colors.get(status, "secondary")

    return dbc.Card(
        id={"type": "step-card", "index": index},
        className=f"mb-1 step-card{'  border-primary' if selected else ''}",
        style={"cursor": "pointer"},
        children=dbc.CardBody(
            className="p-2 d-flex justify-content-between align-items-center",
            children=[
                html.Div([
                    html.Span(f"{index + 1}. ", className="text-muted small"),
                    html.Span(friendly_id, className="fw-semibold"),
                ]),
                html.Div([
                    dbc.Badge(status, color=color, className="me-1"),
                    dbc.Button(
                        html.I(className="bi bi-trash"),
                        id={"type": "btn-remove-step", "index": index},
                        color="link",
                        size="sm",
                        className="text-danger p-0",
                    ),
                ], className="d-flex align-items-center"),
            ],
        ),
    )
