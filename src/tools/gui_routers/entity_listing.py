"""Helpers for GUI entity list payloads."""

from __future__ import annotations

from typing import Any

from src.common.artifact_types import EntityRecord
from src.tools.gui_routers import state as s


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
    parent_by_child: dict[str, tuple[str, str]] = {}
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
        prev = parent_by_child.get(child_id)
        candidate = (parent_id, conn.conn_type)
        if prev is None:
            parent_by_child[child_id] = candidate
            continue
        prev_parent, prev_conn_type = prev
        prev_key = (_HIERARCHY_PRIORITY[prev_conn_type], prev_parent)
        next_key = (_HIERARCHY_PRIORITY[conn.conn_type], parent_id)
        if next_key < prev_key:
            parent_by_child[child_id] = candidate

    depth_cache: dict[str, int] = {}

    def depth_for(entity_id: str, trail: set[str] | None = None) -> int:
        if entity_id in depth_cache:
            return depth_cache[entity_id]
        parent = parent_by_child.get(entity_id)
        if not parent:
            depth_cache[entity_id] = 0
            return 0
        trail = trail or set()
        if entity_id in trail:
            depth_cache[entity_id] = 0
            return 0
        depth_cache[entity_id] = depth_for(parent[0], trail | {entity_id}) + 1
        return depth_cache[entity_id]

    return {
        e.artifact_id: {
            **(
                {
                    "parent_entity_id": parent_by_child[e.artifact_id][0],
                    "hierarchy_relation_type": _HIERARCHY_LABEL[parent_by_child[e.artifact_id][1]],
                    "parent_specialization_id": parent_by_child[e.artifact_id][0],
                }
                if e.artifact_id in parent_by_child else {}
            ),
            "hierarchy_depth": depth_for(e.artifact_id),
            "specialization_depth": depth_for(e.artifact_id),
        }
        for e in entities
    }


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
