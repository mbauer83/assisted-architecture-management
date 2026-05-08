"""OntologyModule, DiagramKindModule, DiagramRenderer protocols and DiagramKindBase mixin."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeAlias, runtime_checkable

from src.domain.module_types import (
    ConnectionTypeName,
    DiagramKindName,
    ElementClassName,
    EntityTypeName,
    _FreeOntologyType,
)
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

if TYPE_CHECKING:
    from src.domain.artifact_types import ConnectionRecord, EntityRecord


# ── PrimaryOntology alias ────────────────────────────────────────────────────

PrimaryOntology: TypeAlias = "OntologyModule | _FreeOntologyType"


# ── OntologyModule protocol ──────────────────────────────────────────────────

@runtime_checkable
class OntologyModule(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...

    @property
    def connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def display_section_id(self) -> str:
        """Section name used as the ``### <id>`` header in entity markdown display blocks."""
        ...

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]: ...

    def connection_types_with_classification(
        self, classification: str
    ) -> frozenset[ConnectionTypeName]: ...

    def permits_connection(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
        conn: ConnectionTypeName,
    ) -> bool: ...

    def render_display_section(
        self,
        artifact_type: str,
        name: str,
        alias: str,
    ) -> str:
        """Generate the YAML content for the display block of a new entity.

        Returns the raw YAML string to be embedded under ``### {display_section_id}``.
        """
        ...

    def extract_display_section(self, section_content: str) -> dict | None:
        """Parse a display block string back into a dict, or ``None`` on failure."""
        ...

    def sprite_for(self, artifact_type: str) -> str | None:
        """Return a PlantUML sprite line (``sprite $name <svg...>``) or ``None``."""
        ...


# ── DiagramRenderer protocol ─────────────────────────────────────────────────

@runtime_checkable
class DiagramRenderer(Protocol):
    def render_body(
        self,
        name: str,
        entities: Sequence[EntityRecord],
        connections: Sequence[ConnectionRecord],
        diagram_type: str,
        repo_root: Path,
    ) -> str: ...

    def inject_includes(self, body: str, repo_root: Path) -> str: ...


# ── DiagramKindModule protocol ───────────────────────────────────────────────

@runtime_checkable
class DiagramKindModule(Protocol):
    @property
    def name(self) -> DiagramKindName: ...

    @property
    def primary_ontology(self) -> OntologyModule | _FreeOntologyType: ...

    def accepts_entity_type(self, t: EntityTypeName) -> bool: ...
    def accepts_connection_type(self, t: ConnectionTypeName) -> bool: ...

    def effective_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...
    def effective_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def own_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]: ...

    @property
    def own_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]: ...

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def effective_permitted_relationships(self) -> PermittedRelationshipSet: ...

    @property
    def renderer(self) -> DiagramRenderer: ...


# ── DiagramKindBase mixin ────────────────────────────────────────────────────

class DiagramKindBase:
    """Default implementations for DiagramKindModule.

    Subclasses must declare: name, primary_ontology, accepts_entity_type,
    accepts_connection_type, own_entity_types, own_connection_types,
    own_permitted_relationships, and _config (the loaded config.yaml dict).
    """

    @property
    def effective_permitted_relationships(self) -> PermittedRelationshipSet:
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return PermittedRelationshipSet.empty()

        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        accepted_base_entities = frozenset(
            t for t in ontology.entity_types
            if self.accepts_entity_type(t)  # type: ignore[attr-defined]
        )
        accepted_base_conns = frozenset(
            t for t in ontology.connection_types
            if self.accepts_connection_type(t)  # type: ignore[attr-defined]
        )
        inherited = ontology.permitted_relationships.filter_to(
            accepted_base_entities,
            accepted_base_conns,
        )
        return inherited | self.own_permitted_relationships  # type: ignore[attr-defined]

    def effective_entity_types(self) -> Mapping[EntityTypeName, EntityTypeInfo]:
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return dict(self.own_entity_types)  # type: ignore[attr-defined]

        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        out = {
            t: info for t, info in ontology.entity_types.items()
            if self.accepts_entity_type(t)  # type: ignore[attr-defined]
        }
        out.update(self.own_entity_types)  # type: ignore[attr-defined]
        return out

    def effective_connection_types(self) -> Mapping[ConnectionTypeName, ConnectionTypeInfo]:
        if isinstance(self.primary_ontology, _FreeOntologyType):  # type: ignore[attr-defined]
            return dict(self.own_connection_types)  # type: ignore[attr-defined]

        ontology: OntologyModule = self.primary_ontology  # type: ignore[assignment]
        out = {
            t: info for t, info in ontology.connection_types.items()
            if self.accepts_connection_type(t)  # type: ignore[attr-defined]
        }
        out.update(self.own_connection_types)  # type: ignore[attr-defined]
        return out

    @property
    def renderer(self) -> DiagramRenderer:
        from src.infrastructure.rendering.generic_puml_renderer import GenericPumlRenderer
        return GenericPumlRenderer(self._config)  # type: ignore[attr-defined]
