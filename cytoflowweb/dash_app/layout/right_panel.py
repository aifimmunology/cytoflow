"""
cytoflowweb.dash_app.layout.right_panel
-----------------------------------------

Right panel: FCS upload, experiment browser (channels / conditions), and
operation/view parameter form placeholder.

Fully parameterised forms are implemented per-operation in Phase 3.
"""

import dash_bootstrap_components as dbc
from dash import html, dcc


def make_right_panel() -> html.Div:
    return html.Div(
        id="right-panel",
        className="right-panel d-flex flex-column h-100",
        children=[
            dbc.Tabs(
                id="right-panel-tabs",
                active_tab="tab-import",
                children=[
                    # ── Import tab ────────────────────────────────────────────
                    dbc.Tab(
                        label="Import",
                        tab_id="tab-import",
                        children=_make_import_tab(),
                    ),
                    # ── Operation params tab ──────────────────────────────────
                    dbc.Tab(
                        label="Parameters",
                        tab_id="tab-params",
                        children=_make_params_tab(),
                    ),
                    # ── Experiment info tab ───────────────────────────────────
                    dbc.Tab(
                        label="Experiment",
                        tab_id="tab-experiment",
                        children=_make_experiment_tab(),
                    ),
                ],
            ),
        ],
    )


def _make_import_tab() -> html.Div:
    return html.Div(
        className="p-3",
        children=[
            html.H6("Upload FCS Files", className="mb-2"),
            dcc.Upload(
                id="upload-fcs",
                children=html.Div([
                    html.I(className="bi bi-cloud-upload me-2"),
                    "Drag & drop FCS files here, or ",
                    html.A("click to browse"),
                ]),
                className="upload-dropzone border border-dashed rounded p-4 text-center mb-3",
                multiple=True,
                accept=".fcs",
            ),
            html.Div(id="upload-status", className="small"),
            html.Hr(),
            html.H6("Uploaded Files", className="mb-2"),
            html.Div(id="uploaded-files-list", className="small text-muted"),
            html.Hr(),
            html.H6("Conditions", className="mb-2"),
            html.P(
                "After uploading, define experimental conditions here.",
                className="text-muted small",
                id="conditions-help",
            ),
            html.Div(id="conditions-form"),
            dbc.Button(
                "Run Import",
                id="btn-run-import",
                color="success",
                size="sm",
                className="mt-2 w-100",
                disabled=True,
            ),
        ],
    )


def _make_params_tab() -> html.Div:
    return html.Div(
        className="p-3",
        children=[
            html.H6("Plot Parameters", className="mb-3"),
            dbc.Row(
                className="g-2 mb-2",
                children=[
                    dbc.Col(_labeled_dropdown("View", "dropdown-view-select", clearable=False), width=12),
                ],
            ),
            dbc.Row(
                className="g-2 mb-2",
                children=[
                    dbc.Col(_labeled_number_input("Events Per Sample", "input-events-per-sample", min_value=1, step=1000), width=6),
                    dbc.Col(_labeled_dropdown("Method", "dropdown-sampling-method", clearable=False), width=6),
                ],
            ),
            dbc.Row(
                className="g-2 mb-2",
                children=[
                    dbc.Col(_labeled_dropdown("X Channel", "dropdown-xchannel", clearable=False), width=6),
                    dbc.Col(_labeled_dropdown("Y Channel", "dropdown-ychannel", clearable=False), width=6),
                ],
            ),
            dbc.Row(
                className="g-2 mb-2",
                children=[
                    dbc.Col(_labeled_dropdown("X Scale", "dropdown-xscale", clearable=False), width=6),
                    dbc.Col(_labeled_dropdown("Y Scale", "dropdown-yscale", clearable=False), width=6),
                ],
            ),
            dbc.Row(
                className="g-2 mb-3",
                children=[
                    dbc.Col(_labeled_dropdown("Hue Facet", "dropdown-huefacet", clearable=True), width=12),
                    dbc.Col(_labeled_dropdown("X Facet", "dropdown-xfacet", clearable=True), width=6),
                    dbc.Col(_labeled_dropdown("Y Facet", "dropdown-yfacet", clearable=True), width=6),
                ],
            ),
            html.Hr(),
            html.Div(
                id="op-params-container",
                children=html.P(
                    "Select a pipeline step to see its parameters.",
                    className="text-muted small",
                ),
            ),
        ],
    )


def _labeled_dropdown(label: str, control_id: str, clearable: bool) -> html.Div:
    return html.Div(
        children=[
            html.Label(label, className="small text-muted mb-1 d-block"),
            dcc.Dropdown(
                id=control_id,
                options=[],
                clearable=clearable,
            ),
        ],
    )


def _labeled_number_input(label: str, control_id: str, min_value: int = 1, step: int = 1) -> html.Div:
    return html.Div(
        children=[
            html.Label(label, className="small text-muted mb-1 d-block"),
            dbc.Input(
                id=control_id,
                type="number",
                min=min_value,
                step=step,
                value=500000,
            ),
        ],
    )


def _make_experiment_tab() -> html.Div:
    return html.Div(
        className="p-3",
        children=[
            html.H6("Channels", className="mb-1"),
            html.Div(id="exp-channels", className="small mb-3 text-muted"),
            html.H6("Conditions", className="mb-1"),
            html.Div(id="exp-conditions", className="small mb-3 text-muted"),
            html.H6("Statistics", className="mb-1"),
            html.Div(id="exp-statistics", className="small text-muted"),
        ],
    )
