"""AIBOM read use case (PLAN Stream D / WU-D1): the application surface that turns a model
read into the derived component set and its coverage report — what the REST/MCP export and
coverage endpoints (Stream E) and the GUI wizard (Stream F) consume.

``project_aibom`` is pure composition over the segregated read port (entities + connections)
plus the resolved role bindings and the per-specialization required/recommended attribute
names — no schema IO here, so it unit-tests over fakes. ``aibom_schema_levels`` is the thin
resolver that reads those attribute levels from the effective schemata for the caller."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from src.application.aibom_coverage import AibomCoverage, evaluate_coverage
from src.application.aibom_derivation import AI_SPECIALIZATIONS, AibomComponent, derive_aibom
from src.application.ports import ArtifactSearch
from src.application.runtime_catalogs import RuntimeCatalogs
from src.domain.aibom_roles import DerivationRoleBindings


@dataclass(frozen=True)
class AibomProjection:
    """The derived AIBOM and its coverage — one read result for every AIBOM surface."""

    components: tuple[AibomComponent, ...]
    coverage: AibomCoverage


def project_aibom(
    search: ArtifactSearch,
    bindings: DerivationRoleBindings,
    *,
    required_by_spec: Mapping[str, list[str]],
    recommended_by_spec: Mapping[str, list[str]] | None = None,
) -> AibomProjection:
    """Derive the AIBOM components from the model and evaluate their coverage. Pure over the
    read port + the passed-in attribute levels — no schema/store IO."""
    entities = list(search.list_entities())
    connections = list(search.list_connections())
    components = derive_aibom(entities, connections, bindings)
    coverage = evaluate_coverage(
        components, required_by_spec, bindings, recommended_attributes=recommended_by_spec
    )
    return AibomProjection(components=components, coverage=coverage)


def aibom_schema_levels(
    repo_root: Path, catalogs: RuntimeCatalogs
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """``(required_by_spec, recommended_by_spec)`` for every AI specialization, read from its
    effective attribute schema. The caller passes these into ``project_aibom`` so coverage
    knows which attributes are blocking vs advisory for each specialization."""
    from src.application.artifact_schema import compute_effective_attribute_schema  # noqa: PLC0415

    parent_by_slug = _ai_specialization_parents(catalogs)
    required: dict[str, list[str]] = {}
    recommended: dict[str, list[str]] = {}
    for slug, parent_type in parent_by_slug.items():
        schema, _ = compute_effective_attribute_schema(
            repo_root, parent_type, [slug],
            specialization_catalog=catalogs.specializations, profile_registry=catalogs.profiles,
        )
        if schema is None:
            continue
        required[slug] = list(schema.get("required", []) or [])
        recommended[slug] = list(schema.get("x-recommended", []) or [])
    return required, recommended


def _ai_specialization_parents(catalogs: RuntimeCatalogs) -> dict[str, str]:
    """Each AI specialization slug → its base (parent) entity type, from the catalog."""
    parents: dict[str, str] = {}
    for entry in catalogs.specializations.entries:
        if entry.concept_kind == "entity" and entry.slug in AI_SPECIALIZATIONS:
            parents.setdefault(entry.slug, entry.parent_type)
    return parents
