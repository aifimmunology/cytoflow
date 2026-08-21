"""
cytoflowweb.api.routers.views
------------------------------

Plot-rendering endpoints.

``GET /sessions/{id}/workflow/steps/{n}/plot`` dispatches to the appropriate
renderer in ``cytoflowweb.views.plotly.VIEW_REGISTRY`` based on the step's
``current_view_id``.  When no view is selected it defaults to the histogram
of the first non-Time channel.

Renderers return either:
  - A Plotly figure dict  → passed directly to ``dcc.Graph``
  - A table dict          → ``{"type": "table", "columns": [...], "data": [...]}``
"""

from __future__ import annotations

import logging

import numpy as np
import plotly.graph_objects as go
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cytoflowweb.api.models import session_manager, StepStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions/{session_id}/workflow", tags=["views"])

_MAX_PLOT_EVENTS = 500_000

# Import all view renderers (populates VIEW_REGISTRY)
try:
    import cytoflowweb.views.plotly as _plotly_views
    _VIEW_REGISTRY = _plotly_views.VIEW_REGISTRY
except Exception as _err:  # pragma: no cover
    logger.warning("Could not load plotly view renderers: %s", _err)
    _VIEW_REGISTRY = {}


# ── Request model ─────────────────────────────────────────────────────────────

class SetViewRequest(BaseModel):
    view_id: str
    params: dict = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/steps/{step_index}/view", status_code=200)
def set_view(session_id: str, step_index: int, body: SetViewRequest) -> dict:
    """Set the active view for a step."""
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not (0 <= step_index < len(state.steps)):
        raise HTTPException(status_code=422, detail="step_index out of range")
    step = state.steps[step_index]
    step.current_view_id = body.view_id
    step.view_params = body.params
    return {"step_index": step_index, "view_id": body.view_id}


@router.get("/steps/{step_index}/plot")
def get_plot(
    session_id: str,
    step_index: int,
    view_id: str | None = None,
    channel: str | None = None,
    xchannel: str | None = None,
    ychannel: str | None = None,
    scale: str | None = None,
    xscale: str | None = None,
    yscale: str | None = None,
    events_per_sample: int | None = None,
    sampling_method: str | None = None,
    huefacet: str | None = None,
    xfacet: str | None = None,
    yfacet: str | None = None,
) -> dict:
    """Return a Plotly figure JSON (or table dict) for the active view of a step.

    Query parameters supplement / override any params stored on the step via
    POST /view.  ``view_id`` defaults to ``cytoflow.view.histogram``.
    """
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not (0 <= step_index < len(state.steps)):
        raise HTTPException(status_code=422, detail="step_index out of range")

    step = state.steps[step_index]

    if step.status in (StepStatus.APPLYING, StepStatus.ESTIMATING):
        return _placeholder_figure("Computing…")
    if step.status == StepStatus.ERROR:
        msg = step.op_error or step.estimate_error or "Unknown error"
        return _placeholder_figure(f"Error: {msg}")
    if step.status != StepStatus.VALID or step.result is None:
        return _placeholder_figure("No result yet — run the pipeline first")

    experiment = step.result

    # Merge: stored params → override with URL query params
    params = dict(step.view_params or {})
    active_view_id = view_id or step.current_view_id or "cytoflow.view.histogram"

    # URL query param overrides
    if channel:    params["channel"]  = channel
    if xchannel:   params["xchannel"] = xchannel
    if ychannel:   params["ychannel"] = ychannel
    if scale:      params["scale"]    = scale
    if xscale:     params["xscale"]   = xscale
    if yscale:     params["yscale"]   = yscale
    if events_per_sample is not None: params["events_per_sample"] = events_per_sample
    if sampling_method: params["sampling_method"] = sampling_method
    if huefacet:   params["huefacet"] = huefacet
    if xfacet:     params["xfacet"]   = xfacet
    if yfacet:     params["yfacet"]   = yfacet

    renderer = _VIEW_REGISTRY.get(active_view_id)
    if renderer is None:
        return _placeholder_figure(
            f"No renderer for view '{active_view_id}'. "
            f"Available: {sorted(_VIEW_REGISTRY.keys())}"
        )

    try:
        return renderer(experiment, params)
    except Exception as exc:
        logger.exception("render failed: view=%s step=%d", active_view_id, step_index)
        return _placeholder_figure(f"Render error: {exc}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _placeholder_figure(message: str) -> dict:
    return {
        "data": [],
        "layout": {
            "annotations": [{
                "text": message,
                "xref": "paper", "yref": "paper",
                "x": 0.5, "y": 0.5,
                "showarrow": False,
                "font": {"size": 16, "color": "#888"},
            }],
            "xaxis": {"visible": False},
            "yaxis": {"visible": False},
            "plot_bgcolor": "#fafafa",
            "paper_bgcolor": "#fafafa",
        },
    }

