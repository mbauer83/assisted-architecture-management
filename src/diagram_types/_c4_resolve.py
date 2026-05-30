"""C4 state resolution: model-backed (ArchiMate graph) and standalone (explicit entities)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class _ResolvedItem:
    local_id: str
    item_type: str
    alias: str
    label: str
    description: str
    technology: str
    external: bool
    entity_id: str | None = None  # set in standalone when item maps to a model entity


@dataclass(frozen=True)
class _C4Connection:
    src_alias: str
    tgt_alias: str
    label: str
    artifact_id: str | None = None


@dataclass(frozen=True)
class _ResolvedState:
    scope_item: _ResolvedItem
    scope_render_mode: str
    internal_items: list[_ResolvedItem]
    outside_items: list[_ResolvedItem]
    connections: tuple[_C4Connection, ...]
    entity_ids: tuple[str, ...]
    connection_artifact_ids: tuple[str, ...]


def resolve_c4_state(
    config: dict[str, Any],
    diagram_type: str,
    repo_root: Path,
    diagram_entities: Mapping[str, object],
    diagram_connections: list[dict[str, object]],
    person_archimate_types: frozenset[str],
) -> _ResolvedState:
    scope_entity_id = str(diagram_entities.get("_scope_entity_id") or "").strip()
    c4_cfg = _c4_settings(config)
    scope_entity_type = str(c4_cfg["scope_entity_type"])
    scope_render_mode = str(c4_cfg["scope_render_mode"])
    internal_types = [str(t) for t in (c4_cfg.get("internal_entity_types") or [])]
    internal_c4_type = internal_types[0] if internal_types else "container"

    if scope_entity_id:
        return _resolve_model_backed(
            diagram_type, repo_root, diagram_entities, scope_entity_id,
            scope_entity_type, scope_render_mode, internal_c4_type, person_archimate_types,
        )
    return _resolve_standalone(
        diagram_type, diagram_entities, diagram_connections,
        scope_entity_type, scope_render_mode, frozenset(internal_types),
    )


def _resolve_model_backed(
    diagram_type: str,
    repo_root: Path,
    diagram_entities: Mapping[str, object],
    scope_entity_id: str,
    scope_entity_type: str,
    scope_render_mode: str,
    internal_c4_type: str,
    person_archimate_types: frozenset[str],
) -> _ResolvedState:
    repo = _repo(repo_root)
    scope_entity = repo.get_entity(scope_entity_id)
    if scope_entity is None:
        raise ValueError(f"{diagram_type!r}: scope entity {scope_entity_id!r} not found")

    all_conns = list(repo.list_connections())

    internal_ids = frozenset(
        c.target for c in all_conns
        if c.source == scope_entity_id and c.conn_type == "c4-contains"
    )

    candidate_ids: set[str] = set()
    for c in all_conns:
        if c.conn_type == "c4-contains":
            continue
        if c.source == scope_entity_id or c.source in internal_ids:
            candidate_ids.add(c.target)
        if c.target == scope_entity_id or c.target in internal_ids:
            candidate_ids.add(c.source)
    candidate_ids.discard(scope_entity_id)
    candidate_ids -= internal_ids

    raw_included = diagram_entities.get("_included_entity_ids")
    raw_excluded = diagram_entities.get("_excluded_entity_ids")
    if isinstance(raw_included, list) and raw_included:
        candidate_ids &= set(str(x) for x in raw_included)
    elif isinstance(raw_excluded, list) and raw_excluded:
        candidate_ids -= set(str(x) for x in raw_excluded)

    entity_cache: dict[str, Any] = {}

    def _get(eid: str) -> Any:
        if eid not in entity_cache:
            entity_cache[eid] = repo.get_entity(eid)
        return entity_cache[eid]

    scope_item = _item_from_entity(_get(scope_entity_id), scope_entity_id, scope_entity_type, external=False)
    internal_items = [
        _item_from_entity(_get(eid), eid, internal_c4_type, external=False)
        for eid in sorted(internal_ids)
        if _get(eid) is not None
    ]
    outside_items = [
        _item_from_entity(
            _get(eid), eid,
            "person" if (_get(eid) is not None and _get(eid).artifact_type in person_archimate_types)
            else "software-system",
            external=True,
        )
        for eid in sorted(candidate_ids)
        if _get(eid) is not None
    ]

    all_displayed = {scope_entity_id} | internal_ids | candidate_ids
    alias_by_eid = {i.local_id: i.alias for i in [scope_item] + internal_items + outside_items}

    model_conns = [
        c for c in all_conns
        if c.conn_type != "c4-contains"
        and c.source in all_displayed and c.target in all_displayed
        and c.source in alias_by_eid and c.target in alias_by_eid
    ]
    connections = tuple(
        _C4Connection(
            src_alias=alias_by_eid[c.source],
            tgt_alias=alias_by_eid[c.target],
            label=_conn_label(c),
            artifact_id=c.artifact_id,
        )
        for c in sorted(model_conns, key=lambda x: x.artifact_id)
    )

    return _ResolvedState(
        scope_item=scope_item,
        scope_render_mode=scope_render_mode,
        internal_items=internal_items,
        outside_items=outside_items,
        connections=connections,
        entity_ids=tuple(sorted(all_displayed)),
        connection_artifact_ids=tuple(c.artifact_id for c in model_conns),
    )


def _resolve_standalone(
    diagram_type: str,
    diagram_entities: Mapping[str, object],
    diagram_connections: list[dict[str, object]],
    scope_entity_type: str,
    scope_render_mode: str,
    internal_types: frozenset[str],
) -> _ResolvedState:
    items = _items_from_diagram_entities(diagram_entities)

    if not items:
        placeholder = _ResolvedItem(
            local_id="_blank", item_type=scope_entity_type,
            alias="C4_blank", label="(add entities to get started)",
            description="", technology="", external=False,
        )
        return _ResolvedState(
            scope_item=placeholder, scope_render_mode=scope_render_mode,
            internal_items=[], outside_items=[], connections=(),
            entity_ids=(), connection_artifact_ids=(),
        )

    scope_items_of_type = [i for i in items if i.item_type == scope_entity_type]
    if not scope_items_of_type:
        raise ValueError(f"{diagram_type!r} (standalone): needs at least one '{scope_entity_type}' item")

    # Prefer item marked with scope=true in the raw data; fall back to first
    raw_scope_marked = _scope_marked_id(diagram_entities, scope_entity_type)
    scope_item = next(
        (i for i in scope_items_of_type if i.local_id == raw_scope_marked),
        scope_items_of_type[0],
    )

    internal_items = [
        i for i in items
        if i.local_id != scope_item.local_id and not i.external and i.item_type in internal_types
    ]
    outside_items = [
        i for i in items
        if i.local_id != scope_item.local_id and i not in internal_items
    ]

    alias_by_lid = {i.local_id: i.alias for i in items}
    connections = tuple(
        _C4Connection(
            src_alias=alias_by_lid[str(dc.get("source") or "")],
            tgt_alias=alias_by_lid[str(dc.get("target") or "")],
            label=str(dc.get("label") or ""),
        )
        for dc in diagram_connections
        if isinstance(dc, dict)
        and str(dc.get("source") or "") in alias_by_lid
        and str(dc.get("target") or "") in alias_by_lid
    )

    return _ResolvedState(
        scope_item=scope_item,
        scope_render_mode=scope_render_mode,
        internal_items=internal_items,
        outside_items=outside_items,
        connections=connections,
        entity_ids=(),
        connection_artifact_ids=(),
    )


def _item_from_entity(entity: Any, entity_id: str, item_type: str, *, external: bool) -> _ResolvedItem:
    label = entity.name if entity is not None else entity_id
    raw_alias = getattr(entity, "display_alias", "") or "" if entity is not None else ""
    alias = _normalize_alias(raw_alias) if raw_alias else _alias_for(item_type, entity_id)
    return _ResolvedItem(
        local_id=entity_id,
        item_type=item_type,
        alias=alias,
        label=label,
        description="",
        technology="",
        external=external,
    )


def _items_from_diagram_entities(diagram_entities: Mapping[str, object]) -> list[_ResolvedItem]:
    items: list[_ResolvedItem] = []
    for item_type, raw_list in diagram_entities.items():
        if not isinstance(raw_list, list):
            continue
        for index, raw in enumerate(raw_list):
            if not isinstance(raw, Mapping):
                continue
            local_id = str(raw.get("id") or "").strip()
            if not local_id:
                continue
            entity_id = str(raw.get("entity_id") or "").strip() or None
            label = str(raw.get("label") or local_id)
            alias = _normalize_alias(str(raw.get("alias") or "")) or _alias_for(item_type, local_id, index)
            items.append(_ResolvedItem(
                local_id=local_id,
                item_type=str(item_type),
                alias=alias,
                label=label,
                description=str(raw.get("description") or ""),
                technology=str(raw.get("technology") or ""),
                external=bool(raw.get("external", False)),
                entity_id=entity_id,
            ))
    return items


def _scope_marked_id(diagram_entities: Mapping[str, object], scope_entity_type: str) -> str | None:
    raw_list: object = diagram_entities.get(scope_entity_type)
    if not isinstance(raw_list, list):
        return None
    for raw in raw_list:
        if isinstance(raw, Mapping) and raw.get("scope") and raw.get("id"):
            return str(raw["id"])
    return None


def _conn_label(conn: Any) -> str:
    from src.domain.archimate_relation_rendering import display_connection_label  # noqa: PLC0415
    description = " ".join((conn.content_text or "").split())
    if description:
        return description
    return f"<<{display_connection_label(conn.conn_type)}>>"


def _alias_for(item_type: str, local_id: str, index: int = 0) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", local_id)
    prefix = "".join(p[:1].upper() for p in item_type.replace("-", "_").split("_")) or "C"
    return f"{prefix}_{normalized}_{index}"


def _normalize_alias(alias: str) -> str:
    return alias.strip().replace("-", "_")


def _c4_settings(config: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = config.get("c4")
    if not isinstance(raw, Mapping):
        raise ValueError("C4 config must define a 'c4' mapping")
    if not raw.get("scope_entity_type"):
        raise ValueError("C4 config must define c4.scope_entity_type")
    if not raw.get("scope_render_mode"):
        raise ValueError("C4 config must define c4.scope_render_mode")
    return raw


def _repo(repo_root: Path) -> Any:
    from src.application.artifact_repository import ArtifactRepository  # noqa: PLC0415
    from src.infrastructure.artifact_index import shared_artifact_index  # noqa: PLC0415
    return ArtifactRepository(shared_artifact_index([repo_root]))
