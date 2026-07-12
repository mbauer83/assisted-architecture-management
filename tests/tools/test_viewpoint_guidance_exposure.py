"""Tests for viewpoint enumeration + scope summary in artifact_authoring_guidance (WU-E6).

Covers:
- get_type_guidance always includes a 'viewpoints' list, regardless of filter/diagram_type mode
- entries carry slug/version/name/description/purpose/content/scope
- scope summary reports unrestricted=True for a default (unrestricted) ConceptScope
- scope summary reports entity_types/connection_types when the scope is restricted
- entries are sorted by slug
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache

from src.application.runtime_catalogs import RuntimeCatalogs
from src.domain.concept_scope import ConceptScope
from src.domain.module_types import ConnectionTypeName, EntityTypeName
from src.domain.viewpoints import ViewpointCatalog, ViewpointDefinition
from src.infrastructure.write.artifact_write.type_guidance import get_type_guidance


@lru_cache(maxsize=1)
def _base_catalogs() -> RuntimeCatalogs:
    from src.infrastructure.app_bootstrap import build_module_registry, build_runtime_catalogs

    return build_runtime_catalogs(build_module_registry())


def _catalogs_with(entries: tuple[ViewpointDefinition, ...]) -> RuntimeCatalogs:
    return replace(_base_catalogs(), viewpoints=ViewpointCatalog(entries=entries))


def test_viewpoints_key_present_with_no_args() -> None:
    result = get_type_guidance(catalogs=_catalogs_with(()))
    assert "viewpoints" in result
    assert result["viewpoints"] == []


def test_viewpoints_key_present_with_filter() -> None:
    result = get_type_guidance(filter=["requirement"], catalogs=_catalogs_with(()))
    assert "viewpoints" in result


def test_viewpoints_key_present_with_diagram_type_only() -> None:
    result = get_type_guidance(diagram_type="archimate-motivation", catalogs=_catalogs_with(()))
    assert "viewpoints" in result


def test_viewpoint_entry_shape() -> None:
    defn = ViewpointDefinition(
        slug="application-landscape",
        version=2,
        name="Application Landscape",
        description="Application components and their serving relationships.",
        purpose=("designing", "deciding"),
        content=("overview",),
    )
    result = get_type_guidance(catalogs=_catalogs_with((defn,)))
    entries = result["viewpoints"]
    assert isinstance(entries, list)
    assert entries == [
        {
            "slug": "application-landscape",
            "version": 2,
            "name": "Application Landscape",
            "description": "Application components and their serving relationships.",
            "purpose": ["designing", "deciding"],
            "content": ["overview"],
            "scope": {"unrestricted": True},
        }
    ]


def test_scope_summary_restricted_entity_and_connection_types() -> None:
    scope = ConceptScope(
        entity_types=frozenset({EntityTypeName("application-component")}),
        connection_types=frozenset({ConnectionTypeName("archimate-serving")}),
    )
    defn = ViewpointDefinition(slug="narrow-vp", version=1, name="Narrow", scope=scope)
    result = get_type_guidance(catalogs=_catalogs_with((defn,)))
    scope_summary = result["viewpoints"][0]["scope"]
    assert scope_summary == {
        "unrestricted": False,
        "entity_types": ["application-component"],
        "connection_types": ["archimate-serving"],
    }


def test_viewpoint_entries_sorted_by_slug() -> None:
    defn_b = ViewpointDefinition(slug="b-viewpoint", version=1, name="B")
    defn_a = ViewpointDefinition(slug="a-viewpoint", version=1, name="A")
    result = get_type_guidance(catalogs=_catalogs_with((defn_b, defn_a)))
    slugs = [e["slug"] for e in result["viewpoints"]]
    assert slugs == ["a-viewpoint", "b-viewpoint"]
