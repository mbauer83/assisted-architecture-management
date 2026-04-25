"""
connection_ontology.py — ArchiMate relationship query API.

All rules are loaded from config/connection_ontology.yaml via ontology_loader.
Used by ArtifactVerifier (rule enforcement), GUI (form generation), and MCP tools.
"""

from __future__ import annotations

from src.common.ontology_loader import (
    PERMITTED_RELATIONSHIPS,
    RULES_BY_SOURCE,
    RULES_BY_TARGET,
    SYMMETRIC_CONNECTIONS,
)


def is_symmetric(conn_type: str) -> bool:
    """Return True if the connection type is symmetric (undirected)."""
    return conn_type in SYMMETRIC_CONNECTIONS


def permissible_connection_types(
    source_type: str,
    target_type: str,
) -> list[str]:
    """Return ArchiMate connection types valid between source and target type."""
    result: set[str] = set()

    key = (source_type, target_type)
    if key in PERMITTED_RELATIONSHIPS:
        result.update(PERMITTED_RELATIONSHIPS[key])

    # Reverse for symmetric types
    rev_key = (target_type, source_type)
    if rev_key in PERMITTED_RELATIONSHIPS:
        for ct in PERMITTED_RELATIONSHIPS[rev_key]:
            if is_symmetric(ct):
                result.add(ct)

    return sorted(result)


def permissible_target_types(source_type: str) -> dict[str, list[str]]:
    """For a source type, return {conn_type: [valid_target_types]}."""
    out: dict[str, list[str]] = {}
    for tgt, conn_types in RULES_BY_SOURCE.get(source_type, []):
        for ct in conn_types:
            out.setdefault(ct, []).append(tgt)
    return {ct: sorted(tgts) for ct, tgts in sorted(out.items())}


def classify_connections(
    source_type: str,
) -> dict[str, dict[str, list[str]]]:
    """Classify permissible connections into outgoing/incoming/symmetric.

    Returns ``{"outgoing": {tgt_type: [conn_types]}, "incoming": ...,
    "symmetric": ...}``.
    """
    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    symmetric: dict[str, list[str]] = {}

    for tgt, conn_types in RULES_BY_SOURCE.get(source_type, []):
        for ct in conn_types:
            if is_symmetric(ct):
                symmetric.setdefault(tgt, []).append(ct)
            else:
                outgoing.setdefault(tgt, []).append(ct)

    for src, conn_types in RULES_BY_TARGET.get(source_type, []):
        for ct in conn_types:
            if is_symmetric(ct):
                if src not in symmetric:
                    symmetric.setdefault(src, []).append(ct)
            else:
                incoming.setdefault(src, []).append(ct)

    return {"outgoing": outgoing, "incoming": incoming, "symmetric": symmetric}
