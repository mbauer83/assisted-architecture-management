"""Helpers for resolving diagram-owned mapping specs to concrete model entity types."""

from __future__ import annotations

from collections.abc import Iterable

from src.domain.module_registry import ModuleRegistry
from src.domain.module_types import ElementClassName, EntityTypeName
from src.domain.ontology_protocol import DiagramOwnEntityTypeUiConfig
from src.domain.ontology_types import PermittedMappingSpec


def resolve_model_entity_types(
    spec: PermittedMappingSpec,
    registry: ModuleRegistry,
) -> frozenset[EntityTypeName]:
    """Return the registered model entity types allowed by one mapping spec."""
    result: set[EntityTypeName] = {EntityTypeName(name) for name in spec.entity_types}

    for cls in spec.entity_classes:
        result.update(registry.entity_types_with_class(ElementClassName(cls)))

    for source in spec.sources:
        ontology = registry.find_ontology(source.ontology)
        if ontology is None:
            raise ValueError(f"Unknown ontology in permitted_mappings source: {source.ontology!r}")
        if source.entity_type:
            entity_type = EntityTypeName(source.entity_type)
            if entity_type not in ontology.entity_types:
                raise ValueError(
                    f"Unknown entity type {source.entity_type!r} in ontology {source.ontology!r}"
                )
            result.add(entity_type)
        if source.entity_class:
            result.update(ontology.entity_types_with_class(ElementClassName(source.entity_class)))

    return frozenset(result)


def resolve_model_entity_types_for_diagram_only_types(
    own_types: Iterable[DiagramOwnEntityTypeUiConfig],
    registry: ModuleRegistry,
) -> frozenset[EntityTypeName]:
    """Return the union of all model entity types accepted by diagram-owned entity types."""
    result: set[EntityTypeName] = set()
    for own_type in own_types:
        result.update(resolve_model_entity_types(own_type.permitted_mappings, registry))
    return frozenset(result)
