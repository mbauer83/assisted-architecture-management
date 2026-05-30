"""OntologyModule, DiagramTypeModule, DiagramRenderer protocols and DiagramTypeBase mixin."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

from src.domain.module_types import (
    ConnectionTypeName,
    DiagramTypeName,
    ElementClassName,
    EntityTypeName,
    _FreeOntologyType,
)
from src.domain.allowed_bindings import AllowedBindingsSpec
from src.domain.ontology_types import (
    ConnectionTypeInfo,
    ElementClassInfo,
    EntityTypeInfo,
    PermittedMappingSpec,
    RequiredConnection,
    mapping_spec_from_config,
)
from src.domain.permitted_relationships import PermittedRelationshipSet, permitted_connections_from_config

if TYPE_CHECKING:
    from src.domain.artifact_types import ConnectionRecord, EntityRecord

PrimaryOntology: TypeAlias = "OntologyModule | _FreeOntologyType"


@dataclass(frozen=True)
class DiagramOwnEntityTypePropertySpec:
    """Domain-specific property for a diagram-only entity type (management fields are auto-added)."""

    name: str
    schema: dict[str, object]
    required: bool = True


@dataclass(frozen=True)
class DiagramOwnEntityTypeUiConfig:
    entity_type: str
    label: str
    plural: str
    min: int = 0
    max: int | None = None
    permitted_mappings: PermittedMappingSpec = field(default_factory=PermittedMappingSpec)
    mapping_required: bool = False
    classes: tuple[str, ...] = ()
    create_when: str = ""
    never_create_when: str = ""
    properties: tuple[DiagramOwnEntityTypePropertySpec, ...] = ()
    permitted_connections: PermittedRelationshipSet = field(default_factory=PermittedRelationshipSet.empty)
    required_connections: tuple[RequiredConnection, ...] = ()
    managed_fields: tuple[tuple[str, str], ...] | None = None


@dataclass(frozen=True)
class DiagramTypeUiConfig:
    label: str
    description: str = ""
    entity_search_filter: bool = True
    diagram_only_types: tuple[DiagramOwnEntityTypeUiConfig, ...] = ()
    type_ui_slots: dict[str, str] = field(default_factory=dict)


def diagram_type_ui_config_from_mapping(
    config: Mapping[str, Any],
    *,
    default_label: str,
) -> DiagramTypeUiConfig:
    ui = config.get("ui")
    if not isinstance(ui, Mapping):
        return DiagramTypeUiConfig(label=default_label, entity_search_filter=True)
    return DiagramTypeUiConfig(
        label=str(ui.get("label") or default_label),
        description=str(ui.get("description") or ""),
        entity_search_filter=bool(ui.get("entity_search_filter", True)),
        diagram_only_types=tuple(
            _own_entity_ui_config_from_mapping(entry)
            for entry in ui.get("diagram_only_types", ())
            if isinstance(entry, Mapping)
        ),
        type_ui_slots={str(k): str(v) for k, v in ui.get("type_ui_slots", {}).items()},
    )


def _own_entity_ui_config_from_mapping(config: Mapping[str, Any]) -> DiagramOwnEntityTypeUiConfig:
    mapping_spec = mapping_spec_from_config(config.get("permitted_mappings"))
    raw_props: object = config.get("properties") or {}
    props = tuple(
        DiagramOwnEntityTypePropertySpec(
            name=name,
            schema={k: v for k, v in spec.items() if k != "required"},
            required=bool(spec.get("required", True)),
        )
        for name, spec in (raw_props.items() if isinstance(raw_props, Mapping) else ())
        if isinstance(spec, Mapping)
    )
    raw_conns = config.get("permitted_connections")
    raw_req = config.get("required_connections") or ()
    max_val = config.get("max")
    return DiagramOwnEntityTypeUiConfig(
        entity_type=str(config["entity_type"]),
        label=str(config["label"]),
        plural=str(config.get("plural") or config["label"] + "s"),
        min=int(config.get("min", 0)),
        max=None if max_val is None else int(max_val),
        permitted_mappings=mapping_spec,
        mapping_required=bool(config.get("mapping_required", False)),
        classes=tuple(str(c) for c in config.get("classes", ())),
        create_when=str(config.get("create_when") or ""),
        never_create_when=str(config.get("never_create_when") or ""),
        properties=props,
        permitted_connections=(
            permitted_connections_from_config(raw_conns)
            if isinstance(raw_conns, list)
            else PermittedRelationshipSet.empty()
        ),
        required_connections=tuple(_required_connection_from_mapping(rc) for rc in raw_req if isinstance(rc, Mapping)),
        managed_fields=_parse_managed_fields(config.get("managed_fields")),
    )


def _parse_managed_fields(raw: object) -> tuple[tuple[str, str], ...] | None:
    if not isinstance(raw, Mapping) or not raw:
        return None
    return tuple((str(k), str(v)) for k, v in raw.items())


def _required_connection_from_mapping(config: Mapping[str, Any]) -> RequiredConnection:
    raw_card = config.get("cardinality") or [1, 1]
    card_min = int(raw_card[0]) if raw_card else 1
    card_max: int | None = int(raw_card[1]) if len(raw_card) > 1 and raw_card[1] is not None else None
    return RequiredConnection(
        connection_type=str(config["connection_type"]),
        target=str(config["target"]),
        cardinality_min=card_min,
        cardinality_max=card_max,
    )


@dataclass(frozen=True)
class DiagramTypeWriteGuidance:
    """Authoring guidance for one diagram type, returned by artifact_authoring_guidance(diagram_type=...)."""

    when_to_use: str
    when_not_to_use: str
    accepted_domains: tuple[str, ...] = ()
    diagram_entities_schema: dict[str, object] | None = None
    own_entity_types: tuple[DiagramOwnEntityTypeUiConfig, ...] = ()
    puml_notes: tuple[str, ...] = ()
    allowed_bindings: AllowedBindingsSpec | None = None


@dataclass(frozen=True)
class DiagramRendererReferences:
    """Model artifact references discovered by a renderer from diagram-owned data."""

    entity_ids: tuple[str, ...] = ()
    connection_ids: tuple[str, ...] = ()


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
    def element_classes(self) -> Mapping[str, ElementClassInfo]: ...

    @property
    def display_section_id(self) -> str: ...

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

    @property
    def renderer(self) -> DiagramRenderer:
        from src.infrastructure.rendering.generic_puml_renderer import GenericPumlRenderer  # noqa: PLC0415

        return GenericPumlRenderer(self._config)  # type: ignore[attr-defined]

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
