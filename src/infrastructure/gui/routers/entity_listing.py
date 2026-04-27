"""Helpers for GUI entity list payloads."""

from __future__ import annotations

from typing import Any

from src.domain.artifact_types import EntityRecord
from src.infrastructure.gui.routers import state as s

_HIERARCHY_PRIORITY = {
    "archimate-specialization": 0,
    "archimate-composition": 1,
    "archimate-aggregation": 2,
}
_HIERARCHY_TYPES = frozenset(_HIERARCHY_PRIORITY)

_HIERARCHY_LABEL = {
    "archimate-specialization": "specialization",
    "archimate-composition": "composition",
    "archimate-aggregation": "aggregation",
}


def hierarchy_meta(entities: list[EntityRecord], repo) -> dict[str, dict[str, object]]:
    entity_ids = {e.artifact_id for e in entities}
    parents_by_child: dict[str, list[tuple[str, str]]] = {}
    for conn in repo.list_connections_by_types(_HIERARCHY_TYPES):
        if conn.conn_type not in _HIERARCHY_PRIORITY:
            continue
        if conn.conn_type == "archimate-specialization":
            child_id = conn.source
            parent_id = conn.target
        else:
            parent_id = conn.source
            child_id = conn.target
        if child_id not in entity_ids or parent_id not in entity_ids:
            continue
        if child_id not in parents_by_child:
            parents_by_child[child_id] = []
        parents_by_child[child_id].append((parent_id, conn.conn_type))

    for child_id in parents_by_child:
        parents_by_child[child_id].sort(key=lambda p: (_HIERARCHY_PRIORITY[p[1]], p[0]))

    depth_cache: dict[str, int] = {}

    def depth_for(entity_id: str, trail: set[str] | None = None) -> int:
        if entity_id in depth_cache:
            return depth_cache[entity_id]
        parents = parents_by_child.get(entity_id, [])
        if not parents:
            depth_cache[entity_id] = 0
            return 0
        trail = trail or set()
        if entity_id in trail:
            depth_cache[entity_id] = 0
            return 0
        min_depth = min(depth_for(p[0], trail | {entity_id}) for p in parents)
        depth_cache[entity_id] = min_depth + 1
        return depth_cache[entity_id]

    result: dict[str, dict[str, object]] = {}
    for e in entities:
        parents = parents_by_child.get(e.artifact_id, [])
        primary = parents[0] if parents else None
        meta: dict[str, object] = {
            "hierarchy_depth": depth_for(e.artifact_id),
            "specialization_depth": depth_for(e.artifact_id),
            "all_parents": [
                {"parent_id": pid, "relation_type": _HIERARCHY_LABEL[ct]}
                for pid, ct in parents
            ],
        }
        if primary:
            pid, ct = primary
            meta["parent_entity_id"] = pid
            meta["parent_specialization_id"] = pid
            meta["hierarchy_relation_type"] = _HIERARCHY_LABEL[ct]
        result[e.artifact_id] = meta
    return result


def build_entity_summary_rows(
    entities: list[EntityRecord],
    repo,
) -> list[dict[str, Any]]:
    counts = s.build_conn_counts(repo)
    hierarchy = hierarchy_meta(entities, repo)
    items: list[dict[str, Any]] = []
    for entity in entities:
        row = s.entity_to_summary(entity, counts)
        row.update(hierarchy.get(entity.artifact_id, {}))
        items.append(row)
    return items
