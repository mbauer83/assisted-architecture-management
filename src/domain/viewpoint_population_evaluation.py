"""Population-level evaluation (companion plan §4.1, §3.1, §5.4): widening the primary
entity population via ``NeighborInclusion`` terms, and selecting the connections displayed
for a resolved entity population (the ordinary structural invariant and the sharper matrix
bridging form). Built entirely on the pure per-record predicates in
``viewpoint_criteria_evaluation.py`` — no independent evaluation logic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.artifact_types import ConnectionRecord
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria import ConnectionSelection, NeighborInclusion
from src.domain.viewpoint_criteria_evaluation import (
    direction_matches,
    evaluate_connection_criteria,
    evaluate_entity_criteria,
)
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess


@dataclass(frozen=True)
class NeighborInclusionResult:
    """Entities widened into the population (membership precedence: an entity already in
    the primary set is never re-added here; entities matched by several inclusion terms
    appear once)."""

    expanded_ids: frozenset[str]
    schema_drift: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ConnectionSelectionResult:
    connections: tuple[ConnectionRecord, ...]
    schema_drift: frozenset[str] = frozenset()


def resolve_neighbor_inclusions(
    primary_ids: frozenset[str],
    inclusions: Sequence[NeighborInclusion],
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
) -> NeighborInclusionResult:
    """Anchors are always the primary set — inclusions never chain off other inclusions'
    results, so this is one evaluation pass, deterministic."""
    expanded: set[str] = set()
    drift: set[str] = set()
    for inclusion in inclusions:
        for anchor_id in primary_ids:
            for connection in read_access.find_connections_for(anchor_id, direction="any"):
                if inclusion.connection_criteria is not None:
                    outcome = evaluate_connection_criteria(
                        inclusion.connection_criteria, connection, read_access=read_access, registries=registries
                    )
                    drift |= outcome.schema_drift
                    if not outcome.matched:
                        continue
                if not direction_matches(connection, anchor_id, inclusion.direction, registries):
                    continue
                neighbor_id = connection.target if connection.source == anchor_id else connection.source
                if neighbor_id in primary_ids or neighbor_id in expanded:
                    continue
                neighbor_entity = read_access.get_entity(neighbor_id)
                if neighbor_entity is None:
                    continue  # dangling endpoint never matches
                if inclusion.neighbor_criteria is not None:
                    outcome = evaluate_entity_criteria(
                        inclusion.neighbor_criteria, neighbor_entity, read_access=read_access, registries=registries
                    )
                    drift |= outcome.schema_drift
                    if not outcome.matched:
                        continue
                expanded.add(neighbor_id)
    return NeighborInclusionResult(frozenset(expanded), frozenset(drift))


def select_connections(
    included_entity_ids: frozenset[str],
    selection: ConnectionSelection,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
) -> ConnectionSelectionResult:
    """Structural invariant (§3.1): a connection is included only if both endpoints are in
    ``included_entity_ids``; ``selection.criteria`` narrows within that set and can never
    widen past it."""
    if not selection.enabled:
        return ConnectionSelectionResult(())
    return _select(included_entity_ids, selection, read_access=read_access, registries=registries, bridging=None)


def select_matrix_connections(
    row_entity_ids: frozenset[str],
    column_entity_ids: frozenset[str],
    selection: ConnectionSelection,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
) -> ConnectionSelectionResult:
    """Matrix bridging invariant (§5.4): included only if one endpoint is in the row
    population and the OTHER is in the column population — row↔column only, never row↔row
    or column↔column."""
    if not selection.enabled:
        return ConnectionSelectionResult(())
    combined = row_entity_ids | column_entity_ids
    return _select(
        combined,
        selection,
        read_access=read_access,
        registries=registries,
        bridging=(row_entity_ids, column_entity_ids),
    )


def _select(
    scan_ids: frozenset[str],
    selection: ConnectionSelection,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    bridging: tuple[frozenset[str], frozenset[str]] | None,
) -> ConnectionSelectionResult:
    seen: dict[str, ConnectionRecord] = {}
    drift: set[str] = set()
    for entity_id in scan_ids:
        for connection in read_access.find_connections_for(entity_id, direction="any"):
            if connection.artifact_id in seen:
                continue
            if bridging is None:
                structurally_included = connection.source in scan_ids and connection.target in scan_ids
            else:
                rows, columns = bridging
                structurally_included = (connection.source in rows and connection.target in columns) or (
                    connection.source in columns and connection.target in rows
                )
            if not structurally_included:
                continue
            outcome = evaluate_connection_criteria(
                selection.criteria, connection, read_access=read_access, registries=registries
            )
            drift |= outcome.schema_drift
            if outcome.matched:
                seen[connection.artifact_id] = connection
    ordered = tuple(sorted(seen.values(), key=lambda connection: connection.artifact_id))
    return ConnectionSelectionResult(ordered, frozenset(drift))
