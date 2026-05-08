"""Domain metadata types for entity and connection ontologies."""

from __future__ import annotations

from dataclasses import dataclass


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
