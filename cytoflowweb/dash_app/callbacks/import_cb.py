"""
cytoflowweb.dash_app.callbacks.import_cb
------------------------------------------

Callbacks for the FCS file upload and ImportOp configuration.

Flow:
  1. User uploads FCS files  → files saved server-side, metadata returned
  2. UI shows file list + auto-detected channels
  3. User optionally defines conditions per file
  4. "Run Import" pressed  → POST /steps with ImportOp params
  5. Workflow store refreshed → sidebar re-renders
"""

from __future__ import annotations

import base64
import io
import json
from typing import Any

import httpx
import dash
from dash import Input, Output, State, ctx, no_update, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from cytoflowweb import config

API_BASE = config.API_BASE


def _api(method: str, path: str, **kwargs):
    url = f"{API_BASE}{path}"
    resp = getattr(httpx, method)(url, timeout=60, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _api_upload(path: str, filename: str, content_bytes: bytes):
    url = f"{API_BASE}{path}"
    resp = httpx.post(url, files={"file": (filename, content_bytes, "application/octet-stream")}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _format_http_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            payload = exc.response.json()
            detail = payload.get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        return f"{exc.response.status_code}: {detail}"
    return str(exc)


def register(app: dash.Dash) -> None:

    # ── Handle FCS file uploads ───────────────────────────────────────────────
    @app.callback(
        Output("store-uploaded-files", "data"),
        Output("upload-status", "children"),
        Output("uploaded-files-list", "children"),
        Output("btn-run-import", "disabled"),
        Input("upload-fcs", "contents"),
        State("upload-fcs", "filename"),
        State("store-session-id", "data"),
        State("store-uploaded-files", "data"),
        prevent_initial_call=True,
    )
    def handle_upload(
        contents_list: list[str] | None,
        filenames: list[str] | None,
        session_id: str | None,
        existing_files: list[dict],
    ):
        if not contents_list or not session_id:
            raise PreventUpdate

        uploaded = list(existing_files or [])
        errors = []

        for content, filename in zip(contents_list, filenames):
            # Dash uploads are data URIs: "data:<mime>;base64,<data>"
            _, b64 = content.split(",", 1)
            raw = base64.b64decode(b64)
            try:
                meta = _api_upload(f"/sessions/{session_id}/files", filename, raw)
                uploaded.append({
                    "file_id": meta["file_id"],
                    "original_name": meta["original_name"],
                    "server_path": meta["server_path"],
                    "channels": meta["channels"],
                    "event_count": meta["event_count"],
                })
            except Exception as exc:
                errors.append(f"{filename}: {_format_http_error(exc)}")

        status_msg = []
        if errors:
            status_msg = [dbc.Alert(f"Upload errors: {'; '.join(errors)}", color="danger", className="small py-1")]

        file_items = [
            html.Div([
                html.I(className="bi bi-file-earmark me-1"),
                f"{f['original_name']} ",
                html.Span(f"({f['event_count']:,} events)", className="text-muted"),
            ], className="mb-1")
            for f in uploaded
        ]

        return uploaded, status_msg, file_items, (len(uploaded) == 0)

    # ── Run ImportOp ──────────────────────────────────────────────────────────
    @app.callback(
        Output("store-workflow", "data"),
        Output("store-selected-step", "data", allow_duplicate=True),
        Output("interval-status-poll", "disabled"),
        Input("btn-run-import", "n_clicks"),
        State("store-session-id", "data"),
        State("store-uploaded-files", "data"),
        prevent_initial_call=True,
    )
    def run_import(n_clicks: int, session_id: str, uploaded_files: list[dict]):
        if not n_clicks or not session_id or not uploaded_files:
            raise PreventUpdate

        # When multiple files are uploaded without explicit conditions, cytoflow
        # requires each tube to have a distinct condition dict.  Auto-assign a
        # "Tube" condition using the original filename so the import succeeds.
        # Phase 3 will replace this with a proper per-tube condition assignment UI.
        needs_auto_condition = len(uploaded_files) > 1
        tubes = [
            {
                "file": f["server_path"],
                "conditions": {"Tube": f["original_name"]} if needs_auto_condition else {},
            }
            for f in uploaded_files
        ]
        params = {
            "tubes": tubes,
            "conditions": {"Tube": "category"} if needs_auto_condition else {},
        }

        try:
            step_resp = _api("post", f"/sessions/{session_id}/workflow/steps",
                             json={"operation_id": "cytoflow.operations.import_op", "params": params})
            workflow = _api("get", f"/sessions/{session_id}/workflow")
            selected = workflow.get("selected_step_index", 0)
            return workflow, selected, False  # enable status polling
        except Exception as exc:
            raise PreventUpdate
