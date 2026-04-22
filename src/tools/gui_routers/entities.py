"""Entity read and write endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.tools.gui_routers.entity_listing import build_entity_summary_rows
from src.tools.gui_routers import state as s

router = APIRouter()


def _score_reference_hit(name: str, artifact_id: str, query: str) -> tuple[int, str, str]:
    q = query.strip().lower()
    if not q:
        return (3, name.lower(), artifact_id.lower())
    name_lc = name.lower()
    id_lc = artifact_id.lower()
    if name_lc == q or id_lc == q:
        return (0, name_lc, id_lc)
    if name_lc.startswith(q) or id_lc.startswith(q):
        return (1, name_lc, id_lc)
    return (2, name_lc, id_lc)


def _diagram_domain(diagram_type: str) -> str | None:
    if not diagram_type.startswith("archimate-"):
        return None
    suffix = diagram_type.removeprefix("archimate-")
    domain = suffix.split("-", 1)[0]
    return domain if domain in {"motivation", "strategy", "business", "application", "technology", "common"} else None


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
        from src.tools.artifact_write.parse_existing import parse_entity_file
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


@router.get("/api/entity-context")
def read_entity_context(id: str) -> dict[str, Any]:
    repo = s.get_repo()
    context = repo.read_entity_context(id)
    if context is None:
        raise HTTPException(404, f"Not found: {id!r}")
    entity_rec = repo.get_entity(id)
    if entity_rec is not None:
        from src.tools.artifact_write.parse_existing import parse_entity_file
        try:
            parsed = parse_entity_file(entity_rec.path)
            context["entity"]["summary"] = parsed.summary or ""
            context["entity"]["properties"] = parsed.properties
            context["entity"]["notes"] = parsed.notes or ""
        except Exception:  # noqa: BLE001
            pass
        context["entity"]["is_global"] = s.is_global(entity_rec.path)
    return context


@router.get("/api/entity-schemata")
def get_entity_schemata(artifact_type: str) -> dict[str, Any]:
    repo_root = s._repo_root
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.common.artifact_schema import (
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
    from src.tools.artifact_write.entity import create_entity as _create
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
    from src.tools.artifact_write.entity_edit import edit_entity as _edit, _UNSET
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


@router.get("/api/artifact-search")
def search_artifacts(
    q: str,
    limit: int = Query(default=20, le=100),
    include_connections: bool = False,
    include_diagrams: bool = True,
    include_documents: bool = True,
) -> dict[str, Any]:
    repo = s.get_repo()
    result = repo.search_artifacts(
        q,
        limit=limit,
        include_connections=include_connections,
        include_diagrams=include_diagrams,
        include_documents=include_documents,
    )
    hits = []
    for h in result.hits:
        aid = getattr(h.record, "artifact_id", "")
        hits.append({
            "score": h.score,
            "record_type": h.record_type,
            "artifact_id": aid,
            "name": getattr(h.record, "name", getattr(h.record, "title", "")),
            "status": getattr(h.record, "status", ""),
            "path": str(h.record.path),
        })
    return {"query": result.query, "hits": hits}


@router.get("/api/reference-search")
def search_reference_artifacts(
    q: str = "",
    kind: str | None = None,
    domains: str | None = None,
    entity_types: str | None = None,
    doc_types: str | None = None,
    limit: int = Query(default=30, le=100),
) -> dict[str, Any]:
    repo = s.get_repo()
    selected_domains = {value.strip().lower() for value in (domains or "").split(",") if value.strip()}
    selected_entity_types = {value.strip() for value in (entity_types or "").split(",") if value.strip()}
    selected_doc_types = {value.strip() for value in (doc_types or "").split(",") if value.strip()}
    q_lc = q.strip().lower()

    hits: list[dict[str, Any]] = []

    if kind in (None, "entity"):
        for entity in repo.list_entities():
            if entity.artifact_type == "global-entity-reference":
                continue
            if selected_domains and entity.domain not in selected_domains:
                continue
            if selected_entity_types and entity.artifact_type not in selected_entity_types:
                continue
            if q_lc and q_lc not in entity.name.lower() and q_lc not in entity.artifact_id.lower():
                continue
            hits.append({
                "artifact_id": entity.artifact_id,
                "record_type": "entity",
                "name": entity.name,
                "status": entity.status,
                "path": str(entity.path),
                "domain": entity.domain,
                "artifact_type": entity.artifact_type,
                "is_global": s.is_global(entity.path),
            })

    if kind in (None, "diagram"):
        for diagram in repo.list_diagrams():
            domain = _diagram_domain(diagram.diagram_type)
            if selected_domains and (domain is None or domain not in selected_domains):
                continue
            if q_lc and q_lc not in diagram.name.lower() and q_lc not in diagram.artifact_id.lower():
                continue
            hits.append({
                "artifact_id": diagram.artifact_id,
                "record_type": "diagram",
                "name": diagram.name,
                "status": diagram.status,
                "path": str(diagram.path),
                "diagram_type": diagram.diagram_type,
                "domain": domain,
            })

    if kind in (None, "document"):
        for document in repo.list_documents():
            if selected_doc_types and document.doc_type not in selected_doc_types:
                continue
            if q_lc and q_lc not in document.title.lower() and q_lc not in document.artifact_id.lower():
                continue
            hits.append({
                "artifact_id": document.artifact_id,
                "record_type": "document",
                "name": document.title,
                "status": document.status,
                "path": str(document.path),
                "doc_type": document.doc_type,
                "sections": list(document.sections),
            })

    hits.sort(key=lambda hit: _score_reference_hit(str(hit["name"]), str(hit["artifact_id"]), q))
    return {"query": q, "hits": hits[:limit]}


@router.post("/api/entity/remove")
def delete_entity(body: DeleteEntityBody) -> dict[str, Any]:
    repo_root, registry, _verifier = s.get_write_deps()
    from src.tools.artifact_write.entity_delete import delete_entity as _delete
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
