"""Parsing for the ``query:`` block (companion plan §4): entity criteria, neighbor
inclusions, and connection selection, Appendix-A canonical form."""

from __future__ import annotations

from collections.abc import Mapping

from src.domain.viewpoint_criteria import EntityCriteriaGroup
from src.domain.viewpoint_criteria_parsing import (
    parse_connection_selection,
    parse_entity_criteria_group,
    parse_neighbor_inclusion,
)
from src.domain.viewpoints import QUERY_SCHEMA_VERSION, VALID_REPO_SCOPES, ExecutableViewpointQuery, RepoScope

_QUERY_KEYS = frozenset({"query_schema", "entity_criteria", "include_connected", "connections", "repo_scope"})


def _require_repo_scope(value: object, *, label: str) -> RepoScope:
    text = str(value)
    if text not in ("enterprise", "engagement", "both"):
        raise ValueError(f"{label}: repo_scope {text!r} is not one of {sorted(VALID_REPO_SCOPES)}")
    return text


def query_from_mapping(raw: object, *, label: str) -> ExecutableViewpointQuery:
    if not isinstance(raw, Mapping):
        return ExecutableViewpointQuery()
    unknown = set(raw.keys()) - _QUERY_KEYS
    if unknown:
        raise ValueError(f"{label}: query: unknown key(s) {sorted(unknown)}")
    schema_version = raw.get("query_schema", QUERY_SCHEMA_VERSION)
    if int(schema_version) != QUERY_SCHEMA_VERSION:
        raise ValueError(f"{label}: unsupported query_schema {schema_version!r}, expected {QUERY_SCHEMA_VERSION}")
    entity_criteria_raw = raw.get("entity_criteria")
    entity_criteria = (
        parse_entity_criteria_group(entity_criteria_raw) if entity_criteria_raw is not None else EntityCriteriaGroup()
    )
    include_connected_raw = raw.get("include_connected", ())
    if not isinstance(include_connected_raw, (list, tuple)):
        raise ValueError(f"{label}: include_connected must be a list")
    include_connected = tuple(parse_neighbor_inclusion(item) for item in include_connected_raw)
    return ExecutableViewpointQuery(
        query_schema=QUERY_SCHEMA_VERSION,
        entity_criteria=entity_criteria,
        include_connected=include_connected,
        connections=parse_connection_selection(raw.get("connections")),
        repo_scope=_require_repo_scope(raw.get("repo_scope", "both"), label=label),
    )
