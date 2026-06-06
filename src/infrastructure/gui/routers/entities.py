"""Entity read and write endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.application.artifact_parsing import parse_entity_content_sections
from src.application.entity_type_predicates import is_assurance_entity_type, is_internal_entity_type
from src.application.read_models import EntityContextReadModel
from src.infrastructure.gui.routers import state as s
from src.infrastructure.gui.routers.entity_listing import build_entity_list_rows

router = APIRouter()


@router.get("/api/stats")
def get_stats() -> dict[str, Any]:
    return s.get_repo().stats()


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
    if scope == "global":
        entities = [e for e in entities if s.is_global(e.path) and not is_assurance_entity_type(e.artifact_type)]
    elif scope == "engagement":
        entities = [
            e for e in entities
            if not s.is_global(e.path)
            and not is_internal_entity_type(e.artifact_type)
            and not is_assurance_entity_type(e.artifact_type)
        ]
    else:
        entities = [
            e for e in entities
            if not is_internal_entity_type(e.artifact_type) and not is_assurance_entity_type(e.artifact_type)
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
    if result is None:
        raise HTTPException(404, f"Not found: {id!r}")
    entity_rec = repo.get_entity(id)
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
        context["entity"]["summary"] = parsed["summary"]
        context["entity"]["properties"] = parsed["properties"]
        context["entity"]["notes"] = parsed["notes"]
        context["entity"]["is_global"] = s.is_global(entity_rec.path)
    return context


@router.get("/api/entity-schemata")
def get_entity_schemata(artifact_type: str) -> dict[str, Any]:
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.application.artifact_schema import (
        load_attribute_schema,
        schema_all_properties,
        schema_required_properties,
    )

    schema = load_attribute_schema(repo_root, artifact_type)
    if schema is None:
        return {"artifact_type": artifact_type, "schema": None, "properties": [], "required": []}
    return {
        "artifact_type": artifact_type,
        "schema": schema,
        "properties": schema_all_properties(schema),
        "required": schema_required_properties(schema),
    }


class CreateEntityBody(BaseModel):
    artifact_type: str
    name: str
    summary: str | None = None
    properties: dict[str, str] | None = None
    notes: str | None = None
    keywords: list[str] | None = None
    version: str = "0.1.0"
    status: str = "draft"
    dry_run: bool = True


class EditEntityBody(BaseModel):
    artifact_id: str
    name: str | None = None
    summary: str | None = None
    properties: dict[str, str] | None = None
    notes: str | None = None
    keywords: list[str] | None = None
    version: str | None = None
    status: str | None = None
    dry_run: bool = True


class DeleteEntityBody(BaseModel):
    artifact_id: str
    dry_run: bool = True


@router.post("/api/entity")
def create_entity(body: CreateEntityBody) -> dict[str, Any]:
    if is_internal_entity_type(body.artifact_type):
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
            notes=body.notes,
            keywords=body.keywords,
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
            notes=body.notes if "notes" in provided else _UNSET,
            keywords=body.keywords if "keywords" in provided else _UNSET,
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
