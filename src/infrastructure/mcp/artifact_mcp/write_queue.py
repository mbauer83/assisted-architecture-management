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
_event_loop: asyncio.AbstractEventLoop | None = None


def attach_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the running event loop so worker threads can schedule SSE notifications."""
    global _event_loop
    _event_loop = loop


def _notify_gui_dirty() -> None:
    """Emit sync_status_changed on the GUI event bus from a worker thread (best-effort)."""
    if _event_loop is None or not _event_loop.is_running():
        return
    try:
        from src.infrastructure.gui.routers.events import event_bus
        from src.infrastructure.gui.routers.sync_status_cache import invalidate_sync_status_cache

        invalidate_sync_status_cache()
        asyncio.run_coroutine_threadsafe(
            event_bus.publish({"type": "artifact_write_completed"}),
            _event_loop,
        )
    except Exception:
        pass


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
        result = fn(*args, **kwargs)
        _notify_gui_dirty()
        return result
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

        future = _submit(fn, *args, **kwargs)
        while not future.done():
            await asyncio.sleep(0.001)
        return future.result()

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
        _executor.shutdown(wait=wait, cancel_futures=True)
        _executor = None
    with _state_cond:
        _submitted_jobs = 0
        _completed_jobs = 0
        _active_jobs = 0
        publish_write_queue_state(active_jobs=0, pending_jobs=0)
        _state_cond.notify_all()


def _shutdown_atexit() -> None:
    """Best-effort executor teardown during interpreter shutdown.

    Avoid publishing queue-state events here; subscriber modules may already be
    partially torn down, and tests explicitly exercise the full shutdown path.
    """

    global _executor
    executor = _executor
    _executor = None
    if executor is not None:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


atexit.register(_shutdown_atexit)
