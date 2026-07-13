"""Bounded, deterministic enumeration of ephemeral derived relationships."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from src.domain.artifact_types import ConnectionRecord
from src.domain.module_catalog import ModuleCatalog
from src.domain.module_types import ConnectionTypeName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.relationship_derivation import DerivedStep, OrientedRelation, compose
from src.domain.relationship_path_reconstruction import (
    PathDerivationOutcome,
    RelationshipPathReadAccess,
    oriented_relation,
    shared_entity_info,
)
from src.domain.relationship_path_reconstruction import (
    derive_relationship_for_path as _derive_relationship_for_path,
)
from src.domain.viewpoint_criteria import IncidentDirection
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess

DerivationCertaintyPolicy = Literal["certain_only", "include_potential"]

DERIVED_CONNECTION_ID_PREFIX = "derived::"


def is_derived_connection_id(artifact_id: str) -> bool:
    """Whether ``artifact_id`` is a synthetic derived-relationship id
    (``derived::<type-slug>::<path-key>``) rather than a real, persisted connection —
    never written to a model file, the artifact index, or a ``CandidateSet``."""
    return artifact_id.startswith(DERIVED_CONNECTION_ID_PREFIX)


def derive_relationship_for_path(
    path_key: str,
    *,
    read_access: RelationshipPathReadAccess,
    registries: ModuleCatalog,
) -> PathDerivationOutcome:
    """Reconstruct one recorded relationship-derivation witness path."""
    return _derive_relationship_for_path(path_key, read_access=read_access, registries=registries)


@dataclass(frozen=True)
class DerivationBounds:
    max_hops: int
    max_relationships: int


@dataclass(frozen=True)
class RelationshipDerivationRequest:
    anchors: frozenset[str]
    direction: IncidentDirection
    certainty: DerivationCertaintyPolicy
    bounds: DerivationBounds


@dataclass(frozen=True)
class DerivedRelationship:
    artifact_id: str
    source_id: str
    target_id: str
    connection_type: str
    certainty: Literal["certain", "potential"]
    hops: int
    via_connection_ids: tuple[str, ...]
    path_key: str


@dataclass(frozen=True)
class DerivedRelationshipSet:
    relationships: tuple[DerivedRelationship, ...]


class DerivationLimitError(ValueError):
    """Raised before returning a partial derived-relationship set."""

    def __init__(self, maximum: int) -> None:
        super().__init__(f"relationship derivation exceeded the configured limit of {maximum}")
        self.maximum = maximum


@dataclass(frozen=True)
class _FrontierItem:
    relation: OrientedRelation
    path: tuple[tuple[str, Literal["fwd", "rev"]], ...]
    used_connection_ids: frozenset[str]


def derive_relationships(
    request: RelationshipDerivationRequest,
    *,
    read_access: CriteriaReadAccess,
    registries: ModuleCatalog,
) -> DerivedRelationshipSet:
    """Enumerate bounded relationship compositions adjacent to the requested anchors."""
    if request.bounds.max_hops < 2 or not request.anchors:
        return DerivedRelationshipSet(())
    entity_types = registries.all_entity_types()
    connection_types = registries.all_connection_types()
    rules = tuple(rule for module in registries.all_ontologies().values() for rule in module.derivation_rules)
    restrictions = tuple(
        rule for module in registries.all_ontologies().values() for rule in module.derivation_restrictions
    )
    permitted = registries.aggregated_permitted_relationships()
    queue = deque(
        _initial_frontier(request.anchors, request.bounds.max_hops, read_access, entity_types, connection_types)
    )
    results: dict[tuple[str, str, str], DerivedRelationship] = {}
    seen_paths: set[tuple[str, ...]] = set()

    while queue:
        current = queue.popleft()
        if len(current.path) >= request.bounds.max_hops:
            continue
        for connection in _adjacent_connections(current.relation, read_access):
            if connection.artifact_id in current.used_connection_ids:
                continue
            next_relation = oriented_relation(connection, read_access, entity_types, connection_types)
            if next_relation is None:
                continue
            intermediate = shared_entity_info(current.relation, next_relation, read_access, entity_types)
            if intermediate is not None:
                step = compose(
                    current.relation,
                    next_relation,
                    intermediate,
                    rules,
                    permitted,
                    restrictions,
                )
                if step is None or (step.certainty == "potential" and request.certainty == "certain_only"):
                    continue
                path = current.path + ((connection.artifact_id, "fwd"),)
                path_ids = tuple(item[0] for item in path)
                if path_ids in seen_paths:
                    continue
                seen_paths.add(path_ids)
                next_item = _FrontierItem(
                    _derived_relation(step, path),
                    path,
                    current.used_connection_ids | {connection.artifact_id},
                )
                _record_if_incident(step, path, request, results)
                queue.append(next_item)
                if len(results) > request.bounds.max_relationships:
                    raise DerivationLimitError(request.bounds.max_relationships)
    ordered = tuple(sorted(results.values(), key=lambda relationship: relationship.artifact_id))
    return DerivedRelationshipSet(ordered)


def _initial_frontier(
    anchors: frozenset[str],
    max_hops: int,
    read_access: CriteriaReadAccess,
    entity_types: Mapping[EntityTypeName, EntityTypeInfo],
    connection_types: Mapping[ConnectionTypeName, ConnectionTypeInfo],
) -> Iterable[_FrontierItem]:
    discovered: dict[str, ConnectionRecord] = {}
    pending = deque((anchor, 0) for anchor in sorted(anchors))
    visited_entities: set[str] = set()
    while pending:
        entity_id, depth = pending.popleft()
        if entity_id in visited_entities or depth >= max_hops:
            continue
        visited_entities.add(entity_id)
        for connection in read_access.find_connections_for(entity_id, direction="any"):
            discovered.setdefault(connection.artifact_id, connection)
            neighbor = connection.target if connection.source == entity_id else connection.source
            if read_access.get_entity(neighbor) is not None:
                pending.append((neighbor, depth + 1))
    for connection_id in sorted(discovered):
        relation = oriented_relation(discovered[connection_id], read_access, entity_types, connection_types)
        if relation is not None:
            yield _FrontierItem(relation, ((connection_id, "fwd"),), frozenset({connection_id}))


def _adjacent_connections(relation: OrientedRelation, read_access: CriteriaReadAccess) -> Iterable[ConnectionRecord]:
    seen: set[str] = set()
    for entity_id in (relation.source_id, relation.target_id):
        for connection in read_access.find_connections_for(entity_id, direction="any"):
            if connection.artifact_id not in seen:
                seen.add(connection.artifact_id)
                yield connection


def _derived_relation(step: DerivedStep, path: tuple[tuple[str, Literal["fwd", "rev"]], ...]) -> OrientedRelation:
    return OrientedRelation(
        f"derived:{step.connection_type.artifact_type}:{_path_key(path)}",
        step.connection_type,
        step.source_id,
        step.target_id,
        source_info=step.source_info,
        target_info=step.target_info,
        source_type=EntityTypeName(step.source_info.artifact_type) if step.source_info is not None else None,
        target_type=EntityTypeName(step.target_info.artifact_type) if step.target_info is not None else None,
        potential_steps=step.potential_steps,
    )


def _record_if_incident(
    step: DerivedStep,
    path: tuple[tuple[str, Literal["fwd", "rev"]], ...],
    request: RelationshipDerivationRequest,
    results: dict[tuple[str, str, str], DerivedRelationship],
) -> None:
    if not _matches_direction(step, request.anchors, request.direction):
        return
    path_key = _path_key(path)
    candidate = DerivedRelationship(
        f"derived::{step.connection_type.artifact_type}::{path_key}",
        step.source_id,
        step.target_id,
        step.connection_type.artifact_type,
        step.certainty,
        len(path),
        tuple(item[0] for item in path),
        path_key,
    )
    key = (candidate.source_id, candidate.target_id, candidate.connection_type)
    existing = results.get(key)
    if existing is None or _is_better(candidate, existing):
        results[key] = candidate


def _matches_direction(step: DerivedStep, anchors: frozenset[str], direction: IncidentDirection) -> bool:
    if direction == "outgoing":
        return step.source_id in anchors
    if direction == "incoming":
        return step.target_id in anchors
    return step.source_id in anchors or step.target_id in anchors


def _is_better(candidate: DerivedRelationship, existing: DerivedRelationship) -> bool:
    if candidate.certainty != existing.certainty:
        return candidate.certainty == "certain"
    if candidate.hops != existing.hops:
        return candidate.hops < existing.hops
    return candidate.path_key < existing.path_key


def _path_key(path: tuple[tuple[str, Literal["fwd", "rev"]], ...]) -> str:
    return "|".join(f"{connection_id}@{orientation}" for connection_id, orientation in path)
