"""
cytoflowweb.api.workers.tasks
------------------------------

Top-level (picklable) functions that run inside the ``ProcessPoolExecutor``.

All functions in this module must be importable at the top level and must not
close over any non-picklable state.  They receive plain data, call the cytoflow
core library, and return plain data or raise exceptions.

The companion async helpers (``apply_step_async``, etc.) wrap these in
``run_in_executor`` for use from FastAPI route handlers.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

from cytoflow import Experiment
from cytoflow.operations.i_operation import IOperation
from cytoflow.utility import CytoflowError, CytoflowOpError

from cytoflowweb.api.workers.executor import run_in_executor

logger = logging.getLogger(__name__)


# ── Pure functions executed in the worker process ─────────────────────────────

def _apply(operation: IOperation, experiment: Experiment | None) -> Experiment:
    """Apply *operation* to *experiment* and return the result.

    Parameters
    ----------
    operation:
        A fully-configured ``IOperation`` instance.
    experiment:
        The input experiment, or *None* for ``ImportOp`` (first step).

    Returns
    -------
    Experiment
        The result experiment.

    Raises
    ------
    CytoflowOpError
        Propagated from the operation if parameters are invalid.
    """
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        return operation.apply(experiment)


def _estimate(operation: IOperation, experiment: Experiment) -> IOperation:
    """Run ``operation.estimate()`` and return the updated operation.

    The updated operation (with fitted parameters stored as traits) is
    returned so it can be sent back to the main process.
    """
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        operation.estimate(experiment)
    return operation


# ── Async wrappers for use in FastAPI route handlers ─────────────────────────

async def apply_step_async(
    operation: IOperation,
    experiment: Experiment | None,
) -> Experiment:
    """Async wrapper around :func:`_apply`."""
    return await run_in_executor(_apply, operation, experiment)


async def estimate_step_async(
    operation: IOperation,
    experiment: Experiment,
) -> IOperation:
    """Async wrapper around :func:`_estimate`."""
    return await run_in_executor(_estimate, operation, experiment)
