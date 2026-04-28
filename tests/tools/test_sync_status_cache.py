from __future__ import annotations

import asyncio

from src.infrastructure.gui.routers import sync_status_cache
from src.infrastructure.gui.routers.events import EventBus


def test_sync_status_cache_coalesces_concurrent_refreshes(monkeypatch) -> None:
    sync_status_cache.reset_sync_status_cache()
    calls = 0

    async def fake_compute() -> dict[str, object]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"engagement": {"has_uncommitted_changes": False}, "enterprise": None}

    monkeypatch.setattr(sync_status_cache, "_compute_sync_status", fake_compute)

    async def run() -> list[dict[str, object]]:
        return await asyncio.gather(
            *[sync_status_cache.get_sync_status() for _ in range(25)]
        )

    results = asyncio.run(run())

    assert calls == 1
    assert len(results) == 25
    assert all(result["engagement"] == {"has_uncommitted_changes": False} for result in results)


def test_sync_status_cache_recomputes_after_invalidation(monkeypatch) -> None:
    sync_status_cache.reset_sync_status_cache()
    calls = 0

    async def fake_compute() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"engagement": {"has_uncommitted_changes": bool(calls % 2)}, "enterprise": None}

    monkeypatch.setattr(sync_status_cache, "_compute_sync_status", fake_compute)

    first = asyncio.run(sync_status_cache.get_sync_status())
    second = asyncio.run(sync_status_cache.get_sync_status())
    sync_status_cache.invalidate_sync_status_cache()
    third = asyncio.run(sync_status_cache.get_sync_status())

    assert calls == 2
    assert first == second
    assert third != second


def test_event_bus_coalesces_redundant_status_events() -> None:
    async def run() -> None:
        bus = EventBus()
        queue = await bus.subscribe()
        await bus.publish({"type": "sync_status_changed", "repo": "/tmp/repo-a", "seq": 1})
        await bus.publish({"type": "sync_status_changed", "repo": "/tmp/repo-a", "seq": 2})
        await bus.publish({"type": "artifact_write_completed"})
        await bus.publish({"type": "artifact_write_completed"})

        assert queue.qsize() == 2
        first = await queue.get()
        second = await queue.get()
        assert first["type"] == "sync_status_changed"
        assert first["seq"] == 2
        assert second["type"] == "artifact_write_completed"

    asyncio.run(run())
