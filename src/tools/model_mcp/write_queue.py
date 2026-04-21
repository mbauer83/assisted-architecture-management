"""Write queue — serializes all model write operations through a single worker.

Concurrent write calls (model_create_entity, model_add_connection, etc.) race on
shared .md files and the SQLite index when issued in parallel. This module provides
a single-worker ThreadPoolExecutor that drains write operations serially: each call
is accepted immediately and returns its result as soon as it completes, but only one
write runs at a time.

Usage at MCP registration time:
    from src.tools.model_mcp.write_queue import queued
    mcp.tool(...)(queued(my_sync_write_fn))

The wrapped function is async and preserves the original signature via __wrapped__
so FastMCP can derive the correct JSON schema.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, TypeVar

_F = TypeVar("_F", bound=Callable[..., Any])

_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None or _executor._shutdown:
        _executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="model-write-queue"
        )
    return _executor


def queued(fn: _F) -> _F:
    """Wrap a synchronous write function to execute serially through the write queue.

    Returns an async coroutine function with the same parameter signature as *fn*
    (FastMCP inspects __wrapped__ to derive the tool schema). At most one queued
    operation runs at a time; all others wait in the executor's work queue.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_get_executor(), lambda: fn(*args, **kwargs))

    return wrapper  # type: ignore[return-value]


def run_sync(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    """Execute a synchronous write through the shared single-worker queue.

    This is intended for REST handlers, which are currently synchronous and need
    to serialize writes with MCP tool calls once both paths share one process.
    """

    return _get_executor().submit(fn, *args, **kwargs).result()


def shutdown(wait: bool = True) -> None:
    """Shut down the write queue executor (for testing / clean teardown)."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
