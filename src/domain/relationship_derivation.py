"""Pure relationship-derivation types and certain pairwise composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from src.domain.module_types import ConnectionTypeName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet
from src.domain.relationship_derivation_rules import Certainty, CompositionRule

DerivationDomain = Literal["motivation", "strategy", "core", "implementation_migration", "relationships"]
Orientation = Literal["forward", "reverse"]


@dataclass(frozen=True)
class OrientedRelation:
    connection_id: str
    connection_type: ConnectionTypeInfo
    source_id: str
    target_id: str
    orientation: Orientation = "forward"
    source_type: EntityTypeName | None = None
    target_type: EntityTypeName | None = None


@dataclass(frozen=True)
class DerivedStep:
    source_id: str
    target_id: str
    connection_type: ConnectionTypeInfo
    certainty: Certainty
    potential_steps: int = 0


def derivation_domain(info: EntityTypeInfo) -> DerivationDomain:
    if "junction" in info.classes:
        return "relationships"
    if not info.hierarchy:
        raise ValueError(f"entity type {info.artifact_type!r} has no hierarchy")
    head = info.hierarchy[0]
    if head in {"business", "application", "technology", "common"}:
        return "core"
    if head == "implementation":
        return "implementation_migration"
    if head in {"motivation", "strategy"}:
        return cast(DerivationDomain, head)
    raise ValueError(f"entity type {info.artifact_type!r} has unknown derivation domain {head!r}")


def compose(
    first: OrientedRelation,
    second: OrientedRelation,
    intermediate: EntityTypeInfo,
    rules: tuple[CompositionRule, ...],
    permitted_relationships: PermittedRelationshipSet | None = None,
) -> DerivedStep | None:
    """Derive one relationship from an oriented, joined pair."""
    if "junction" in intermediate.classes:
        return None
    for rule in rules:
        if not _matches(rule, first, second, intermediate):
            continue
        result = _result_type(rule, first.connection_type, second.connection_type)
        if result is None:
            continue
        source_id, target_id = _endpoints(rule, first, second)
        if source_id == target_id:
            return None
        source_type, target_type = _endpoint_types(rule, first, second)
        if rule.requires_permitted_result and (
            source_type is None
            or target_type is None
            or permitted_relationships is None
            or not permitted_relationships.permits(source_type, target_type, ConnectionTypeName(result.artifact_type))
        ):
            return None
        return DerivedStep(source_id, target_id, result, rule.certainty, int(rule.certainty == "potential"))
    return None


def fold_chain(
    relations: tuple[OrientedRelation, ...],
    intermediates: tuple[EntityTypeInfo, ...],
    rules: tuple[CompositionRule, ...],
) -> DerivedStep | None:
    """Left-fold a chain using the same composition operation as pairwise derivation."""
    if len(relations) < 2 or len(intermediates) != len(relations) - 1:
        return None
    current = relations[0]
    potential_steps = 0
    certainty: Certainty = "certain"
    for next_relation, intermediate in zip(relations[1:], intermediates, strict=True):
        step = compose(current, next_relation, intermediate, rules)
        if step is None:
            return None
        potential_steps += step.potential_steps
        if step.certainty == "potential":
            certainty = "potential"
        current = OrientedRelation(
            connection_id=f"derived:{current.connection_id}:{next_relation.connection_id}",
            connection_type=step.connection_type,
            source_id=step.source_id,
            target_id=step.target_id,
        )
    return DerivedStep(current.source_id, current.target_id, current.connection_type, certainty, potential_steps)


def _matches(
    rule: CompositionRule,
    first: OrientedRelation,
    second: OrientedRelation,
    intermediate: EntityTypeInfo,
) -> bool:
    if first.connection_type.derivation_role != rule.first_role:
        return False
    if second.connection_type.derivation_role != rule.second_role:
        return False
    if not _joins(rule.join, first, second):
        return False
    if rule.first_artifact_type is not None and first.connection_type.artifact_type != rule.first_artifact_type:
        return False
    if rule.second_artifact_type is not None and second.connection_type.artifact_type != rule.second_artifact_type:
        return False
    if rule.second_artifact_types and second.connection_type.artifact_type not in rule.second_artifact_types:
        return False
    return rule.intermediate_artifact_type is None or intermediate.artifact_type == rule.intermediate_artifact_type


def _result_type(
    rule: CompositionRule,
    first: ConnectionTypeInfo,
    second: ConnectionTypeInfo,
) -> ConnectionTypeInfo | None:
    if rule.result == "first":
        return first
    if rule.result == "second":
        return second
    if rule.result == "specialization":
        return first
    if rule.result in {"triggering", "flow"}:
        return first if rule.result == "triggering" else second
    if first.derivation_strength is None or second.derivation_strength is None:
        return None
    return first if first.derivation_strength <= second.derivation_strength else second


def _endpoints(rule: CompositionRule, first: OrientedRelation, second: OrientedRelation) -> tuple[str, str]:
    values = {
        "first-source": _source(first),
        "first-target": _target(first),
        "second-source": _source(second),
        "second-target": _target(second),
    }
    return values[rule.result_source], values[rule.result_target]


def _endpoint_types(
    rule: CompositionRule,
    first: OrientedRelation,
    second: OrientedRelation,
) -> tuple[EntityTypeName | None, EntityTypeName | None]:
    values = {
        "first-source": _source_type(first),
        "first-target": _target_type(first),
        "second-source": _source_type(second),
        "second-target": _target_type(second),
    }
    return values[rule.result_source], values[rule.result_target]


def _joins(join: str, first: OrientedRelation, second: OrientedRelation) -> bool:
    endpoints = {
        "target-source": (_target(first), _source(second)),
        "target-target": (_target(first), _target(second)),
        "source-source": (_source(first), _source(second)),
        "source-target": (_source(first), _target(second)),
    }
    left, right = endpoints[join]
    return left == right


def _source(relation: OrientedRelation) -> str:
    return relation.source_id if relation.orientation == "forward" else relation.target_id


def _target(relation: OrientedRelation) -> str:
    return relation.target_id if relation.orientation == "forward" else relation.source_id


def _source_type(relation: OrientedRelation) -> EntityTypeName | None:
    return relation.source_type if relation.orientation == "forward" else relation.target_type


def _target_type(relation: OrientedRelation) -> EntityTypeName | None:
    return relation.target_type if relation.orientation == "forward" else relation.source_type
