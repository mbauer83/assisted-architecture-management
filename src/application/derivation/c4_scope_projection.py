"""c4.scope-projection/v1 strategy implementing the C4 projection tables.

Projection tables from SPEC-phase-3 §2.3:

  c4-system-context: root entity + 1-hop neighbors via dependency connections.
    - application-component / service (root or neighbor) → software-system
    - business-actor / role (neighbor) → person

  c4-container: root's structural children → container; neighbors → software-system / person.
    - application-component / service / data-object / node (internal) → container
    - application-component / service (neighbor) → software-system
    - business-actor / role (neighbor) → person

  c4-component: root's structural children → component; neighbors → software-system.
    - application-component / function / service (internal) → component
    - application-component / service (neighbor) → software-system

Containment (§2.2): internal entities are reached via archimate-composition /
archimate-aggregation outbound from root within max_depth hops (default 1).

Also self-registers as a module projection under ("c4", 1) for use via
scope-projection/v1 with projection_id="c4" and projection_version=1.

Supported pre_filters: repo_scope
"""

from __future__ import annotations

from src.application.derivation.scope_projection import register_module_projection
from src.application.derivation.strategy_registry import StrategySpec, register_strategy
from src.application.derivation.types import CandidateSet, ModelQuery
from src.domain.view_derivations import SourceModelSnapshot

# ArchiMate structural (nesting) connection types
_NESTING_TYPES: frozenset[str] = frozenset({
    "archimate-composition", "archimate-aggregation",
})
# ArchiMate dependency/flow connection types that project to c4-uses edges
_NEIGHBOR_TYPES: frozenset[str] = frozenset({
    "archimate-serving", "archimate-flow", "archimate-triggering", "archimate-access",
})

# Allowed model entity types per C4 level and role
_CONTEXT_PROJ_TYPES: frozenset[str] = frozenset({
    "application-component", "service", "business-actor", "role",
})
_CONTAINER_INTERNAL_TYPES: frozenset[str] = frozenset({
    "application-component", "service", "data-object", "node",
})
_CONTAINER_NEIGHBOR_TYPES: frozenset[str] = frozenset({
    "application-component", "service", "business-actor", "role",
})
_COMPONENT_INTERNAL_TYPES: frozenset[str] = frozenset({
    "application-component", "function", "service",
})
_COMPONENT_NEIGHBOR_TYPES: frozenset[str] = frozenset({
    "application-component", "service",
})

_SUPPORTED_FILTERS = frozenset({"repo_scope"})


def _entity_type(entity_id: str, query: ModelQuery) -> str:
    rec = query.get_entity(entity_id)
    return rec.artifact_type if rec else ""


def _int_param(params: dict[str, object], key: str, default: int) -> int:
    v = params.get(key, default)
    return int(v) if isinstance(v, (int, float)) else default


def _structural_children(root: str, max_depth: int, query: ModelQuery) -> set[str]:
    """BFS from root via nesting connection types (outbound) up to max_depth hops."""
    visited: set[str] = set()
    frontier: set[str] = {root}
    for _ in range(max_depth):
        next_frontier: set[str] = set()
        for eid in frontier:
            for conn in query.find_connections_for(eid, direction="outbound"):
                if conn.conn_type in _NESTING_TYPES and conn.target not in visited:
                    visited.add(conn.target)
                    next_frontier.add(conn.target)
        frontier = next_frontier
        if not frontier:
            break
    return visited


def _neighbor_entities(
    scope: set[str],
    allowed_types: frozenset[str],
    query: ModelQuery,
) -> set[str]:
    """Entities reachable from scope via _NEIGHBOR_TYPES, NOT in scope, with allowed type."""
    result: set[str] = set()
    for eid in scope:
        for conn in query.find_connections_for(eid, direction="any"):
            if conn.conn_type not in _NEIGHBOR_TYPES:
                continue
            other = conn.target if conn.source == eid else conn.source
            if other in scope:
                continue
            if _entity_type(other, query) in allowed_types:
                result.add(other)
    return result


def _direct_conns(projected: set[str], query: ModelQuery) -> set[str]:
    """_NEIGHBOR_TYPES connections where both source and target are in projected."""
    result: set[str] = set()
    for eid in projected:
        for conn in query.find_connections_for(eid, direction="outbound"):
            if conn.conn_type in _NEIGHBOR_TYPES and conn.target in projected:
                result.add(conn.artifact_id)
    return result


def _project_system_context(
    root: str, params: dict[str, object], query: ModelQuery
) -> CandidateSet:
    """Root + 1-hop neighbors via dependency connections."""
    scope = {root}
    neighbors = _neighbor_entities(scope, _CONTEXT_PROJ_TYPES, query)
    projected = scope | neighbors
    return CandidateSet(
        entity_ids=frozenset(projected),
        connection_ids=frozenset(_direct_conns(projected, query)),
    )


def _project_container(
    root: str, params: dict[str, object], query: ModelQuery
) -> CandidateSet:
    """Root's structural children (container) + neighbors (software-system, person)."""
    max_depth = _int_param(params, "max_depth", 1)
    raw_children = _structural_children(root, max_depth, query)
    internal = {e for e in raw_children if _entity_type(e, query) in _CONTAINER_INTERNAL_TYPES}
    scope = {root} | internal
    neighbors = _neighbor_entities(scope, _CONTAINER_NEIGHBOR_TYPES, query)
    projected = internal | neighbors
    return CandidateSet(
        entity_ids=frozenset(projected),
        connection_ids=frozenset(_direct_conns(projected, query)),
    )


def _project_component(
    root: str, params: dict[str, object], query: ModelQuery
) -> CandidateSet:
    """Root's structural children (component) + neighbors (software-system)."""
    max_depth = _int_param(params, "max_depth", 1)
    raw_children = _structural_children(root, max_depth, query)
    internal = {e for e in raw_children if _entity_type(e, query) in _COMPONENT_INTERNAL_TYPES}
    scope = {root} | internal
    neighbors = _neighbor_entities(scope, _COMPONENT_NEIGHBOR_TYPES, query)
    projected = internal | neighbors
    return CandidateSet(
        entity_ids=frozenset(projected),
        connection_ids=frozenset(_direct_conns(projected, query)),
    )


_PROJECTORS = {
    "c4-system-context": _project_system_context,
    "c4-container": _project_container,
    "c4-component": _project_component,
}


def derive(
    params: dict[str, object],
    snapshot: SourceModelSnapshot,
    query: ModelQuery,
) -> CandidateSet:
    """c4.scope-projection/v1: dispatch to the correct C4-level projector."""
    root = snapshot.root_entity_id or str(params.get("scope_entity_id", ""))
    if not root:
        return CandidateSet()

    diagram_type = str(params.get("diagram_type", ""))
    projector = _PROJECTORS.get(diagram_type)
    if projector is None:
        return CandidateSet()

    return projector(root, params, query)


# Register as a named strategy in the strategy registry
register_strategy(
    StrategySpec(
        name="c4.scope-projection",
        version=1,
        supported_filters=_SUPPORTED_FILTERS,
    ),
    derive_fn=derive,
)

# Register as a module projection for use via scope-projection/v1 with projection_id="c4"
register_module_projection("c4", 1, derive)
