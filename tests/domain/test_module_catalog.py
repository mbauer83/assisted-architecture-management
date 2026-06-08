"""Unit tests for ModuleCatalogBuilder and ModuleCatalog."""

from __future__ import annotations

import types
from collections.abc import Mapping
from typing import Any

import pytest

from src.domain.diagram_type_config import DiagramTypeUiConfig
from src.domain.module_catalog import ModuleCatalog, ModuleCatalogBuilder
from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, ElementClassInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

# ── Minimal stubs ─────────────────────────────────────────────────────────────


def _et(name: str, domain: str = "d", classes: tuple[str, ...] = (), internal: bool = False) -> EntityTypeInfo:
    return EntityTypeInfo(
        artifact_type=name,
        prefix=name[:2].upper(),
        hierarchy=(domain, name),
        classes=classes,
        create_when="",
        never_create_when="",
        internal=internal,
    )


def _ct(name: str, classes: tuple[str, ...] = ()) -> ConnectionTypeInfo:
    return ConnectionTypeInfo(artifact_type=name, conn_lang="test", classes=classes)


class _StubOntology:
    module_class = "architecture"

    def __init__(
        self,
        name: str,
        entity_names: list[str] | None = None,
        conn_names: list[str] | None = None,
        *,
        classes: tuple[str, ...] = (),
        element_classes: dict[str, ElementClassInfo] | None = None,
    ) -> None:
        self._name = name
        self._entity_types: dict[EntityTypeName, EntityTypeInfo] = {
            EntityTypeName(n): _et(n, classes=classes) for n in (entity_names or [])
        }
        self._conn_types: dict[ConnectionTypeName, ConnectionTypeInfo] = {
            ConnectionTypeName(n): _ct(n) for n in (conn_names or [])
        }
        self._element_classes: dict[str, ElementClassInfo] = element_classes or {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        return self._entity_types

    @property
    def connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        return self._conn_types

    @property
    def permitted_relationships(self) -> PermittedRelationshipSet:
        return PermittedRelationshipSet.empty()

    @property
    def element_classes(self) -> Mapping[str, ElementClassInfo]:
        return self._element_classes

    @property
    def display_section_id(self) -> str:
        return self._name

    @property
    def attribute_profiles(self) -> Mapping[str, dict[str, object]]:
        return {}

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]:
        return frozenset(n for n, info in self._entity_types.items() if cls in info.classes)

    def connection_types_with_class(self, cls: str) -> frozenset[ConnectionTypeName]:
        return frozenset(n for n, info in self._conn_types.items() if cls in info.classes)

    def permits_connection(self, src: Any, tgt: Any, conn: Any) -> bool:
        return False

    def render_display_section(self, artifact_type: str, name: str, alias: str) -> str:
        return ""

    def extract_display_section(self, section_content: str) -> dict | None:
        return None

    def sprite_for(self, artifact_type: str) -> str | None:
        return None


