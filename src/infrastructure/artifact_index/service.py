"""SQLite-backed artifact index — in-memory read model with incremental update."""

from __future__ import annotations

import hashlib
import threading
from collections import Counter
from pathlib import Path
from typing import Callable, Literal, TypeVar

from src.common._artifact_query_helpers import (
    matches_connection,
    matches_connection_sets,
    matches_diagram,
    matches_diagram_sets,
    matches_entity,
    matches_entity_sets,
    read_connection,
    read_diagram,
    read_document,
    read_entity,
    to_set,
)
from src.common.artifact_types import (
    ArtifactSummary,
    ConnectionRecord,
    DiagramRecord,
    DocumentRecord,
    EntityRecord,
    RepoMount,
    summary_from_connection,
    summary_from_diagram,
    summary_from_document,
    summary_from_entity,
)
from src.common.workspace_paths import infer_repo_scope

from . import _sqlite_queries as _q
from ._mem_store import _MemStore
from ._scope_registry import _ScopeRegistry
from ._service_incremental import (
    apply_diagram_change,
    apply_document_change,
    apply_entity_change,
    apply_outgoing_change,
    is_diagram_source_path,
    is_document_path,
    scan_mount,
)
from ._sqlite_store import _SqliteStore
from .bootstrap import get_shared_index, normalize_mounts, service_key
from .types import EntityContextReadModel
from .versioning import ReadModelVersion, build_read_model_etag

_T = TypeVar("_T", EntityRecord, ConnectionRecord, DiagramRecord, DocumentRecord)


def shared_artifact_index(repo_root: Path | list[Path] | list[RepoMount]) -> "ArtifactIndex":
    return get_shared_index(ArtifactIndex, repo_root)


