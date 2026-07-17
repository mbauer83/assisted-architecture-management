"""Entity read and write endpoints."""

from __future__ import annotations

from functools import lru_cache as _lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.application._artifact_query_helpers import read_entity as serialize_entity
from src.application._diagram_entity_extraction import extract_diagram_entities
from src.application.artifact_parsing import decode_entity_properties, parse_entity_content_sections
from src.application.artifact_schema import load_attribute_schema
from src.application.document_links import reference_dicts_for_entity
from src.application.entity_type_predicates import is_assurance_entity_type, is_internal_entity_type
from src.application.read_models import EntityContextReadModel
from src.domain.artifact_types import EntityRecord
from src.infrastructure.gui.routers import state as s
from src.infrastructure.gui.routers.entity_listing import build_entity_list_rows


@_lru_cache(maxsize=1)
def _catalogs():
    from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry  # noqa: PLC0415

    return build_runtime_catalogs(get_module_registry())

router = APIRouter()


def engagement_model_catalog(records: list[EntityRecord]) -> list[EntityRecord]:
    """Filter to the engagement model-entity catalog: standalone (non-diagram-owned),
    engagement-side, non-internal, non-assurance entities — the exact population
    `/api/entities?scope=engagement` lists. Shared with `/api/groups`'s member counts so sidebar
    badges can never drift from what browsing a group actually shows."""
    _cat = _catalogs()
    return [
        e for e in records
        if e.host_diagram_id is None
        and not s.is_global(e.path)
        and not is_internal_entity_type(e.artifact_type, _cat.ontology)
        and not is_assurance_entity_type(e.artifact_type, _cat.module_catalog)
    ]


@router.get("/api/stats")
def get_stats() -> dict[str, Any]:
    return s.get_repo().stats()


@router.get("/api/backend-identity")
def get_backend_identity() -> dict[str, Any]:
    """Realpath-normalized served repo roots + software version.

    Consumed by `arch-repair upgrade --commit`'s guard, which refuses to run against a repo a
    running backend is currently serving; `/api/stats` carries no repo roots, hence this
    dedicated endpoint.
    """
    from importlib.metadata import PackageNotFoundError  # noqa: PLC0415
    from importlib.metadata import version as _pkg_version  # noqa: PLC0415

    try:
        software_version = _pkg_version("architectonic")
    except PackageNotFoundError:
        software_version = "unknown"
    return {
        "repo_roots": [str(root) for root in s.configured_roots()],
        "software_version": software_version,
    }


@router.get("/api/entities")
def list_entities(
    request: Request,
    domain: str | None = None,
    artifact_type: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    group: str | None = None,
    meta_ontology: str | None = None,
    limit: int = Query(default=200, le=2000),
    offset: int = 0,
) -> dict[str, Any]:
    repo = s.get_repo()
    entities = repo.list_entities(domain=domain, artifact_type=artifact_type, status=status, group=group)
    # Diagram-owned entities (swimlanes, lifelines, actions, …) live inside a diagram's
    # frontmatter; they are indexed for in-diagram queries but are not standalone model
    # entities and must not surface in the model-entity catalog.
    entities = [e for e in entities if e.host_diagram_id is None]
    _cat = _catalogs()
    if scope == "global":
        entities = [
            e for e in entities
            if s.is_global(e.path) and not is_assurance_entity_type(e.artifact_type, _cat.module_catalog)
        ]
    elif scope == "engagement":
        entities = engagement_model_catalog(entities)
    else:
        entities = [
            e for e in entities
            if not is_internal_entity_type(e.artifact_type, _cat.ontology)
            and not is_assurance_entity_type(e.artifact_type, _cat.module_catalog)
        ]
    if meta_ontology:
        from src.infrastructure.app_bootstrap import (  # noqa: PLC0415
            module_registry_from_app,
            resolve_meta_ontology_artifact_types,
        )
        allowed = resolve_meta_ontology_artifact_types(meta_ontology, module_registry_from_app(request.app))
        if allowed is not None:
            entities = [e for e in entities if e.artifact_type in allowed]
    page = entities[offset : offset + limit]
    return {"total": len(entities), "items": build_entity_list_rows(page, repo)}


