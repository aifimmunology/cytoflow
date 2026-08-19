"""
cytoflowweb.api.workers.executor
---------------------------------

Manages a ``ProcessPoolExecutor`` for running CPU-bound cytoflow operations
(apply, estimate, plot) off the FastAPI event loop.

All submitted tasks are tracked per-session so the API can report status and
prevent duplicate submissions.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor, Future

logger = logging.getLogger(__name__)

# A single process pool shared across the application.
# Initialised once in the FastAPI lifespan handler.
_executor: ProcessPoolExecutor | None = None
_loop: asyncio.AbstractEventLoop | None = None


def init_executor(max_workers: int | None = None) -> None:
    """Create the process pool.  Call once at application startup."""
    global _executor, _loop
    _executor = ProcessPoolExecutor(max_workers=max_workers)
    _loop = asyncio.get_event_loop()
    logger.info("ProcessPoolExecutor started (max_workers=%s)", max_workers)


def shutdown_executor() -> None:
    """Gracefully shut down the process pool.  Call at application shutdown."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=False, cancel_futures=True)
        _executor = None
        logger.info("ProcessPoolExecutor shut down")


async def run_in_executor(fn, *args):
    """Run a synchronous callable in the process pool and await its result.

    Parameters
    ----------
    fn:
        A *picklable* top-level function (or bound method of a picklable
        object).  Lambdas and closures are not picklable and will fail.
    *args:
        Arguments forwarded to ``fn``.

    Returns
    -------
    Any
        The return value of ``fn(*args)``.

    Raises
    ------
    RuntimeError
        If the executor has not been initialised.
    """
    if _executor is None:
        raise RuntimeError("Executor not initialised. Call init_executor() first.")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, fn, *args)
