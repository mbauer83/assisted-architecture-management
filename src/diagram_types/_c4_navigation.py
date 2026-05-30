"""C4 diagram navigation: computes parent/child C4 diagram links from shared scope entities."""

from __future__ import annotations

from typing import Any

_C4_LEVELS: dict[str, int] = {
    "c4-system-landscape": 0,
    "c4-system-context": 1,
    "c4-container": 2,
    "c4-component": 3,
}


def scope_entity_id(diagram_entities: dict[str, Any]) -> str:
    explicit = str(diagram_entities.get("_scope_entity_id") or "").strip()
    if explicit:
        return explicit
    for key, items in diagram_entities.items():
        if key.startswith("_") or not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("scope") and item.get("entity_id"):
                return str(item["entity_id"])
    return ""


def item_entity_ids(diagram_entities: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for key, items in diagram_entities.items():
        if key.startswith("_") or not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and item.get("entity_id"):
                result.add(str(item["entity_id"]))
    return result


def build_c4_navigation(
    repo: Any,
    current_id: str,
    diagram_type: str,
    diagram_entities: dict[str, Any],
) -> dict[str, Any] | None:
    current_level = _C4_LEVELS.get(diagram_type)
    if current_level is None:
        return None
    scope_id = scope_entity_id(diagram_entities)
    scope_entity = repo.get_entity(scope_id) if scope_id else None
    current_item_ids = item_entity_ids(diagram_entities)

    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []

    for other in repo.list_diagrams():
        if other.artifact_id == current_id or other.diagram_type not in _C4_LEVELS:
            continue
        other_level = _C4_LEVELS[other.diagram_type]
        raw_de = other.extra.get("diagram-entities") if other.extra else None
        other_de: dict[str, Any] = raw_de if isinstance(raw_de, dict) else {}
        other_scope_id = scope_entity_id(other_de)
        link: dict[str, Any] = {
            "diagram_id": other.artifact_id,
            "diagram_name": other.name,
            "diagram_type": other.diagram_type,
        }

        # L1 ↔ L2: both scope the same software-system
        if (
            diagram_type in ("c4-system-context", "c4-container")
            and other.diagram_type in ("c4-system-context", "c4-container")
            and scope_id
            and other_scope_id == scope_id
        ):
            (parents if other_level < current_level else children).append(link)

        # L2 → L3: L3's scope container appears as an item in this L2
        elif diagram_type == "c4-container" and other.diagram_type == "c4-component":
            if other_scope_id and other_scope_id in current_item_ids:
                children.append({**link, "scope_entity_id": other_scope_id})

        # L3 → L2: this L3's scope container appears as an item in the other L2
        elif diagram_type == "c4-component" and other.diagram_type == "c4-container":
            if scope_id and scope_id in item_entity_ids(other_de):
                parents.append(link)

    return {
        "current_level": current_level,
        "scope_entity_id": scope_id or None,
        "scope_entity_name": scope_entity.name if scope_entity else None,
        "parent_diagrams": parents,
        "child_diagrams": children,
    }
