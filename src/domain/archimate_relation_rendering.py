from __future__ import annotations

from functools import lru_cache

from src.domain.module_types import ConnectionTypeName

_DIRECTION_SUFFIX = {
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
}


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def display_connection_label(conn_type: str) -> str:
    return conn_type.removeprefix("archimate-")


def format_cardinality_label(src_cardinality: str, tgt_cardinality: str) -> str:
    """Return a compact cardinality label for a connection, or '' when neither end is set."""
    has_src = bool(src_cardinality)
    has_tgt = bool(tgt_cardinality)
    if has_src and has_tgt:
        return f"{src_cardinality} -> {tgt_cardinality}"
    if has_src:
        return f"{src_cardinality} ->"
    if has_tgt:
        return f"-> {tgt_cardinality}"
    return ""


def render_archimate_relation(
    source_alias: str,
    target_alias: str,
    conn_type: str,
    *,
    direction: str | None = None,
    label_text: str = "",
) -> str | None:
    ct = _registry().find_connection_type(ConnectionTypeName(conn_type))
    if ct is None or ct.conn_lang != "archimate" or not ct.archimate_relationship_type:
        return None
    macro = f"Rel_{ct.archimate_relationship_type}"
    suffix = _DIRECTION_SUFFIX.get((direction or "").lower())
    if suffix:
        macro = f"{macro}_{suffix}"
    escaped = label_text.replace('"', "'")
    return f'{macro}({source_alias}, {target_alias}, "{escaped}")'
