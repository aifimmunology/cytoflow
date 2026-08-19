"""
cytoflowweb.dash_app.callbacks.workflow
-----------------------------------------

Callbacks that manage the pipeline step list:

- Create a session on first page load
- Render the sidebar step list
- Select a step on card click
- Remove a step
- Toggle the Add-Step modal
"""

from __future__ import annotations

import json
import httpx

import dash
from dash import Input, Output, State, ALL, MATCH, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash import html

from cytoflowweb.dash_app.layout.sidebar import make_step_card
from cytoflowweb import config

API_BASE = config.API_BASE


def _api(method: str, path: str, **kwargs):
    """Thin synchronous wrapper around httpx for server-side API calls."""
    url = f"{API_BASE}{path}"
    resp = getattr(httpx, method)(url, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def register(app: dash.Dash) -> None:

    # ── Create session on first load ──────────────────────────────────────────
    @app.callback(
        Output("store-session-id", "data"),
        Input("store-session-id", "data"),
        prevent_initial_call=False,
    )
    def init_session(existing_id: str | None) -> str:
        if existing_id:
            # Verify it still exists on the server
            try:
                _api("get", f"/sessions/{existing_id}")
                return existing_id
            except Exception:
                pass  # Session expired; create a new one
        data = _api("post", "/sessions")
        return data["session_id"]

    # ── Render the pipeline step list ─────────────────────────────────────────
    @app.callback(
        Output("pipeline-steps", "children"),
        Output("pipeline-empty-msg", "style"),
        Input("store-workflow", "data"),
        Input("store-selected-step", "data"),
    )
    def render_pipeline(workflow: dict | None, selected_index: int):
        if not workflow or not workflow.get("steps"):
            return [], {"display": "block"}

        cards = [
            make_step_card(
                index=s["index"],
                friendly_id=s["friendly_id"],
                status=s["status"],
                selected=(s["index"] == selected_index),
            )
            for s in workflow["steps"]
        ]
        return cards, {"display": "none"}

    # ── Select step on card click ─────────────────────────────────────────────
    @app.callback(
        Output("store-selected-step", "data"),
        Output("store-workflow", "data", allow_duplicate=True),
        Input({"type": "step-card", "index": ALL}, "n_clicks"),
        State("store-session-id", "data"),
        State("store-workflow", "data"),
        prevent_initial_call=True,
    )
    def select_step(n_clicks_list, session_id: str, workflow: dict):
        if not any(n_clicks_list) or not session_id:
            raise PreventUpdate

        triggered = ctx.triggered_id
        if triggered is None:
            raise PreventUpdate

        step_index = triggered["index"]
        try:
            updated = _api("post", f"/sessions/{session_id}/workflow/select",
                           json={"step_index": step_index})
            return step_index, updated
        except Exception:
            raise PreventUpdate

    # ── Remove step ───────────────────────────────────────────────────────────
    @app.callback(
        Output("store-workflow", "data", allow_duplicate=True),
        Output("store-selected-step", "data", allow_duplicate=True),
        Input({"type": "btn-remove-step", "index": ALL}, "n_clicks"),
        State("store-session-id", "data"),
        prevent_initial_call=True,
    )
    def remove_step(n_clicks_list, session_id: str):
        if not any(n_clicks_list) or not session_id:
            raise PreventUpdate

        triggered = ctx.triggered_id
        if triggered is None:
            raise PreventUpdate

        step_index = triggered["index"]
        try:
            updated = _api("delete", f"/sessions/{session_id}/workflow/steps/{step_index}")
            return updated, updated.get("selected_step_index", -1)
        except Exception:
            raise PreventUpdate

    # ── Toggle Add-Step modal ─────────────────────────────────────────────────
    @app.callback(
        Output("modal-add-step", "is_open"),
        Input("btn-add-step", "n_clicks"),
        Input("btn-cancel-add-step", "n_clicks"),
        State("modal-add-step", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_add_modal(open_clicks, cancel_clicks, is_open: bool):
        return not is_open

    # ── Help offcanvas ────────────────────────────────────────────────────────
    @app.callback(
        Output("help-offcanvas", "is_open"),
        Input("btn-help", "n_clicks"),
        State("help-offcanvas", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_help(n, is_open):
        return not is_open
