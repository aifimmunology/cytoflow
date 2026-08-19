"""
cytoflowweb.api.routers.sessions
---------------------------------

Endpoints for creating and deleting analysis sessions.

A session is the server-side container for one user's workflow state.
The session ID is a UUID that the browser stores in a ``dcc.Store`` and
includes in every subsequent request.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cytoflowweb.api.models import session_manager, WorkflowState

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    session_id: str
    step_count: int


@router.post("", response_model=SessionResponse, status_code=201)
def create_session() -> SessionResponse:
    """Create a new empty session and return its ID."""
    state: WorkflowState = session_manager.create()
    return SessionResponse(session_id=state.session_id, step_count=0)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    """Return basic info about an existing session."""
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(session_id=state.session_id, step_count=len(state.steps))


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    """Delete a session and free its resources."""
    if not session_manager.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