class _StubDiagramType:
    module_class = "architecture"

    def __init__(self, name: str, conn_names: list[str] | None = None) -> None:
        self._name = name
        self._own_connection_types: dict[ConnectionTypeName, ConnectionTypeInfo] = {
            ConnectionTypeName(n): _ct(n) for n in (conn_names or [])
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def own_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        return self._own_connection_types

    @property
    def own_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        return {}

    @property
    def element_classes(self) -> Mapping[str, ElementClassInfo]:
        return {}

    @property
    def ui_config(self) -> DiagramTypeUiConfig:
        return DiagramTypeUiConfig(label=self._name, entity_search_filter=False)

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet:
        return PermittedRelationshipSet.empty()

    @property
    def effective_permitted_relationships(self) -> PermittedRelationshipSet:
        return PermittedRelationshipSet.empty()

    @property
    def bridges(self) -> tuple:
        return ()

    def accepts_entity_type(self, t: Any) -> bool:
        return False

    def accepts_connection_type(self, t: Any) -> bool:
        return False

    def effective_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        return {}

    def effective_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        return {}

    @property
    def primary_ontology(self) -> Any:
        return None

    @property
    def renderer(self) -> Any:
        return None

    def write_guidance(self) -> Any:
        return None

    def build_context_extras(self, repo: Any, diagram_id: str, diagram_entities: dict) -> dict:
        return {}

    def read_diagram_extras(self, parsed_source: dict) -> dict:
        return {}


# ── Builder: registration lifecycle ──────────────────────────────────────────


class TestBuilderRegistration:
    def test_register_and_build(self) -> None:
        b = ModuleCatalogBuilder()
        onto = _StubOntology("o1", ["e-a"])
        b.register_ontology(onto)
        cat = b.build()
        assert cat.get_ontology("o1") is onto

    def test_duplicate_ontology_raises(self) -> None:
        b = ModuleCatalogBuilder()
        b.register_ontology(_StubOntology("o1"))
        with pytest.raises(ValueError, match="already registered"):
            b.register_ontology(_StubOntology("o1"))

    def test_replace_ontology_before_build(self) -> None:
        b = ModuleCatalogBuilder()
        o1 = _StubOntology("o1", ["e-a"])
        o2 = _StubOntology("o1", ["e-b"])
        b.register_ontology(o1)
        b.replace_ontology(o2)
        cat = b.build()
        assert cat.get_ontology("o1") is o2

    def test_unregister_ontology_before_build(self) -> None:
        b = ModuleCatalogBuilder()
        b.register_ontology(_StubOntology("o1"))
        b.unregister_ontology("o1")
        cat = b.build()
        assert cat.find_ontology("o1") is None

    def test_unregister_missing_raises(self) -> None:
        b = ModuleCatalogBuilder()
        with pytest.raises(KeyError):
            b.unregister_ontology("no-such")

    def test_register_diagram_type(self) -> None:
        b = ModuleCatalogBuilder()
        dt = _StubDiagramType("dt-a")
        b.register_diagram_type(dt)
        cat = b.build()
        assert cat.get_diagram_type("dt-a") is dt

    def test_duplicate_diagram_type_raises(self) -> None:
        b = ModuleCatalogBuilder()
        b.register_diagram_type(_StubDiagramType("dt-a"))
        with pytest.raises(ValueError, match="already registered"):
            b.register_diagram_type(_StubDiagramType("dt-a"))


# ── Builder: post-build lock ──────────────────────────────────────────────────


class TestBuilderLock:
    def setup_method(self) -> None:
        self.b = ModuleCatalogBuilder()
        self.b.build()  # seal it

    def test_register_ontology_after_build_raises(self) -> None:
        with pytest.raises(RuntimeError, match="already been built"):
            self.b.register_ontology(_StubOntology("o1"))

    def test_replace_ontology_after_build_raises(self) -> None:
        with pytest.raises(RuntimeError, match="already been built"):
            self.b.replace_ontology(_StubOntology("o1"))

    def test_unregister_ontology_after_build_raises(self) -> None:
        with pytest.raises(RuntimeError, match="already been built"):
            self.b.unregister_ontology("o1")

    def test_register_diagram_type_after_build_raises(self) -> None:
        with pytest.raises(RuntimeError, match="already been built"):
            self.b.register_diagram_type(_StubDiagramType("dt-a"))

    def test_replace_diagram_type_after_build_raises(self) -> None:
        with pytest.raises(RuntimeError, match="already been built"):
            self.b.replace_diagram_type(_StubDiagramType("dt-a"))

    def test_unregister_diagram_type_after_build_raises(self) -> None:
        with pytest.raises(RuntimeError, match="already been built"):
            self.b.unregister_diagram_type("dt-a")


# ── Catalog: query round-trips ────────────────────────────────────────────────


def _build(ontologies: list | None = None, diagram_types: list | None = None) -> ModuleCatalog:
    b = ModuleCatalogBuilder()
    for o in ontologies or []:
        b.register_ontology(o)
    for d in diagram_types or []:
        b.register_diagram_type(d)
    return b.build()


class TestCatalogQueries:
    def test_get_ontology(self) -> None:
        onto = _StubOntology("o1", ["e-x"])
        cat = _build([onto])
        assert cat.get_ontology("o1") is onto

    def test_get_ontology_missing_raises(self) -> None:
        cat = _build()
        with pytest.raises(KeyError, match="No ontology"):
            cat.get_ontology("missing")

    def test_find_ontology_missing_returns_none(self) -> None:
        cat = _build()
        assert cat.find_ontology("x") is None

    def test_all_ontologies_contains_all(self) -> None:
        o1, o2 = _StubOntology("o1"), _StubOntology("o2")
        cat = _build([o1, o2])
        assert set(cat.all_ontologies()) == {"o1", "o2"}

    def test_get_diagram_type(self) -> None:
        dt = _StubDiagramType("dt-a")
        cat = _build(diagram_types=[dt])
        assert cat.get_diagram_type("dt-a") is dt

    def test_get_diagram_type_missing_raises(self) -> None:
        cat = _build()
        with pytest.raises(KeyError, match="No diagram type"):
            cat.get_diagram_type("missing")

    def test_all_entity_types_merges_ontologies(self) -> None:
        o1 = _StubOntology("o1", ["e-a", "e-b"])
        o2 = _StubOntology("o2", ["e-c"])
        cat = _build([o1, o2])
        all_et = cat.all_entity_types()
        assert set(all_et) == {EntityTypeName("e-a"), EntityTypeName("e-b"), EntityTypeName("e-c")}

    def test_all_connection_types_merges_ontology_and_diagram_types(self) -> None:
        o1 = _StubOntology("o1", conn_names=["c-from-ont"])
        dt = _StubDiagramType("dt", conn_names=["c-from-dt"])
        cat = _build([o1], [dt])
        all_ct = cat.all_connection_types()
        assert ConnectionTypeName("c-from-ont") in all_ct
        assert ConnectionTypeName("c-from-dt") in all_ct

    def test_get_entity_type(self) -> None:
        o1 = _StubOntology("o1", ["my-entity"])
        cat = _build([o1])
        et = cat.get_entity_type(EntityTypeName("my-entity"))
        assert et.artifact_type == "my-entity"

    def test_get_entity_type_missing_raises(self) -> None:
        cat = _build()
        with pytest.raises(KeyError, match="not found"):
            cat.get_entity_type(EntityTypeName("nope"))

    def test_find_entity_type_missing_returns_none(self) -> None:
        cat = _build()
        assert cat.find_entity_type(EntityTypeName("nope")) is None

    def test_get_connection_type_from_ontology(self) -> None:
        cat = _build([_StubOntology("o1", conn_names=["my-conn"])])
        assert cat.get_connection_type(ConnectionTypeName("my-conn")).artifact_type == "my-conn"

    def test_get_connection_type_from_diagram_type(self) -> None:
        cat = _build(diagram_types=[_StubDiagramType("dt", conn_names=["dt-conn"])])
        assert cat.get_connection_type(ConnectionTypeName("dt-conn")).artifact_type == "dt-conn"

    def test_get_connection_type_missing_raises(self) -> None:
        cat = _build()
        with pytest.raises(KeyError, match="not found"):
            cat.get_connection_type(ConnectionTypeName("nope"))

    def test_entity_types_with_class(self) -> None:
        o = _StubOntology("o1", entity_names=["tagged", "plain"], classes=("my-cls",))
        # Override: only 'tagged' gets the class
        o._entity_types[EntityTypeName("plain")] = _et("plain", classes=())
        o._entity_types[EntityTypeName("tagged")] = _et("tagged", classes=("my-cls",))
        cat = _build([o])
        result = cat.entity_types_with_class(ElementClassName("my-cls"))
        assert EntityTypeName("tagged") in result
        assert EntityTypeName("plain") not in result

    def test_ontology_for_entity_type(self) -> None:
        onto = _StubOntology("o1", ["some-et"])
        cat = _build([onto])
        assert cat.ontology_for_entity_type(EntityTypeName("some-et")) is onto
        assert cat.ontology_for_entity_type(EntityTypeName("unknown")) is None

    def test_domain_order_excludes_internal(self) -> None:
        onto = _StubOntology("o1")
        onto._entity_types = {
            EntityTypeName("e-visible"): _et("e-visible", domain="layer-a"),
            EntityTypeName("e-internal"): _et("e-internal", domain="layer-b", internal=True),
        }
        cat = _build([onto])
        order = cat.domain_order()
        assert "layer-a" in order
        assert "layer-b" not in order


# ── Catalog: immutable / read-only views ──────────────────────────────────────


class TestCatalogImmutability:
    def test_all_ontologies_returns_mapping_proxy(self) -> None:
        cat = _build([_StubOntology("o1")])
        view = cat.all_ontologies()
        assert isinstance(view, types.MappingProxyType)
        with pytest.raises(TypeError):
            view["injected"] = _StubOntology("injected")  # type: ignore[index]

    def test_all_diagram_types_returns_mapping_proxy(self) -> None:
        cat = _build(diagram_types=[_StubDiagramType("dt-a")])
        view = cat.all_diagram_types()
        assert isinstance(view, types.MappingProxyType)
        with pytest.raises(TypeError):
            view["injected"] = _StubDiagramType("injected")  # type: ignore[index]

    def test_all_entity_types_returns_mapping_proxy(self) -> None:
        cat = _build([_StubOntology("o1", ["e-x"])])
        view = cat.all_entity_types()
        assert isinstance(view, types.MappingProxyType)
        with pytest.raises(TypeError):
            view[EntityTypeName("injected")] = _et("injected")  # type: ignore[index]

    def test_all_connection_types_returns_mapping_proxy(self) -> None:
        cat = _build([_StubOntology("o1", conn_names=["c-x"])])
        view = cat.all_connection_types()
        assert isinstance(view, types.MappingProxyType)
        with pytest.raises(TypeError):
            view[ConnectionTypeName("injected")] = _ct("injected")  # type: ignore[index]

    def test_builder_mutation_after_build_does_not_affect_catalog(self) -> None:
        """Catalog holds a snapshot; post-build attempts are rejected before they can mutate."""
        b = ModuleCatalogBuilder()
        b.register_ontology(_StubOntology("o1"))
        cat = b.build()
        with pytest.raises(RuntimeError):
            b.register_ontology(_StubOntology("o2"))
        assert cat.find_ontology("o2") is None