@router.get("/api/entity")
def read_entity(id: str) -> dict[str, Any]:
    repo = s.get_repo()
    result = repo.read_artifact(id, mode="full")
    entity_rec = repo.get_entity(id)
    if result is None and "#" in id:
        diagram_id = id.split("#", 1)[0]
        diagram = repo.get_diagram(diagram_id)
        if diagram is not None:
            entity_rec = next(
                (entity for entity in extract_diagram_entities(diagram) if entity.artifact_id == id),
                None,
            )
            if entity_rec is not None:
                result = serialize_entity(entity_rec, mode="full")
    if result is None:
        raise HTTPException(404, f"Not found: {id!r}")
    if entity_rec is not None:
        parsed = parse_entity_content_sections(entity_rec.content_text)
        result["summary"] = parsed["summary"]
        result["properties"] = parsed["properties"]
        result["notes"] = parsed["notes"]
        inc, sym, out = repo.connection_counts_for(id)
        result["conn_in"] = inc
        result["conn_sym"] = sym
        result["conn_out"] = out
        result["is_global"] = s.is_global(entity_rec.path)
    return result


@router.get("/api/entity-context")
def read_entity_context(id: str) -> EntityContextReadModel:
    repo = s.get_repo()
    context = repo.read_entity_context(id)
    if context is None:
        raise HTTPException(404, f"Not found: {id!r}")
    entity_rec = repo.get_entity(id)
    if entity_rec is not None:
        parsed = parse_entity_content_sections(entity_rec.content_text)
        # Decode raw cell strings to typed Python values using the attribute schema.
        repo_root = s.maybe_engagement_root()
        raw_props: dict[str, str] = parsed["properties"]
        artifact_type = entity_rec.artifact_type
        attr_schema = load_attribute_schema(repo_root, artifact_type) if repo_root else None
        prop_schemata: dict[str, dict] = (attr_schema or {}).get("properties", {}) or {}
        _raw_attr_types = entity_rec.extra.get("attribute-types")
        attr_types: dict[str, str] = (
            {k: str(v) for k, v in _raw_attr_types.items()} if isinstance(_raw_attr_types, dict) else {}
        )
        context["entity"]["summary"] = parsed["summary"]
        context["entity"]["properties"] = decode_entity_properties(raw_props, prop_schemata, attr_types)
        context["entity"]["notes"] = parsed["notes"]
        context["entity"]["is_global"] = s.is_global(entity_rec.path)
        context["entity"]["referenced_in_documents"] = reference_dicts_for_entity(
            documents=repo.list_documents(),
            entity=entity_rec,
        )
    return context


