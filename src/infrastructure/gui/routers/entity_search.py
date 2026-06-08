"""Artifact search endpoints (full-text and reference/linking search)."""

from __future__ import annotations

from functools import lru_cache as _lru_cache
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from src.application.entity_type_predicates import is_assurance_entity_type, is_internal_entity_type
from src.application.runtime_catalogs import RuntimeCatalogs
from src.infrastructure.app_bootstrap import runtime_catalogs_dependency
from src.infrastructure.gui.routers import state as s


@_lru_cache(maxsize=1)
def _catalogs():
    from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry  # noqa: PLC0415

    return build_runtime_catalogs(get_module_registry())

router = APIRouter()


def _score_reference_hit(name: str, artifact_id: str, query: str) -> tuple[int, str, str]:
    q = query.strip().lower()
    if not q:
        return (3, name.lower(), artifact_id.lower())
    name_lc, id_lc = name.lower(), artifact_id.lower()
    if name_lc == q or id_lc == q:
        return (0, name_lc, id_lc)
    if name_lc.startswith(q) or id_lc.startswith(q):
        return (1, name_lc, id_lc)
    return (2, name_lc, id_lc)


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
    catalogs: RuntimeCatalogs = Depends(runtime_catalogs_dependency),
) -> dict[str, Any]:
    repo = s.get_repo()
    selected_domains = {v.strip().lower() for v in (domains or "").split(",") if v.strip()}
    selected_entity_types = {v.strip() for v in (entity_types or "").split(",") if v.strip()}
    selected_doc_types = {v.strip() for v in (doc_types or "").split(",") if v.strip()}
    q_lc = q.strip().lower()
    hits: list[dict[str, Any]] = []

    if kind in (None, "entity"):
        for entity in repo.list_entities():
            if is_internal_entity_type(entity.artifact_type, _catalogs().ontology):
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
            domain = catalogs.diagram_types.diagram_type_domain(diagram.diagram_type)
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

    hits.sort(key=lambda h: _score_reference_hit(str(h["name"]), str(h["artifact_id"]), q))
    return {"query": q, "hits": hits[:limit]}


@router.get("/api/entity-taxonomy")
def get_entity_taxonomy(
    request: Request,
    scope: str | None = None,
    meta_ontology: str | None = None,
    group: str | None = None,
) -> dict[str, Any]:
    from src.infrastructure.app_bootstrap import (  # noqa: PLC0415
        module_registry_from_app,
        resolve_meta_ontology_artifact_types,
    )

    registry = module_registry_from_app(request.app)
    repo = s.get_repo()
    entities = repo.list_entities(group=group)
    if scope == "global":
        _cat = _catalogs()
        entities = [
            e for e in entities
            if s.is_global(e.path) and not is_assurance_entity_type(e.artifact_type, _cat.module_catalog)
        ]
    elif scope == "engagement":
        _cat = _catalogs()
        entities = [
            e for e in entities
            if not s.is_global(e.path)
            and not is_internal_entity_type(e.artifact_type, _cat.ontology)
            and not is_assurance_entity_type(e.artifact_type, _cat.module_catalog)
        ]
    else:
        _cat = _catalogs()
        entities = [
            e for e in entities
            if not is_internal_entity_type(e.artifact_type, _cat.ontology)
            and not is_assurance_entity_type(e.artifact_type, _cat.module_catalog)
        ]

    allowed_types = resolve_meta_ontology_artifact_types(meta_ontology or "", registry)
    if allowed_types is not None:
        entities = [e for e in entities if e.artifact_type in allowed_types]

    domain_type_counts: dict[str, dict[str, int]] = {}
    for entity in entities:
        domain = entity.domain or ""
        tc = domain_type_counts.setdefault(domain, {})
        tc[entity.artifact_type] = tc.get(entity.artifact_type, 0) + 1

    ordered = registry.domain_order()
    extra = [d for d in domain_type_counts if d not in ordered]
    domains = []
    for domain_name in ordered + extra:
        tc = domain_type_counts.get(domain_name, {})
        if not tc:
            continue
        types = [{"name": t, "count": c} for t, c in sorted(tc.items())]
        domains.append({"name": domain_name, "count": sum(tc.values()), "types": types})
    return {"domains": domains}
