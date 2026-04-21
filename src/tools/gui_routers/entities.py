"""Entity read and write endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.tools.gui_routers.entity_listing import build_entity_summary_rows
from src.tools.gui_routers import state as s

router = APIRouter()


@router.get("/api/stats")
def get_stats() -> dict[str, Any]:
    return s.get_repo().stats()


@router.get("/api/entities")
def list_entities(
    domain: str | None = None, artifact_type: str | None = None,
    status: str | None = None, scope: str | None = None,
    limit: int = Query(default=200, le=1000), offset: int = 0,
) -> dict[str, Any]:
    repo = s.get_repo()
    entities = repo.list_entities(domain=domain, artifact_type=artifact_type, status=status)
    if scope == "global":
        entities = [e for e in entities if s.is_global(e.path)]
    elif scope == "engagement":
        entities = [e for e in entities if not s.is_global(e.path)
                    and e.artifact_type != "global-entity-reference"]
    else:
        entities = [e for e in entities if e.artifact_type != "global-entity-reference"]
    page = entities[offset: offset + limit]
    return {"total": len(entities), "items": build_entity_summary_rows(page, repo)}


@router.get("/api/entity")
def read_entity(id: str) -> dict[str, Any]:
    repo = s.get_repo()
    result = repo.read_artifact(id, mode="full")
    if result is None:
        raise HTTPException(404, f"Not found: {id!r}")
    entity_rec = repo.get_entity(id)
    if entity_rec is not None:
        from src.tools.model_write.parse_existing import parse_entity_file
        try:
            parsed = parse_entity_file(entity_rec.path)
            result["summary"] = parsed.summary or ""
            result["properties"] = parsed.properties
            result["notes"] = parsed.notes or ""
        except Exception:  # noqa: BLE001
            pass
        counts = s.build_conn_counts(repo)
        inc, sym, out = counts.get(id, (0, 0, 0))
        result["conn_in"] = inc
        result["conn_sym"] = sym
        result["conn_out"] = out
        result["is_global"] = s.is_global(entity_rec.path)
    return result


@router.get("/api/entity-schemata")
def get_entity_schemata(artifact_type: str) -> dict[str, Any]:
    repo_root = s._repo_root
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.common.model_schema import (
        load_attribute_schema, schema_all_properties, schema_required_properties,
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
    if body.artifact_type == "global-entity-reference":
        raise HTTPException(400, "global-entity-reference entities cannot be created directly")
    repo_root, _registry, verifier = s.get_write_deps()
    from src.tools.model_write.entity import create_entity as _create
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
    from src.tools.model_write.entity_edit import edit_entity as _edit, _UNSET
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
    from src.tools.model_write.entity_delete import delete_entity as _delete
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
