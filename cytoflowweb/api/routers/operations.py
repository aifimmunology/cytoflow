"""
cytoflowweb.api.routers.operations
------------------------------------

Endpoints for adding operations to a pipeline and triggering computation.

POST   /sessions/{id}/workflow/steps          — add a new step (by op id)
PUT    /sessions/{id}/workflow/steps/{n}      — update op parameters
POST   /sessions/{id}/workflow/steps/{n}/apply    — (re-)apply the step
POST   /sessions/{id}/workflow/steps/{n}/estimate — run estimate()
"""

from __future__ import annotations

import importlib
import inspect
import logging
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from traits.api import HasTraits, TraitError

from cytoflowweb.api.models import session_manager, WorkflowStep, StepStatus
from cytoflowweb.api.workers.tasks import apply_step_async, estimate_step_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions/{session_id}/workflow", tags=["operations"])

# ── Operation registry ────────────────────────────────────────────────────────
# Maps operation_id strings to their IOperation classes.
# Populated lazily on first use.
_OP_REGISTRY: dict[str, type] = {}

def _get_op_class(operation_id: str):
    if operation_id not in _OP_REGISTRY:
        # operation_id is e.g. "cytoflow.operations.threshold"
        # The class name is the last segment in CamelCase
        module_path, _, class_hint = operation_id.rpartition(".")
        try:
            mod = importlib.import_module(module_path)
        except ModuleNotFoundError:
            raise HTTPException(status_code=422, detail=f"Unknown operation module: {module_path}")
        # Try standard naming conventions
        for candidate in [
            class_hint.replace("_", " ").title().replace(" ", "") + "Op",
            class_hint.replace("_", " ").title().replace(" ", ""),
        ]:
            cls = getattr(mod, candidate, None)
            if cls is not None:
                _OP_REGISTRY[operation_id] = cls
                return cls
        raise HTTPException(status_code=422, detail=f"Cannot find class for operation_id '{operation_id}'")
    return _OP_REGISTRY[operation_id]


# ── Request / response models ─────────────────────────────────────────────────

class AddStepRequest(BaseModel):
    operation_id: str
    params: dict[str, Any] = {}


class UpdateParamsRequest(BaseModel):
    params: dict[str, Any]


class StepStatusResponse(BaseModel):
    index: int
    status: str
    op_error: str
    op_warning: str
    estimate_error: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_session(session_id: str):
    state = session_manager.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


def _require_step(state, step_index: int):
    if not (0 <= step_index < len(state.steps)):
        raise HTTPException(status_code=422, detail="step_index out of range")
    return state.steps[step_index]


def _coerce_value(operation, key: str, value: Any) -> Any:
    """Coerce a list of plain dicts to the appropriate List(HasTraits) type.

    Traits raises a descriptive ``TraitError`` when you try to assign a dict
    where a HasTraits subclass instance is expected.  We parse the error to
    discover the expected class name, resolve it in the operation's module, and
    reconstruct each item.  This makes the JSON API transparent for simple
    nested objects like ``ImportOp.tubes``.
    """
    if not isinstance(value, list) or not value or not all(isinstance(v, dict) for v in value):
        return value

    # Probe with a single-item list to get the traits error message
    try:
        setattr(operation, key, [value[0]])
        # Setting a dict succeeded — traits accepted it, return as-is
        setattr(operation, key, [])  # reset to avoid side-effects
        return value
    except TraitError as te:
        # e.g. "… must be a Tube or None, but a value of {…} <class 'dict'> was specified."
        m = re.search(r"must be a (\w+)(?: or \w+)?", str(te))
        if not m:
            raise  # re-raise; setattr in _apply_params will surface it

        class_name = m.group(1)
        mod = inspect.getmodule(type(operation))
        klass = getattr(mod, class_name, None)
        if klass is None or not (isinstance(klass, type) and issubclass(klass, HasTraits)):
            raise  # can't coerce; let the caller raise a meaningful error

        return [klass(**d) if isinstance(d, dict) else d for d in value]


def _apply_params(operation, params: dict[str, Any]) -> None:
    """Set operation traits from a plain dict, ignoring unknown keys."""
    for key, value in params.items():
        if hasattr(operation, key):
            value = _coerce_value(operation, key, value)
            try:
                setattr(operation, key, value)
            except Exception as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid value for parameter '{key}': {exc}",
                )


# ── Background task helpers ───────────────────────────────────────────────────

