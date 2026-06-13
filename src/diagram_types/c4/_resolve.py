"""C4 state resolution: model-backed (ArchiMate graph) and standalone (explicit entities)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Short, direction-consistent C4 edge labels per ArchiMate interaction type.
# Projected (model-backed) C4 edges always use these verbs rather than the model
# connection's prose description: C4 labels are short, and a directional sentence
# would contradict an arrow the projector may have reversed/re-oriented. The rich
# description stays on the model connection for documentation. (Standalone diagrams
# still honour an explicit per-edge label.) Never emits structural names like
# "aggregation".
_C4_CONN_LABELS: dict[str, str] = {
    "archimate-serving": "uses",
    "archimate-flow": "flows to",
    "archimate-triggering": "triggers",
    "archimate-access": "accesses",
    "archimate-association": "uses",
}


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
    from src.diagram_types.c4._projection import project_c4  # noqa: PLC0415
    from src.infrastructure.artifact_index import shared_artifact_index  # noqa: PLC0415

    query = shared_artifact_index([repo_root])
    scope_entity = query.get_entity(scope_entity_id)
    if scope_entity is None:
        raise ValueError(f"{diagram_type!r}: scope entity {scope_entity_id!r} not found")

    projection = project_c4(
        diagram_type, scope_entity_id, query,
        internal_c4_type=internal_c4_type,
        scope_entity_type=scope_entity_type,
        person_archimate_types=person_archimate_types,
    )

    raw_included = diagram_entities.get("_included_entity_ids")
    raw_excluded = diagram_entities.get("_excluded_entity_ids")
    included_only: set[str] | None = None
    excluded_ids: set[str] = set()
    if isinstance(raw_included, list) and raw_included:
        included_only = {str(x) for x in raw_included}
    elif isinstance(raw_excluded, list) and raw_excluded:
        excluded_ids = {str(x) for x in raw_excluded}

    scope_item = _item_from_entity(scope_entity, scope_entity_id, scope_entity_type, external=False)
    internal_items: list[_ResolvedItem] = []
    outside_items: list[_ResolvedItem] = []

    for proj_item in projection.items:
        if proj_item.role == "scope":
            continue
        eid = proj_item.entity_id
        if included_only is not None and eid not in included_only:
            continue
        if eid in excluded_ids:
            continue
        entity = query.get_entity(eid)
        if entity is None:
            continue
        resolved = _item_from_entity(entity, eid, proj_item.item_type, external=(proj_item.role == "external"))
        if proj_item.role == "internal":
            internal_items.append(resolved)
        else:
            outside_items.append(resolved)

    # additive validated inclusion — extra IDs in _included_entity_ids that the
    # projection did not yield are added as external neighbours if graph-justified (they
    # have at least one connection to the already-projected entity set).
    if included_only:
        projected_eids = {scope_entity_id} | {i.local_id for i in internal_items} | {i.local_id for i in outside_items}
        for extra_eid in sorted(included_only - projected_eids):
            entity = query.get_entity(extra_eid)
            if entity is None:
                continue
            if any(
                c.source in projected_eids or c.target in projected_eids
                for c in query.find_connections_for(extra_eid, direction="any")
            ):
                outside_items.append(_item_from_entity(entity, extra_eid, "software-system", external=True))

    all_displayed = (
        {scope_entity_id}
        | {i.local_id for i in internal_items}
        | {i.local_id for i in outside_items}
    )
    alias_by_eid = {i.local_id: i.alias for i in [scope_item] + internal_items + outside_items}

    # Collect model connections — include roll-up connections (one endpoint may be an
    # internal entity not in alias_by_eid; the render loop below handles remapping).
    model_conns: list[Any] = []
    for cid in projection.connection_ids:
        conn = query.get_connection(cid)
        if conn is None:
            continue
        # Keep if at least one endpoint touches the displayed set (excludes internal↔internal)
        if conn.source not in all_displayed and conn.target not in all_displayed:
            continue
        model_conns.append(conn)
    model_conns.sort(key=lambda x: x.artifact_id)

    # Build the C4 edge list:
    #   - reverse archimate-serving so the arrow reads consumer --uses--> provider
    #   - orient symmetric archimate-association by a deterministic role rule: the
    #     system side (scope/internal) is the provider, so the edge points
    #     consumer (person/external) --uses--> system side
    #   - for system-context, internal endpoints remap to the scope root
    #   - deduplicate by (src, tgt) after remapping; drop self-loops
    is_ctx = (diagram_type == "c4-system-context")
    scope_alias = alias_by_eid.get(scope_entity_id, "")
    provider_aliases = {scope_alias} | {i.alias for i in internal_items}
    seen_pairs: set[tuple[str, str]] = set()
    conn_list: list[_C4Connection] = []
    for c in model_conns:
        src = alias_by_eid.get(c.source) or (scope_alias if is_ctx else None)
        tgt = alias_by_eid.get(c.target) or (scope_alias if is_ctx else None)
        if src is None or tgt is None:
            continue
        if c.conn_type == "archimate-serving":
            src, tgt = tgt, src  # provider→consumer becomes consumer --uses--> provider
        elif c.conn_type == "archimate-association" and src in provider_aliases and tgt not in provider_aliases:
            src, tgt = tgt, src  # role rule: consumer --uses--> system side
        if src == tgt:
            continue
        pair = (src, tgt)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        conn_list.append(_C4Connection(src_alias=src, tgt_alias=tgt, label=_conn_label(c), artifact_id=c.artifact_id))
    connections = tuple(conn_list)

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


def _short_description(entity: Any) -> str:
    """First prose sentence of the entity's body, truncated — the C4 element/person role line.

    Skips the leading ``## Name`` heading and any table/properties blocks; returns the first
    real paragraph's opening sentence so C4 boxes (and especially Persons) carry a short role
    description rather than rendering bare.
    """
    text = getattr(entity, "content_text", "") if entity is not None else ""
    if not text:
        return ""
    for block in text.split("\n\n"):
        line = block.strip().splitlines()[0].strip() if block.strip() else ""
        if not line or line.startswith(("#", "|", "-", "*", ">")):
            continue
        sentence = line.split(". ")[0].rstrip(".")
        return sentence if len(sentence) <= 100 else sentence[:99].rstrip() + "…"
    return ""


def _item_from_entity(entity: Any, entity_id: str, item_type: str, *, external: bool) -> _ResolvedItem:
    label = entity.name if entity is not None else entity_id
    raw_alias = getattr(entity, "display_alias", "") or "" if entity is not None else ""
    alias = _normalize_alias(raw_alias) if raw_alias else _alias_for(item_type, entity_id)
    return _ResolvedItem(
        local_id=entity_id,
        item_type=item_type,
        alias=alias,
        label=label,
        description=_short_description(entity),
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
    # Short C4 verb keyed on connection type — direction-consistent with the
    # (possibly reversed/re-oriented) C4 arrow. Prose lives on the model connection.
    return _C4_CONN_LABELS.get(conn.conn_type, "uses")


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
