"""
connection_ontology.py — ArchiMate relationship query API.

All rules are loaded from the registered ontology modules via the module registry.
Used by ArtifactVerifier (rule enforcement), GUI (form generation), and MCP tools.
"""

from __future__ import annotations

from functools import lru_cache

from src.domain.module_types import ConnectionTypeName, EntityTypeName
from src.domain.permitted_relationships import PermittedRelationshipSet


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415
    return get_module_registry()


@lru_cache(maxsize=1)
def _permitted_relationships() -> PermittedRelationshipSet:
    return _registry().aggregated_permitted_relationships()


def is_symmetric(conn_type: str) -> bool:
    """Return True if the connection type is symmetric (undirected)."""
    info = _registry().find_connection_type(ConnectionTypeName(conn_type))
    return info.symmetric if info is not None else False


def permissible_connection_types(
    source_type: str,
    target_type: str,
) -> list[str]:
    """Return ArchiMate connection types valid between source and target type."""
    prs = _permitted_relationships()
    src = EntityTypeName(source_type)
    tgt = EntityTypeName(target_type)
    result = set(prs.permitted_connection_types(src, tgt))
    for ct in prs.permitted_connection_types(tgt, src):
        if is_symmetric(ct):
            result.add(ct)
    return sorted(result)


def permissible_target_types(source_type: str) -> dict[str, list[str]]:
    """For a source type, return {conn_type: [valid_target_types]}."""
    out: dict[str, list[str]] = {}
    for tgt, ct in _permitted_relationships().by_source().get(EntityTypeName(source_type), []):
        out.setdefault(str(ct), []).append(str(tgt))
    return {ct: sorted(tgts) for ct, tgts in sorted(out.items())}


def classify_connections(
    source_type: str,
) -> dict[str, dict[str, list[str]]]:
    """Classify permissible connections into outgoing/incoming/symmetric.

    Returns ``{"outgoing": {tgt_type: [conn_types]}, "incoming": ...,
    "symmetric": ...}``.
    """
    prs = _permitted_relationships()
    src = EntityTypeName(source_type)
    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    symmetric: dict[str, list[str]] = {}

    for tgt, ct in prs.by_source().get(src, []):
        if is_symmetric(ct):
            symmetric.setdefault(str(tgt), []).append(str(ct))
        else:
            outgoing.setdefault(str(tgt), []).append(str(ct))

    for src2, ct in prs.by_target().get(src, []):
        if is_symmetric(ct):
            if str(src2) not in symmetric:
                symmetric.setdefault(str(src2), []).append(str(ct))
        else:
            incoming.setdefault(str(src2), []).append(str(ct))

    return {"outgoing": outgoing, "incoming": incoming, "symmetric": symmetric}
