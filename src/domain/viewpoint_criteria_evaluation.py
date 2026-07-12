"""Tree-recursive evaluation over ``EntityCriteriaGroup``/``ConnectionCriteriaGroup``
(companion plan §3.4): the pure entry points ``evaluate_entity_criteria``/
``evaluate_connection_criteria`` that ``NeighborInclusion``/``ConnectionSelection``
resolution (``viewpoint_population_evaluation.py``) and the eventual execution use case
build on. Leaf conditions delegate to ``viewpoint_condition_evaluation.py``.
"""

from __future__ import annotations

from src.domain.artifact_types import ConnectionRecord, EntityRecord
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
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess, EvaluationOutcome


def direction_matches(
    connection: ConnectionRecord, entity_id: str, direction: IncidentDirection, registries: RegistrySnapshot
) -> bool:
    """Symmetric-type direction normalization (§3.4): a symmetric connection type's
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
    group: EntityCriteriaGroup, entity: EntityRecord, *, read_access: CriteriaReadAccess, registries: RegistrySnapshot
) -> EvaluationOutcome:
    outcomes = tuple(
        _evaluate_entity_node(child, entity, read_access=read_access, registries=registries) for child in group.children
    )
    return _combine(outcomes, conjunction=group.conjunction, negate=group.negate)


def _evaluate_entity_node(
    node: EntityCriteriaNode, entity: EntityRecord, *, read_access: CriteriaReadAccess, registries: RegistrySnapshot
) -> EvaluationOutcome:
    if isinstance(node, EntityCriteriaGroup):
        return evaluate_entity_criteria(node, entity, read_access=read_access, registries=registries)
    if isinstance(node, IncidentConnectionCondition):
        return _evaluate_incident(node, entity, read_access=read_access, registries=registries)
    if isinstance(node, AttributeCondition):
        return evaluate_attribute_condition(
            node, record=entity, context="entity", read_access=read_access, registries=registries, connection=None
        )
    raise AssertionError(f"unhandled entity criteria node {node!r}")


def evaluate_connection_criteria(
    group: ConnectionCriteriaGroup,
    connection: ConnectionRecord,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
) -> EvaluationOutcome:
    outcomes = tuple(
        _evaluate_connection_node(child, connection, read_access=read_access, registries=registries)
        for child in group.children
    )
    return _combine(outcomes, conjunction=group.conjunction, negate=group.negate)


def _evaluate_connection_node(
    node: ConnectionCriteriaNode,
    connection: ConnectionRecord,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
) -> EvaluationOutcome:
    if isinstance(node, ConnectionCriteriaGroup):
        return evaluate_connection_criteria(node, connection, read_access=read_access, registries=registries)
    if isinstance(node, AttributeCondition):
        return evaluate_attribute_condition(
            node,
            record=connection,
            context="connection",
            read_access=read_access,
            registries=registries,
            connection=connection,
        )
    raise AssertionError(f"unhandled connection criteria node {node!r}")


def _evaluate_incident(
    condition: IncidentConnectionCondition,
    entity: EntityRecord,
    *,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
) -> EvaluationOutcome:
    drift: set[str] = set()
    any_match = False
    for connection in read_access.find_connections_for(entity.artifact_id, direction="any"):
        if condition.connection_criteria is not None:
            outcome = evaluate_connection_criteria(
                condition.connection_criteria, connection, read_access=read_access, registries=registries
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
                condition.endpoint_criteria, other_entity, read_access=read_access, registries=registries
            )
            drift |= outcome.schema_drift
            if not outcome.matched:
                continue
        any_match = True
    matched = not any_match if condition.negate else any_match
    return EvaluationOutcome(matched, frozenset(drift))
