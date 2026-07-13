"""Tree-recursive evaluation over ``EntityCriteriaGroup``/``ConnectionCriteriaGroup``:
the pure entry points ``evaluate_entity_criteria``/
``evaluate_connection_criteria`` that ``NeighborInclusion``/``ConnectionSelection``
resolution (``viewpoint_population_evaluation.py``) and the eventual execution use case
build on. Leaf conditions delegate to ``viewpoint_condition_evaluation.py``.
"""

from __future__ import annotations

from typing import cast

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.relationship_reachability import DerivationBounds, RelationshipDerivationRequest, derive_relationships
from src.domain.viewpoint_condition_evaluation import evaluate_attribute_condition
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria import (
    AttributeCondition,
    ConnectionCriteriaGroup,
    ConnectionCriteriaNode,
    EntityCriteriaGroup,
    EntityCriteriaNode,
    IncidentConnectionCondition,
    IncidentDirection,
)
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess, EvaluationEnvironment, EvaluationOutcome


def direction_matches(
    connection: ConnectionRecord, entity_id: str, direction: IncidentDirection, registries: RegistrySnapshot
) -> bool:
    """Symmetric-type direction normalization: a symmetric connection type's
    direction test always passes, regardless of the requested direction — source/target
    order is authoring order, not semantics, for those types."""
    if direction == "either":
        return True
    if connection.conn_type in registries.symmetric_connection_types:
        return True
    actual: IncidentDirection = "outgoing" if connection.source == entity_id else "incoming"
    return actual == direction


def _combine(outcomes: tuple[EvaluationOutcome, ...], *, conjunction: str, negate: bool) -> EvaluationOutcome:
    drift = frozenset().union(*(outcome.schema_drift for outcome in outcomes)) if outcomes else frozenset()
    if conjunction == "and":
        matched = all(outcome.matched for outcome in outcomes) if outcomes else True
    else:
        matched = any(outcome.matched for outcome in outcomes) if outcomes else False
    return EvaluationOutcome(not matched if negate else matched, drift)


def evaluate_entity_criteria(
    group: EntityCriteriaGroup,
    entity: EntityRecord,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment = EvaluationEnvironment(),
) -> EvaluationOutcome:
    outcomes = tuple(
        _evaluate_entity_node(child, entity, read_access, registries, environment) for child in group.children
    )
    return _combine(outcomes, conjunction=group.conjunction, negate=group.negate)


def _evaluate_entity_node(
    node: EntityCriteriaNode,
    entity: EntityRecord,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment,
) -> EvaluationOutcome:
    if isinstance(node, EntityCriteriaGroup):
        return evaluate_entity_criteria(
            node, entity, read_access=read_access, registries=registries, environment=environment
        )
    if isinstance(node, IncidentConnectionCondition):
        return _evaluate_incident(node, entity, read_access=read_access, registries=registries, environment=environment)
    if isinstance(node, AttributeCondition):
        return evaluate_attribute_condition(
            node,
            record=entity,
            context="entity",
            read_access=read_access,
            registries=registries,
            connection=None,
            environment=environment,
        )
    raise AssertionError(f"unhandled entity criteria node {node!r}")


def evaluate_connection_criteria(
    group: ConnectionCriteriaGroup,
    connection: ConnectionRecord,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment = EvaluationEnvironment(),
) -> EvaluationOutcome:
    outcomes = tuple(
        _evaluate_connection_node(
            child, connection, read_access=read_access, registries=registries, environment=environment
        )
        for child in group.children
    )
    return _combine(outcomes, conjunction=group.conjunction, negate=group.negate)


def _evaluate_connection_node(
    node: ConnectionCriteriaNode,
    connection: ConnectionRecord,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment,
) -> EvaluationOutcome:
    if isinstance(node, ConnectionCriteriaGroup):
        return evaluate_connection_criteria(
            node, connection, read_access=read_access, registries=registries, environment=environment
        )
    if isinstance(node, AttributeCondition):
        return evaluate_attribute_condition(
            node,
            record=connection,
            context="connection",
            read_access=read_access,
            registries=registries,
            connection=connection,
            environment=environment,
        )
    raise AssertionError(f"unhandled connection criteria node {node!r}")


