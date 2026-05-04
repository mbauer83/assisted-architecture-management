"""ModuleRegistry — single authority for all registered ontologies and diagram kinds."""

from __future__ import annotations

from collections.abc import Mapping

from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_protocol import DiagramKindModule, OntologyModule
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet


class ModuleRegistry:
    def __init__(self) -> None:
        self._ontologies: dict[str, OntologyModule] = {}
        self._diagram_kinds: dict[str, DiagramKindModule] = {}

    # ── Registration ─────────────────────────────────────────────────────────

    def register_ontology(self, module: OntologyModule) -> None:
        if module.name in self._ontologies:
            raise ValueError(f"Ontology '{module.name}' already registered; use replace_ontology")
        self._ontologies[module.name] = module

    def unregister_ontology(self, name: str) -> None:
        if name not in self._ontologies:
            raise KeyError(name)
        del self._ontologies[name]

    def replace_ontology(self, module: OntologyModule) -> None:
        self._ontologies[module.name] = module

    def register_diagram_kind(self, module: DiagramKindModule) -> None:
        if module.name in self._diagram_kinds:
            raise ValueError(f"DiagramKind '{module.name}' already registered; use replace_diagram_kind")
        self._diagram_kinds[module.name] = module

    def unregister_diagram_kind(self, name: str) -> None:
        if name not in self._diagram_kinds:
            raise KeyError(name)
        del self._diagram_kinds[name]

    def replace_diagram_kind(self, module: DiagramKindModule) -> None:
        self._diagram_kinds[module.name] = module

    # ── Ontology queries ──────────────────────────────────────────────────────

    def get_ontology(self, name: str) -> OntologyModule:
        try:
            return self._ontologies[name]
        except KeyError:
            raise KeyError(f"No ontology registered with name '{name}'")

    def find_ontology(self, name: str) -> OntologyModule | None:
        return self._ontologies.get(name)

    def all_ontologies(self) -> Mapping[str, OntologyModule]:
        return dict(self._ontologies)

    # ── Diagram kind queries ──────────────────────────────────────────────────

    def get_diagram_kind(self, name: str) -> DiagramKindModule:
        try:
            return self._diagram_kinds[name]
        except KeyError:
            raise KeyError(f"No diagram kind registered with name '{name}'")

    def find_diagram_kind(self, name: str) -> DiagramKindModule | None:
        return self._diagram_kinds.get(name)

    def all_diagram_kinds(self) -> Mapping[str, DiagramKindModule]:
        return dict(self._diagram_kinds)

    # ── Aggregated type queries ───────────────────────────────────────────────

    def all_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        out: dict[EntityTypeName, EntityTypeInfo] = {}
        for om in self._ontologies.values():
            out.update(om.entity_types)
        return out

    def all_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        out: dict[ConnectionTypeName, ConnectionTypeInfo] = {}
        for om in self._ontologies.values():
            out.update(om.connection_types)
        return out

    def get_entity_type(self, name: EntityTypeName) -> EntityTypeInfo:
        for om in self._ontologies.values():
            if name in om.entity_types:
                return om.entity_types[name]
        raise KeyError(f"Entity type '{name}' not found in any registered ontology")

    def find_entity_type(self, name: EntityTypeName) -> EntityTypeInfo | None:
        for om in self._ontologies.values():
            if name in om.entity_types:
                return om.entity_types[name]
        return None

    def get_connection_type(self, name: ConnectionTypeName) -> ConnectionTypeInfo:
        for om in self._ontologies.values():
            if name in om.connection_types:
                return om.connection_types[name]
        raise KeyError(f"Connection type '{name}' not found in any registered ontology")

    def find_connection_type(self, name: ConnectionTypeName) -> ConnectionTypeInfo | None:
        for om in self._ontologies.values():
            if name in om.connection_types:
                return om.connection_types[name]
        return None

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]:
        result: set[EntityTypeName] = set()
        for om in self._ontologies.values():
            result.update(om.entity_types_with_class(cls))
        return frozenset(result)

    def connection_types_with_classification(
        self, classification: str
    ) -> frozenset[ConnectionTypeName]:
        result: set[ConnectionTypeName] = set()
        for om in self._ontologies.values():
            result.update(om.connection_types_with_classification(classification))
        return frozenset(result)

    def ontology_for_entity_type(self, name: EntityTypeName) -> OntologyModule | None:
        for om in self._ontologies.values():
            if name in om.entity_types:
                return om
        return None

    def aggregated_permitted_relationships(self) -> PermittedRelationshipSet:
        result = PermittedRelationshipSet.empty()
        for om in self._ontologies.values():
            result = result | om.permitted_relationships
        return result

    # ── Domain ordering ───────────────────────────────────────────────────────

    def domain_order(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for om in self._ontologies.values():
            for et in om.entity_types.values():
                if not et.internal and et.domain_dir not in seen:
                    seen.add(et.domain_dir)
                    result.append(et.domain_dir)
        return result
