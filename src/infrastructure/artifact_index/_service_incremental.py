"""Scanning and incremental file-change handlers for ArtifactIndex."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from src.application.artifact_parsing import (
    parse_diagram,
    parse_document,
    parse_entity,
    parse_outgoing_file,
)
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, DOCS, MODEL, RENDERED
from src.domain.artifact_types import (
    ConnectionRecord,
    DiagramRecord,
    DocumentRecord,
    DuplicateArtifactIdError,
    EntityRecord,
    RepoMount,
)

from ._mem_store import _MemStore
from ._sqlite_store import _SqliteStore

_ArtT = TypeVar("_ArtT", EntityRecord, ConnectionRecord, DiagramRecord, DocumentRecord)


# ── Path classification helpers ───────────────────────────────────────────────


def mount_for_path(path: Path, mounts: list[RepoMount]) -> RepoMount | None:
    resolved = path.resolve()
    return next((m for m in mounts if resolved.is_relative_to(m.root)), None)


def model_root_for_path(path: Path, mounts: list[RepoMount]) -> Path | None:
    mount = mount_for_path(path, mounts)
    return None if mount is None else mount.root / MODEL


def is_diagram_source_path(path: Path, mounts: list[RepoMount]) -> bool:
    mount = mount_for_path(path, mounts)
    if mount is None:
        return False
    try:
        rel = path.resolve().relative_to(mount.root.resolve()).as_posix()
    except ValueError:
        return False
    return rel.startswith("diagram-catalog/diagrams/") and path.suffix in {".md", ".puml"}


def is_document_path(path: Path, mounts: list[RepoMount]) -> bool:
    mount = mount_for_path(path, mounts)
    if mount is None:
        return False
    try:
        rel = path.resolve().relative_to(mount.root.resolve()).as_posix()
    except ValueError:
        return False
    return rel.startswith(f"{DOCS}/") and path.suffix == ".md"


# ── Full scan ─────────────────────────────────────────────────────────────────


def _insert_mounted(
    rec: _ArtT,
    label: str,
    mount_root: Path,
    store: dict[str, _ArtT],
) -> None:
    existing = store.get(rec.artifact_id)
    if existing is None:
        store[rec.artifact_id] = rec
        return
    try:
        existing.path.resolve().relative_to(mount_root.resolve())
    except ValueError:
        return
    raise DuplicateArtifactIdError(
        f"Duplicate {label} artifact-id '{rec.artifact_id}' in {rec.path} and {existing.path}"
    )


def scan_mount(mount: RepoMount, mem: _MemStore) -> None:
    model_root = mount.root / MODEL
    if model_root.exists():
        for path in sorted(model_root.rglob("*.md")):
            if not path.name.endswith(".outgoing.md"):
                entity = parse_entity(path, model_root)
                if entity is not None:
                    _insert_mounted(entity, "entity", mount.root, mem.entities)
        for path in sorted(model_root.rglob("*.outgoing.md")):
            for conn in parse_outgoing_file(path):
                _insert_mounted(conn, "connection", mount.root, mem.connections)
    diagrams_root = mount.root / DIAGRAM_CATALOG / DIAGRAMS
    if diagrams_root.exists():
        for suffix in ("*.puml", "*.md"):
            for path in sorted(diagrams_root.rglob(suffix)):
                if path.parent.name != RENDERED:
                    diag = parse_diagram(path)
                    if diag is not None:
                        _insert_mounted(diag, "diagram", mount.root, mem.diagrams)
    docs_root = mount.root / DOCS
    if docs_root.exists():
        for path in sorted(docs_root.rglob("*.md")):
            doc = parse_document(path)
            if doc is not None:
                _insert_mounted(doc, "document", mount.root, mem.documents)


# ── Incremental updates ───────────────────────────────────────────────────────


def apply_entity_change(
    path: Path,
    mem: _MemStore,
    db: _SqliteStore,
    mounts: list[RepoMount],
) -> None:
    old_id = mem.entity_by_path.get(path.resolve())
    old = mem.entities.get(old_id) if old_id else None
    model_root = model_root_for_path(path, mounts)
    new = parse_entity(path, model_root) if path.exists() and model_root else None

    impacted: set[str] = set()
    if old is not None:
        impacted.add(old.artifact_id)
        impacted.update(
            r.source if r.source != old.artifact_id else r.target
            for r in mem.connections.values()
            if old.artifact_id in (r.source, r.target)
        )
        if new is None or old.artifact_id != new.artifact_id:
            db.delete_entity(old.artifact_id)
    if new is not None:
        db.upsert_entity(new)
        impacted.add(new.artifact_id)
        impacted.update(
            r.source if r.source != new.artifact_id else r.target
            for r in mem.connections.values()
            if new.artifact_id in (r.source, r.target)
        )
    for eid in sorted(impacted):
        db.rebuild_context_for(eid)


def apply_outgoing_change(path: Path, mem: _MemStore, db: _SqliteStore) -> None:
    old_ids = mem.connections_by_path.get(path.resolve(), set())
    old_recs = [mem.connections[cid] for cid in old_ids if cid in mem.connections]
    new_recs = parse_outgoing_file(path) if path.exists() else []

    affected = {eid for r in old_recs + new_recs for eid in (r.source, r.target)}
    removed = {r.artifact_id for r in old_recs} - {r.artifact_id for r in new_recs}
    for aid in sorted(removed):
        db.delete_connection(aid)
    for rec in new_recs:
        db.upsert_connection(rec)
    for eid in sorted(affected):
        db.rebuild_context_for(eid)


def apply_diagram_change(path: Path, mem: _MemStore, db: _SqliteStore) -> None:
    old_id = mem.diagram_by_path.get(path.resolve())
    old = mem.diagrams.get(old_id) if old_id else None
    new = parse_diagram(path) if path.exists() else None
    if old is not None and (new is None or old.artifact_id != new.artifact_id):
        db.delete_diagram(old.artifact_id)
    if new is not None:
        db.upsert_diagram(new)


def apply_document_change(path: Path, mem: _MemStore, db: _SqliteStore) -> None:
    old_id = mem.document_by_path.get(path.resolve())
    old = mem.documents.get(old_id) if old_id else None
    new = parse_document(path) if path.exists() else None
    if old is not None and (new is None or old.artifact_id != new.artifact_id):
        db.delete_document(old.artifact_id)
    if new is not None:
        db.upsert_document(new)
