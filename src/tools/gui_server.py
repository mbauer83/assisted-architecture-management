"""FastAPI REST server backing the GUI tool — read + write endpoints."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
import uvicorn

from src.common.model_query import ModelRepository
from src.common.model_query_types import ConnectionRecord, DiagramRecord, EntityRecord

app = FastAPI(title="Architecture Repository GUI", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_repo: ModelRepository | None = None
_repo_root: Path | None = None


def _get_repo() -> ModelRepository:
    if _repo is None:
        raise HTTPException(500, "Repository not initialized")
    return _repo


def _entity_to_summary(
    e: EntityRecord,
    conn_counts: dict[str, tuple[int, int, int]] | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "artifact_id": e.artifact_id, "artifact_type": e.artifact_type,
        "name": e.name, "version": e.version, "status": e.status,
        "domain": e.domain, "subdomain": e.subdomain, "path": str(e.path),
    }
    if conn_counts is not None:
        inc, sym, out = conn_counts.get(e.artifact_id, (0, 0, 0))
        d["conn_in"] = inc
        d["conn_sym"] = sym
        d["conn_out"] = out
    return d


def _build_conn_counts(repo: ModelRepository) -> dict[str, tuple[int, int, int]]:
    """Single pass over connections → {entity_id: (incoming, symmetric, outgoing)}."""
    from src.common.ontology_loader import SYMMETRIC_CONNECTIONS

    counts: dict[str, list[int]] = {}  # [in, sym, out]
    for rec in repo._connections.values():
        is_sym = rec.conn_type in SYMMETRIC_CONNECTIONS
        src = counts.setdefault(rec.source, [0, 0, 0])
        tgt = counts.setdefault(rec.target, [0, 0, 0])
        if is_sym:
            src[1] += 1
            if rec.target != rec.source:
                tgt[1] += 1
        else:
            src[2] += 1
            tgt[0] += 1
    return {k: (v[0], v[1], v[2]) for k, v in counts.items()}


def _connection_to_dict(c: ConnectionRecord) -> dict[str, Any]:
    return {
        "artifact_id": c.artifact_id, "source": c.source, "target": c.target,
        "conn_type": c.conn_type, "version": c.version, "status": c.status,
        "path": str(c.path), "content_text": c.content_text,
    }


def _diagram_to_summary(d: DiagramRecord) -> dict[str, Any]:
    return {
        "artifact_id": d.artifact_id, "name": d.name, "diagram_type": d.diagram_type,
        "version": d.version, "status": d.status, "path": str(d.path),
    }


# ── Read endpoints ────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats() -> dict[str, Any]:
    return _get_repo().stats()


@app.get("/api/entities")
def list_entities(
    domain: str | None = None, artifact_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=200, le=1000), offset: int = 0,
) -> dict[str, Any]:
    repo = _get_repo()
    entities = repo.list_entities(domain=domain, artifact_type=artifact_type, status=status)
    page = entities[offset : offset + limit]
    counts = _build_conn_counts(repo)
    return {"total": len(entities), "items": [_entity_to_summary(e, counts) for e in page]}


@app.get("/api/entity")
def read_entity(id: str) -> dict[str, Any]:
    repo = _get_repo()
    result = repo.read_artifact(id, mode="full")
    if result is None:
        raise HTTPException(404, f"Not found: {id!r}")
    # Enrich with parsed summary / properties / notes from file
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
        # Connection counts
        counts = _build_conn_counts(repo)
        inc, sym, out = counts.get(id, (0, 0, 0))
        result["conn_in"] = inc
        result["conn_sym"] = sym
        result["conn_out"] = out
    return result


@app.get("/api/connections")
def get_connections(
    entity_id: str, direction: Literal["any", "outbound", "inbound"] = "any",
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
    result = _get_repo().search_artifacts(q, limit=limit)
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
        if isinstance(rec, DiagramRecord):
            hit["diagram_type"] = rec.diagram_type
        hits.append(hit)
    return {"query": result.query, "hits": hits}


# ── Diagram endpoints ─────────────────────────────────────────────────────────

@app.get("/api/diagrams")
def list_diagrams(
    diagram_type: str | None = None, status: str | None = None,
) -> dict[str, Any]:
    diagrams = _get_repo().list_diagrams(diagram_type=diagram_type, status=status)
    return {"total": len(diagrams), "items": [_diagram_to_summary(d) for d in diagrams]}


@app.get("/api/diagram")
def read_diagram(id: str) -> dict[str, Any]:
    result = _get_repo().read_artifact(id, mode="full")
    if result is None or result.get("record_type") != "diagram":
        raise HTTPException(404, f"Diagram not found: {id!r}")
    # Resolve rendered PNG filename from the diagram path
    diag_rec = _get_repo().get_diagram(id)
    if diag_rec:
        rendered_name = _rendered_png_name(diag_rec)
        result["rendered_filename"] = rendered_name
    return result


def _rendered_png_name(d: DiagramRecord) -> str | None:
    """Derive the rendered PNG filename for a diagram."""
    if _repo_root is None:
        return None
    rendered_dir = _repo_root / "diagram-catalog" / "rendered"
    # Rendered PNGs use the friendly-name part: e.g. "application-component-map.png"
    parts = d.artifact_id.split(".")
    if len(parts) >= 3:
        friendly = ".".join(parts[2:])
        candidate = rendered_dir / f"{friendly}.png"
        if candidate.exists():
            return candidate.name
    # Fallback: search by matching stem
    if rendered_dir.exists():
        for f in rendered_dir.iterdir():
            if f.suffix == ".png" and f.stem in d.artifact_id:
                return f.name
    return None


@app.get("/api/diagram-image/{filename}")
def get_diagram_image(filename: str) -> FileResponse:
    if _repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    # Sanitize filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = _repo_root / "diagram-catalog" / "rendered" / filename
    if not path.exists():
        raise HTTPException(404, f"Rendered image not found: {filename}")
    return FileResponse(path, media_type="image/png")


@app.get("/api/diagram-refs")
def get_diagram_refs(source_id: str, target_id: str) -> list[dict[str, str]]:
    """Find diagrams that likely reference a connection between two entities."""
    repo = _get_repo()
    source_entity = repo.get_entity(source_id)
    target_entity = repo.get_entity(target_id)
    if not source_entity or not target_entity:
        return []
    src_alias = source_entity.display_alias
    tgt_alias = target_entity.display_alias
    if not src_alias or not tgt_alias:
        return []
    refs = []
    for diag in repo.list_diagrams():
        try:
            puml = diag.path.read_text(encoding="utf-8")
        except OSError:
            continue
        if src_alias in puml and tgt_alias in puml:
            refs.append({"artifact_id": diag.artifact_id, "name": diag.name})
    return refs


# ── Write endpoints ───────────────────────────────────────────────────────────

@app.get("/api/ontology")
def get_ontology(
    source_type: str,
    target_type: str | None = None,
) -> dict[str, Any]:
    """Return connection ontology data for a source entity type.

    Without target_type: returns full classification (outgoing/incoming/symmetric).
    With target_type: returns just the permissible connection types for that pair.
    """
    from src.common.connection_ontology import (
        classify_connections, permissible_connection_types, is_symmetric,
    )
    if target_type:
        conn_types = permissible_connection_types(source_type, target_type)
        return {
            "source_type": source_type, "target_type": target_type,
            "connection_types": conn_types,
            "symmetric": [ct for ct in conn_types if is_symmetric(ct)],
        }
    classification = classify_connections(source_type)
    return {"source_type": source_type, **classification}


@app.get("/api/write-help")
def get_write_help() -> dict[str, Any]:
    from src.tools.model_write.help import write_help
    return write_help()


@app.get("/api/entity-schemata")
def get_entity_schemata(artifact_type: str) -> dict[str, Any]:
    """Return the JSON attribute schema for an entity type, or {} if none configured."""
    if _repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.common.model_schema import load_attribute_schema, schema_all_properties, schema_required_properties
    schema = load_attribute_schema(_repo_root, artifact_type)
    if schema is None:
        return {"artifact_type": artifact_type, "schema": None, "properties": [], "required": []}
    return {
        "artifact_type": artifact_type,
        "schema": schema,
        "properties": schema_all_properties(schema),
        "required": schema_required_properties(schema),
    }


_DOMAIN_ORDER = ["motivation", "strategy", "common", "business", "application", "technology", "implementation"]


@app.get("/api/diagram-entities")
def get_diagram_entities(id: str) -> list[dict[str, Any]]:
    """Return entities referenced in a diagram, sorted by domain order."""
    repo = _get_repo()
    diag_rec = repo.get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {id!r}")
    try:
        puml = diag_rec.path.read_text(encoding="utf-8")
    except OSError:
        return []
    entities = []
    for rec in repo._entities.values():
        if rec.display_alias and rec.display_alias in puml:
            s = _entity_to_summary(rec)
            s["display_alias"] = rec.display_alias
            entities.append(s)
    entities.sort(key=lambda e: (
        _DOMAIN_ORDER.index(e["domain"]) if e["domain"] in _DOMAIN_ORDER else 99,
        e["name"],
    ))
    return entities


@app.get("/api/diagram-connections")
def get_diagram_connections(id: str) -> list[dict[str, Any]]:
    """Return connections between entities that are both referenced in the diagram."""
    repo = _get_repo()
    diag_rec = repo.get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {id!r}")
    try:
        puml = diag_rec.path.read_text(encoding="utf-8")
    except OSError:
        return []
    in_diagram = {
        rec.artifact_id: rec
        for rec in repo._entities.values()
        if rec.display_alias and rec.display_alias in puml
    }
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for conn in repo._connections.values():
        if conn.artifact_id in seen:
            continue
        src = in_diagram.get(conn.source)
        tgt = in_diagram.get(conn.target)
        if src and tgt:
            d = _connection_to_dict(conn)
            d["source_name"] = src.name
            d["target_name"] = tgt.name
            d["source_alias"] = src.display_alias
            d["target_alias"] = tgt.display_alias
            result.append(d)
            seen.add(conn.artifact_id)
    return result


class AddConnectionBody(BaseModel):
    source_entity: str
    connection_type: str
    target_entity: str
    description: str | None = None
    dry_run: bool = True


class RemoveConnectionBody(BaseModel):
    source_entity: str
    connection_type: str
    target_entity: str
    dry_run: bool = True


def _get_write_deps() -> tuple[Path, Any, Any]:
    """Return (repo_root, registry, verifier) for write operations."""
    if _repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.common.model_verifier import ModelVerifier
    from src.common.model_verifier_registry import ModelRegistry
    registry = ModelRegistry(_repo_root)
    verifier = ModelVerifier(registry)
    return _repo_root, registry, verifier


def _clear_caches(root: Path) -> None:
    """Clear query repository caches after a write."""
    if _repo is not None:
        _repo.refresh()


def _write_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "wrote": bool(result.wrote), "path": str(result.path),
        "artifact_id": result.artifact_id,
        "content": result.content, "warnings": result.warnings,
        "verification": result.verification,
    }


@app.post("/api/connection")
def add_connection(body: AddConnectionBody) -> dict[str, Any]:
    repo_root, registry, verifier = _get_write_deps()
    from src.tools.model_write.connection import add_connection as _add
    try:
        result = _add(
            repo_root=repo_root, registry=registry, verifier=verifier,
            clear_repo_caches=_clear_caches,
            source_entity=body.source_entity, connection_type=body.connection_type,
            target_entity=body.target_entity, description=body.description,
            version="0.1.0", status="draft", last_updated=None, dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _write_result_to_dict(result)


@app.post("/api/connection/remove")
def remove_connection(body: RemoveConnectionBody) -> dict[str, Any]:
    repo_root, registry, verifier = _get_write_deps()
    from src.tools.model_write.connection_edit import remove_connection as _remove
    try:
        result = _remove(
            repo_root=repo_root, registry=registry, verifier=verifier,
            clear_repo_caches=_clear_caches,
            source_entity=body.source_entity, connection_type=body.connection_type,
            target_entity=body.target_entity, dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _write_result_to_dict(result)


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


@app.post("/api/entity")
def create_entity(body: CreateEntityBody) -> dict[str, Any]:
    repo_root, _registry, verifier = _get_write_deps()
    from src.tools.model_write.entity import create_entity as _create
    try:
        result = _create(
            repo_root=repo_root, verifier=verifier,
            clear_repo_caches=_clear_caches,
            artifact_type=body.artifact_type, name=body.name,
            summary=body.summary, properties=body.properties,
            notes=body.notes, keywords=body.keywords,
            artifact_id=None, version=body.version,
            status=body.status, last_updated=None, dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _write_result_to_dict(result)


@app.post("/api/entity/edit")
def edit_entity(body: EditEntityBody) -> dict[str, Any]:
    repo_root, registry, verifier = _get_write_deps()
    from src.tools.model_write.entity_edit import edit_entity as _edit, _UNSET
    # Only pass fields that were explicitly included in the request body
    provided = body.model_fields_set
    try:
        result = _edit(
            repo_root=repo_root, registry=registry, verifier=verifier,
            clear_repo_caches=_clear_caches,
            artifact_id=body.artifact_id,
            name=body.name,
            summary=body.summary if "summary" in provided else _UNSET,
            properties=body.properties if "properties" in provided else _UNSET,
            notes=body.notes if "notes" in provided else _UNSET,
            keywords=body.keywords if "keywords" in provided else _UNSET,
            version=body.version, status=body.status, dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _write_result_to_dict(result)


# ── Diagram create / preview endpoints ───────────────────────────────────────

@app.get("/api/entity-display-search")
def entity_display_search(q: str, limit: int = Query(default=20, le=50)) -> list[dict[str, Any]]:
    """Search entities and return archimate display metadata (alias, element-type, label).

    Used by the diagram-creation form to populate the live entity-search dropdown.
    """
    import yaml as _yaml
    repo = _get_repo()
    result = repo.search_artifacts(q, limit=limit * 3)
    items: list[dict[str, Any]] = []
    for hit in result.hits:
        if hit.record_type != "entity":
            continue
        rec = hit.record
        if not isinstance(rec, EntityRecord):
            continue
        arch_data: dict = {}
        arch_block = rec.display_blocks.get("archimate", "")
        if arch_block:
            try:
                arch_data = _yaml.safe_load(arch_block) or {}
            except Exception:
                pass
        items.append({
            "artifact_id": rec.artifact_id, "name": rec.name,
            "artifact_type": rec.artifact_type, "domain": rec.domain,
            "subdomain": rec.subdomain, "status": rec.status,
            "display_alias": rec.display_alias,
            "element_type": arch_data.get("element-type", ""),
            "element_label": arch_data.get("label", rec.name),
        })
        if len(items) >= limit:
            break
    return items


class DiagramPreviewBody(BaseModel):
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]


@app.post("/api/diagram/preview")
def preview_diagram(body: DiagramPreviewBody) -> dict[str, Any]:
    """Generate a transient PUML + PNG preview without writing any files.

    Returns ``{puml, image, warnings}`` where *image* is a base64 data-URL or null.
    Uses the same PlantUML rendering pipeline as ``model_create_diagram``.
    """
    if _repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.tools.diagram_builder import generate_archimate_puml_body, render_puml_preview
    repo = _get_repo()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(body.name, entities, connections, diagram_type=body.diagram_type)
    image, warnings = render_puml_preview(puml, _repo_root)
    return {"puml": puml, "image": image, "warnings": warnings}


class CreateDiagramGuiBody(BaseModel):
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]
    keywords: list[str] | None = None
    version: str = "0.1.0"
    status: str = "draft"
    dry_run: bool = True


@app.post("/api/diagram")
def create_diagram_gui(body: CreateDiagramGuiBody) -> dict[str, Any]:
    """Create a diagram from a GUI-selected set of entities and connections.

    Generates PUML via ``diagram_builder``, then delegates to ``create_diagram``
    (same code path as the ``model_create_diagram`` MCP tool) for verification,
    file writing, and PNG rendering.
    """
    from src.common.model_write import generate_entity_id
    from src.tools.diagram_builder import generate_archimate_puml_body
    from src.tools.model_write.diagram import create_diagram
    repo = _get_repo()
    repo_root, _, verifier = _get_write_deps()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(body.name, entities, connections, diagram_type=body.diagram_type)
    artifact_id = generate_entity_id("DIA", body.name)
    try:
        result = create_diagram(
            repo_root=repo_root, verifier=verifier, clear_repo_caches=_clear_caches,
            diagram_type=body.diagram_type, name=body.name, puml=puml,
            artifact_id=artifact_id, keywords=body.keywords,
            version=body.version, status=body.status, last_updated=None,
            connection_inference="none", dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _write_result_to_dict(result)


def _rendered_svg_name(d: DiagramRecord) -> str | None:
    """Derive the rendered SVG filename for a diagram."""
    if _repo_root is None:
        return None
    rendered_dir = _repo_root / "diagram-catalog" / "rendered"
    parts = d.artifact_id.split(".")
    if len(parts) >= 3:
        friendly = ".".join(parts[2:])
        candidate = rendered_dir / f"{friendly}.svg"
        if candidate.exists():
            return candidate.name
    if rendered_dir.exists():
        for f in rendered_dir.iterdir():
            if f.suffix == ".svg" and f.stem in d.artifact_id:
                return f.name
    return None


@app.get("/api/diagram-svg")
def get_diagram_svg(id: str) -> Response:
    """Return SVG for a diagram — serves cached file first, falls back to live render."""
    if _repo_root is None:
        raise HTTPException(500, "Repository not initialized")

    diagram_path = _repo_root / "diagram-catalog" / "diagrams" / f"{id}.puml"
    if not diagram_path.exists():
        raise HTTPException(404, f"Diagram '{id}' not found")

    # Serve pre-computed SVG if available
    diag_rec = _get_repo().get_diagram(id)
    if diag_rec:
        svg_name = _rendered_svg_name(diag_rec)
        if svg_name:
            svg_path = _repo_root / "diagram-catalog" / "rendered" / svg_name
            if svg_path.exists():
                return Response(content=svg_path.read_bytes(), media_type="image/svg+xml")

    from src.tools.diagram_builder import render_puml_svg
    from src.tools.model_write.parse_existing import parse_diagram_file
    parsed = parse_diagram_file(diagram_path)
    svg, warnings = render_puml_svg(parsed.puml_body, _repo_root)
    if svg is None:
        raise HTTPException(500, f"SVG render failed: {'; '.join(warnings)}")
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/diagram-download")
def download_diagram(id: str, format: Literal["png", "svg"] = "png") -> FileResponse:
    """Download a rendered diagram file as an attachment."""
    if _repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    rendered_dir = _repo_root / "diagram-catalog" / "rendered"
    diag_rec = _get_repo().get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram '{id}' not found")

    if format == "svg":
        svg_name = _rendered_svg_name(diag_rec)
        if svg_name:
            path = rendered_dir / svg_name
            if path.exists():
                return FileResponse(path, media_type="image/svg+xml",
                                    headers={"Content-Disposition": f'attachment; filename="{svg_name}"'})
        raise HTTPException(404, "SVG not yet rendered — save the diagram to generate it")

    png_name = _rendered_png_name(diag_rec)
    if png_name:
        path = rendered_dir / png_name
        if path.exists():
            return FileResponse(path, media_type="image/png",
                                headers={"Content-Disposition": f'attachment; filename="{png_name}"'})
    raise HTTPException(404, "PNG not yet rendered — save the diagram to generate it")


class EditDiagramGuiBody(BaseModel):
    artifact_id: str
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]
    version: str | None = None
    status: str | None = None
    dry_run: bool = True


@app.post("/api/diagram/edit")
def edit_diagram_gui(body: EditDiagramGuiBody) -> dict[str, Any]:
    """Edit an existing diagram's entity/connection selection and regenerate its PUML.

    Regenerates PUML via ``diagram_builder`` from the given entity/connection
    selection, then delegates to ``edit_diagram`` (same code path as the
    ``model_edit_diagram`` MCP tool). Keywords are preserved from the existing file.
    """
    from src.tools.diagram_builder import generate_archimate_puml_body
    from src.tools.model_write.diagram_edit import edit_diagram
    repo = _get_repo()
    repo_root, _, verifier = _get_write_deps()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(body.name, entities, connections, diagram_type=body.diagram_type)
    try:
        result = edit_diagram(
            repo_root=repo_root, verifier=verifier, clear_repo_caches=_clear_caches,
            artifact_id=body.artifact_id, puml=puml, name=body.name,
            keywords=..., version=body.version, status=body.status,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _write_result_to_dict(result)


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="GUI server for architecture repository")
    parser.add_argument("--repo-root", default=None, help="Path to architecture repository root (default: from arch-init)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    global _repo, _repo_root
    if args.repo_root:
        _repo_root = Path(args.repo_root)
    else:
        from src.tools.workspace_init import load_init_state
        state = load_init_state()
        if state and "engagement_root" in state:
            _repo_root = Path(state["engagement_root"])
        else:
            parser.error("No --repo-root given and no .arch/init-state.yaml found. Run `arch-init` first.")
    _repo = ModelRepository(_repo_root)

    gui_dist = Path(__file__).resolve().parent.parent.parent / "tools" / "gui" / "dist"
    if gui_dist.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(gui_dist), html=True), name="static")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
