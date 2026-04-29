"""Diagram-to-model sync: reconcile a diagram against the current model state."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from src.application.artifact_parsing import extract_declared_puml_aliases, normalize_puml_alias
from src.application.modeling.artifact_write import ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE
from src.application.verification.artifact_verifier import ArtifactVerifier
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS
from src.domain.artifact_types import ConnectionRecord, EntityRecord

from .boundary import assert_engagement_write_root
from .coerce import as_optional_str_list
from .diagram_delete import delete_diagram
from .diagram_edit import edit_diagram
from .parse_existing import parse_diagram_file
from .types import SyncDiagramToModelResult


class _LookupStore(Protocol):
    def get_entity(self, artifact_id: str) -> EntityRecord | None: ...
    def get_connection(self, artifact_id: str) -> ConnectionRecord | None: ...
    def list_entities(
        self,
        *,
        artifact_type: str | None = None,
        domain: str | None = None,
        subdomain: str | None = None,
        status: str | None = None,
    ) -> list[EntityRecord]: ...
    def list_connections(
        self,
        *,
        conn_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
    ) -> list[ConnectionRecord]: ...


_REL_MACRO_RE = re.compile(
    r"^\s*Rel_(?P<rel>[A-Za-z0-9]+)(?:_(?:Up|Down|Left|Right))?"
    r"\(\s*(?P<src>[A-Za-z0-9_-]+)\s*,\s*(?P<tgt>[A-Za-z0-9_-]+)",
    re.MULTILINE,
)
_REL_LINE_RE = re.compile(
    r"^\s*(?P<src>[A-Za-z0-9_-]+)\s+[-.*|o<>][^\n:]*\s+(?P<tgt>[A-Za-z0-9_-]+)\s*:\s*<<(?P<rel>[A-Za-z]+)>>",
    re.MULTILINE,
)
_STD_ALIAS_RE = re.compile(r"^(?P<prefix>[A-Z]{2,6})_(?P<random>[A-Za-z0-9_-]{4,})$")


def _stable_prefix(artifact_id: str) -> str:
    """Return the rename-stable part of an artifact ID (drops the trailing slug)."""
    return artifact_id.rsplit(".", 1)[0]


def _resolve_entities(
    ids: list[str],
    store: _LookupStore,
) -> tuple[list[EntityRecord], list[str]]:
    """Resolve entity IDs to records, following renames via stable-prefix fallback.

    Returns (resolved_records, removed_ids) where removed_ids are IDs for which
    no entity could be found even after rename detection.
    """
    by_prefix: dict[str, EntityRecord] = {_stable_prefix(e.artifact_id): e for e in store.list_entities()}
    records: list[EntityRecord] = []
    removed: list[str] = []
    for eid in ids:
        record = store.get_entity(eid)
        if record is None:
            record = by_prefix.get(_stable_prefix(eid))
        if record is not None:
            records.append(record)
        else:
            removed.append(eid)
    return records, removed


def _resolve_connections(
    ids: list[str],
    store: _LookupStore,
) -> tuple[list[ConnectionRecord], list[str]]:
    """Resolve connection IDs to records, following renames via stable-prefix fallback."""
    connections = store.list_connections()
    by_prefix: dict[str, ConnectionRecord] = {_stable_prefix(c.artifact_id): c for c in connections}
    records: list[ConnectionRecord] = []
    removed: list[str] = []
    for cid in ids:
        record = store.get_connection(cid)
        if record is None:
            record = by_prefix.get(_stable_prefix(cid))
        if record is None:
            record = _resolve_connection_by_parts(cid, connections)
        if record is not None:
            records.append(record)
        else:
            removed.append(cid)
    return records, removed


def _parse_connection_artifact_id(artifact_id: str) -> tuple[str, str, str] | None:
    if "---" in artifact_id and "@@" in artifact_id:
        try:
            source, remainder = artifact_id.split("---", 1)
            target, conn_type = remainder.rsplit("@@", 1)
        except ValueError:
            return None
        return source, target, conn_type
    if " → " in artifact_id:
        try:
            left, target = artifact_id.split(" → ", 1)
            source, conn_type = left.split(" ", 1)
        except ValueError:
            return None
        return source, target, conn_type
    return None


def _resolve_connection_by_parts(
    artifact_id: str,
    connections: list[ConnectionRecord],
) -> ConnectionRecord | None:
    parsed = _parse_connection_artifact_id(artifact_id)
    if parsed is None:
        return None
    source, target, conn_type = parsed
    source_prefix = _stable_prefix(source)
    target_prefix = _stable_prefix(target)
    for record in connections:
        if record.conn_type != conn_type:
            continue
        if _stable_prefix(record.source) == source_prefix and _stable_prefix(record.target) == target_prefix:
            return record
    return None


def _normalize_standard_alias(artifact_id: str) -> str:
    parts = artifact_id.split(".")
    if len(parts) < 2 or "@" not in parts[0]:
        return ""
    prefix = parts[0].split("@", 1)[0]
    return f"{prefix}_{parts[1]}"


def _resolve_standard_alias(alias: str, entities: list[EntityRecord]) -> EntityRecord | None:
    match = _STD_ALIAS_RE.match(alias)
    if match is None:
        return None
    prefix = match.group("prefix")
    random = match.group("random")
    needle = f".{random}."
    for entity in entities:
        if entity.artifact_id.startswith(f"{prefix}@") and needle in entity.artifact_id:
            return entity
    return None


def _alias_entity_lookup(store: _LookupStore) -> dict[str, EntityRecord]:
    alias_map: dict[str, EntityRecord] = {}
    entities = store.list_entities()
    for entity in entities:
        if entity.display_alias:
            alias_map.setdefault(normalize_puml_alias(entity.display_alias), entity)
        std_alias = _normalize_standard_alias(entity.artifact_id)
        if std_alias:
            alias_map.setdefault(normalize_puml_alias(std_alias), entity)
    return alias_map


def _infer_entities_from_puml(
    puml_body: str,
    store: _LookupStore,
) -> tuple[list[EntityRecord], list[str]]:
    alias_map = _alias_entity_lookup(store)
    inferred: list[EntityRecord] = []
    unresolved_aliases: list[str] = []
    seen: set[str] = set()
    for alias in sorted(extract_declared_puml_aliases(puml_body)):
        normalized = normalize_puml_alias(alias)
        record = alias_map.get(normalized)
        if record is None:
            record = _resolve_standard_alias(normalized, store.list_entities())
        if record is None:
            unresolved_aliases.append(alias)
            continue
        if record.artifact_id in seen:
            continue
        seen.add(record.artifact_id)
        inferred.append(record)
    return inferred, unresolved_aliases


def _iter_declared_relations(content: str) -> list[tuple[str, str, str]]:
    relations: list[tuple[str, str, str]] = []
    for match in _REL_MACRO_RE.finditer(content):
        conn_type = ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.get(match.group("rel").lower())
        if conn_type is None:
            continue
        relations.append((match.group("src"), match.group("tgt"), conn_type))
    for match in _REL_LINE_RE.finditer(content):
        conn_type = ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE.get(match.group("rel").lower())
        if conn_type is None:
            continue
        relations.append((match.group("src"), match.group("tgt"), conn_type))
    return relations


def _resolve_relation_connection(
    src_id: str,
    tgt_id: str,
    conn_type: str,
    connections: list[ConnectionRecord],
) -> ConnectionRecord | None:
    direct = _resolve_connection_by_parts(f"{src_id}---{tgt_id}@@{conn_type}", connections)
    if direct is not None:
        return direct
    if conn_type == "archimate-realization":
        return _resolve_connection_by_parts(f"{tgt_id}---{src_id}@@{conn_type}", connections)
    return None


def _infer_connections_from_puml(
    puml_body: str,
    store: _LookupStore,
) -> tuple[list[ConnectionRecord], list[str]]:
    alias_map = _alias_entity_lookup(store)
    all_connections = store.list_connections()
    inferred: list[ConnectionRecord] = []
    removed: list[str] = []
    seen: set[str] = set()

    for src_alias, tgt_alias, conn_type in _iter_declared_relations(puml_body):
        src = alias_map.get(normalize_puml_alias(src_alias))
        tgt = alias_map.get(normalize_puml_alias(tgt_alias))
        if src is None or tgt is None:
            continue
        record = _resolve_relation_connection(src.artifact_id, tgt.artifact_id, conn_type, all_connections)
        if record is None:
            removed.append(f"{src.artifact_id}---{tgt.artifact_id}@@{conn_type}")
            continue
        if record.artifact_id in seen:
            continue
        seen.add(record.artifact_id)
        inferred.append(record)
    return inferred, removed


def _dedupe_entities(records: list[EntityRecord]) -> list[EntityRecord]:
    out: list[EntityRecord] = []
    seen: set[str] = set()
    for record in records:
        if record.artifact_id in seen:
            continue
        seen.add(record.artifact_id)
        out.append(record)
    return out


def _dedupe_connections(records: list[ConnectionRecord]) -> list[ConnectionRecord]:
    out: list[ConnectionRecord] = []
    seen: set[str] = set()
    for record in records:
        if record.artifact_id in seen:
            continue
        seen.add(record.artifact_id)
        out.append(record)
    return out


def sync_diagram_to_model(
    *,
    repo_root: Path,
    store: _LookupStore,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> SyncDiagramToModelResult:
    """Reconcile a diagram against the current model state.

    Reads ``entity-ids-used`` and ``connection-ids-used`` from the diagram's
    frontmatter, looks up each ID in the store, and drops any that no longer
    exist. Renamed entities are detected by matching the stable prefix
    (``TYPE@timestamp.random``) so a name change updates the reference rather
    than removing the entity. Surviving records are passed to
    ``generate_archimate_puml_body`` so names are always current.
    """
    from src.infrastructure.rendering.diagram_builder import generate_archimate_puml_body

    assert_engagement_write_root(repo_root)

    diagram_path = repo_root / DIAGRAM_CATALOG / DIAGRAMS / f"{artifact_id}.puml"
    if not diagram_path.exists():
        raise ValueError(f"Diagram '{artifact_id}' not found at {diagram_path}")

    parsed = parse_diagram_file(diagram_path)
    fm = parsed.frontmatter

    existing_entity_ids: list[str] = as_optional_str_list(fm.get("entity-ids-used")) or []
    existing_conn_ids: list[str] = as_optional_str_list(fm.get("connection-ids-used")) or []
    diagram_type = str(fm.get("diagram-type", "archimate"))
    name = str(fm.get("name", ""))

    fm_entity_records, removed_entity_ids = _resolve_entities(existing_entity_ids, store)
    fm_conn_records, removed_conn_ids = _resolve_connections(existing_conn_ids, store)
    puml_entity_records, _unresolved_aliases = _infer_entities_from_puml(parsed.puml_body, store)
    puml_conn_records, inferred_removed_conn_ids = _infer_connections_from_puml(parsed.puml_body, store)

    entity_records = _dedupe_entities([*puml_entity_records, *fm_entity_records])
    conn_records = _dedupe_connections([*puml_conn_records, *fm_conn_records])
    removed_conn_ids = list(dict.fromkeys([*removed_conn_ids, *inferred_removed_conn_ids]))

    if not entity_records:
        write_result = delete_diagram(
            repo_root=repo_root,
            clear_repo_caches=clear_repo_caches,
            artifact_id=artifact_id,
            dry_run=dry_run,
        )
        return SyncDiagramToModelResult(
            wrote=write_result.wrote,
            path=write_result.path,
            artifact_id=write_result.artifact_id,
            content=write_result.content,
            warnings=write_result.warnings,
            verification=write_result.verification,
            removed_entity_ids=removed_entity_ids,
            removed_connection_ids=removed_conn_ids,
            deleted_diagram=True,
        )

    puml = generate_archimate_puml_body(name, entity_records, conn_records, diagram_type=diagram_type)

    write_result = edit_diagram(
        repo_root=repo_root,
        verifier=verifier,
        clear_repo_caches=clear_repo_caches,
        artifact_id=artifact_id,
        puml=puml,
        entity_ids_used=[e.artifact_id for e in entity_records],
        connection_ids_used=[c.artifact_id for c in conn_records],
        dry_run=dry_run,
    )

    return SyncDiagramToModelResult(
        wrote=write_result.wrote,
        path=write_result.path,
        artifact_id=write_result.artifact_id,
        content=write_result.content,
        warnings=write_result.warnings,
        verification=write_result.verification,
        removed_entity_ids=removed_entity_ids,
        removed_connection_ids=removed_conn_ids,
        deleted_diagram=False,
    )
