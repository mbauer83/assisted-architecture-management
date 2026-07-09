"""Tests for ConceptScope predicates and intersections."""

from __future__ import annotations

from src.domain.concept_scope import ConceptScope, EndpointRule, HierarchyPredicate
from src.domain.module_types import ConnectionTypeName, EntityTypeName
from src.domain.ontology_types import EntityTypeInfo


def _entity_info(artifact_type: str, hierarchy: tuple[str, ...], classes: tuple[str, ...] = ()) -> EntityTypeInfo:
    return EntityTypeInfo(
        artifact_type=artifact_type,
        prefix=artifact_type[:3].upper(),
        hierarchy=hierarchy,
        classes=classes,
        create_when="",
        never_create_when="",
    )


def test_unrestricted_scope_admits_any_type() -> None:
    scope = ConceptScope.unrestricted()

    assert scope.admits_entity_type(EntityTypeName("service")) is True
    assert scope.admits_connection_type(ConnectionTypeName("archimate-serving")) is True
    assert scope.admits_connection(
        EntityTypeName("service"),
        EntityTypeName("role"),
        ConnectionTypeName("archimate-serving"),
    )


def test_entity_scope_combines_explicit_class_and_hierarchy_predicates() -> None:
    service = _entity_info("service", ("business", "service"), ("behavior", "external"))
    process = _entity_info("process", ("business", "process"), ("behavior",))
    technology_service = _entity_info("service", ("technology", "service"), ("behavior", "external"))
    scope = ConceptScope(
        entity_types=frozenset({EntityTypeName("service"), EntityTypeName("process")}),
        entity_class_predicates=(frozenset({"external"}),),
        hierarchy_predicates=(HierarchyPredicate(index=0, values=frozenset({"business"})),),
    )

    assert scope.admits_entity_type(EntityTypeName("service"), service) is True
    assert scope.admits_entity_type(EntityTypeName("process"), process) is False
    assert scope.admits_entity_type(EntityTypeName("service"), technology_service) is False
    assert scope.admits_entity_type(EntityTypeName("unknown"), service) is False
    assert scope.admits_entity_type(EntityTypeName("service")) is False


def test_connection_scope_applies_endpoint_rules_when_present() -> None:
    scope = ConceptScope(
        connection_types=frozenset({ConnectionTypeName("archimate-flow")}),
        endpoint_rules=(
            EndpointRule(
                connection_type=ConnectionTypeName("archimate-flow"),
                source_types=frozenset({EntityTypeName("business-actor")}),
                target_types=frozenset({EntityTypeName("role")}),
            ),
        ),
    )

    assert scope.admits_connection_type(ConnectionTypeName("archimate-flow")) is True
    assert scope.admits_connection_type(ConnectionTypeName("archimate-serving")) is False
    assert scope.admits_connection(
        EntityTypeName("business-actor"),
        EntityTypeName("role"),
        ConnectionTypeName("archimate-flow"),
    )
    assert not scope.admits_connection(
        EntityTypeName("role"),
        EntityTypeName("business-actor"),
        ConnectionTypeName("archimate-flow"),
    )


def test_intersection_combines_type_sets_and_predicates() -> None:
    left = ConceptScope(
        entity_types=frozenset({EntityTypeName("service"), EntityTypeName("process"), EntityTypeName("role")}),
        hierarchy_predicates=(HierarchyPredicate(index=0, values=frozenset({"business", "application"})),),
        connection_types=frozenset({ConnectionTypeName("archimate-flow"), ConnectionTypeName("archimate-serving")}),
        endpoint_rules=(
            EndpointRule(
                connection_type=ConnectionTypeName("archimate-flow"),
                source_types=frozenset({EntityTypeName("service"), EntityTypeName("process")}),
            ),
        ),
    )
    right = ConceptScope(
        entity_types=frozenset({EntityTypeName("service"), EntityTypeName("role")}),
        hierarchy_predicates=(HierarchyPredicate(index=0, values=frozenset({"business"})),),
        connection_types=frozenset({ConnectionTypeName("archimate-flow")}),
        endpoint_rules=(
            EndpointRule(
                connection_type=ConnectionTypeName("archimate-flow"),
                source_types=frozenset({EntityTypeName("service")}),
                target_types=frozenset({EntityTypeName("role")}),
            ),
        ),
    )

    scope = left & right
    service = _entity_info("service", ("business", "service"), ("behavior",))

    assert scope.entity_types == frozenset({EntityTypeName("service"), EntityTypeName("role")})
    assert scope.hierarchy_predicates == (HierarchyPredicate(index=0, values=frozenset({"business"})),)
    assert scope.connection_types == frozenset({ConnectionTypeName("archimate-flow")})
    assert scope.admits_entity_type(EntityTypeName("service"), service)
    assert scope.admits_connection(
        EntityTypeName("service"),
        EntityTypeName("role"),
        ConnectionTypeName("archimate-flow"),
    )
    assert not scope.admits_connection(
        EntityTypeName("process"),
        EntityTypeName("role"),
        ConnectionTypeName("archimate-flow"),
    )
