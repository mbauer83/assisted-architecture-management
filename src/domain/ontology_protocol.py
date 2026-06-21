"""OntologyModule, DiagramTypeModule, DiagramRenderer protocols."""

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
    from src.domain.diagram_verification import DiagramVerificationContribution, RepositoryVerificationContribution

# Re-export all diagram_type_config public names for backward-compatible imports.
__all__ = [
    "DiagramOwnEntityTypePropertySpec",
    "DiagramOwnEntityTypeUiConfig",
    "DiagramRendererReferences",
    "DiagramTypeModule",
    "DiagramTypeUiConfig",
    "DiagramTypeWriteGuidance",
    "DiagramRenderer",
    "NativeSvgDiagramRenderer",
    "ModuleClass",
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
class NativeSvgDiagramRenderer(Protocol):
    """Optional capability for diagram types that own their SVG notation."""

    def render_svg(self, puml_body: str) -> str: ...


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

    def diagram_verification_contributions(self) -> tuple[DiagramVerificationContribution, ...]: ...

    def repository_verification_contributions(self) -> tuple[RepositoryVerificationContribution, ...]: ...

    def prepare_render_model(
        self, diagram_entities: dict[str, Any], candidate: Any
    ) -> dict[str, Any]: ...

