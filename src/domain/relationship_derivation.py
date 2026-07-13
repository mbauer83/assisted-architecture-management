"""Pure relationship-derivation types and certain pairwise composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, cast

from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.relationship_derivation_rules import CERTAIN_COMPOSITION_RULES, Certainty, CompositionRule

DerivationDomain = Literal["motivation", "strategy", "core", "implementation_migration", "relationships"]
Orientation = Literal["forward", "reverse"]


@dataclass(frozen=True)
class OrientedRelation:
    connection_id: str
    connection_type: ConnectionTypeInfo
    source_id: str
    target_id: str
    orientation: Orientation = "forward"


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
) -> DerivedStep | None:
    """Derive one certain relationship from an oriented, joined pair."""
    if first.target_id != second.source_id or first.source_id == second.target_id:
        return None
    if "junction" in intermediate.classes:
        return None
    for rule in CERTAIN_COMPOSITION_RULES:
        if not _matches(rule, first, second):
            continue
        result = _result_type(rule, first.connection_type, second.connection_type)
        if result is None:
            continue
        source_id, target_id = _endpoints(rule, first, second)
        return DerivedStep(source_id, target_id, result, rule.certainty)
    return None


def fold_chain(
    relations: tuple[OrientedRelation, ...],
    intermediates: tuple[EntityTypeInfo, ...],
    connection_types: Mapping[str, ConnectionTypeInfo],
) -> DerivedStep | None:
    """Left-fold a chain using the same composition operation as pairwise derivation."""
    if len(relations) < 2 or len(intermediates) != len(relations) - 1:
        return None
    current = relations[0]
    potential_steps = 0
    for next_relation, intermediate in zip(relations[1:], intermediates, strict=True):
        step = compose(current, next_relation, intermediate)
        if step is None:
            return None
        potential_steps += step.potential_steps
        current = OrientedRelation(
            connection_id=f"derived:{current.connection_id}:{next_relation.connection_id}",
            connection_type=step.connection_type,
            source_id=step.source_id,
            target_id=step.target_id,
        )
    return DerivedStep(current.source_id, current.target_id, current.connection_type, "certain", potential_steps)


def _matches(rule: CompositionRule, first: OrientedRelation, second: OrientedRelation) -> bool:
    if first.connection_type.derivation_role != rule.first_role:
        return False
    if second.connection_type.derivation_role != rule.second_role:
        return False
    if rule.second_orientation != "either" and second.orientation != rule.second_orientation:
        return False
    if rule.result == "flow" and second.connection_type.artifact_type != "archimate-flow":
        return False
    if rule.result == "triggering" and first.connection_type.artifact_type != "archimate-triggering":
        return False
    return rule.result != "triggering" or (
        rule.spec_ref == "DR8" and second.connection_type.artifact_type == "archimate-triggering"
        or rule.spec_ref != "DR8"
    )


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
    if rule.second_orientation == "reverse":
        return second.target_id, first.source_id
    return first.source_id, second.target_id
