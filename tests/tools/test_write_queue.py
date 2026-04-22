"""Tests for the model write queue serialization mechanism.

Verifies that:
- queued() wraps sync functions into awaitable coroutines
- concurrent writes are serialized (no interleaving)
- results are returned correctly to each caller
- exceptions raised inside queued functions propagate to the caller
- the original function signature is preserved via __wrapped__
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

import pytest

from src.tools.artifact_mcp.write_queue import queued, shutdown


@pytest.fixture(autouse=True)
def reset_executor():
    """Ensure a fresh executor for each test."""
    shutdown(wait=True)
    yield
    shutdown(wait=True)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------

class TestQueuedDecorator:
    def test_returns_coroutine_function(self):
        def sync_fn(x: int) -> int:
            return x * 2

        wrapped = queued(sync_fn)
        assert inspect.iscoroutinefunction(wrapped), "queued() must return an async function"

    def test_preserves_signature_via_wrapped(self):
        def sync_fn(a: int, b: str = "default") -> dict[str, Any]:
            return {"a": a, "b": b}

        wrapped = queued(sync_fn)
        sig = inspect.signature(wrapped)
        params = list(sig.parameters.keys())
        assert params == ["a", "b"], f"Unexpected params: {params}"

    def test_preserves_name_and_docstring(self):
        def my_write_fn(x: int) -> int:
            """Does a thing."""
            return x

        wrapped = queued(my_write_fn)
        assert wrapped.__name__ == "my_write_fn"
        assert wrapped.__doc__ == "Does a thing."

    def test_result_returned_correctly(self):
        def sync_fn(x: int, y: int) -> int:
            return x + y

        wrapped = queued(sync_fn)
        result = asyncio.run(wrapped(3, 4))
        assert result == 7

    def test_kwargs_forwarded(self):
        def sync_fn(*, name: str, count: int = 1) -> list[str]:
            return [name] * count

        wrapped = queued(sync_fn)
        result = asyncio.run(wrapped(name="hello", count=3))
        assert result == ["hello", "hello", "hello"]

    def test_exception_propagates(self):
        def sync_fn() -> None:
            raise ValueError("boom")

        wrapped = queued(sync_fn)
        with pytest.raises(ValueError, match="boom"):
            asyncio.run(wrapped())


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_concurrent_calls_are_serialized(self):
        """At most one queued write should run at a time."""
        active: list[int] = []
        peak_concurrency: list[int] = []
        lock = threading.Lock()

        def slow_write(task_id: int) -> int:
            with lock:
                active.append(task_id)
                peak_concurrency.append(len(active))
            import time
            time.sleep(0.01)
            with lock:
                active.remove(task_id)
            return task_id

        wrapped = queued(slow_write)

        async def run_all() -> list[int]:
            tasks = [wrapped(i) for i in range(8)]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_all())
        assert sorted(results) == list(range(8))
        assert max(peak_concurrency) == 1, (
            f"Expected max concurrency of 1, got {max(peak_concurrency)}"
        )

    def test_ordering_is_fifo(self):
        """Results should complete in the order submitted (FIFO queue)."""
        execution_order: list[int] = []

        def ordered_write(task_id: int) -> int:
            execution_order.append(task_id)
            return task_id

        wrapped = queued(ordered_write)

        async def run_sequentially() -> list[int]:
            results = []
            for i in range(5):
                results.append(await wrapped(i))
            return results

        results = asyncio.run(run_sequentially())
        assert results == list(range(5))
        assert execution_order == list(range(5))

    def test_exception_does_not_block_subsequent_writes(self):
        """A write that raises should not leave the queue stuck."""
        call_count: list[int] = [0]

        def maybe_raise(fail: bool) -> str:
            call_count[0] += 1
            if fail:
                raise RuntimeError("intentional failure")
            return "ok"

        wrapped = queued(maybe_raise)

        async def run() -> None:
            with pytest.raises(RuntimeError):
                await wrapped(fail=True)
            result = await wrapped(fail=False)
            assert result == "ok"

        asyncio.run(run())
        assert call_count[0] == 2

    def test_multiple_concurrent_exceptions_do_not_block(self):
        """Multiple concurrent failures should each propagate without deadlock."""
        def always_fail(task_id: int) -> None:
            raise ValueError(f"fail-{task_id}")

        wrapped = queued(always_fail)

        async def run_all() -> None:
            tasks = [wrapped(i) for i in range(4)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, r in enumerate(results):
                assert isinstance(r, ValueError)
                assert str(r) == f"fail-{i}"

        asyncio.run(run_all())


# ---------------------------------------------------------------------------
# Shutdown / reset
# ---------------------------------------------------------------------------

class TestShutdown:
    def test_shutdown_and_restart(self):
        """After shutdown, a new executor is created on the next call."""
        def sync_fn() -> str:
            return "alive"

        wrapped = queued(sync_fn)

        result1 = asyncio.run(wrapped())
        assert result1 == "alive"

        shutdown(wait=True)

        result2 = asyncio.run(wrapped())
        assert result2 == "alive"
