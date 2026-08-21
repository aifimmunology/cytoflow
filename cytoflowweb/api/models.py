"""
cytoflowweb.api.models
----------------------

Server-side data models for a workflow session.

Each browser session owns one :class:`WorkflowState` that holds the analysis
pipeline and all computed :class:`~cytoflow.Experiment` results.
:class:`SessionManager` keeps an LRU cache of live sessions.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

from cytoflow import Experiment
from cytoflow.operations.i_operation import IOperation


# ── Step status ───────────────────────────────────────────────────────────────

class StepStatus(str, Enum):
    INVALID    = "invalid"
    WAITING    = "waiting"
    APPLYING   = "applying"
    ESTIMATING = "estimating"
    VALID      = "valid"
    ERROR      = "error"


# ── Pipeline step ─────────────────────────────────────────────────────────────

@dataclass
class WorkflowStep:
    """One step in the analysis pipeline.

    Holds the operation, its computed result, and any error/warning text.
    The ``result`` is populated by the worker after a successful ``apply()``.
    """

    operation: IOperation
    """The cytoflow operation for this step."""

    result: Experiment | None = field(default=None, repr=False)
    """The :class:`~cytoflow.Experiment` produced by ``operation.apply()``."""

    status: StepStatus = StepStatus.INVALID

    # Human-readable error/warning text from the last apply/estimate call
    op_error: str = ""
    op_warning: str = ""
    estimate_error: str = ""
    estimate_warning: str = ""
    view_error: str = ""
    view_warning: str = ""

    # Metadata derived from result (populated after apply)
    channels: list[str] = field(default_factory=list)
    conditions: dict[str, pd.Series] = field(default_factory=dict)
    statistics: dict[str, pd.DataFrame] = field(default_factory=dict)

    # Currently selected view id (string) and its parameters
    current_view_id: str | None = None
    view_params: dict[str, Any] = field(default_factory=dict)

    def update_from_result(self, experiment: Experiment) -> None:
        """Populate metadata fields from a freshly computed experiment."""
        self.result = experiment
        self.channels = list(experiment.channels)
        self.conditions = {
            name: experiment.data[name]
            for name in experiment.conditions
        }
        self.statistics = dict(experiment.statistics)
        self.status = StepStatus.VALID
        self.op_error = ""
        self.op_warning = ""


# ── Workflow state ────────────────────────────────────────────────────────────

@dataclass
class WorkflowState:
    """All mutable state owned by one browser session.

    Thread-safety: all mutations should be made while holding ``lock``.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: list[WorkflowStep] = field(default_factory=list)
    selected_step_index: int = -1

    # Tracks which step indices currently have a running background task so
    # the API can return a 409 instead of submitting a duplicate job.
    running_tasks: set[int] = field(default_factory=set)

    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ── Convenience helpers ───────────────────────────────────────────────────

    @property
    def selected_step(self) -> WorkflowStep | None:
        if 0 <= self.selected_step_index < len(self.steps):
            return self.steps[self.selected_step_index]
        return None

    def input_experiment(self, step_index: int) -> Experiment | None:
        """Return the experiment that feeds into ``steps[step_index]``."""
        if step_index == 0:
            return None
        prev = self.steps[step_index - 1]
        return prev.result

    def invalidate_from(self, step_index: int) -> None:
        """Mark all steps at or after ``step_index`` as invalid."""
        for step in self.steps[step_index:]:
            step.status = StepStatus.INVALID
            step.result = None

    def to_summary(self) -> list[dict]:
        """Return a JSON-serialisable summary of all steps (no DataFrames)."""
        return [
            {
                "index": i,
                "operation_id": step.operation.id,
                "friendly_id": step.operation.friendly_id,
                "status": step.status.value,
                "op_error": step.op_error,
                "op_warning": step.op_warning,
                "estimate_error": step.estimate_error,
                "channels": step.channels,
                "conditions": list(step.conditions.keys()),
                "statistics": list(step.statistics.keys()),
                "current_view_id": step.current_view_id,
                "view_params": dict(step.view_params),
            }
            for i, step in enumerate(self.steps)
        ]


# ── Session manager ───────────────────────────────────────────────────────────

class SessionManager:
    """In-memory LRU cache of active :class:`WorkflowState` objects.

    Parameters
    ----------
    max_sessions:
        Maximum number of sessions to keep alive simultaneously.  When the
        limit is reached the least-recently-used session is evicted.

    Notes
    -----
    All public methods are thread-safe.
    """

    def __init__(self, max_sessions: int = 50) -> None:
        self._max = max_sessions
        self._sessions: OrderedDict[str, WorkflowState] = OrderedDict()
        self._lock = threading.Lock()

    def create(self) -> WorkflowState:
        """Create a new session and return it."""
        state = WorkflowState()
        with self._lock:
            self._evict_if_needed()
            self._sessions[state.session_id] = state
        return state

    def get(self, session_id: str) -> WorkflowState | None:
        """Return the session or *None* if it does not exist."""
        with self._lock:
            if session_id not in self._sessions:
                return None
            # Move to end (most-recently-used)
            self._sessions.move_to_end(session_id)
            return self._sessions[session_id]

    def delete(self, session_id: str) -> bool:
        """Remove a session.  Returns *True* if it existed."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def _evict_if_needed(self) -> None:
        """Evict the LRU session if at capacity.  Must hold ``_lock``."""
        while len(self._sessions) >= self._max:
            self._sessions.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)


from cytoflowweb import config

# ── Module-level singleton used by FastAPI dependency injection ───────────────
session_manager = SessionManager(max_sessions=config.MAX_SESSIONS)
