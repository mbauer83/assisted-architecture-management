"""REST endpoints backing the GUI viewpoints management view: the effective merged
catalog (full definitions, tier-tagged), the criteria-catalog registries snapshot pickers
are built from, a plain-language query-summary preview, and create/edit/delete — the same
``persist_edit``-mode validation and catalog-file persistence as the ``artifact_viewpoint``
MCP tool. One write path, two front ends.

Catalogs are rebuilt fresh per request (``build_runtime_catalogs(get_module_registry())``,
not the app-state-cached ``runtime_catalogs_dependency``) — the same pattern every other
write-adjacent GUI router uses, so a definition written here is visible to the very next
request without a backend restart.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.application.viewpoints.persist_definition import (
    PersistAction,
    ViewpointPersistResult,
    delete_viewpoint_definition,
    find_viewpoint_referencers,
    persist_viewpoint_definition,
)
from src.application.viewpoints.pins import load_pinned_slugs, save_pinned_slugs
from src.application.viewpoints.registry_snapshot import build_registry_snapshot
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria import RESERVED_CONNECTION_PATHS, RESERVED_ENTITY_PATHS
from src.domain.viewpoint_parsing import viewpoint_definition_from_mapping
from src.domain.viewpoint_query_parsing import query_from_mapping
from src.domain.viewpoint_serialization import viewpoint_definition_to_mapping
from src.domain.viewpoint_summary import render_query_summary
from src.domain.viewpoints import ViewpointCatalog, ViewpointDefinition
from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry
from src.infrastructure.gui.routers import state as s
from src.infrastructure.viewpoint_declarations import (
    load_effective_viewpoint_catalog,
    load_viewpoint_catalog_file,
    write_viewpoint_catalog_file,
)
from src.infrastructure.write.artifact_write.viewpoint_type_guidance import summarize_scope

router = APIRouter()


def _engagement_root():
    root = s.maybe_engagement_root()
    if root is None:
        raise HTTPException(500, "Engagement repository not initialized")
    return root


def _both_roots() -> list[Any]:
    return list(s.get_repo().repo_roots)


def _tier(slug: str, *, engagement_catalog: ViewpointCatalog, enterprise_catalog: ViewpointCatalog) -> str:
    if engagement_catalog.get(slug) is not None:
        return "engagement"
    if enterprise_catalog.get(slug) is not None:
        return "enterprise"
    return "module"


def _full_entry(definition: ViewpointDefinition, *, tier: str) -> dict[str, Any]:
    return {
        **viewpoint_definition_to_mapping(definition),
        "tier": tier,
        "scope_summary": summarize_scope(definition.scope),
        "query_summary": render_query_summary(definition.query) if definition.query is not None else None,
    }


@router.get("/api/viewpoints")
def list_viewpoint_definitions() -> dict[str, Any]:
    """The effective merged catalog (module + enterprise + engagement), each entry
    carrying its full serialized mapping (to populate an edit form) and a ``tier`` so the
    GUI can mark enterprise/module definitions read-only."""
    engagement_root = _engagement_root()
    enterprise_root = s.maybe_enterprise_root()
    engagement_catalog = load_viewpoint_catalog_file(engagement_root)
    enterprise_catalog = (
        load_viewpoint_catalog_file(enterprise_root) if enterprise_root is not None else ViewpointCatalog.empty()
    )
    merged = load_effective_viewpoint_catalog(_both_roots())
    entries = [
        _full_entry(d, tier=_tier(d.slug, engagement_catalog=engagement_catalog, enterprise_catalog=enterprise_catalog))
        for d in sorted(merged.entries, key=lambda d: d.slug)
    ]
    return {"viewpoints": entries}


@router.get("/api/viewpoints/criteria-catalog")
def get_criteria_catalog() -> dict[str, Any]:
    """Registries snapshot the criteria-tree builder's pickers are fed from — the same
    ``RegistrySnapshot`` save-mode validation itself resolves attribute paths against."""
    catalogs = build_runtime_catalogs(get_module_registry())
    registries: RegistrySnapshot = build_registry_snapshot(catalogs, _both_roots())
    derivation = {
        str(name): {"role": info.derivation_role, "strength": info.derivation_strength}
        for name, info in catalogs.ontology.all_connection_types().items()
        if info.derivation_role is not None
    }
    return {
        "entity_types": sorted(registries.known_entity_types),
        "connection_types": sorted(registries.known_connection_types),
        "specialization_slugs": sorted(registries.known_specialization_slugs),
        "entity_attribute_types": dict(registries.entity_attribute_types),
        "connection_attribute_types": dict(registries.connection_attribute_types),
        "symmetric_connection_types": sorted(registries.symmetric_connection_types),
        "reserved_entity_paths": sorted(RESERVED_ENTITY_PATHS),
        "reserved_connection_paths": sorted(RESERVED_CONNECTION_PATHS),
        "depth_cap": registries.depth_cap,
        "bindings": {
            "select": ["entity", "connection"],
            "aggregate": ["count", "min", "max", "sum", "average", "first", "last"],
            "result_types": [
                "entity[type-slug]", "connection[type-slug]", "entities[type-slug]", "connections[type-slug]",
                "string", "integer", "number", "date", "boolean", "slug", "optional[result-type]",
                "list[result-type]", "tuple[result-type, ...]",
            ],
        },
        "parameters": {"types": ["string", "integer", "number", "date", "boolean", "slug", "entity-id"]},
        "derived": {
            "traversal": ["direct", "derived"],
            "certainty": ["certain", "potential"],
            "reduce": ["count", "min", "max", "sum", "average", "first", "last"],
        },
        "connection_derivation": derivation,
    }


@router.get("/api/viewpoints/pins")
def get_viewpoint_pins() -> dict[str, Any]:
    """Pinned definition slugs (Home/management quick access) — an engagement-repo-local
    sidecar list, never definition content and never promoted. Slugs no longer in the
    effective catalog are dropped and reported under ``pruned``."""
    engagement_root = _engagement_root()
    merged = load_effective_viewpoint_catalog(_both_roots())
    known = frozenset(d.slug for d in merged.entries)
    pinned = load_pinned_slugs(engagement_root, known_slugs=known)
    return {"slugs": list(pinned.slugs), "pruned": list(pinned.pruned)}


class ViewpointPinsBody(BaseModel):
    slugs: list[str]


@router.put("/api/viewpoints/pins")
def put_viewpoint_pins(body: ViewpointPinsBody) -> dict[str, Any]:
    engagement_root = _engagement_root()
    merged = load_effective_viewpoint_catalog(_both_roots())
    known = frozenset(d.slug for d in merged.entries)
    unknown = [slug for slug in body.slugs if slug not in known]
    if unknown:
        raise HTTPException(400, f"unknown viewpoint slug(s): {', '.join(unknown)}")
    save_pinned_slugs(engagement_root, tuple(body.slugs))
    return {"slugs": body.slugs}


@router.get("/api/viewpoints/{slug}/referencers")
def get_viewpoint_referencers(slug: str) -> dict[str, Any]:
    """Diagrams/matrices whose viewpoint application pins this slug — the management view
    uses this to warn, before a semantic edit, which views a version bump would leave
    pinned to a now-stale version."""
    referencers = find_viewpoint_referencers(slug, read_access=s.get_repo())
    return {"referencers": [asdict(r) for r in referencers]}


class SummarizeQueryBody(BaseModel):
    query: dict[str, Any]


@router.post("/api/viewpoints/summarize")
def summarize_query(body: SummarizeQueryBody) -> dict[str, str]:
    """Plain-language rendering of an in-progress (possibly ad-hoc, unsaved) query — the
    same ``render_query_summary`` MCP ``list``/``execute`` and REST execution use, so the
    live builder preview can never disagree with what those surfaces say later."""
    try:
        query = query_from_mapping(body.query, label="query")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"summary": render_query_summary(query)}


def _result_to_dict(result: ViewpointPersistResult, *, dry_run: bool) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "action": result.action,
        "slug": result.slug,
        "version": result.version,
        "dry_run": dry_run,
        "issues": [asdict(i) for i in result.issues],
        "referencers": [asdict(r) for r in result.referencers],
    }


class ViewpointWriteBody(BaseModel):
    definition: dict[str, Any]
    dry_run: bool = True


def _persist(action: PersistAction, body: ViewpointWriteBody) -> dict[str, Any]:
    engagement_root = _engagement_root()
    both_roots = _both_roots()
    catalogs = build_runtime_catalogs(get_module_registry())
    merged_catalog = load_effective_viewpoint_catalog(both_roots)
    local_catalog = load_viewpoint_catalog_file(engagement_root)
    registries = build_registry_snapshot(catalogs, both_roots)
    try:
        parsed = viewpoint_definition_from_mapping(body.definition)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    result = persist_viewpoint_definition(
        action, parsed, local_catalog=local_catalog, merged_catalog=merged_catalog, registries=registries
    )
    if result.ok and not body.dry_run and result.catalog_to_write is not None:
        write_viewpoint_catalog_file(engagement_root, result.catalog_to_write)
    return _result_to_dict(result, dry_run=body.dry_run)


@router.post("/api/viewpoints")
def create_viewpoint_definition(body: ViewpointWriteBody) -> dict[str, Any]:
    return _persist("create", body)


@router.post("/api/viewpoints/edit")
def edit_viewpoint_definition(body: ViewpointWriteBody) -> dict[str, Any]:
    return _persist("edit", body)


class DeleteViewpointBody(BaseModel):
    slug: str
    dry_run: bool = True


@router.post("/api/viewpoints/remove")
def delete_viewpoint_definition_route(body: DeleteViewpointBody) -> dict[str, Any]:
    engagement_root = _engagement_root()
    both_roots = _both_roots()
    merged_catalog = load_effective_viewpoint_catalog(both_roots)
    local_catalog = load_viewpoint_catalog_file(engagement_root)
    repo = s.get_repo()
    result = delete_viewpoint_definition(
        body.slug, local_catalog=local_catalog, merged_catalog=merged_catalog, read_access=repo
    )
    if result.ok and not body.dry_run and result.catalog_to_write is not None:
        write_viewpoint_catalog_file(engagement_root, result.catalog_to_write)
    return _result_to_dict(result, dry_run=body.dry_run)
