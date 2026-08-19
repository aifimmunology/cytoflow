"""
cytoflowweb.dash_app.layout.canvas
------------------------------------

Central plot canvas: the ``dcc.Graph`` component that displays the active view.
"""

import dash_bootstrap_components as dbc
from dash import html, dcc


def make_canvas() -> html.Div:
    return html.Div(
        id="canvas",
        className="canvas d-flex flex-column h-100",
        children=[
            # ── Plot toolbar ──────────────────────────────────────────────────
            html.Div(
                className="canvas-toolbar d-flex align-items-center p-2 border-bottom gap-2",
                children=[
                    html.Span("View:", className="text-muted small"),
                    dcc.Dropdown(
                        id="dropdown-view-select",
                        placeholder="Select a view…",
                        options=[],
                        style={"minWidth": "200px"},
                        clearable=False,
                    ),
                    dbc.Button(
                        html.I(className="bi bi-arrow-clockwise"),
                        id="btn-refresh-plot",
                        color="outline-secondary",
                        size="sm",
                        title="Refresh plot",
                    ),
                    html.Div(id="plot-sample-annotation", className="ms-auto small text-muted"),
                ],
            ),

            # ── Main graph ────────────────────────────────────────────────────
            dcc.Graph(
                id="main-plot",
                figure={
                    "data": [],
                    "layout": {
                        "annotations": [{
                            "text": "Upload FCS files and add a pipeline step to begin.",
                            "xref": "paper", "yref": "paper",
                            "x": 0.5, "y": 0.5,
                            "showarrow": False,
                            "font": {"size": 15, "color": "#aaa"},
                        }],
                        "xaxis": {"visible": False},
                        "yaxis": {"visible": False},
                        "plot_bgcolor": "#fafafa",
                        "paper_bgcolor": "#fafafa",
                        "margin": {"t": 20, "b": 20, "l": 20, "r": 20},
                    },
                },
                style={"flex": "1 1 auto", "minHeight": 0},
                config={
                    "displaylogo": False,
                    "modeBarButtonsToAdd": ["lasso2d", "select2d"],
                    "toImageButtonOptions": {"format": "png", "scale": 2},
                },
            ),

            # Loading overlay while a plot is being rendered
            dcc.Loading(
                id="plot-loading",
                type="circle",
                color="#0d6efd",
                children=html.Div(id="plot-loading-trigger"),
            ),
        ],
    )
