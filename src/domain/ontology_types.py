"""Domain metadata types for entity and connection ontologies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityTypeInfo:
    """Canonical metadata for a single entity type."""

    artifact_type: str
    prefix: str
    domain_dir: str
    subdir: str
    archimate_element_type: str | None
    element_classes: tuple[str, ...]
    create_when: str
    never_create_when: str
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()
    has_sprite: bool = False
    internal: bool = False


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
