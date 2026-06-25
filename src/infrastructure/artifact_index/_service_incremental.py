"""Scanning and incremental file-change handlers for ArtifactIndex."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import TypeVar

from src.application._diagram_entity_extraction import (
    extract_diagram_connections as _extract_diagram_connections,
)
from src.application._diagram_entity_extraction import (
    extract_diagram_entities as _extract_diagram_entities,
)
from src.application.artifact_parsing import (
    parse_diagram,
    parse_document,
    parse_entity,
    parse_outgoing_file,
)
from src.application.ports import Candidate
from src.application.repo_path_helpers import (
    all_model_roots,
    diagram_source_root,
    docs_root,
    group_fn_diagram,
    group_fn_document,
    group_fn_entity,
)
from src.config.repo_paths import DOCS, MODEL, RENDERED
from src.domain.artifact_id import stable_id
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
    """Return the nearest model root for path (supports both legacy and target layouts)."""
    mount = mount_for_path(path, mounts)
    if mount is None:
        return None
    # Check target layout first: projects/<slug>/model/
    for mroot in all_model_roots(mount.root):
        try:
            path.resolve().relative_to(mroot.resolve())
            return mroot
        except ValueError:
            continue
    # Fallback to legacy root
    return mount.root / MODEL


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
    *,
    candidates_map: dict[str, list[Candidate]] | None = None,
    scope: str | None = None,
) -> None:
    if candidates_map is not None and scope is not None:
        key = stable_id(rec.artifact_id)
        candidates_map.setdefault(key, []).append(
            Candidate(artifact_id=rec.artifact_id, path=rec.path, scope=scope)  # type: ignore[arg-type]
        )
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


def _scan_model_records(mount: RepoMount, mem: _MemStore, *, domain_names: frozenset[str]) -> None:
    """Index entities and outgoing connections across every model root of a repo."""
    for model_root in all_model_roots(mount.root):
        for path in sorted(model_root.rglob("*.md")):
            if path.name.endswith(".outgoing.md"):
                continue
            entity = parse_entity(path, model_root, domain_names=domain_names)
            if entity is not None:
                grp = group_fn_entity(path, mount.root)
                _insert_mounted(
                    replace(entity, group=grp), "entity", mount.root, mem.entities,
                    candidates_map=mem.identity_candidates, scope=mount.scope,
                )
        for path in sorted(model_root.rglob("*.outgoing.md")):
            grp = group_fn_entity(path, mount.root)
            for conn in parse_outgoing_file(path):
                _insert_mounted(
                    replace(conn, group=grp), "connection", mount.root, mem.connections,
                    candidates_map=mem.identity_candidates, scope=mount.scope,
                )


def _iter_diagram_sources(diag_root: Path) -> Iterator[Path]:
    """Diagram .puml/.md sources under *diag_root*, excluding the rendered output tree."""
    rendered = (diag_root.parent / RENDERED).resolve()
    for suffix in ("*.puml", "*.md"):
        for path in sorted(diag_root.rglob(suffix)):
            if not path.resolve().is_relative_to(rendered):
                yield path


_AttrTypeRefFn = Callable[["DiagramRecord"], list[tuple[str, str, str]]]


def _scan_diagram_records(
    repo_root: Path,
    mem: _MemStore,
    *,
    workspace_types: dict[str, frozenset[str]] | None = None,
    attr_type_ref_fn: _AttrTypeRefFn | None = None,
) -> None:
    """Index diagrams and the entities/connections they materialise."""
    diag_root = diagram_source_root(repo_root)
    if not diag_root.exists():
        return
    for path in _iter_diagram_sources(diag_root):
        diag = parse_diagram(path)
        if diag is None:
            continue
        diag = replace(diag, group=group_fn_diagram(path, repo_root))
        _insert_mounted(diag, "diagram", repo_root, mem.diagrams)
        ws = (workspace_types or {}).get(diag.diagram_type, frozenset())
        mem.entities.update({de.artifact_id: de for de in _extract_diagram_entities(diag, ws)})
        mem.connections.update({dc.artifact_id: dc for dc in _extract_diagram_connections(diag, ws)})
        if attr_type_ref_fn is not None:
            mem.attribute_type_refs[diag.artifact_id] = attr_type_ref_fn(diag)


def _scan_document_records(repo_root: Path, mem: _MemStore) -> None:
    doc_root = docs_root(repo_root)
    if not doc_root.exists():
        return
    for path in sorted(doc_root.rglob("*.md")):
        doc = parse_document(path)
        if doc is not None:
            grp = group_fn_document(path, repo_root)
            _insert_mounted(replace(doc, group=grp), "document", repo_root, mem.documents)


def scan_mount(
    mount: RepoMount,
    mem: _MemStore,
    *,
    domain_names: frozenset[str],
    workspace_types: dict[str, frozenset[str]] | None = None,
    attr_type_ref_fn: _AttrTypeRefFn | None = None,
) -> None:
    _scan_model_records(mount, mem, domain_names=domain_names)
    _scan_diagram_records(mount.root, mem, workspace_types=workspace_types, attr_type_ref_fn=attr_type_ref_fn)
    _scan_document_records(mount.root, mem)


# ── Incremental updates ───────────────────────────────────────────────────────

# Each change type has two phases:
#   parse_*  — reads the file from disk; call OUTSIDE the index write lock
#   apply_*  — updates mem and SQLite; call UNDER the index write lock


def parse_entity_for_path(
    path: Path, mounts: list[RepoMount], *, domain_names: frozenset[str]
) -> EntityRecord | None:
    model_root = model_root_for_path(path, mounts)
    return (
        parse_entity(path, model_root, domain_names=domain_names) if path.exists() and model_root else None
    )


def classify_path_change(
    path: Path, mounts: list[RepoMount], *, domain_names: frozenset[str]
) -> tuple[str, Path, object] | None:
    """Return a (kind, path, parsed-data) triple or None if the path needs a full refresh."""
    if path.name.endswith(".outgoing.md"):
        return ("outgoing", path, parse_outgoing_for_path(path))
    if is_diagram_source_path(path, mounts):
        return ("diagram", path, parse_diagram_for_path(path))
    if is_document_path(path, mounts):
        return ("document", path, parse_document_for_path(path))
    if path.suffix == ".md":
        return ("entity", path, parse_entity_for_path(path, mounts, domain_names=domain_names))
    return None


def _touching_endpoints(entity_id: str, mem: _MemStore) -> set[str]:
    """*entity_id* plus the far endpoint of every connection touching it."""
    endpoints = {entity_id}
    for cid in mem.connections_by_entity.get(entity_id, set()):
        r = mem.connections.get(cid)
        if r is not None:
            endpoints.add(r.source if r.source != entity_id else r.target)
    return endpoints


def _apply_entity_record(path: Path, new: EntityRecord | None, mem: _MemStore, db: _SqliteStore) -> None:
    old_id = mem.entity_by_path.get(path.resolve())
    old = mem.entities.get(old_id) if old_id else None

    impacted: set[str] = set()
    if old is not None:
        impacted |= _touching_endpoints(old.artifact_id, mem)
        if new is None or old.artifact_id != new.artifact_id:
            db.delete_entity(old.artifact_id)
    if new is not None:
        db.upsert_entity(new)
        impacted |= _touching_endpoints(new.artifact_id, mem)
    for eid in sorted(impacted):
        db.rebuild_context_for(eid)


def parse_outgoing_for_path(path: Path) -> list[ConnectionRecord]:
    return parse_outgoing_file(path) if path.exists() else []


def _apply_outgoing_records(path: Path, new_recs: list[ConnectionRecord], mem: _MemStore, db: _SqliteStore) -> None:
    old_ids = mem.connections_by_path.get(path.resolve(), set())
    old_recs = [mem.connections[cid] for cid in old_ids if cid in mem.connections]

    affected = {eid for r in old_recs + new_recs for eid in (r.source, r.target)}
    removed = {r.artifact_id for r in old_recs} - {r.artifact_id for r in new_recs}
    for aid in sorted(removed):
        db.delete_connection(aid)
    for rec in new_recs:
        db.upsert_connection(rec)
    for eid in sorted(affected):
        db.rebuild_context_for(eid)


def parse_diagram_for_path(path: Path) -> DiagramRecord | None:
    return parse_diagram(path) if path.exists() else None


def apply_diagram_change(
    path: Path,
    mem: _MemStore,
    db: _SqliteStore,
    *,
    parsed: DiagramRecord | None,
    workspace_types: dict[str, frozenset[str]] | None = None,
    attr_type_ref_fn: _AttrTypeRefFn | None = None,
) -> None:
    old_id = mem.diagram_by_path.get(path.resolve())
    old = mem.diagrams.get(old_id) if old_id else None
    if old is not None:
        _delete_diagram_entities(old.artifact_id, mem, db)
        _delete_diagram_connections(old.artifact_id, mem, db)
        db.delete_attribute_type_refs(old.artifact_id)
        if parsed is None or old.artifact_id != parsed.artifact_id:
            db.delete_diagram(old.artifact_id)
    if parsed is not None:
        ws = (workspace_types or {}).get(parsed.diagram_type, frozenset())
        # Upsert diagram-local entities first so the diagram's FTS row (built in
        # upsert_diagram) can resolve their names via entities_by_diagram.
        for de in _extract_diagram_entities(parsed, ws):
            db.upsert_entity(de)
        for dc in _extract_diagram_connections(parsed, ws):
            db.upsert_connection(dc)
        db.upsert_diagram(parsed)
        refs = attr_type_ref_fn(parsed) if attr_type_ref_fn is not None else []
        db.upsert_attribute_type_refs(parsed.artifact_id, refs)


def _delete_diagram_entities(diagram_id: str, mem: _MemStore, db: _SqliteStore) -> None:
    owned = list(mem.entities_by_diagram.get(diagram_id, set()))
    for aid in owned:
        db.delete_entity(aid)


def _delete_diagram_connections(diagram_id: str, mem: _MemStore, db: _SqliteStore) -> None:
    owned = list(mem.connections_by_diagram.get(diagram_id, set()))
    for aid in owned:
        db.delete_connection(aid)



def parse_document_for_path(path: Path) -> DocumentRecord | None:
    return parse_document(path) if path.exists() else None


def apply_document_change(
    path: Path,
    mem: _MemStore,
    db: _SqliteStore,
    *,
    parsed: DocumentRecord | None,
) -> None:
    old_id = mem.document_by_path.get(path.resolve())
    old = mem.documents.get(old_id) if old_id else None
    if old is not None and (parsed is None or old.artifact_id != parsed.artifact_id):
        db.delete_document(old.artifact_id)
    if parsed is not None:
        db.upsert_document(parsed)
