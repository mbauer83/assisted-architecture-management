"""FastAPI REST server backing the GUI Authoring Tool (Phase 1: read-only)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.common.model_query import ModelRepository
from src.common.model_query_types import ConnectionRecord, EntityRecord

app = FastAPI(title="Architecture Repository GUI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_repo: ModelRepository | None = None


def _get_repo() -> ModelRepository:
    if _repo is None:
        raise HTTPException(500, "Repository not initialized")
    return _repo


def _entity_to_summary(e: EntityRecord) -> dict[str, Any]:
    return {
        "artifact_id": e.artifact_id,
        "artifact_type": e.artifact_type,
        "name": e.name,
        "version": e.version,
        "status": e.status,
        "domain": e.domain,
        "subdomain": e.subdomain,
        "path": str(e.path),
    }


def _connection_to_dict(c: ConnectionRecord) -> dict[str, Any]:
    return {
        "artifact_id": c.artifact_id,
        "source": c.source,
        "target": c.target,
        "conn_type": c.conn_type,
        "version": c.version,
        "status": c.status,
        "path": str(c.path),
        "content_text": c.content_text,
    }


@app.get("/api/stats")
def get_stats() -> dict[str, Any]:
    return _get_repo().stats()


@app.get("/api/entities")
def list_entities(
    domain: str | None = None,
    artifact_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
) -> dict[str, Any]:
    entities = _get_repo().list_entities(
        domain=domain,
        artifact_type=artifact_type,
        status=status,
    )
    page = entities[offset : offset + limit]
    return {"total": len(entities), "items": [_entity_to_summary(e) for e in page]}


@app.get("/api/entity")
def read_entity(id: str) -> dict[str, Any]:
    result = _get_repo().read_artifact(id, mode="full")
    if result is None:
        raise HTTPException(404, f"Not found: {id!r}")
    return result


@app.get("/api/connections")
def get_connections(
    entity_id: str,
    direction: Literal["any", "outbound", "inbound"] = "any",
    conn_type: str | None = None,
) -> list[dict[str, Any]]:
    conns = _get_repo().find_connections_for(entity_id, direction=direction, conn_type=conn_type)
    return [_connection_to_dict(c) for c in conns]


@app.get("/api/neighbors")
def get_neighbors(entity_id: str, max_hops: int = 1) -> dict[str, list[str]]:
    result = _get_repo().find_neighbors(entity_id, max_hops=max_hops)
    return {hop: list(ids) for hop, ids in result.items()}


@app.get("/api/search")
def search(q: str, limit: int = Query(default=20, le=100)) -> dict[str, Any]:
    from src.common.model_query_types import EntityRecord, DiagramRecord
    result = _get_repo().search_artifacts(q, limit=limit)
    hits = []
    for h in result.hits:
        rec = h.record
        # ConnectionRecord has no artifact_type — use conn_type as fallback
        artifact_type = getattr(rec, "artifact_type", None) or getattr(rec, "conn_type", "connection")
        hit: dict[str, Any] = {
            "score": h.score,
            "record_type": h.record_type,
            "artifact_id": rec.artifact_id,
            "artifact_type": artifact_type,
            "status": rec.status,
            "path": str(rec.path),
            "name": getattr(rec, "name", ""),
        }
        if isinstance(rec, EntityRecord):
            hit["domain"] = rec.domain
            hit["subdomain"] = rec.subdomain
        hits.append(hit)
    return {"query": result.query, "hits": hits}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GUI server for architecture repository")
    parser.add_argument("--repo-root", required=True, help="Path to architecture repository root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    global _repo
    _repo = ModelRepository(Path(args.repo_root))

    gui_dist = Path(__file__).resolve().parent.parent.parent / "tools" / "gui" / "dist"
    if gui_dist.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(gui_dist), html=True), name="static")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
