"""Predicates for entity type classification via the module registry."""

from functools import lru_cache

from src.domain.module_types import ElementClassName, EntityTypeName


@lru_cache(maxsize=1)
def _internal_types() -> frozenset[EntityTypeName]:
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry().entity_types_with_class(ElementClassName("internal"))


def is_internal_entity_type(artifact_type: str) -> bool:
    """Return True if artifact_type belongs to the 'internal' element class.

    Internal types (e.g. global-artifact-reference) are system-managed and must
    not be created or surfaced directly in user-facing entity lists.
    """
    return EntityTypeName(artifact_type) in _internal_types()
