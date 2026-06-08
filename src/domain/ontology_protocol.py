"""OntologyModule, DiagramTypeModule, DiagramRenderer protocols and DiagramTypeBase mixin."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeAlias, runtime_checkable

from src.domain.bridges import BridgeDeclaration
from src.domain.diagram_type_config import (
    DiagramOwnEntityTypePropertySpec,
    DiagramOwnEntityTypeUiConfig,
    DiagramRendererReferences,
    DiagramTypeUiConfig,
    DiagramTypeWriteGuidance,
    diagram_type_ui_config_from_mapping,
)
from src.domain.module_types import (
    ConnectionTypeName,
    DiagramTypeName,
    ElementClassName,
    EntityTypeName,
    _FreeOntologyType,
)
from src.domain.ontology_types import (
    ConnectionTypeInfo,
    ElementClassInfo,
    EntityTypeInfo,
)
from src.domain.permitted_relationships import PermittedRelationshipSet

if TYPE_CHECKING:
    from src.domain.artifact_types import ConnectionRecord, EntityRecord

# Re-export all diagram_type_config public names for backward-compatible imports.
__all__ = [
    "DiagramOwnEntityTypePropertySpec",
    "DiagramOwnEntityTypeUiConfig",
    "DiagramRendererReferences",
    "DiagramTypeBase",
    "DiagramTypeModule",
    "DiagramTypeUiConfig",
    "DiagramTypeWriteGuidance",
    "DiagramRenderer",
    "OntologyModule",
    "PrimaryOntology",
    "diagram_type_ui_config_from_mapping",
]

PrimaryOntology: TypeAlias = "OntologyModule | _FreeOntologyType"

ModuleClass = Literal["architecture", "assurance"]


@runtime_checkable
class OntologyModule(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def module_class(self) -> ModuleClass: ...

    @property
    def entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...

    @property
    def connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def element_classes(self) -> Mapping[str, ElementClassInfo]: ...

    @property
    def display_section_id(self) -> str: ...

    @property
    def attribute_profiles(self) -> Mapping[str, dict[str, object]]: ...

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]: ...

    def connection_types_with_class(self, cls: str) -> frozenset[ConnectionTypeName]: ...

    def permits_connection(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
        conn: ConnectionTypeName,
    ) -> bool: ...

    def render_display_section(self, artifact_type: str, name: str, alias: str) -> str: ...

    def extract_display_section(self, section_content: str) -> dict | None: ...

    def sprite_for(self, artifact_type: str) -> str | None: ...


@runtime_checkable
class DiagramRenderer(Protocol):
    def render_body(
        self,
        name: str,
        entities: Sequence[EntityRecord],
        connections: Sequence[ConnectionRecord],
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
    ) -> str: ...

    def inject_includes(self, body: str, repo_root: Path) -> str: ...

    def collect_references(
        self,
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
        bindings: list[dict[str, object]] | None = None,
    ) -> DiagramRendererReferences: ...


@runtime_checkable
class DiagramTypeModule(Protocol):
    @property
    def name(self) -> DiagramTypeName: ...

    @property
    def module_class(self) -> ModuleClass: ...

    @property
    def primary_ontology(self) -> OntologyModule | _FreeOntologyType: ...

    @property
    def element_classes(self) -> Mapping[str, ElementClassInfo]: ...

    def accepts_entity_type(self, t: EntityTypeName) -> bool: ...
    def accepts_connection_type(self, t: ConnectionTypeName) -> bool: ...

    def effective_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...
    def effective_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def own_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...

    @property
    def own_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def ui_config(self) -> DiagramTypeUiConfig: ...

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def effective_permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def bridges(self) -> tuple[BridgeDeclaration, ...]: ...

    @property
    def renderer(self) -> DiagramRenderer: ...

    def write_guidance(self) -> DiagramTypeWriteGuidance: ...

    def build_context_extras(
        self,
        repo: Any,
        diagram_id: str,
        diagram_entities: dict[str, Any],
    ) -> dict[str, Any]: ...

    def read_diagram_extras(self, parsed_source: dict[str, Any]) -> dict[str, Any]: ...


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

    def effective_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
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

    def effective_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
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
