"""
cytoflowweb.dash_app.callbacks.plot
-------------------------------------

Callbacks that fetch and display plots:

- On step selection change: fetch plot JSON from the API and update dcc.Graph
- On view dropdown change: set the active view, then refresh the plot
- On status poll: refresh the plot when the selected step becomes valid
- On refresh button: force re-fetch
"""

from __future__ import annotations

import httpx
import dash
from dash import Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from cytoflowweb import config

API_BASE = config.API_BASE

# View IDs must match the backend registry keys in
# cytoflowweb.views.plotly.* @register("...").
PLOT_VIEW_OPTIONS = [
    {"label": "Histogram", "value": "cytoflow.view.histogram"},
    {"label": "Scatterplot", "value": "cytoflow.view.scatterplot"},
    {"label": "2D Histogram", "value": "cytoflow.view.histogram2d"},
    {"label": "1D KDE", "value": "cytoflow.view.kde1d"},
    {"label": "2D KDE", "value": "cytoflow.view.kde2d"},
    {"label": "Density", "value": "cytoflow.view.density"},
    {"label": "Violin", "value": "cytoflow.view.violin"},
    {"label": "Bar Chart", "value": "cytoflow.view.barchart"},
    {"label": "Stats 1D", "value": "cytoflow.view.stats1d"},
    {"label": "Stats 2D", "value": "cytoflow.view.stats2d"},
    {"label": "Parallel Coordinates", "value": "cytoflow.view.parallel_coords"},
    {"label": "Radviz", "value": "cytoflow.view.radviz"},
    {"label": "Matrix", "value": "cytoflow.view.matrix"},
    {"label": "MST", "value": "cytoflow.view.mst"},
]


def _api(method: str, path: str, **kwargs):
    url = f"{API_BASE}{path}"
    resp = getattr(httpx, method)(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def register(app: dash.Dash) -> None:

    # ── Populate view dropdown when a step is selected ────────────────────────
    @app.callback(
        Output("dropdown-view-select", "options"),
        Output("dropdown-view-select", "value"),
        Input("store-selected-step", "data"),
        State("store-workflow", "data"),
        prevent_initial_call=True,
    )
    def update_view_options(selected_index: int, workflow: dict | None):
        if selected_index < 0 or not workflow:
            return [], None

        steps = workflow.get("steps", [])
        if not steps or selected_index >= len(steps):
            return [], None

        step = steps[selected_index]
        current_view_id = step.get("current_view_id")

        options = PLOT_VIEW_OPTIONS
        option_values = {opt["value"] for opt in options}
        value = current_view_id if current_view_id in option_values else (options[0]["value"] if options else None)
        return options, value

    # ── Set active view when dropdown changes ─────────────────────────────────
    @app.callback(
        Output("store-workflow", "data", allow_duplicate=True),
        Input("dropdown-view-select", "value"),
        State("store-session-id", "data"),
        State("store-selected-step", "data"),
        prevent_initial_call=True,
    )
    def set_active_view(view_id: str | None, session_id: str, selected_index: int):
        if view_id is None or not session_id or selected_index < 0:
            raise PreventUpdate
        try:
            _api("post", f"/sessions/{session_id}/workflow/steps/{selected_index}/view",
                 json={"view_id": view_id, "params": {}})
            return _api("get", f"/sessions/{session_id}/workflow")
        except Exception:
            raise PreventUpdate

    # ── Fetch and display the plot ─────────────────────────────────────────────
    @app.callback(
        Output("main-plot", "figure"),
        Output("plot-loading-trigger", "children"),
        Input("store-selected-step", "data"),
        Input("store-workflow", "data"),
        Input("btn-refresh-plot", "n_clicks"),
        State("store-session-id", "data"),
        prevent_initial_call=True,
    )
    def refresh_plot(selected_index: int, workflow: dict | None,
                     _refresh_clicks, session_id: str):
        if selected_index < 0 or not session_id:
            raise PreventUpdate

        try:
            figure = _api("get", f"/sessions/{session_id}/workflow/steps/{selected_index}/plot")
            return figure, None
        except Exception:
            raise PreventUpdate

    # ── Status polling: re-fetch plot when selected step becomes valid ─────────
    @app.callback(
        Output("store-workflow", "data", allow_duplicate=True),
        Output("interval-status-poll", "disabled", allow_duplicate=True),
        Input("interval-status-poll", "n_intervals"),
        State("store-session-id", "data"),
        State("store-selected-step", "data"),
        prevent_initial_call=True,
    )
    def poll_status(n_intervals: int, session_id: str, selected_index: int):
        if not session_id:
            raise PreventUpdate
        try:
            workflow = _api("get", f"/sessions/{session_id}/workflow")
            steps = workflow.get("steps", [])
            # Stop polling if all steps are in a terminal state
            running = any(s["status"] in ("applying", "estimating") for s in steps)
            return workflow, not running
        except Exception:
            raise PreventUpdate

    # ── Update experiment browser panel ───────────────────────────────────────
    @app.callback(
        Output("exp-channels", "children"),
        Output("exp-conditions", "children"),
        Output("exp-statistics", "children"),
        Input("store-workflow", "data"),
        Input("store-selected-step", "data"),
    )
    def update_experiment_panel(workflow: dict | None, selected_index: int):
        if not workflow or selected_index < 0:
            return "—", "—", "—"

        steps = workflow.get("steps", [])
        if not steps or selected_index >= len(steps):
            return "—", "—", "—"

        step = steps[selected_index]
        channels = ", ".join(step.get("channels", [])) or "—"
        return channels, "—", "—"
