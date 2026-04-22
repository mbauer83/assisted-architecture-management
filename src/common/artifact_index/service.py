"""Shared runtime SQLite-backed index for entities, connections, and diagrams."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path
from typing import cast, overload

from .bootstrap import get_shared_index, normalize_mounts, service_key
from src.common.artifact_parsing import parse_diagram, parse_document, parse_entity, parse_outgoing_file
from src.common.workspace_paths import infer_repo_scope
from src.common.artifact_types import (
    ConnectionRecord,
    DiagramRecord,
    DocumentRecord,
    DuplicateArtifactIdError,
    EntityRecord,
    RepoMount,
)

from .context import (
    apply_diagram_file_change,
    apply_document_file_change,
    apply_entity_file_change,
    apply_outgoing_file_change,
    read_entity_context,
    rebuild_entity_context_for,
    rebuild_entity_context_projection,
)
from .queries import find_connection_ids_for, find_neighbors, search_artifacts
from .schema import init_db
from .storage import (
    delete_connection_record,
    delete_diagram_record,
    delete_document_record,
    delete_entity_record,
    rebuild_sqlite,
    upsert_diagram_record,
    upsert_connection_record,
    upsert_document_record,
    upsert_entity_record,
)
from .types import EntityContextReadModel
from .versioning import ReadModelVersion, build_read_model_etag

def shared_artifact_index(repo_root: Path | list[Path] | list[RepoMount]) -> "ArtifactIndex":
    return get_shared_index(ArtifactIndex, repo_root)


class ArtifactIndex:
    def __init__(self, repo_root: Path | list[Path] | list[RepoMount]) -> None:
        mounts = normalize_mounts(repo_root)
        self.repo_mounts = mounts
        self.repo_roots = [m.root for m in mounts]
        self.repo_root = mounts[0].root
        self._scope_key = service_key(mounts)
        self._entities: dict[str, EntityRecord] = {}
        self._connections: dict[str, ConnectionRecord] = {}
        self._diagrams: dict[str, DiagramRecord] = {}
        self._documents: dict[str, DocumentRecord] = {}
        self._loaded = False
        self._generation = 0
        self._etag = build_read_model_etag(self._scope_key, self._generation)
        self._lock = threading.RLock()
        self._fts_enabled = True
        name_hash = hashlib.blake2b(service_key(mounts).encode("utf-8"), digest_size=10).hexdigest()
        self._conn = sqlite3.connect(
            f"file:arch-artifact-index-{name_hash}?mode=memory&cache=shared",
            uri=True,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        init_db(self)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if not self._loaded:
                self.refresh()

    def refresh(self) -> None:
        with self._lock:
            entities: dict[str, EntityRecord] = {}
            connections: dict[str, ConnectionRecord] = {}
            diagrams: dict[str, DiagramRecord] = {}
            documents: dict[str, DocumentRecord] = {}
            for mount in self.repo_mounts:
                self._scan_mount(mount, entities, connections, diagrams, documents)
            self._entities = entities
            self._connections = connections
            self._diagrams = diagrams
            self._documents = documents
            rebuild_sqlite(self)
            self._generation += 1
            self._etag = build_read_model_etag(self._scope_key, self._generation)
            self._loaded = True

    def _scan_mount(
        self,
        mount: RepoMount,
        entities: dict[str, EntityRecord],
        connections: dict[str, ConnectionRecord],
        diagrams: dict[str, DiagramRecord],
        documents: dict[str, DocumentRecord],
    ) -> None:
        model_root = mount.root / "model"
        if model_root.exists():
            for path in sorted(model_root.rglob("*.md")):
                if path.name.endswith(".outgoing.md"):
                    continue
                rec = parse_entity(path, model_root)
                if rec is not None:
                    self._insert_mounted(entities, rec.artifact_id, rec, "entity", mount.root)
            for path in sorted(model_root.rglob("*.outgoing.md")):
                for rec in parse_outgoing_file(path):
                    self._insert_mounted(connections, rec.artifact_id, rec, "connection", mount.root)
        diagrams_root = mount.root / "diagram-catalog" / "diagrams"
        if diagrams_root.exists():
            for suffix in ("*.puml", "*.md"):
                for path in sorted(diagrams_root.rglob(suffix)):
                    if path.parent.name != "rendered":
                        rec = parse_diagram(path)
                        if rec is not None:
                            self._insert_mounted(diagrams, rec.artifact_id, rec, "diagram", mount.root)
        docs_root = mount.root / "documents"
        if docs_root.exists():
            for path in sorted(docs_root.rglob("*.md")):
                rec = parse_document(path)
                if rec is not None:
                    self._insert_mounted(documents, rec.artifact_id, rec, "document", mount.root)

    @staticmethod
    def _insert_mounted(
        store: dict[str, EntityRecord] | dict[str, ConnectionRecord] | dict[str, DiagramRecord] | dict[str, DocumentRecord],
        artifact_id: str,
        rec: EntityRecord | ConnectionRecord | DiagramRecord | DocumentRecord,
        label: str,
        mount_root: Path,
    ) -> None:
        existing = store.get(artifact_id)
        if existing is None:
            ArtifactIndex._insert_unique(store, artifact_id, rec, label)
            return
        try:
            existing.path.resolve().relative_to(mount_root.resolve())
        except ValueError:
            return
        raise DuplicateArtifactIdError(f"Duplicate {label} artifact-id '{artifact_id}' in {rec.path} and {existing.path}")

    @staticmethod
    @overload
    def _insert_unique(store: dict[str, EntityRecord], artifact_id: str, rec: EntityRecord, label: str) -> None: ...

    @staticmethod
    @overload
    def _insert_unique(store: dict[str, ConnectionRecord], artifact_id: str, rec: ConnectionRecord, label: str) -> None: ...

    @staticmethod
    @overload
    def _insert_unique(store: dict[str, DiagramRecord], artifact_id: str, rec: DiagramRecord, label: str) -> None: ...

    @staticmethod
    @overload
    def _insert_unique(store: dict[str, DocumentRecord], artifact_id: str, rec: DocumentRecord, label: str) -> None: ...

    @staticmethod
    def _insert_unique(
        store: dict[str, EntityRecord] | dict[str, ConnectionRecord] | dict[str, DiagramRecord] | dict[str, DocumentRecord],
        artifact_id: str,
        rec: EntityRecord | ConnectionRecord | DiagramRecord | DocumentRecord,
        label: str,
    ) -> None:
        existing = store.get(artifact_id)
        if existing is not None:
            raise DuplicateArtifactIdError(f"Duplicate {label} artifact-id '{artifact_id}' in {rec.path} and {existing.path}")
        if isinstance(rec, EntityRecord):
            cast("dict[str, EntityRecord]", store)[artifact_id] = rec
        elif isinstance(rec, ConnectionRecord):
            cast("dict[str, ConnectionRecord]", store)[artifact_id] = rec
        elif isinstance(rec, DocumentRecord):
            cast("dict[str, DocumentRecord]", store)[artifact_id] = rec
        else:
            cast("dict[str, DiagramRecord]", store)[artifact_id] = rec

    @staticmethod
    def _scope_for_root(root: Path) -> str:
        return "enterprise" if infer_repo_scope(root) == "enterprise" else "engagement"

    def scope_for_path(self, path: Path) -> str:
        resolved = path.resolve()
        for root in self.repo_roots:
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            return self._scope_for_root(root)
        return "unknown"

    def _mount_for_path(self, path: Path) -> RepoMount | None:
        resolved = path.resolve()
        return next((mount for mount in self.repo_mounts if resolved.is_relative_to(mount.root)), None)

    def _model_root_for_path(self, path: Path) -> Path | None:
        mount = self._mount_for_path(path)
        return None if mount is None else mount.root / "model"

    def _is_diagram_source_path(self, path: Path) -> bool:
        mount = self._mount_for_path(path)
        if mount is None:
            return False
        try:
            rel = path.resolve().relative_to(mount.root.resolve()).as_posix()
        except ValueError:
            return False
        return rel.startswith("diagram-catalog/diagrams/") and path.suffix in {".md", ".puml"}

    def _is_document_path(self, path: Path) -> bool:
        mount = self._mount_for_path(path)
        if mount is None:
            return False
        try:
            rel = path.resolve().relative_to(mount.root.resolve()).as_posix()
        except ValueError:
            return False
        return rel.startswith("documents/") and path.suffix == ".md"

    def _rebuild_entity_context_projection(self) -> None:
        rebuild_entity_context_projection(self)

    def _upsert_entity_record(self, rec: EntityRecord) -> None:
        upsert_entity_record(self, rec)

    def _delete_entity_record(self, artifact_id: str) -> None:
        delete_entity_record(self, artifact_id)

    def _upsert_connection_record(self, rec: ConnectionRecord) -> None:
        upsert_connection_record(self, rec)

    def _delete_connection_record(self, artifact_id: str) -> None:
        delete_connection_record(self, artifact_id)

    def _upsert_diagram_record(self, rec: DiagramRecord) -> None:
        upsert_diagram_record(self, rec)

    def _delete_diagram_record(self, artifact_id: str) -> None:
        delete_diagram_record(self, artifact_id)

    def _upsert_document_record(self, rec: DocumentRecord) -> None:
        upsert_document_record(self, rec)

    def _delete_document_record(self, artifact_id: str) -> None:
        delete_document_record(self, artifact_id)

    def _bump_generation(self) -> None:
        self._generation += 1
        self._etag = build_read_model_etag(self._scope_key, self._generation)
        self._loaded = True

    def generation(self) -> int:
        self._ensure_loaded()
        return self._generation

    def read_model_version(self) -> ReadModelVersion:
        self._ensure_loaded()
        return ReadModelVersion(generation=self._generation, etag=self._etag)

    def apply_entity_file_change(self, path: Path) -> None:
        apply_entity_file_change(self, path)

    def apply_outgoing_file_change(self, path: Path) -> None:
        apply_outgoing_file_change(self, path)

    def apply_diagram_file_change(self, path: Path) -> None:
        apply_diagram_file_change(self, path)

    def apply_document_file_change(self, path: Path) -> None:
        apply_document_file_change(self, path)

    def apply_file_changes(self, paths: list[Path]) -> ReadModelVersion:
        self._ensure_loaded()
        normalized = sorted({path.resolve() for path in paths})
        if not normalized:
            return self.read_model_version()
        if any(path.is_dir() for path in normalized):
            self.refresh()
            return self.read_model_version()
        with self._lock:
            for path in normalized:
                if path.name.endswith(".outgoing.md"):
                    apply_outgoing_file_change(self, path, bump_generation=False)
                elif self._is_diagram_source_path(path):
                    apply_diagram_file_change(self, path, bump_generation=False)
                elif self._is_document_path(path):
                    apply_document_file_change(self, path, bump_generation=False)
                elif path.suffix == ".md":
                    apply_entity_file_change(self, path, bump_generation=False)
                else:
                    self.refresh()
                    return self.read_model_version()
            self._bump_generation()
        return self.read_model_version()

    def rebuild_entity_context_for(self, entity_id: str) -> None:
        rebuild_entity_context_for(self, entity_id)

    def read_entity_context(self, entity_id: str) -> EntityContextReadModel | None:
        return read_entity_context(self, entity_id)

    def entity_records(self) -> dict[str, EntityRecord]:
        self._ensure_loaded()
        return self._entities

    def connection_records(self) -> dict[str, ConnectionRecord]:
        self._ensure_loaded()
        return self._connections

    def diagram_records(self) -> dict[str, DiagramRecord]:
        self._ensure_loaded()
        return self._diagrams

    def document_records(self) -> dict[str, DocumentRecord]:
        self._ensure_loaded()
        return self._documents

    def get_document(self, artifact_id: str) -> DocumentRecord | None:
        self._ensure_loaded()
        return self._documents.get(artifact_id)

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        self._ensure_loaded()
        return self._entities.get(artifact_id)

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        self._ensure_loaded()
        return self._connections.get(artifact_id)

    def get_diagram(self, artifact_id: str) -> DiagramRecord | None:
        self._ensure_loaded()
        return self._diagrams.get(artifact_id)

    def find_file_by_id(self, artifact_id: str) -> Path | None:
        rec = self.get_entity(artifact_id)
        return rec.path if rec is not None else None

    def entity_ids(self) -> set[str]:
        self._ensure_loaded()
        return set(self._entities.keys())

    def connection_ids(self) -> set[str]:
        self._ensure_loaded()
        return set(self._connections.keys())

    def enterprise_entity_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._entities.items() if self.scope_for_path(rec.path) == "enterprise"}

    def engagement_entity_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._entities.items() if self.scope_for_path(rec.path) == "engagement"}

    def enterprise_connection_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._connections.items() if self.scope_for_path(rec.path) == "enterprise"}

    def engagement_connection_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._connections.items() if self.scope_for_path(rec.path) == "engagement"}

    def scope_of_entity(self, artifact_id: str) -> str:
        rec = self.get_entity(artifact_id)
        return self.scope_for_path(rec.path) if rec is not None else "unknown"

    def scope_of_connection(self, artifact_id: str) -> str:
        rec = self.get_connection(artifact_id)
        return self.scope_for_path(rec.path) if rec is not None else "unknown"

    def entity_status(self, artifact_id: str) -> str | None:
        rec = self.get_entity(artifact_id)
        return rec.status if rec is not None else None

    def entity_statuses(self) -> dict[str, str]:
        self._ensure_loaded()
        return {aid: rec.status for aid, rec in self._entities.items()}

    def connection_status(self, artifact_id: str) -> str | None:
        rec = self.get_connection(artifact_id)
        return rec.status if rec is not None else None

    def find_connection_ids_for(self, entity_id: str, *, direction: str = "any", conn_type: str | None = None) -> list[str]:
        return find_connection_ids_for(self, entity_id, direction=direction, conn_type=conn_type)

    def search_artifacts(
        self,
        query: str,
        *,
        limit: int = 10,
        include_connections: bool = True,
        include_diagrams: bool = True,
        include_documents: bool = True,
        prefer_record_type: str | None = None,
        strict_record_type: bool = False,
    ) -> list[tuple[str, str, float]]:
        return search_artifacts(
            self,
            query,
            limit=limit,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
            prefer_record_type=prefer_record_type,
            strict_record_type=strict_record_type,
        )

    def find_neighbors(self, entity_id: str, *, max_hops: int = 1, conn_type: str | None = None) -> dict[str, set[str]]:
        return find_neighbors(self, entity_id, max_hops=max_hops, conn_type=conn_type)
