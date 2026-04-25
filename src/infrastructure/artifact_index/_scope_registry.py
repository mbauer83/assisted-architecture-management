"""Scope-aware registry queries over _MemStore — injected into ArtifactIndex."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Literal

from ._mem_store import _MemStore


class _ScopeRegistry:
    """Provides entity/connection registry lookups filtered by repo scope.

    Receives the shared _MemStore, lock, and an ensure_loaded callback so it
    stays fully in sync with the owning ArtifactIndex without coupling to it.
    """

    def __init__(
        self,
        mem: _MemStore,
        lock: threading.RLock,
        ensure_loaded: Callable[[], None],
        scope_fn: Callable[[Path], Literal["enterprise", "engagement", "unknown"]],
    ) -> None:
        self._mem = mem
        self._lock = lock
        self._ensure_loaded = ensure_loaded
        self._scope = scope_fn

    # ── Full ID sets ──────────────────────────────────────────────────────────

    def entity_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return set(self._mem.entities)

    def connection_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return set(self._mem.connections)

    # ── Scope-filtered ID sets ────────────────────────────────────────────────

    def enterprise_entity_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return {aid for aid, r in self._mem.entities.items()
                    if self._scope(r.path) == "enterprise"}

    def engagement_entity_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return {aid for aid, r in self._mem.entities.items()
                    if self._scope(r.path) == "engagement"}

    def enterprise_connection_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return {aid for aid, r in self._mem.connections.items()
                    if self._scope(r.path) == "enterprise"}

    def engagement_connection_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return {aid for aid, r in self._mem.connections.items()
                    if self._scope(r.path) == "engagement"}

    def enterprise_document_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return {aid for aid, r in self._mem.documents.items()
                    if self._scope(r.path) == "enterprise"}

    def enterprise_diagram_ids(self) -> set[str]:
        self._ensure_loaded()
        with self._lock:
            return {aid for aid, r in self._mem.diagrams.items()
                    if self._scope(r.path) == "enterprise"}

    # ── Status and file lookups ───────────────────────────────────────────────

    def entity_status(self, artifact_id: str) -> str | None:
        self._ensure_loaded()
        with self._lock:
            r = self._mem.entities.get(artifact_id)
            return r.status if r is not None else None

    def entity_statuses(self) -> dict[str, str]:
        self._ensure_loaded()
        with self._lock:
            return {aid: r.status for aid, r in self._mem.entities.items()}

    def connection_status(self, artifact_id: str) -> str | None:
        self._ensure_loaded()
        with self._lock:
            r = self._mem.connections.get(artifact_id)
            return r.status if r is not None else None

    def find_file_by_id(self, artifact_id: str) -> Path | None:
        self._ensure_loaded()
        with self._lock:
            r = self._mem.entities.get(artifact_id)
            return r.path if r is not None else None