def _attribute_descriptors(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract per-attribute UI descriptors (type, enum, default, constraints) from a JSON Schema."""
    props: dict[str, Any] = schema.get("properties", {}) or {}
    out: dict[str, dict[str, Any]] = {}
    for name, prop_schema in props.items():
        if not isinstance(prop_schema, dict):
            continue
        schema_type = prop_schema.get("type", "string")
        descriptor: dict[str, Any] = {"type": schema_type}
        if "enum" in prop_schema:
            descriptor["enum"] = [str(v) for v in prop_schema["enum"]]
        if "default" in prop_schema:
            raw = prop_schema["default"]
            if isinstance(raw, bool):
                descriptor["default"] = "true" if raw else "false"
            elif raw is not None:
                descriptor["default"] = str(raw)
        constraints: dict[str, Any] = {}
        for key in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                    "minLength", "maxLength", "pattern"):
            if key in prop_schema:
                constraints[key] = prop_schema[key]
        if constraints:
            descriptor["constraints"] = constraints
        out[name] = descriptor
    return out


@router.get("/api/entity-schemata")
def get_entity_schemata(artifact_type: str, specialization: str = "") -> dict[str, Any]:
    """Effective attribute schema for an entity type, merged with the selected
    specialization's contributed attributes — the same schema the verifier
    validates against, so the authoring form and verification can never drift."""
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.application.artifact_schema import (
        compute_effective_attribute_schema,
        schema_all_properties,
        schema_required_properties,
    )

    schema, conflicts = compute_effective_attribute_schema(
        repo_root,
        artifact_type,
        specialization,
        specialization_catalog=_catalogs().specializations,
    )
    if schema is None:
        return {
            "artifact_type": artifact_type,
            "specialization": specialization,
            "schema": None,
            "properties": [],
            "required": [],
            "descriptors": {},
            "conflicts": conflicts,
        }
    return {
        "artifact_type": artifact_type,
        "specialization": specialization,
        "schema": schema,
        "properties": schema_all_properties(schema),
        "required": schema_required_properties(schema),
        "descriptors": _attribute_descriptors(schema),
        "conflicts": conflicts,
    }


class CreateEntityBody(BaseModel):
    artifact_type: str
    name: str
    summary: str | None = None
    properties: dict[str, Any] | None = None
    attribute_types: dict[str, str] | None = None
    notes: str | None = None
    keywords: list[str] | None = None
    specialization: str | None = None
    version: str = "0.1.0"
    status: str = "draft"
    dry_run: bool = True


class EditEntityBody(BaseModel):
    artifact_id: str
    name: str | None = None
    summary: str | None = None
    properties: dict[str, Any] | None = None
    attribute_types: dict[str, str] | None = None
    notes: str | None = None
    keywords: list[str] | None = None
    specialization: str | None = None
    version: str | None = None
    status: str | None = None
    dry_run: bool = True


class DeleteEntityBody(BaseModel):
    artifact_id: str
    dry_run: bool = True


@router.post("/api/entity")
def create_entity(body: CreateEntityBody) -> dict[str, Any]:
    if is_internal_entity_type(body.artifact_type, _catalogs().ontology):
        raise HTTPException(400, "global-artifact-reference entities cannot be created directly")
    repo_root, _registry, verifier = s.get_write_deps()
    from src.infrastructure.write.artifact_write.entity import create_entity as _create

    try:
        result = s.run_serialized_write(
            _create,
            repo_root=repo_root,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            artifact_type=body.artifact_type,
            name=body.name,
            summary=body.summary,
            properties=body.properties,
            attribute_types=body.attribute_types,
            notes=body.notes,
            keywords=body.keywords,
            specialization=body.specialization,
            artifact_id=None,
            version=body.version,
            status=body.status,
            last_updated=None,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/entity/edit")
def edit_entity(body: EditEntityBody) -> dict[str, Any]:
    repo_root, registry, verifier = s.get_write_deps()
    from src.infrastructure.write.artifact_write.entity_edit import _UNSET
    from src.infrastructure.write.artifact_write.entity_edit import edit_entity as _edit

    provided = body.model_fields_set
    try:
        result = s.run_serialized_write(
            _edit,
            repo_root=repo_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id,
            name=body.name,
            summary=body.summary if "summary" in provided else _UNSET,
            properties=body.properties if "properties" in provided else _UNSET,
            attribute_types=body.attribute_types if "attribute_types" in provided else _UNSET,
            notes=body.notes if "notes" in provided else _UNSET,
            keywords=body.keywords if "keywords" in provided else _UNSET,
            specialization=body.specialization if "specialization" in provided else _UNSET,
            version=body.version,
            status=body.status,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/entity/remove")
def delete_entity(body: DeleteEntityBody) -> dict[str, Any]:
    repo_root, registry, _verifier = s.get_write_deps()
    from src.infrastructure.write.artifact_write.entity_delete import delete_entity as _delete

    try:
        result = s.run_serialized_write(
            _delete,
            repo_root=repo_root,
            registry=registry,
            clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)
