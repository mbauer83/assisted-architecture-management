"""Registry-backed ontology catalog helpers."""

from __future__ import annotations

from functools import lru_cache

from src.domain.module_types import ElementClassName
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.ontologies.archimate_next import module as archimate_next


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


@lru_cache(maxsize=1)
def all_entity_types() -> dict[str, EntityTypeInfo]:
    """Return all registered entity types keyed by their public name."""
    return {str(name): info for name, info in _registry().all_entity_types().items()}


@lru_cache(maxsize=1)
def all_connection_types() -> dict[str, ConnectionTypeInfo]:
    """Return all registered connection types keyed by their public name."""
    return {str(name): info for name, info in _registry().all_connection_types().items()}


@lru_cache(maxsize=1)
def all_entity_type_names() -> frozenset[str]:
    return frozenset(all_entity_types())


@lru_cache(maxsize=1)
def all_connection_type_names() -> frozenset[str]:
    return frozenset(all_connection_types())


@lru_cache(maxsize=1)
def known_domain_names() -> frozenset[str]:
    domains = {info.domain_dir for info in all_entity_types().values()}
    return frozenset(domains | {"unknown"})


@lru_cache(maxsize=1)
def domain_order() -> list[str]:
    return _registry().domain_order()


@lru_cache(maxsize=1)
def domain_grouping() -> dict[str, str]:
    return {domain: f"{domain.capitalize()}Grouping" for domain in domain_order()}


def entity_types_with_class(element_class: str) -> frozenset[str]:
    values = _registry().entity_types_with_class(ElementClassName(element_class))
    return frozenset(str(name) for name in values)


def expand_entity_type_term(term: str) -> list[str]:
    if term == "@all":
        return sorted(all_entity_type_names())
    if term.startswith("@"):
        return sorted(entity_types_with_class(term[1:]))
    return [term] if term in all_entity_type_names() else []


def format_entity_type_term(term: str) -> str:
    if term == "@all":
        return "entity"
    normalized = term[1:] if term.startswith("@") else term
    return normalized.replace("-", " ").replace("_", " ")


def entity_type_term_matches(term: str, linked_types: set[str]) -> bool:
    return bool(set(expand_entity_type_term(term)) & linked_types)


@lru_cache(maxsize=1)
def archimate_stereotype_to_connection_type() -> dict[str, str]:
    result: dict[str, str] = {}
    for info in all_connection_types().values():
        if info.conn_lang != "archimate" or info.archimate_relationship_type is None:
            continue
        result[info.archimate_relationship_type.lower()] = info.artifact_type
    return result


@lru_cache(maxsize=1)
def entity_type_prefixes() -> dict[str, str]:
    return {info.prefix: artifact_type for artifact_type, info in all_entity_types().items()}


@lru_cache(maxsize=1)
def matrix_abbreviations_by_connection_type() -> dict[str, str]:
    return dict(archimate_next.matrix_abbreviations)


@lru_cache(maxsize=1)
def matrix_connection_type_abbreviations() -> dict[str, str]:
    return {conn_type: abbrev for abbrev, conn_type in matrix_abbreviations_by_connection_type().items()}
