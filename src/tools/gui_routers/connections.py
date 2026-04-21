"""Connection read and write endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.tools.gui_routers import state as s

router = APIRouter()


@router.get("/api/connections")
def get_connections(
    entity_id: str,
    direction: Literal["any", "outbound", "inbound"] = "any",
    conn_type: str | None = None,
) -> list[dict[str, Any]]:
    conns = s.get_repo().find_connections_for(entity_id, direction=direction, conn_type=conn_type)
    return [s.connection_to_dict(c) for c in conns]


@router.get("/api/neighbors")
def get_neighbors(entity_id: str, max_hops: int = 1) -> dict[str, list[str]]:
    result = s.get_repo().find_neighbors(entity_id, max_hops=max_hops)
    return {hop: list(ids) for hop, ids in result.items()}


@router.get("/api/search")
def search(q: str, limit: int = 20) -> dict[str, Any]:
    from src.common.model_query_types import DiagramRecord, EntityRecord
    result = s.get_repo().search_artifacts(q, limit=limit)
    hits = []
    for h in result.hits:
        rec = h.record
        artifact_type = getattr(rec, "artifact_type", None) or getattr(rec, "conn_type", "connection")
        hit: dict[str, Any] = {
            "score": h.score, "record_type": h.record_type,
            "artifact_id": rec.artifact_id, "artifact_type": artifact_type,
            "status": rec.status, "path": str(rec.path), "name": getattr(rec, "name", ""),
        }
        if isinstance(rec, EntityRecord):
            hit["domain"] = rec.domain
            hit["subdomain"] = rec.subdomain
            hit["is_global"] = s.is_global(rec.path)
        if isinstance(rec, DiagramRecord):
            hit["diagram_type"] = rec.diagram_type
        hits.append(hit)
    return {"query": result.query, "hits": hits}


@router.get("/api/ontology")
def get_ontology(source_type: str, target_type: str | None = None) -> dict[str, Any]:
    from src.common.connection_ontology import (
        classify_connections, is_symmetric, permissible_connection_types,
    )
    if target_type:
        conn_types = permissible_connection_types(source_type, target_type)
        return {
            "source_type": source_type, "target_type": target_type,
            "connection_types": conn_types,
            "symmetric": [ct for ct in conn_types if is_symmetric(ct)],
        }
    return {"source_type": source_type, **classify_connections(source_type)}


@router.get("/api/write-help")
def get_write_help() -> dict[str, Any]:
    from src.tools.model_write.help import write_help
    return write_help()


class AddConnectionBody(BaseModel):
    source_entity: str
    connection_type: str
    target_entity: str
    description: str | None = None
    src_cardinality: str | None = None
    tgt_cardinality: str | None = None
    dry_run: bool = True


class RemoveConnectionBody(BaseModel):
    source_entity: str
    connection_type: str
    target_entity: str
    dry_run: bool = True


@router.post("/api/connection")
def add_connection(body: AddConnectionBody) -> dict[str, Any]:
    repo_root, registry, verifier = s.get_write_deps()
    from src.tools.model_write.connection import add_connection as _add

    effective_source = body.source_entity
    effective_target = body.target_entity
    grf_source_id: str | None = None
    grf_artifact_id: str | None = None
    grf_warnings: list[str] = []

    def _ensure_grf(global_id: str) -> str:
        nonlocal registry, verifier
        from src.tools.model_write.global_entity_reference import ensure_global_entity_reference
        repo = s.get_repo()
        global_rec = repo.get_entity(global_id)
        global_name = global_rec.name if global_rec else global_id
        grf_result = s.run_serialized_write(
            ensure_global_entity_reference,
            engagement_repo=repo,
            engagement_root=repo_root,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            global_entity_id=global_id,
            global_entity_name=global_name,
            dry_run=body.dry_run,
        )
        if grf_result.wrote:
            grf_warnings.append(f"Created global-entity-reference proxy {grf_result.artifact_id}")
            _, registry, verifier = s.get_write_deps()
        else:
            grf_warnings.append(f"Routed via existing global-entity-reference {grf_result.artifact_id}")
        return grf_result.artifact_id

    if s._enterprise_root is not None and registry.scope_of_entity(body.source_entity) == "enterprise":
        grf_source_id = _ensure_grf(body.source_entity)
        effective_source = grf_source_id

    if s._enterprise_root is not None and registry.scope_of_entity(body.target_entity) == "enterprise":
        grf_artifact_id = _ensure_grf(body.target_entity)
        effective_target = grf_artifact_id

    try:
        result = s.run_serialized_write(
            _add,
            repo_root=repo_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            source_entity=effective_source,
            connection_type=body.connection_type,
            target_entity=effective_target,
            description=body.description,
            src_cardinality=body.src_cardinality,
            tgt_cardinality=body.tgt_cardinality,
            version="0.1.0",
            status="draft",
            last_updated=None,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    d = s.write_result_to_dict(result)
    if grf_source_id:
        d["grf_source_id"] = grf_source_id
        d["original_source"] = body.source_entity
    if grf_artifact_id:
        d["grf_artifact_id"] = grf_artifact_id
        d["original_target"] = body.target_entity
    if grf_warnings:
        d["warnings"] = (d.get("warnings") or []) + grf_warnings
    return d


class EditConnectionBody(BaseModel):
    source_entity: str
    connection_type: str
    target_entity: str
    description: str | None = None
    src_cardinality: str | None = None
    tgt_cardinality: str | None = None
    dry_run: bool = True


class ConnectionAssociateBody(BaseModel):
    source_entity: str
    connection_type: str
    target_entity: str
    add_entities: list[str] | None = None
    remove_entities: list[str] | None = None
    dry_run: bool = True


@router.post("/api/connection/edit")
def edit_connection(body: EditConnectionBody) -> dict[str, Any]:
    repo_root, registry, verifier = s.get_write_deps()
    from src.tools.model_write.connection_edit import edit_connection as _edit, _UNSET
    provided = body.model_fields_set
    try:
        result = s.run_serialized_write(
            _edit,
            repo_root=repo_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            source_entity=body.source_entity,
            connection_type=body.connection_type,
            target_entity=body.target_entity,
            description=body.description,
            src_cardinality=body.src_cardinality if "src_cardinality" in provided else _UNSET,
            tgt_cardinality=body.tgt_cardinality if "tgt_cardinality" in provided else _UNSET,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/connection/associate")
def manage_connection_associations(body: ConnectionAssociateBody) -> dict[str, Any]:
    repo_root, registry, verifier = s.get_write_deps()
    from src.tools.model_write.connection_edit import edit_connection_associations as _assoc
    try:
        result = s.run_serialized_write(
            _assoc,
            repo_root=repo_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            source_entity=body.source_entity,
            connection_type=body.connection_type,
            target_entity=body.target_entity,
            add_entities=body.add_entities,
            remove_entities=body.remove_entities,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/connection/remove")
def remove_connection(body: RemoveConnectionBody) -> dict[str, Any]:
    repo_root, registry, verifier = s.get_write_deps()
    from src.tools.model_write.connection_edit import remove_connection as _remove
    try:
        result = s.run_serialized_write(
            _remove,
            repo_root=repo_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            source_entity=body.source_entity,
            connection_type=body.connection_type,
            target_entity=body.target_entity,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


# ── Broken-reference cleanup ──────────────────────────────────────────────────

class CleanupBrokenRefsBody(BaseModel):
    dry_run: bool = True


@router.post("/api/cleanup-broken-refs")
def cleanup_broken_refs(body: CleanupBrokenRefsBody) -> dict[str, Any]:
    """Find and optionally remove broken global-entity-reference proxies.

    A GRF is broken when the enterprise entity it points to no longer exists.
    dry_run=true (default) returns the plan without modifying files.
    """
    from src.tools.model_write.cleanup_broken_refs import cleanup_broken_refs as _cleanup
    import dataclasses
    eng_root = s._repo_root
    ent_root = s._enterprise_root
    if eng_root is None:
        raise HTTPException(500, "Repository not initialized")
    if ent_root is None:
        raise HTTPException(500, "Enterprise repository not configured")
    report = _cleanup(eng_root, ent_root, dry_run=body.dry_run)
    return {
        "dry_run": body.dry_run,
        "broken_grfs": report.broken_grfs,
        "actions": [dataclasses.asdict(a) for a in report.actions],
        "executed": report.executed,
        "errors": report.errors,
    }