class ArtifactIndex:
    def __init__(self, repo_root: Path | list[Path] | list[RepoMount]) -> None:
        mounts = normalize_mounts(repo_root)
        self.repo_mounts: list[RepoMount] = mounts
        self.repo_roots: list[Path] = [m.root for m in mounts]
        self.repo_root: Path = mounts[0].root
        self._scope_key = service_key(mounts)
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._generation = 0
        self._etag = build_read_model_etag(self._scope_key, 0)
        self._mem = _MemStore()
        name_hash = hashlib.blake2b(service_key(mounts).encode("utf-8"), digest_size=10).hexdigest()
        self._db = _SqliteStore(name_hash, self._mem, self.scope_for_path)
        self._registry = _ScopeRegistry(
            self._mem, self._lock, self._ensure_loaded, self.scope_for_path
        )

    def _ensure_loaded(self) -> None:
        if not self._ready.is_set():
            with self._lock:
                if not self._ready.is_set():
                    self.refresh()
                    self._ready.set()

    def refresh(self) -> None:
        with self._lock:
            self._mem.clear()
            for mount in self.repo_mounts:
                scan_mount(mount, self._mem)
            self._db.rebuild()
            self._mem.rebuild_path_indexes()
            self._bump_generation()
            self._ready.set()

    def apply_file_changes(self, paths: list[Path]) -> ReadModelVersion:
        self._ensure_loaded()
        normalized = sorted({p.resolve() for p in paths})
        if not normalized:
            return self.read_model_version()
        if any(p.is_dir() for p in normalized):
            self.refresh()
            return self.read_model_version()
        with self._lock:
            for path in normalized:
                if path.name.endswith(".outgoing.md"):
                    apply_outgoing_change(path, self._mem, self._db)
                elif is_diagram_source_path(path, self.repo_mounts):
                    apply_diagram_change(path, self._mem, self._db)
                elif is_document_path(path, self.repo_mounts):
                    apply_document_change(path, self._mem, self._db)
                elif path.suffix == ".md":
                    apply_entity_change(path, self._mem, self._db, self.repo_mounts)
                else:
                    self.refresh()
                    return self.read_model_version()
            self._bump_generation()
        return self.read_model_version()

    def read_model_version(self) -> ReadModelVersion:
        self._ensure_loaded()
        return ReadModelVersion(generation=self._generation, etag=self._etag)

    def generation(self) -> int:
        self._ensure_loaded()
        return self._generation

    # ── Point lookups ─────────────────────────────────────────────────────────

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        self._ensure_loaded()
        with self._lock:
            return self._mem.entities.get(artifact_id)

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        self._ensure_loaded()
        with self._lock:
            return self._mem.connections.get(artifact_id)

    def get_diagram(self, artifact_id: str) -> DiagramRecord | None:
        self._ensure_loaded()
        with self._lock:
            return self._mem.diagrams.get(artifact_id)

    def get_document(self, artifact_id: str) -> DocumentRecord | None:
        self._ensure_loaded()
        with self._lock:
            return self._mem.documents.get(artifact_id)

    # ── Filtered list queries ─────────────────────────────────────────────────

    def _list_sorted(self, collection: dict[str, _T], predicate: Callable[[_T], bool]) -> list[_T]:
        self._ensure_loaded()
        with self._lock:
            results = [v for v in collection.values() if predicate(v)]
        return sorted(results, key=lambda r: r.artifact_id)

    def list_entities(
        self,
        *,
        artifact_type: str | None = None,
        domain: str | None = None,
        subdomain: str | None = None,
        status: str | None = None,
    ) -> list[EntityRecord]:
        return self._list_sorted(
            self._mem.entities,
            lambda r: matches_entity(
                r,
                artifact_type=artifact_type,
                domain=domain,
                subdomain=subdomain,
                status=status,
            ),
        )

    def list_connections(
        self,
        *,
        conn_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        status: str | None = None,
    ) -> list[ConnectionRecord]:
        return self._list_sorted(
            self._mem.connections,
            lambda r: matches_connection(
                r,
                conn_type=conn_type,
                source=source,
                target=target,
                status=status,
            ),
        )

    def list_diagrams(
        self, *, diagram_type: str | None = None, status: str | None = None
    ) -> list[DiagramRecord]:
        return self._list_sorted(
            self._mem.diagrams,
            lambda r: matches_diagram(
                r,
                diagram_type=diagram_type,
                status=status,
            ),
        )

    def list_documents(
        self, *, doc_type: str | None = None, status: str | None = None
    ) -> list[DocumentRecord]:
        return self._list_sorted(
            self._mem.documents,
            lambda r: (
                (doc_type is None or r.doc_type == doc_type)
                and (status is None or r.status == status)
            ),
        )

    def list_artifacts(
        self,
        *,
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_connections: bool = False,
        include_diagrams: bool = False,
        include_documents: bool = False,
    ) -> list[ArtifactSummary]:
        self._ensure_loaded()
        types = to_set(artifact_type)
        domains = {d.lower() for d in to_set(domain)}
        statuses = to_set(status)
        with self._lock:
            out: list[ArtifactSummary] = [
                summary_from_entity(r)
                for r in self._mem.entities.values()
                if matches_entity_sets(r, types, domains, statuses)
            ]
            if include_connections:
                out.extend(
                    summary_from_connection(r)
                    for r in self._mem.connections.values()
                    if matches_connection_sets(r, statuses)
                )
            if include_diagrams:
                out.extend(
                    summary_from_diagram(r)
                    for r in self._mem.diagrams.values()
                    if matches_diagram_sets(r, types, statuses)
                )
            if include_documents:
                out.extend(
                    summary_from_document(r)
                    for r in self._mem.documents.values()
                    if (not statuses or r.status in statuses)
                )
        return sorted(out, key=lambda s: s.artifact_id)

    # ── Richer reads ──────────────────────────────────────────────────────────

    def read_artifact(
        self,
        artifact_id: str,
        *,
        mode: Literal["summary", "full"] = "summary",
        section: str | None = None,
    ) -> dict[str, object] | None:
        self._ensure_loaded()
        with self._lock:
            ent = self._mem.entities.get(artifact_id)
            if ent is not None:
                return read_entity(ent, mode=mode)
            conn = self._mem.connections.get(artifact_id)
            if conn is not None:
                return read_connection(conn, mode=mode)
            diag = self._mem.diagrams.get(artifact_id)
            if diag is not None:
                return read_diagram(diag, mode=mode)
            doc = self._mem.documents.get(artifact_id)
            if doc is not None:
                return read_document(doc, mode=mode, section=section)
        return None

    def summarize_artifact(self, artifact_id: str) -> ArtifactSummary | None:
        self._ensure_loaded()
        with self._lock:
            ent = self._mem.entities.get(artifact_id)
            if ent is not None:
                return summary_from_entity(ent)
            conn = self._mem.connections.get(artifact_id)
            if conn is not None:
                return summary_from_connection(conn)
            diag = self._mem.diagrams.get(artifact_id)
            if diag is not None:
                return summary_from_diagram(diag)
            doc = self._mem.documents.get(artifact_id)
            if doc is not None:
                return summary_from_document(doc)
        return None

    def read_entity_context(self, artifact_id: str) -> EntityContextReadModel | None:
        self._ensure_loaded()
        with self._lock:
            entity = self._mem.entities.get(artifact_id)
            if entity is None:
                return None
            entity_data: dict[str, object] = {
                "artifact_id": entity.artifact_id,
                "artifact_type": entity.artifact_type,
                "name": entity.name,
                "version": entity.version,
                "status": entity.status,
                "domain": entity.domain,
                "subdomain": entity.subdomain,
                "record_type": "entity",
                "path": str(entity.path),
                "content_snippet": entity.content_text[:240],
                "keywords": list(entity.keywords),
                "content_text": entity.content_text,
                "display_blocks": entity.display_blocks,
                "extra": entity.extra,
            }
            return _q.entity_context(
                self._db.conn, artifact_id, entity_data, self._generation, self._etag
            )

    def stats(self) -> dict[str, object]:
        self._ensure_loaded()
        with self._lock:
            entities = list(self._mem.entities.values())
            connections = list(self._mem.connections.values())
            diagrams = list(self._mem.diagrams.values())
            documents = list(self._mem.documents.values())
        return {
            "entities": len(entities),
            "connections": len(connections),
            "diagrams": len(diagrams),
            "documents": len(documents),
            "entities_by_domain": dict(Counter(e.domain for e in entities)),
            "connections_by_type": dict(Counter(c.conn_type for c in connections)),
            "documents_by_type": dict(Counter(d.doc_type for d in documents)),
        }

    # ── Connection queries ────────────────────────────────────────────────────

    def connection_counts(self) -> dict[str, tuple[int, int, int]]:
        self._ensure_loaded()
        with self._lock:
            return _q.all_connection_stats(self._db.conn)

    def connection_counts_for(self, entity_id: str) -> tuple[int, int, int]:
        self._ensure_loaded()
        with self._lock:
            return _q.connection_stats_for(self._db.conn, entity_id)

    def list_connections_by_types(self, types: frozenset[str]) -> list[ConnectionRecord]:
        self._ensure_loaded()
        with self._lock:
            return [
                r
                for cid in _q.connection_ids_by_types(self._db.conn, types)
                if (r := self._mem.connections.get(cid)) is not None
            ]

    def find_connections_for(
        self,
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]:
        self._ensure_loaded()
        with self._lock:
            return [
                r
                for cid in _q.connection_ids_for(
                    self._db.conn,
                    entity_id,
                    direction=direction,
                    conn_type=conn_type,
                )
                if (r := self._mem.connections.get(cid)) is not None
            ]

    def find_neighbors(
        self, entity_id: str, *, max_hops: int = 1, conn_type: str | None = None
    ) -> dict[str, set[str]]:
        self._ensure_loaded()
        with self._lock:
            return _q.find_neighbors(
                self._db.conn,
                entity_id,
                max_hops=max_hops,
                conn_type=conn_type,
            )

    def search_fts(
        self,
        query: str,
        *,
        limit: int,
        include_connections: bool,
        include_diagrams: bool,
        include_documents: bool,
        prefer_record_type: str | None,
        strict_record_type: bool,
    ) -> list[tuple[str, str, float]]:
        self._ensure_loaded()
        with self._lock:
            return _q.search_fts(
                self._db.conn,
                query,
                limit=limit,
                include_connections=include_connections,
                include_diagrams=include_diagrams,
                include_documents=include_documents,
                prefer_record_type=prefer_record_type,
                strict_record_type=strict_record_type,
                fts_enabled=self._db.fts_enabled,
            )

    # ── Scope ─────────────────────────────────────────────────────────────────

    def scope_for_path(self, path: Path) -> Literal["enterprise", "engagement", "unknown"]:
        resolved = path.resolve()
        for root in self.repo_roots:
            try:
                resolved.relative_to(root)
                return "enterprise" if infer_repo_scope(root) == "enterprise" else "engagement"
            except ValueError:
                continue
        return "unknown"

    def scope_of_entity(self, artifact_id: str) -> Literal["enterprise", "engagement", "unknown"]:
        rec = self.get_entity(artifact_id)
        return self.scope_for_path(rec.path) if rec is not None else "unknown"

    def scope_of_connection(
        self, artifact_id: str
    ) -> Literal["enterprise", "engagement", "unknown"]:
        rec = self.get_connection(artifact_id)
        return self.scope_for_path(rec.path) if rec is not None else "unknown"

    # ── Registry-style queries (delegated to _ScopeRegistry) ─────────────────

    def entity_ids(self) -> set[str]:
        return self._registry.entity_ids()

    def connection_ids(self) -> set[str]:
        return self._registry.connection_ids()

    def enterprise_entity_ids(self) -> set[str]:
        return self._registry.enterprise_entity_ids()

    def engagement_entity_ids(self) -> set[str]:
        return self._registry.engagement_entity_ids()

    def enterprise_connection_ids(self) -> set[str]:
        return self._registry.enterprise_connection_ids()

    def engagement_connection_ids(self) -> set[str]:
        return self._registry.engagement_connection_ids()

    def enterprise_document_ids(self) -> set[str]:
        return self._registry.enterprise_document_ids()

    def enterprise_diagram_ids(self) -> set[str]:
        return self._registry.enterprise_diagram_ids()

    def entity_status(self, artifact_id: str) -> str | None:
        return self._registry.entity_status(artifact_id)

    def entity_statuses(self) -> dict[str, str]:
        return self._registry.entity_statuses()

    def connection_status(self, artifact_id: str) -> str | None:
        return self._registry.connection_status(artifact_id)

    def find_file_by_id(self, artifact_id: str) -> Path | None:
        return self._registry.find_file_by_id(artifact_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _bump_generation(self) -> None:
        self._generation += 1
        self._etag = build_read_model_etag(self._scope_key, self._generation)
