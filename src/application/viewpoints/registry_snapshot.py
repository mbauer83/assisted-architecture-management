"""Builds a ``RegistrySnapshot`` from the real runtime catalogs
and a repository's ``.arch-repo/schemata/`` files — the wiring the pure criteria evaluator
needs to tell a known attribute path from schema drift, and to normalize incident-condition
direction against symmetric connection types.

Attribute declarations are scoped per (entity type, specialization) but the evaluator's
attribute-path namespace is deliberately flat (one namespace, used
everywhere a path appears") — so this merges every entity/connection type's effective
attribute schema, across every repo tier, into the two flat maps ``RegistrySnapshot`` wants.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from src.application.artifact_schema import compute_effective_attribute_schema, load_connection_metadata_schema
from src.application.runtime_catalogs import RuntimeCatalogs
from src.domain.viewpoint_condition_validation import RegistrySnapshot

_DEFAULT_ATTRIBUTE_TYPE = "string"
_DEFAULT_DERIVATION_MAX_HOPS = 4
_DEFAULT_DERIVATION_MAX_RELATIONSHIPS = 2000


def _property_types(schema: Mapping[str, object] | None) -> dict[str, str]:
    if schema is None:
        return {}
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return {}
    types: dict[str, str] = {}
    for name, prop in properties.items():
        declared = prop.get("type", _DEFAULT_ATTRIBUTE_TYPE) if isinstance(prop, Mapping) else _DEFAULT_ATTRIBUTE_TYPE
        types[str(name)] = str(declared)
    return types


def _entity_attribute_types(runtime_catalogs: RuntimeCatalogs, repo_roots: Sequence[Path]) -> dict[str, str]:
    types: dict[str, str] = {}
    for entity_type in runtime_catalogs.ontology.all_entity_type_names():
        slugs = ("", *(spec.slug for spec in runtime_catalogs.specializations.for_type("entity", entity_type)))
        for repo_root in repo_roots:
            for slug in slugs:
                schema, _conflicts = compute_effective_attribute_schema(
                    repo_root,
                    entity_type,
                    slug,
                    specialization_catalog=runtime_catalogs.specializations,
                )
                types.update(_property_types(schema))
    return types


def _connection_attribute_types(runtime_catalogs: RuntimeCatalogs, repo_roots: Sequence[Path]) -> dict[str, str]:
    types: dict[str, str] = {}
    for connection_type in runtime_catalogs.ontology.all_connection_type_names():
        for repo_root in repo_roots:
            schema = load_connection_metadata_schema(repo_root, connection_type)
            types.update(_property_types(schema))
    return types


def build_registry_snapshot(
    runtime_catalogs: RuntimeCatalogs,
    repo_roots: Sequence[Path],
    *,
    derivation_max_hops: int = _DEFAULT_DERIVATION_MAX_HOPS,
    derivation_max_relationships: int = _DEFAULT_DERIVATION_MAX_RELATIONSHIPS,
) -> RegistrySnapshot:
    """One snapshot for the lifetime of a verification run — callers should build this once
    (e.g. a ``functools.cached_property``) rather than per file, since it scans every entity
    type's effective attribute schema across every repo tier."""
    known_entity_types = runtime_catalogs.ontology.all_entity_type_names()
    known_connection_types = runtime_catalogs.ontology.all_connection_type_names()
    known_specialization_slugs = frozenset(spec.slug for spec in runtime_catalogs.specializations.entries)
    symmetric_connection_types = frozenset(
        ct for ct in known_connection_types if runtime_catalogs.connections.is_symmetric(ct)
    )
    return RegistrySnapshot(
        known_entity_types=known_entity_types,
        known_connection_types=known_connection_types,
        known_specialization_slugs=known_specialization_slugs,
        entity_attribute_types=_entity_attribute_types(runtime_catalogs, repo_roots),
        connection_attribute_types=_connection_attribute_types(runtime_catalogs, repo_roots),
        symmetric_connection_types=symmetric_connection_types,
        entity_type_infos=runtime_catalogs.ontology.all_entity_types(),
        derivation_catalog=runtime_catalogs.module_catalog,
        derivation_max_hops=derivation_max_hops,
        derivation_max_relationships=derivation_max_relationships,
    )
