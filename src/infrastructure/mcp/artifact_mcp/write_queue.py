"""Write queue — serializes all model write operations through a single worker.

Concurrent write calls (artifact_create_entity, artifact_add_connection, etc.) race on
shared .md files and the SQLite index when issued in parallel. This module provides
a single-worker ThreadPoolExecutor that drains write operations serially: each call
is accepted immediately and returns its result as soon as it completes, but only one
write runs at a time.

Usage at MCP registration time:
    from src.infrastructure.mcp.artifact_mcp.write_queue import queued
    mcp.tool(...)(queued(my_sync_write_fn))

The wrapped function is async and preserves the original signature via __wrapped__
so FastMCP can derive the correct JSON schema.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, TypeVar

from src.infrastructure.artifact_index.coordination import publish_write_queue_state

_F = TypeVar("_F", bound=Callable[..., Any])

_executor: ThreadPoolExecutor | None = None
_state_cond = threading.Condition()
_submitted_jobs = 0
_completed_jobs = 0
_active_jobs = 0


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None or _executor._shutdown:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="model-write-queue")
    return _executor


def _emit_queue_state() -> None:
    with _state_cond:
        publish_write_queue_state(
            active_jobs=_active_jobs,
            pending_jobs=max(_submitted_jobs - _completed_jobs - _active_jobs, 0),
        )


def _run_job(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    global _active_jobs, _completed_jobs
    with _state_cond:
        _active_jobs += 1
        publish_write_queue_state(
            active_jobs=_active_jobs,
            pending_jobs=max(_submitted_jobs - _completed_jobs - _active_jobs, 0),
        )
    try:
        return fn(*args, **kwargs)
    finally:
        with _state_cond:
            _active_jobs -= 1
            _completed_jobs += 1
            publish_write_queue_state(
                active_jobs=_active_jobs,
                pending_jobs=max(_submitted_jobs - _completed_jobs - _active_jobs, 0),
            )
            _state_cond.notify_all()


def _submit(fn: Callable[..., Any], /, *args: Any, **kwargs: Any):
    global _submitted_jobs
    with _state_cond:
        _submitted_jobs += 1
        publish_write_queue_state(
            active_jobs=_active_jobs,
            pending_jobs=max(_submitted_jobs - _completed_jobs - _active_jobs, 0),
        )
    return _get_executor().submit(_run_job, fn, *args, **kwargs)


def queued(fn: _F) -> _F:
    """Wrap a synchronous write function to execute serially through the write queue.

    Returns an async coroutine function with the same parameter signature as *fn*
    (FastMCP inspects __wrapped__ to derive the tool schema). At most one queued
    operation runs at a time; all others wait in the executor's work queue.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Check write-block state before submitting to queue
        repo_root_str = kwargs.get("repo_root")
        if repo_root_str is not None:
            from pathlib import Path

            from src.infrastructure.workspace.write_block_manager import is_blocked

            if is_blocked(Path(repo_root_str)):
                raise RuntimeError(
                    "Writes are temporarily blocked (sync in progress or read-only mode)"
                )

        loop = asyncio.get_running_loop()
        future = _submit(fn, *args, **kwargs)
        return await asyncio.wrap_future(future, loop=loop)

    return wrapper  # type: ignore[return-value]


def run_sync(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Execute a synchronous write through the shared single-worker queue.

    This is intended for REST handlers, which are currently synchronous and need
    to serialize writes with MCP tool calls once both paths share one process.
    """

    return _submit(fn, *args, **kwargs).result()


def wait_until_idle(timeout_s: float | None = None) -> bool:
    import time

    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    with _state_cond:
        while _active_jobs > 0 or (_submitted_jobs - _completed_jobs) > 0:
            if deadline is None:
                _state_cond.wait()
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _state_cond.wait(timeout=remaining)
    return True


def shutdown(wait: bool = True) -> None:
    """Shut down the write queue executor (for testing / clean teardown)."""
    global _executor, _submitted_jobs, _completed_jobs, _active_jobs
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
    with _state_cond:
        _submitted_jobs = 0
        _completed_jobs = 0
        _active_jobs = 0
        publish_write_queue_state(active_jobs=0, pending_jobs=0)
        _state_cond.notify_all()


atexit.register(lambda: shutdown(wait=False))