def _evaluate_incident(
    condition: IncidentConnectionCondition,
    entity: EntityRecord,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment,
) -> EvaluationOutcome:
    if condition.traversal == "derived":
        return _evaluate_derived_incident(condition, entity, read_access, registries, environment)
    drift: set[str] = set()
    any_match = False
    for connection in read_access.find_connections_for(entity.artifact_id, direction="any"):
        if condition.connection_criteria is not None:
            outcome = evaluate_connection_criteria(
                condition.connection_criteria,
                connection,
                read_access=read_access,
                registries=registries,
                environment=environment,
            )
            drift |= outcome.schema_drift
            if not outcome.matched:
                continue
        if not direction_matches(connection, entity.artifact_id, condition.direction, registries):
            continue
        other_id = connection.target if connection.source == entity.artifact_id else connection.source
        other_entity = read_access.get_entity(other_id)
        if other_entity is None:
            continue  # dangling endpoint never matches
        if condition.endpoint_criteria is not None:
            outcome = evaluate_entity_criteria(
                condition.endpoint_criteria,
                other_entity,
                read_access=read_access,
                registries=registries,
                environment=environment,
            )
            drift |= outcome.schema_drift
            if not outcome.matched:
                continue
        any_match = True
    matched = not any_match if condition.negate else any_match
    return EvaluationOutcome(matched, frozenset(drift))


def _evaluate_derived_incident(
    condition: IncidentConnectionCondition,
    entity: EntityRecord,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    environment: EvaluationEnvironment,
) -> EvaluationOutcome:
    if registries.derivation_catalog is None:
        return EvaluationOutcome(condition.negate)
    relationships = derive_relationships(
        RelationshipDerivationRequest(
            frozenset({entity.artifact_id}),
            condition.direction,
            "include_potential" if condition.include_potential else "certain_only",
            DerivationBounds(
                condition.max_hops or registries.derivation_max_hops,
                registries.derivation_max_relationships,
                registries.derivation_time_budget_seconds,
            ),
        ),
        read_access=read_access,
        registries=registries.derivation_catalog,
    ).relationships
    drift: set[str] = set()
    for relationship in relationships:
        if condition.connection_criteria is not None and not _derived_matches(
            condition.connection_criteria, relationship.connection_type, relationship.certainty, relationship.hops
        ):
            continue
        other_id = relationship.target_id if relationship.source_id == entity.artifact_id else relationship.source_id
        endpoint = read_access.get_entity(other_id)
        if endpoint is None:
            continue
        if condition.endpoint_criteria is not None:
            outcome = evaluate_entity_criteria(
                condition.endpoint_criteria,
                endpoint,
                read_access=read_access,
                registries=registries,
                environment=environment,
            )
            drift |= outcome.schema_drift
            if not outcome.matched:
                continue
        return EvaluationOutcome(not condition.negate, frozenset(drift))
    return EvaluationOutcome(condition.negate, frozenset(drift))


def _derived_matches(group: ConnectionCriteriaGroup, type_name: str, certainty: str, hops: int) -> bool:
    outcomes = tuple(_derived_node_matches(child, type_name, certainty, hops) for child in group.children)
    matched = all(outcomes) if group.conjunction == "and" else any(outcomes)
    return not matched if group.negate else matched


def _derived_node_matches(node: ConnectionCriteriaNode, type_name: str, certainty: str, hops: int) -> bool:
    if isinstance(node, ConnectionCriteriaGroup):
        return _derived_matches(node, type_name, certainty, hops)
    values = {"type": type_name, "certainty": certainty, "hops": hops}
    actual = values.get(node.attribute)
    if actual is None or node.value.kind != "literal":
        return False
    matched = _derived_compare(node.comparator, actual, node.value.literal)
    return not matched if node.negate else matched


def _derived_compare(comparator: str, actual: object, expected: object) -> bool:
    if comparator == "eq":
        return actual == expected
    if comparator == "neq":
        return actual != expected
    if comparator == "in":
        return isinstance(expected, (list, tuple)) and actual in expected
    if comparator == "exists":
        return True
    if comparator == "absent":
        return False
    if isinstance(actual, str) and isinstance(expected, str):
        return _ordered_compare(comparator, actual, expected)
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return _ordered_compare(comparator, actual, expected)
    return False


def _ordered_compare(comparator: str, actual: str | int | float, expected: str | int | float) -> bool:
    if isinstance(actual, str):
        return _ordered_strings(comparator, actual, cast(str, expected))
    return _ordered_numbers(comparator, actual, cast(int | float, expected))


def _ordered_strings(comparator: str, actual: str, expected: str) -> bool:
    if comparator == "lt":
        return actual < expected
    if comparator == "lte":
        return actual <= expected
    if comparator == "gt":
        return actual > expected
    if comparator == "gte":
        return actual >= expected
    raise AssertionError(f"unsupported comparator {comparator!r}")


def _ordered_numbers(comparator: str, actual: int | float, expected: int | float) -> bool:
    if comparator == "lt":
        return actual < expected
    if comparator == "lte":
        return actual <= expected
    if comparator == "gt":
        return actual > expected
    if comparator == "gte":
        return actual >= expected
    raise AssertionError(f"unsupported comparator {comparator!r}")
