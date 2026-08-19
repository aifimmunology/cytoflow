"""
cytoflowweb.api.routers.views
------------------------------

Plot-rendering endpoints.

Phase 1: minimal histogram renderer (pre-binned ``go.Bar``) used to satisfy
the "display a histogram" milestone.  Phase 2 will replace this with the full
``cytoflowweb/views/plotly/`` layer covering all 15 view types, custom scales,
and faceting.
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


# ── Request / response models ─────────────────────────────────────────────────

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
def get_plot(session_id: str, step_index: int, channel: str | None = None) -> dict:
    """Return a Plotly figure JSON for the active view of a step.

    Phase 1: renders a histogram of ``channel`` (defaults to the first
    non-Time channel) from the step's result Experiment.
    """
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not (0 <= step_index < len(state.steps)):
        raise HTTPException(status_code=422, detail="step_index out of range")

    step = state.steps[step_index]

    if step.status == StepStatus.APPLYING or step.status == StepStatus.ESTIMATING:
        return _placeholder_figure("Computing…")

    if step.status == StepStatus.ERROR:
        msg = step.op_error or step.estimate_error or "Unknown error"
        return _placeholder_figure(f"Error: {msg}")

    if step.status != StepStatus.VALID or step.result is None:
        return _placeholder_figure("No result yet — run the pipeline first")

    experiment = step.result

    try:
        return _render_histogram(experiment, channel)
    except Exception as exc:
        logger.exception("histogram render failed for step %d", step_index)
        return _placeholder_figure(f"Render error: {exc}")


# ── Renderers ─────────────────────────────────────────────────────────────────

def _render_histogram(experiment, channel: str | None) -> dict:
    """Build a pre-binned histogram Plotly figure from an Experiment.

    Histograms are computed from the **full** dataset (no sampling) so that
    bin counts are accurate; only scatter / raw-event plots apply the 500k cap.
    """
    channels = experiment.channels
    if not channels:
        return _placeholder_figure("No channels in experiment")

    # Pick the requested channel or default to the first non-Time channel
    if channel is None:
        channel = next((c for c in channels if c.lower() != "time"), channels[0])
    elif channel not in channels:
        return _placeholder_figure(f"Channel '{channel}' not in experiment")

    data = experiment.data[channel].dropna()
    if data.empty:
        return _placeholder_figure(f"No data for channel '{channel}'")

    counts, bin_edges = np.histogram(data, bins=256)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_width = bin_edges[1] - bin_edges[0]

    fig = go.Figure(
        data=[
            go.Bar(
                x=bin_centers.tolist(),
                y=counts.tolist(),
                width=float(bin_width),
                marker_color="#1f77b4",
                name=channel,
            )
        ],
        layout=go.Layout(
            xaxis_title=channel,
            yaxis_title="Count",
            bargap=0,
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
            margin={"l": 60, "r": 20, "t": 40, "b": 60},
            title={
                "text": f"{channel} — {len(experiment.data):,} events",
                "font": {"size": 14},
            },
        ),
    )
    return fig.to_dict()


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

