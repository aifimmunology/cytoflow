"""
cytoflowweb.api.routers.views
------------------------------

Stub for plot-rendering endpoints.

Full implementation is part of Phase 2.  This stub returns a minimal empty
Plotly figure so the Phase 1 Dash shell can wire up callbacks without errors.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cytoflowweb.api.models import session_manager, StepStatus

router = APIRouter(prefix="/sessions/{session_id}/workflow", tags=["views"])


class SetViewRequest(BaseModel):
    view_id: str
    params: dict = {}


@router.post("/steps/{step_index}/view", status_code=200)
def set_view(session_id: str, step_index: int, body: SetViewRequest) -> dict:
    """Set the active view for a step (stub — full rendering in Phase 2)."""
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
def get_plot(session_id: str, step_index: int) -> dict:
    """Return a Plotly figure JSON for the active view of a step.

    Phase 1 stub: returns an empty figure with a placeholder annotation.
    Full Plotly rendering is implemented in Phase 2.
    """
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not (0 <= step_index < len(state.steps)):
        raise HTTPException(status_code=422, detail="step_index out of range")

    step = state.steps[step_index]

    if step.status != StepStatus.VALID:
        return _placeholder_figure(f"Step status: {step.status.value}")

    if step.current_view_id is None:
        return _placeholder_figure("No view selected")

    # Phase 2 will dispatch to the appropriate PlotlyView class here.
    return _placeholder_figure(f"Rendering '{step.current_view_id}' — coming in Phase 2")


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
