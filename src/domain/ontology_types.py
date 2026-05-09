"""Domain metadata types for entity and connection ontologies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ElementClassInfo:
    """Declaration of an element class (meta-type) used in element_classes lists."""

    name: str
    description: str = ""


@dataclass(frozen=True)
class RequiredConnection:
    """Mandatory connection that an entity type must always have to a host entity."""

    connection_type: str  # ConnectionTypeName
    target: str  # entity type name or "@class-name"; never "_diagram"
    cardinality_min: int = 1
    cardinality_max: int | None = None  # None = unbounded


@dataclass(frozen=True)
class PermittedMappingSpec:
    """Which model entities a diagram-owned entity may reference."""

    entity_types: tuple[str, ...] = ()
    entity_classes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EntityTypeInfo:
    """Canonical metadata for a single entity type.

    ``hierarchy`` is the full path from ``model/`` to the type-specific directory,
    e.g. ``("motivation", "stakeholder")``.  ``hierarchy[0]`` is the domain (layer)
    used for grouping and filtering; ``hierarchy[-1]`` is the type-specific leaf
    directory.  The loader derives the leaf from ``artifact_type`` so YAML only
    needs to specify the domain-level segments.
    """

    artifact_type: str
    prefix: str
    hierarchy: tuple[str, ...]
    element_classes: tuple[str, ...]
    create_when: str
    never_create_when: str
    internal: bool = False
    required_connections: tuple[RequiredConnection, ...] = ()
    min: int = 0
    max: int | None = None
    permitted_mappings: PermittedMappingSpec = field(default_factory=PermittedMappingSpec)
    mapping_required: bool = False


@dataclass(frozen=True)
class ConnectionTypeInfo:
    """Canonical metadata for a single connection type."""

    artifact_type: str
    conn_lang: str
    archimate_relationship_type: str | None = None
    symmetric: bool = False
    puml_arrow: str = "-->"
    classifications: tuple[str, ...] = ()
    hierarchy_priority: int | None = None
    embedding: Literal["none", "array", "property"] = "none"
    embed_key: str | None = None
    cascade_delete_source: bool = False
