"""Serialize a ``query:`` block back to the Appendix-A canonical form — the counterpart to
``viewpoint_query_parsing.py``."""

from __future__ import annotations

from typing import Any

from src.domain.viewpoint_criteria_serialization import (
    connection_selection_to_mapping,
    entity_criteria_group_to_mapping,
    neighbor_inclusion_to_mapping,
)
from src.domain.viewpoints import ExecutableViewpointQuery


def query_to_mapping(query: ExecutableViewpointQuery) -> dict[str, Any]:
    result: dict[str, Any] = {
        "query_schema": query.query_schema,
        "entity_criteria": entity_criteria_group_to_mapping(query.entity_criteria),
    }
    if query.include_connected:
        result["include_connected"] = [neighbor_inclusion_to_mapping(i) for i in query.include_connected]
    connections = connection_selection_to_mapping(query.connections)
    if connections:
        result["connections"] = connections
    if query.repo_scope != "both":
        result["repo_scope"] = query.repo_scope
    return result
