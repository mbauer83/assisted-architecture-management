"""Tests for relationship-derived incident and neighbor query traversal."""

from __future__ import annotations

from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria import (
    AttributeCondition,
    ConnectionCriteriaGroup,
    EntityCriteriaGroup,
    IncidentConnectionCondition,
    NeighborInclusion,
    ValueRef,
)
from src.domain.viewpoint_criteria_evaluation import evaluate_entity_criteria
from src.domain.viewpoint_criteria_parsing import parse_entity_criteria_group, parse_neighbor_inclusion
from src.domain.viewpoint_criteria_serialization import entity_criteria_group_to_mapping, neighbor_inclusion_to_mapping
from src.domain.viewpoint_population_evaluation import resolve_neighbor_inclusions
from tests.fixtures.viewpoints.derivation_examples import catalog, financial_application, hosting_suite


def _registries() -> RegistrySnapshot:
    relationship_catalog = catalog()
    return RegistrySnapshot(
        known_entity_types=frozenset(relationship_catalog.all_entity_types()),
        known_connection_types=frozenset(relationship_catalog.all_connection_types()),
        known_specialization_slugs=frozenset(),
        entity_attribute_types={},
        connection_attribute_types={},
        derivation_catalog=relationship_catalog,
    )


def _type_criteria(name: str) -> ConnectionCriteriaGroup:
    return ConnectionCriteriaGroup(
        children=(AttributeCondition("type", "eq", ValueRef(literal=name)),),
    )


def test_derived_incident_finds_indirect_realization() -> None:
    graph = financial_application()
    condition = IncidentConnectionCondition(
        direction="outgoing",
        traversal="derived",
        max_hops=3,
        connection_criteria=_type_criteria("archimate-realization"),
        endpoint_criteria=EntityCriteriaGroup(
            children=(AttributeCondition("type", "eq", ValueRef(literal="service")),),
        ),
    )
    outcome = evaluate_entity_criteria(
        EntityCriteriaGroup(children=(condition,)),
        graph.entities["financial-application"],
        read_access=graph,
        registries=_registries(),
    )
    assert outcome.matched


def test_derived_neighbor_inclusion_adds_indirect_endpoint() -> None:
    graph = financial_application()
    result = resolve_neighbor_inclusions(
        frozenset({"financial-application"}),
        (
            NeighborInclusion(
                direction="outgoing",
                traversal="derived",
                max_hops=3,
                connection_criteria=_type_criteria("archimate-realization"),
            ),
        ),
        read_access=graph,
        registries=_registries(),
    )
    assert result.expanded_ids == frozenset({"payment-service"})


def test_derived_traversal_respects_potential_opt_in_and_hop_bound() -> None:
    graph = hosting_suite()
    without_potential = resolve_neighbor_inclusions(
        frozenset({"database-hosting"}),
        (NeighborInclusion(direction="outgoing", traversal="derived", max_hops=2),),
        read_access=graph,
        registries=_registries(),
    )
    with_potential = resolve_neighbor_inclusions(
        frozenset({"database-hosting"}),
        (NeighborInclusion(direction="outgoing", traversal="derived", include_potential=True, max_hops=2),),
        read_access=graph,
        registries=_registries(),
    )
    too_shallow = resolve_neighbor_inclusions(
        frozenset({"financial-application"}),
        (
            NeighborInclusion(
                direction="outgoing",
                traversal="derived",
                max_hops=2,
                connection_criteria=_type_criteria("archimate-realization"),
            ),
        ),
        read_access=financial_application(),
        registries=_registries(),
    )
    assert without_potential.expanded_ids == frozenset()
    assert with_potential.expanded_ids == frozenset({"front-end", "back-end"})
    assert too_shallow.expanded_ids == frozenset()


def test_direct_incident_does_not_change_when_derived_traversal_is_available() -> None:
    graph = financial_application()
    condition = IncidentConnectionCondition(
        direction="outgoing",
        connection_criteria=_type_criteria("archimate-assignment"),
    )
    outcome = evaluate_entity_criteria(
        EntityCriteriaGroup(children=(condition,)),
        graph.entities["financial-application"],
        read_access=graph,
        registries=_registries(),
    )
    assert outcome.matched


def test_derived_traversal_round_trips_through_the_query_grammar() -> None:
    incident_raw = {
        "kind": "group",
        "conjunction": "and",
        "children": [{"kind": "incident", "traversal": "derived", "include_potential": True, "max_hops": 3}],
    }
    inclusion_raw = {"traversal": "derived", "include_potential": True, "max_hops": 3}
    assert entity_criteria_group_to_mapping(parse_entity_criteria_group(incident_raw)) == incident_raw
    assert neighbor_inclusion_to_mapping(parse_neighbor_inclusion(inclusion_raw)) == inclusion_raw
