"""Build executable selections from a viewpoint's declared concept scope."""

from __future__ import annotations

from dataclasses import replace

from src.domain.concept_scope import ConceptScope
from src.domain.viewpoint_criteria import (
    AttributeCondition,
    ConnectionCriteriaGroup,
    ConnectionSelection,
    EntityCriteriaGroup,
    ValueRef,
)
from src.domain.viewpoints import ExecutableViewpointQuery, ViewpointDefinition


def definition_with_scope_query(definition: ViewpointDefinition) -> tuple[ViewpointDefinition, bool]:
    """Return a definition with an implicit query when it only declares a scope."""
    if definition.query is not None:
        return definition, False
    return replace(definition, query=query_from_scope(definition.scope)), True


def query_from_scope(scope: ConceptScope) -> ExecutableViewpointQuery:
    """Translate type restrictions to criteria while retaining richer scope checks."""
    entity_criteria = EntityCriteriaGroup()
    if scope.entity_types is not None:
        entity_criteria = EntityCriteriaGroup(
            children=(
                AttributeCondition(
                    attribute="type",
                    comparator="in",
                    value=ValueRef(literal=sorted(scope.entity_types)),
                ),
            )
        )
    connections = ConnectionSelection()
    if scope.connection_types is not None:
        connections = ConnectionSelection(
            criteria=ConnectionCriteriaGroup(
                children=(
                    AttributeCondition(
                        attribute="type",
                        comparator="in",
                        value=ValueRef(literal=sorted(scope.connection_types)),
                    ),
                )
            )
        )
    return ExecutableViewpointQuery(entity_criteria=entity_criteria, connections=connections)
