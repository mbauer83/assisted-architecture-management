"""DiagramTypeBase mixin providing default DiagramTypeModule implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from src.domain.bridges import BridgeDeclaration
from src.domain.diagram_type_config import DiagramTypeUiConfig, DiagramTypeWriteGuidance
from src.domain.module_types import ConnectionTypeName, EntityTypeName, _FreeOntologyType
from src.domain.ontology_protocol import ModuleClass, OntologyModule
from src.domain.ontology_types import ConnectionTypeInfo, ElementClassInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

if TYPE_CHECKING:
    from src.domain.module_registry import ModuleRegistry


class DiagramTypeBase:
    """Mixin providing default DiagramTypeModule implementations.

    Subclasses must provide: name, primary_ontology, accepts_entity_type,
    accepts_connection_type, own_entity_types, own_connection_types,
    own_permitted_relationships, and _config.
    """

    module_class: ModuleClass = "architecture"

    @property
    def bridges(self) -> tuple[BridgeDeclaration, ...]:
        return ()

    @property
    def element_classes(self) -> Mapping[str, ElementClassInfo]:
        return {}

    @property
    def effective_permitted_relationships(self) -> PermittedRelationshipSet:
        diagram_conn_rules = PermittedRelationshipSet.empty()
        for oe in self.ui_config.diagram_only_types:  # type: ignore[attr-defined]
            diagram_conn_rules = diagram_conn_rules | oe.permitted_connections

        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return self.own_permitted_relationships | diagram_conn_rules  # type: ignore[attr-defined]
        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        accepted_base_entities = frozenset(
            t
            for t in ontology.entity_types
            if self.accepts_entity_type(t)  # type: ignore[attr-defined]
        )
        accepted_base_conns = frozenset(
            t
            for t in ontology.connection_types
            if self.accepts_connection_type(t)  # type: ignore[attr-defined]
        )
        inherited = ontology.permitted_relationships.filter_to(
            accepted_base_entities,
            accepted_base_conns,
        )
        return inherited | self.own_permitted_relationships | diagram_conn_rules  # type: ignore[attr-defined]

    def effective_entity_types(self, registry: ModuleRegistry | None = None) -> Mapping[EntityTypeName, EntityTypeInfo]:
        del registry  # ontology-bound types derive from primary_ontology, not the registry
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return dict(self.own_entity_types)  # type: ignore[attr-defined]
        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        out = {
            t: info
            for t, info in ontology.entity_types.items()
            if self.accepts_entity_type(t)  # type: ignore[attr-defined]
        }
        out.update(self.own_entity_types)  # type: ignore[attr-defined]
        return out

    def effective_connection_types(
        self, registry: ModuleRegistry | None = None
    ) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        del registry  # ontology-bound types derive from primary_ontology, not the registry
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return dict(self.own_connection_types)  # type: ignore[attr-defined]
        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        out = {
            t: info
            for t, info in ontology.connection_types.items()
            if self.accepts_connection_type(t)  # type: ignore[attr-defined]
        }
        out.update(self.own_connection_types)  # type: ignore[attr-defined]
        return out

    @property
    def ui_config(self) -> DiagramTypeUiConfig:
        configured = getattr(self, "_ui_config", None)
        if isinstance(configured, DiagramTypeUiConfig):
            return configured
        return DiagramTypeUiConfig(
            label=str(self.name).replace("-", " ").title(),  # type: ignore[attr-defined]
            entity_search_filter=True,
        )

    def write_guidance(self) -> DiagramTypeWriteGuidance:
        return DiagramTypeWriteGuidance(when_to_use="", when_not_to_use="")

    def build_context_extras(
        self,
        repo: Any,
        diagram_id: str,
        diagram_entities: dict[str, Any],
    ) -> dict[str, Any]:
        return {}

    def read_diagram_extras(self, parsed_source: dict[str, Any]) -> dict[str, Any]:
        return {}

    def diagram_verification_contributions(self) -> tuple:
        return ()

    def repository_verification_contributions(self) -> tuple:
        return ()

    def prepare_render_model(
        self, diagram_entities: dict[str, Any], candidate: Any = None
    ) -> dict[str, Any]:
        return diagram_entities
