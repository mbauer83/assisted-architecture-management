"""Cached sync-status read model for GUI and other HTTP clients.

The underlying git probes are relatively expensive. This module keeps a small
in-process cache with singleflight refresh so many concurrent clients do not
multiply git work. Correctness comes from explicit invalidation on writes and
repo updates, plus a stale-age fallback refresh.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from src.config.repo_paths import DIAGRAM_CATALOG, DOCS, MODEL

_MAX_STALE_S = 120.0
_lock = asyncio.Lock()
_refresh_task: asyncio.Task[dict[str, Any]] | None = None
_cached_value: dict[str, Any] | None = None
_cached_at_monotonic = 0.0
_dirty = True


async def _compute_sync_status() -> dict[str, Any]:
    from src.infrastructure.git import enterprise_git_ops, enterprise_sync_state
    from src.infrastructure.gui.routers import state as s
    from src.infrastructure.gui.routers.sync import _status_label

    out: dict[str, Any] = {"engagement": None, "enterprise": None}

    eng_root = s.maybe_engagement_root()
    if eng_root is not None:
        dirty = await asyncio.to_thread(
            enterprise_git_ops.has_uncommitted_changes,
            eng_root,
            MODEL,
            DOCS,
            DIAGRAM_CATALOG,
        )
        out["engagement"] = {"has_uncommitted_changes": dirty}

    ent_root = s.maybe_enterprise_root()
    if ent_root is not None:
        sync_state = enterprise_sync_state.load(ent_root)
        dirty = await asyncio.to_thread(enterprise_git_ops.has_uncommitted_changes, ent_root)
        info: dict[str, Any] = {
            "status": sync_state.status,
            "label": _status_label(sync_state.status),
            "branch": sync_state.branch,
            "branch_tip": sync_state.branch_tip,
            "pushed_at": sync_state.pushed_at,
            "commits_behind": sync_state.commits_behind,
            "has_uncommitted_changes": dirty,
        }
        if sync_state.is_accumulating():
            info["commits_ahead"] = await asyncio.to_thread(enterprise_git_ops.commits_ahead_of_main, ent_root)
        out["enterprise"] = info

    return out


async def get_sync_status() -> dict[str, Any]:
    global _refresh_task
    now = time.monotonic()
    cached = _cached_value
    if cached is not None and not _dirty and (now - _cached_at_monotonic) < _MAX_STALE_S:
        return cached

    async with _lock:
        now = time.monotonic()
        cached = _cached_value
        if cached is not None and not _dirty and (now - _cached_at_monotonic) < _MAX_STALE_S:
            return cached
        if _refresh_task is None or _refresh_task.done():
            _refresh_task = asyncio.create_task(_refresh_now(), name="sync-status-refresh")
        task = _refresh_task

    return await task


async def _refresh_now() -> dict[str, Any]:
    global _cached_value, _cached_at_monotonic, _dirty
    value = await _compute_sync_status()
    async with _lock:
        _cached_value = value
        _cached_at_monotonic = time.monotonic()
        _dirty = False
    return value


def invalidate_sync_status_cache(*, repo: Path | None = None) -> None:
    """Mark the cached sync status dirty.

    The optional repo path is reserved for future per-repo segmentation.
    """

    del repo
    global _dirty
    _dirty = True


def reset_sync_status_cache() -> None:
    """Testing helper to reset process-local cache state."""

    global _refresh_task, _cached_value, _cached_at_monotonic, _dirty
    _refresh_task = None
    _cached_value = None
    _cached_at_monotonic = 0.0
    _dirty = True
