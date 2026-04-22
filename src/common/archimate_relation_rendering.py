from __future__ import annotations

from src.common.ontology_loader import CONNECTION_TYPES

_DIRECTION_SUFFIX = {
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}


def display_connection_label(conn_type: str) -> str:
    return conn_type.removeprefix("archimate-")


def render_archimate_relation(
    source_alias: str,
    target_alias: str,
    conn_type: str,
    *,
    direction: str | None = None,
    label_text: str = "",
) -> str | None:
    ct = CONNECTION_TYPES.get(conn_type)
    if ct is None or ct.conn_lang != "archimate" or not ct.archimate_relationship_type:
        return None
    macro = f"Rel_{ct.archimate_relationship_type}"
    suffix = _DIRECTION_SUFFIX.get((direction or "").lower())
    if suffix:
        macro = f"{macro}_{suffix}"
    escaped = label_text.replace('"', "'")
    return f'{macro}({source_alias}, {target_alias}, "{escaped}")'