async def _run_apply(session_id: str, step_index: int) -> None:
    """Background task: apply a single step and cascade to downstream steps."""
    state = session_manager.get(session_id)
    if state is None:
        return

    with state.lock:
        if step_index >= len(state.steps):
            return
        step = state.steps[step_index]
        step.status = StepStatus.APPLYING
        state.running_tasks.add(step_index)

    try:
        input_exp = state.input_experiment(step_index)
        result = await apply_step_async(step.operation, input_exp)
        with state.lock:
            step.update_from_result(result)
            state.running_tasks.discard(step_index)
        # Cascade: re-apply all downstream steps that were previously valid
        for downstream_idx in range(step_index + 1, len(state.steps)):
            await _run_apply(session_id, downstream_idx)
    except Exception as exc:
        logger.exception("apply failed for step %d in session %s", step_index, session_id)
        with state.lock:
            step.status = StepStatus.ERROR
            step.op_error = str(exc)
            step.result = None
            state.running_tasks.discard(step_index)
            state.invalidate_from(step_index + 1)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/steps", status_code=202)
async def add_step(
    session_id: str,
    body: AddStepRequest,
    background_tasks: BackgroundTasks,
) -> StepStatusResponse:
    """Add a new operation step to the end of the pipeline and schedule apply."""
    state = _require_session(session_id)

    op_class = _get_op_class(body.operation_id)
    operation = op_class()
    _apply_params(operation, body.params)

    step = WorkflowStep(operation=operation)
    with state.lock:
        step_index = len(state.steps)
        state.steps.append(step)
        state.selected_step_index = step_index

    background_tasks.add_task(_run_apply, session_id, step_index)

    return StepStatusResponse(
        index=step_index,
        status=StepStatus.APPLYING.value,
        op_error="",
        op_warning="",
        estimate_error="",
    )


@router.put("/steps/{step_index}", status_code=202)
async def update_step(
    session_id: str,
    step_index: int,
    body: UpdateParamsRequest,
    background_tasks: BackgroundTasks,
) -> StepStatusResponse:
    """Update operation parameters and reschedule apply from this step onward."""
    state = _require_session(session_id)
    step = _require_step(state, step_index)

    # Reject if a task is already running for this step
    if step_index in state.running_tasks:
        raise HTTPException(status_code=409, detail="A task is already running for this step")

    with state.lock:
        _apply_params(step.operation, body.params)
        state.invalidate_from(step_index)

    background_tasks.add_task(_run_apply, session_id, step_index)

    return StepStatusResponse(
        index=step_index,
        status=StepStatus.APPLYING.value,
        op_error="",
        op_warning="",
        estimate_error="",
    )


@router.post("/steps/{step_index}/estimate", status_code=202)
async def estimate_step(
    session_id: str,
    step_index: int,
    background_tasks: BackgroundTasks,
) -> StepStatusResponse:
    """Trigger estimate() for the given step, then re-apply."""
    state = _require_session(session_id)
    step = _require_step(state, step_index)

    if step_index in state.running_tasks:
        raise HTTPException(status_code=409, detail="A task is already running for this step")

    input_exp = state.input_experiment(step_index)
    if input_exp is None and step_index > 0:
        raise HTTPException(status_code=422, detail="Previous step has no result; cannot estimate")

    async def _run_estimate():
        state2 = session_manager.get(session_id)
        if state2 is None:
            return
        step2 = state2.steps[step_index]
        with state2.lock:
            step2.status = StepStatus.ESTIMATING
            state2.running_tasks.add(step_index)
        try:
            updated_op = await estimate_step_async(step2.operation, state2.input_experiment(step_index))
            with state2.lock:
                step2.operation = updated_op
                step2.estimate_error = ""
                state2.running_tasks.discard(step_index)
            await _run_apply(session_id, step_index)
        except Exception as exc:
            logger.exception("estimate failed for step %d", step_index)
            with state2.lock:
                step2.status = StepStatus.ERROR
                step2.estimate_error = str(exc)
                state2.running_tasks.discard(step_index)

    background_tasks.add_task(_run_estimate)

    return StepStatusResponse(
        index=step_index,
        status=StepStatus.ESTIMATING.value,
        op_error="",
        op_warning="",
        estimate_error="",
    )


@router.get("/steps/{step_index}/status", response_model=StepStatusResponse)
def get_step_status(session_id: str, step_index: int) -> StepStatusResponse:
    """Poll the status of a single step."""
    state = _require_session(session_id)
    step = _require_step(state, step_index)
    return StepStatusResponse(
        index=step_index,
        status=step.status.value,
        op_error=step.op_error,
        op_warning=step.op_warning,
        estimate_error=step.estimate_error,
    )
