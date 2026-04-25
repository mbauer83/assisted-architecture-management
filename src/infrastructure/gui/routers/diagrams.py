"""Diagram read and search endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS, RENDERED
from src.domain.artifact_types import DiagramRecord, EntityRecord
from src.infrastructure.gui.routers import state as s
from src.infrastructure.gui.routers._diagram_context import (
    candidate_connections_for_entities,
    diagram_context_payload,
    diagram_entities_and_puml,
    entity_display_item,
    fuzzy_entity_hits,
    hop_suggestions,
    puml_contains,
)
from src.infrastructure.gui.routers._diagram_write import router as _write_router

router = APIRouter()
router.include_router(_write_router)


def _rendered_name(d: DiagramRecord, suffix: str) -> str | None:
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        return None
    rendered_dir = repo_root / DIAGRAM_CATALOG / RENDERED
    parts = d.artifact_id.split(".")
    if len(parts) >= 3:
        candidate = rendered_dir / f"{'.'.join(parts[2:])}{suffix}"
        if candidate.exists():
            return candidate.name
    if rendered_dir.exists():
        for f in rendered_dir.iterdir():
            if f.suffix == suffix and f.stem in d.artifact_id:
                return f.name
    return None


@router.get("/api/diagrams")
def list_diagrams(diagram_type: str | None = None, status: str | None = None) -> dict[str, Any]:
    diagrams = s.get_repo().list_diagrams(diagram_type=diagram_type, status=status)
    return {"total": len(diagrams), "items": [s.diagram_to_summary(d) for d in diagrams]}


@router.get("/api/diagram")
def read_diagram(id: str) -> dict[str, Any]:
    result = s.get_repo().read_artifact(id, mode="full")
    if result is None or result.get("record_type") != "diagram":
        raise HTTPException(404, f"Diagram not found: {id!r}")
    diag_rec = s.get_repo().get_diagram(id)
    if diag_rec:
        result["rendered_filename"] = _rendered_name(diag_rec, ".png")
        result["is_global"] = s.is_global(diag_rec.path)
        from src.infrastructure.write.artifact_write.parse_existing import parse_diagram_file

        parsed = parse_diagram_file(diag_rec.path)
        entity_ids_used = parsed.frontmatter.get("entity-ids-used")
        connection_ids_used = parsed.frontmatter.get("connection-ids-used")
        if isinstance(entity_ids_used, list):
            result["entity_ids_used"] = [str(x) for x in entity_ids_used]
        if isinstance(connection_ids_used, list):
            result["connection_ids_used"] = [str(x) for x in connection_ids_used]
    return result


@router.get("/api/diagram-image/{filename}")
def get_diagram_image(filename: str) -> FileResponse:
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = repo_root / DIAGRAM_CATALOG / RENDERED / filename
    if not path.exists():
        raise HTTPException(404, f"Rendered image not found: {filename}")
    return FileResponse(path, media_type="image/png")


@router.get("/api/diagram-refs")
def get_diagram_refs(source_id: str, target_id: str) -> list[dict[str, str]]:
    repo = s.get_repo()
    src = repo.get_entity(source_id)
    tgt = repo.get_entity(target_id)
    if not src or not tgt or not src.display_alias or not tgt.display_alias:
        return []
    return [
        {"artifact_id": d.artifact_id, "name": d.name}
        for d in repo.list_diagrams()
        if puml_contains(d, src.display_alias, tgt.display_alias)
    ]


@router.get("/api/diagram-entities")
def get_diagram_entities(id: str) -> list[dict[str, Any]]:
    repo = s.get_repo()
    diag_rec = repo.get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {id!r}")
    entities, _puml = diagram_entities_and_puml(repo, diag_rec)
    return entities


@router.get("/api/diagram-connections")
def get_diagram_connections(id: str) -> list[dict[str, Any]]:
    repo = s.get_repo()
    diag_rec = repo.get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {id!r}")
    return diagram_context_payload(repo, diag_rec)["connections"]


@router.get("/api/diagram-context")
def get_diagram_context(id: str) -> dict[str, Any]:
    repo = s.get_repo()
    diag_rec = repo.get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {id!r}")
    return diagram_context_payload(repo, diag_rec)


@router.get("/api/diagram-svg")
def get_diagram_svg(id: str) -> Response:
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    diagram_path = repo_root / DIAGRAM_CATALOG / DIAGRAMS / f"{id}.puml"
    if not diagram_path.exists():
        raise HTTPException(404, f"Diagram '{id}' not found")
    diag_rec = s.get_repo().get_diagram(id)
    if diag_rec:
        svg_name = _rendered_name(diag_rec, ".svg")
        if svg_name:
            svg_path = repo_root / DIAGRAM_CATALOG / RENDERED / svg_name
            if svg_path.exists():
                return Response(content=svg_path.read_bytes(), media_type="image/svg+xml")
    from src.infrastructure.rendering.diagram_builder import render_puml_svg
    from src.infrastructure.write.artifact_write.parse_existing import parse_diagram_file

    parsed = parse_diagram_file(diagram_path)
    svg, warnings = render_puml_svg(parsed.puml_body, repo_root)
    if svg is None:
        raise HTTPException(500, f"SVG render failed: {'; '.join(warnings)}")
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/api/diagram-download")
def download_diagram(id: str, format: Literal["png", "svg"] = "png") -> FileResponse:
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    diag_rec = s.get_repo().get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram '{id}' not found")
    rendered_dir = repo_root / DIAGRAM_CATALOG / RENDERED
    suffix = ".svg" if format == "svg" else ".png"
    media = "image/svg+xml" if format == "svg" else "image/png"
    fname = _rendered_name(diag_rec, suffix)
    if fname:
        path = rendered_dir / fname
        if path.exists():
            return FileResponse(
                path,
                media_type=media,
                headers={"Content-Disposition": f'attachment; filename="{fname}"'},
            )
    raise HTTPException(404, f"{format.upper()} not yet rendered — save the diagram first")


@router.get("/api/entity-display-search")
def entity_display_search(q: str, limit: int = Query(default=20, le=50)) -> list[dict[str, Any]]:
    repo = s.get_repo()
    hits = repo.search_artifacts(q, limit=limit * 3).hits
    items: list[dict[str, Any]] = []
    for h in hits:
        if h.record_type != "entity" or not isinstance(h.record, EntityRecord):
            continue
        rec = h.record
        if rec.artifact_type == "global-artifact-reference":
            continue
        items.append(entity_display_item(rec))
        if len(items) >= limit:
            break
    if len(items) < limit:
        seen = {str(item["artifact_id"]) for item in items}
        items.extend(fuzzy_entity_hits(repo, q, limit - len(items), seen))
    return items


@router.get("/api/diagram-entity-discovery")
def diagram_entity_discovery(
    q: str | None = None,
    included_entity_ids: str | None = None,
    max_hops: int = Query(default=2, ge=1, le=4),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    repo = s.get_repo()
    included = [
        entity_id.strip()
        for entity_id in (included_entity_ids or "").split(",")
        if entity_id.strip() and repo.get_entity(entity_id.strip()) is not None
    ]
    excluded = set(included)
    search_results: list[dict[str, Any]] = (
        entity_display_search(q or "", limit=limit) if (q or "").strip() else []
    )
    search_results = [item for item in search_results if str(item["artifact_id"]) not in excluded][
        :limit
    ]
    return {
        "search_results": search_results,
        "candidate_connections": candidate_connections_for_entities(repo, included),
        "suggested_entities": hop_suggestions(
            repo, included, max_hops=max_hops, limit_per_hop=limit
        ),
    }
