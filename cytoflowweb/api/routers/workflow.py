"""
cytoflowweb.api.routers.workflow
---------------------------------

Endpoints for reading and managing the step list within a session.

These endpoints operate on the *structure* of the pipeline (which steps exist,
their order, and their current status).  Modifying operation parameters is
handled by the ``/operations`` router; triggering computation is implicit —
adding or updating a step schedules ``apply()`` automatically.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cytoflowweb.api.models import session_manager, StepStatus

router = APIRouter(prefix="/sessions/{session_id}/workflow", tags=["workflow"])


# ── Response models ───────────────────────────────────────────────────────────

class StepSummary(BaseModel):
    index: int
    operation_id: str
    friendly_id: str
    status: str
    op_error: str
    op_warning: str
    estimate_error: str
    channels: list[str]
    current_view_id: str | None


class WorkflowSummary(BaseModel):
    session_id: str
    selected_step_index: int
    steps: list[StepSummary]


class SelectStepRequest(BaseModel):
    step_index: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_state(session_id: str):
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=WorkflowSummary)
def get_workflow(session_id: str) -> WorkflowSummary:
    """Return the full step list and current selection for this session."""
    state = _get_state(session_id)
    with state.lock:
        return WorkflowSummary(
            session_id=state.session_id,
            selected_step_index=state.selected_step_index,
            steps=[StepSummary(**s) for s in state.to_summary()],
        )


@router.post("/select", status_code=200)
def select_step(session_id: str, body: SelectStepRequest) -> WorkflowSummary:
    """Set the currently-selected step (controls which plot is displayed)."""
    state = _get_state(session_id)
    with state.lock:
        if not (-1 <= body.step_index < len(state.steps)):
            raise HTTPException(status_code=422, detail="step_index out of range")
        state.selected_step_index = body.step_index
        return WorkflowSummary(
            session_id=state.session_id,
            selected_step_index=state.selected_step_index,
            steps=[StepSummary(**s) for s in state.to_summary()],
        )


@router.delete("/steps/{step_index}", status_code=200)
def remove_step(session_id: str, step_index: int) -> WorkflowSummary:
    """Remove a step from the pipeline and invalidate all downstream steps."""
    state = _get_state(session_id)
    with state.lock:
        if not (0 <= step_index < len(state.steps)):
            raise HTTPException(status_code=422, detail="step_index out of range")
        state.steps.pop(step_index)
        state.invalidate_from(step_index)
        # Clamp selection
        if state.selected_step_index >= len(state.steps):
            state.selected_step_index = len(state.steps) - 1
        return WorkflowSummary(
            session_id=state.session_id,
            selected_step_index=state.selected_step_index,
            steps=[StepSummary(**s) for s in state.to_summary()],
        )
