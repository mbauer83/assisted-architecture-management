"""Repository execution for viewpoint definitions that declare only a concept scope."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.application.viewpoints.evaluate_viewpoint import ViewpointExecutionRequest, evaluate_viewpoint
from src.domain.concept_scope import ConceptScope, HierarchyPredicate
from src.domain.ontology_types import EntityTypeInfo
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria import AttributeCondition, EntityCriteriaGroup, ValueRef
from src.domain.viewpoint_parsing import viewpoint_catalog_from_mapping
from src.domain.viewpoints import ExecutableViewpointQuery, ViewpointCatalog, ViewpointDefinition
from tests.application.viewpoints._fixtures import REGISTRIES, Store, connection, entity

_VIEWPOINTS_PATH = Path("src/ontologies/archimate_4/viewpoints.yaml")
_EXECUTION_DEFAULTS: dict[str, object] = {
    "max_entities": 500,
    "default_limit": 500,
    "timeout_seconds": 10.0,
    "index_generation": None,
}


def _execute(definition: ViewpointDefinition, store: Store, *, registries: RegistrySnapshot = REGISTRIES):
    return evaluate_viewpoint(
        ViewpointExecutionRequest(slug=definition.slug),
        catalog=ViewpointCatalog((definition,)),
        read_access=store,
        registries=registries,
        **_EXECUTION_DEFAULTS,
    )


def _starter_catalog() -> ViewpointCatalog:
    raw = yaml.safe_load(_VIEWPOINTS_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return viewpoint_catalog_from_mapping(raw)


def test_each_shipped_scope_only_definition_selects_its_seeded_population() -> None:
    catalog = _starter_catalog()
    store = Store(
        entities={
            "ENT@motivation": entity(artifact_id="ENT@motivation", artifact_type="goal"),
            "ENT@application": entity(artifact_id="ENT@application", artifact_type="application-component"),
            "ENT@technology": entity(artifact_id="ENT@technology", artifact_type="technology-node"),
        }
    )

    expected = {
        "motivation": {"ENT@motivation"},
        "application-structure": {"ENT@application"},
        "layered": {"ENT@application", "ENT@motivation", "ENT@technology"},
        "technology-usage": {"ENT@application", "ENT@technology"},
    }
    for slug, entity_ids in expected.items():
        definition = catalog.get(slug)
        assert definition is not None
        result = _execute(definition, store)
        assert set(result.entity_ids) == entity_ids
        assert result.query_summary.startswith("Selection derived from the viewpoint's concept scope: ")


def test_scope_predicates_are_applied_after_the_implicit_type_criteria() -> None:
    definition = ViewpointDefinition(
        slug="classified",
        version=1,
        name="Classified",
        scope=ConceptScope(
            entity_class_predicates=(frozenset({"active-structure-element"}),),
            hierarchy_predicates=(HierarchyPredicate(0, frozenset({"application"})),),
        ),
    )
    infos = {
        "application-component": EntityTypeInfo(
            artifact_type="application-component",
            prefix="APP",
            hierarchy=("application",),
            classes=("active-structure-element",),
            create_when="",
            never_create_when="",
        ),
        "process": EntityTypeInfo(
            artifact_type="process",
            prefix="PRC",
            hierarchy=("common",),
            classes=("behavior-element",),
            create_when="",
            never_create_when="",
        ),
    }
    registries = RegistrySnapshot(
        known_entity_types=frozenset(infos),
        known_connection_types=frozenset(),
        known_specialization_slugs=frozenset(),
        entity_attribute_types={},
        connection_attribute_types={},
        entity_type_infos=infos,
    )
    store = Store(
        entities={
            "ENT@app": entity(artifact_id="ENT@app", artifact_type="application-component"),
            "ENT@process": entity(artifact_id="ENT@process", artifact_type="process"),
        }
    )

    assert _execute(definition, store, registries=registries).entity_ids == ("ENT@app",)


def test_scope_connection_types_narrow_the_implicit_connection_selection() -> None:
    definition = ViewpointDefinition(
        slug="connections",
        version=1,
        name="Connections",
        scope=ConceptScope(connection_types=frozenset({"archimate-serving"})),
    )
    store = Store(
        entities={"ENT@A": entity(artifact_id="ENT@A"), "ENT@B": entity(artifact_id="ENT@B")},
        connections=[
            connection(artifact_id="CON@serving", source="ENT@A", target="ENT@B", conn_type="archimate-serving"),
            connection(artifact_id="CON@access", source="ENT@A", target="ENT@B", conn_type="archimate-access"),
        ],
    )

    assert _execute(definition, store).connection_ids == ("CON@serving",)


def test_ad_hoc_query_is_not_replaced_by_scope_fallback() -> None:
    query = ExecutableViewpointQuery(
        entity_criteria=EntityCriteriaGroup(
            children=(AttributeCondition(attribute="type", comparator="eq", value=ValueRef(literal="process")),)
        )
    )
    store = Store(
        entities={
            "ENT@app": entity(artifact_id="ENT@app", artifact_type="application-component"),
            "ENT@process": entity(artifact_id="ENT@process", artifact_type="process"),
        }
    )
    result = evaluate_viewpoint(
        ViewpointExecutionRequest(query=query),
        catalog=ViewpointCatalog.empty(),
        read_access=store,
        registries=REGISTRIES,
        **_EXECUTION_DEFAULTS,
    )

    assert result.entity_ids == ("ENT@process",)
    assert not result.query_summary.startswith("Selection derived from")
