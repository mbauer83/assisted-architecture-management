"""Tests for the shipped Appendix-C default viewpoint library
(``src/ontologies/archimate_4/viewpoints.yaml``): every definition validates cleanly and
returns a non-empty population on a seeded fixture repo. Spec-fidelity comparison lives
in ``test_default_viewpoint_library_spec_fidelity.py``; the common-type-mapping proof
lives in ``test_default_viewpoint_library_common_types.py``.
"""

from __future__ import annotations

from src.application.viewpoints.evaluate_viewpoint import ViewpointExecutionRequest, evaluate_viewpoint
from src.application.viewpoints.registry_snapshot import build_registry_snapshot
from src.domain.viewpoint_validation import validate_viewpoint_definition
from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry
from tests.application.viewpoints._fixtures import Store, entity
from tests.fixtures.viewpoints.standard_viewpoint_tables import STANDARD_VIEWPOINT_TABLES

_CATALOGS = build_runtime_catalogs(get_module_registry())
_REGISTRIES = build_registry_snapshot(_CATALOGS, [])
_KNOWN_SLUGS = {table.slug for table in STANDARD_VIEWPOINT_TABLES}

# One entity per ArchiMate type referenced anywhere in the library, unspecialized, domain
# matching the ontology's own hierarchy — proves every definition finds a real population
# without depending on any repo-specific authoring.
_DOMAIN_BY_TYPE = {
    name: info.hierarchy[0]
    for name, info in _CATALOGS.ontology.all_entity_types().items()
    if info.hierarchy and info.hierarchy[0] != "assurance"
}


def _seeded_store() -> Store:
    entities = {
        f"ENT@{type_slug}": entity(
            artifact_id=f"ENT@{type_slug}", artifact_type=type_slug, name=type_slug, domain=domain, subdomain=""
        )
        for type_slug, domain in _DOMAIN_BY_TYPE.items()
    }
    return Store(entities=entities)


def test_library_covers_exactly_the_25_standard_slugs() -> None:
    slugs = {d.slug for d in _CATALOGS.viewpoints.entries}
    assert slugs == _KNOWN_SLUGS
    assert len(slugs) == 25
    assert not (slugs & {"element-dependents", "element-dependencies", "process-technology-support"})


def test_every_definition_passes_save_mode_validation() -> None:
    for definition in _CATALOGS.viewpoints.entries:
        issues = validate_viewpoint_definition(
            definition,
            mode="save",
            known_entity_types=_REGISTRIES.known_entity_types,
            known_connection_types=_REGISTRIES.known_connection_types,
            known_specialization_slugs=_REGISTRIES.known_specialization_slugs,
            entity_attribute_types=dict(_REGISTRIES.entity_attribute_types),
            connection_attribute_types=dict(_REGISTRIES.connection_attribute_types),
            symmetric_connection_types=_REGISTRIES.symmetric_connection_types,
            depth_cap=_REGISTRIES.depth_cap,
            catalog=_CATALOGS.viewpoints,
        )
        assert issues == (), f"{definition.slug}: {issues}"


def test_every_definition_returns_a_non_empty_population() -> None:
    store = _seeded_store()
    for definition in _CATALOGS.viewpoints.entries:
        result = evaluate_viewpoint(
            ViewpointExecutionRequest(slug=definition.slug),
            catalog=_CATALOGS.viewpoints,
            read_access=store,
            registries=_REGISTRIES,
            index_generation=None,
            max_entities=500,
            default_limit=500,
            timeout_seconds=10.0,
        )
        assert result.entity_ids, f"{definition.slug}: empty population"
        assert result.query_summary
