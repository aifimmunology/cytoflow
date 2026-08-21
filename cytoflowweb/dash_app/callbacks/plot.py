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

SCALE_OPTIONS = [
    {"label": "Linear", "value": "linear"},
    {"label": "Log", "value": "log"},
    {"label": "Logicle", "value": "logicle"},
    {"label": "Hyperlog", "value": "hlog"},
]

SAMPLING_METHOD_OPTIONS = [
    {"label": "First N", "value": "first_n"},
    {"label": "Random", "value": "random"},
]

SINGLE_CHANNEL_VIEWS = {
    "cytoflow.view.histogram",
    "cytoflow.view.kde1d",
    "cytoflow.view.violin",
}

HUE_CAPABLE_VIEWS = {
    "cytoflow.view.histogram",
    "cytoflow.view.scatterplot",
    "cytoflow.view.kde1d",
    "cytoflow.view.parallel_coords",
    "cytoflow.view.radviz",
    "cytoflow.view.violin",
}


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

    # ── Populate plot parameter controls from selected step metadata ───────────
    @app.callback(
        Output("dropdown-xchannel", "options"),
        Output("dropdown-xchannel", "value"),
        Output("dropdown-ychannel", "options"),
        Output("dropdown-ychannel", "value"),
        Output("dropdown-ychannel", "disabled"),
        Output("input-events-per-sample", "value"),
        Output("dropdown-sampling-method", "options"),
        Output("dropdown-sampling-method", "value"),
        Output("dropdown-xscale", "options"),
        Output("dropdown-xscale", "value"),
        Output("dropdown-yscale", "options"),
        Output("dropdown-yscale", "value"),
        Output("dropdown-yscale", "disabled"),
        Output("dropdown-huefacet", "options"),
        Output("dropdown-huefacet", "value"),
        Output("dropdown-huefacet", "disabled"),
        Output("dropdown-xfacet", "options"),
        Output("dropdown-xfacet", "value"),
        Output("dropdown-yfacet", "options"),
        Output("dropdown-yfacet", "value"),
        Input("dropdown-view-select", "value"),
        Input("store-selected-step", "data"),
        Input("store-workflow", "data"),
        prevent_initial_call=True,
    )
    def populate_plot_controls(view_id: str | None, selected_index: int, workflow: dict | None):
        if selected_index < 0 or not workflow:
            return [], None, [], None, False, 20000, SAMPLING_METHOD_OPTIONS, "random", SCALE_OPTIONS, "linear", SCALE_OPTIONS, "linear", False, [], None, False, [], None, [], None

        steps = workflow.get("steps", [])
        if not steps or selected_index >= len(steps):
            return [], None, [], None, False, 20000, SAMPLING_METHOD_OPTIONS, "random", SCALE_OPTIONS, "linear", SCALE_OPTIONS, "linear", False, [], None, False, [], None, [], None

        step = steps[selected_index]
        channels = step.get("channels", [])
        conditions = step.get("conditions", [])
        view_params = step.get("view_params", {}) or {}

        ch_opts = [{"label": c, "value": c} for c in channels]
        cond_opts = [{"label": c, "value": c} for c in conditions]

        default_x = channels[0] if channels else None
        default_y = channels[1] if len(channels) > 1 else (channels[0] if channels else None)
        xchannel = view_params.get("xchannel") or view_params.get("channel") or default_x
        ychannel = view_params.get("ychannel") or default_y
        y_disabled = view_id in SINGLE_CHANNEL_VIEWS
        yscale_disabled = view_id in SINGLE_CHANNEL_VIEWS
        hue_disabled = view_id not in HUE_CAPABLE_VIEWS
        events_per_sample = int(view_params.get("events_per_sample", 20000))
        sampling_method = view_params.get("sampling_method", "random")
        xscale = view_params.get("xscale") or view_params.get("scale") or "linear"
        yscale = view_params.get("yscale", "linear")
        huefacet = view_params.get("huefacet")
        if view_id == "cytoflow.view.violin":
            huefacet = view_params.get("groupby", huefacet)
        xfacet = view_params.get("xfacet")
        yfacet = view_params.get("yfacet")

        return (
            ch_opts, xchannel,
            ch_opts, ychannel,
            y_disabled,
            events_per_sample,
            SAMPLING_METHOD_OPTIONS, sampling_method,
            SCALE_OPTIONS, xscale,
            SCALE_OPTIONS, yscale,
            yscale_disabled,
            cond_opts, huefacet,
            hue_disabled,
            cond_opts, xfacet,
            cond_opts, yfacet,
        )

    # ── Set active view when dropdown changes ─────────────────────────────────
    @app.callback(
        Output("store-workflow", "data", allow_duplicate=True),
        Input("dropdown-view-select", "value"),
        Input("dropdown-xchannel", "value"),
        Input("dropdown-ychannel", "value"),
        Input("input-events-per-sample", "value"),
        Input("dropdown-sampling-method", "value"),
        Input("dropdown-xscale", "value"),
        Input("dropdown-yscale", "value"),
        Input("dropdown-huefacet", "value"),
        Input("dropdown-xfacet", "value"),
        Input("dropdown-yfacet", "value"),
        State("store-session-id", "data"),
        State("store-selected-step", "data"),
        prevent_initial_call=True,
    )
    def set_active_view(
        view_id: str | None,
        xchannel: str | None,
        ychannel: str | None,
        events_per_sample: int | None,
        sampling_method: str | None,
        xscale: str | None,
        yscale: str | None,
        huefacet: str | None,
        xfacet: str | None,
        yfacet: str | None,
        session_id: str,
        selected_index: int,
    ):
        if view_id is None or not session_id or selected_index < 0:
            raise PreventUpdate
        params = {
            "xchannel": xchannel,
            "ychannel": ychannel,
            "events_per_sample": events_per_sample,
            "sampling_method": sampling_method,
            "xscale": xscale,
            "yscale": yscale,
            "huefacet": huefacet,
            "xfacet": xfacet,
            "yfacet": yfacet,
        }
        params = {k: v for k, v in params.items() if v not in (None, "")}
        if view_id in SINGLE_CHANNEL_VIEWS and xchannel:
            params["channel"] = xchannel
            if xscale:
                params["scale"] = xscale
            params.pop("ychannel", None)
            params.pop("yscale", None)
        if view_id == "cytoflow.view.violin" and huefacet:
            params["groupby"] = huefacet
            params.pop("huefacet", None)
        if view_id not in HUE_CAPABLE_VIEWS:
            params.pop("huefacet", None)
        try:
            _api("post", f"/sessions/{session_id}/workflow/steps/{selected_index}/view",
                 json={"view_id": view_id, "params": params})
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
        Input("dropdown-view-select", "value"),
        Input("dropdown-xchannel", "value"),
        Input("dropdown-ychannel", "value"),
        Input("input-events-per-sample", "value"),
        Input("dropdown-sampling-method", "value"),
        Input("dropdown-xscale", "value"),
        Input("dropdown-yscale", "value"),
        Input("dropdown-huefacet", "value"),
        Input("dropdown-xfacet", "value"),
        Input("dropdown-yfacet", "value"),
        State("store-session-id", "data"),
        prevent_initial_call=True,
    )
    def refresh_plot(
        selected_index: int,
        workflow: dict | None,
        _refresh_clicks,
        view_id: str | None,
        xchannel: str | None,
        ychannel: str | None,
        events_per_sample: int | None,
        sampling_method: str | None,
        xscale: str | None,
        yscale: str | None,
        huefacet: str | None,
        xfacet: str | None,
        yfacet: str | None,
        session_id: str,
    ):
        if selected_index < 0 or not session_id:
            raise PreventUpdate

        try:
            params = {
                "view_id": view_id,
                "xchannel": xchannel,
                "ychannel": ychannel,
                "events_per_sample": events_per_sample,
                "sampling_method": sampling_method,
                "xscale": xscale,
                "yscale": yscale,
                "huefacet": huefacet,
                "xfacet": xfacet,
                "yfacet": yfacet,
            }
            params = {k: v for k, v in params.items() if v not in (None, "")}
            if view_id in SINGLE_CHANNEL_VIEWS and xchannel:
                params["channel"] = xchannel
                if xscale:
                    params["scale"] = xscale
                params.pop("ychannel", None)
                params.pop("yscale", None)
            if view_id == "cytoflow.view.violin" and huefacet:
                params["groupby"] = huefacet
                params.pop("huefacet", None)
            if view_id not in HUE_CAPABLE_VIEWS:
                params.pop("huefacet", None)
            figure = _api("get", f"/sessions/{session_id}/workflow/steps/{selected_index}/plot", params=params)
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
        conditions = ", ".join(step.get("conditions", [])) or "—"
        statistics = ", ".join(step.get("statistics", [])) or "—"
        return channels, conditions, statistics
