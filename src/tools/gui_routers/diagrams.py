"""Diagram read, write, and search endpoints."""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from src.common.model_query_parsing import extract_declared_puml_aliases, normalize_puml_alias
from src.common.model_query_types import DiagramRecord, EntityRecord
from src.common.ontology_loader import DOMAIN_ORDER as _DOMAIN_ORDER
from src.tools.gui_routers import state as s

router = APIRouter()


def _rendered_name(d: DiagramRecord, suffix: str) -> str | None:
    repo_root = s._repo_root
    if repo_root is None:
        return None
    rendered_dir = repo_root / "diagram-catalog" / "rendered"
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
    return result


@router.get("/api/diagram-image/{filename}")
def get_diagram_image(filename: str) -> FileResponse:
    if s._repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = s._repo_root / "diagram-catalog" / "rendered" / filename
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
        if _puml_contains(d, src.display_alias, tgt.display_alias)
    ]


def _puml_contains(d: DiagramRecord, *aliases: str) -> bool:
    try:
        puml = d.path.read_text(encoding="utf-8")
        declared_aliases = _declared_aliases_in_puml(puml)
        return all(normalize_puml_alias(a) in declared_aliases for a in aliases)
    except OSError:
        return False


def _declared_aliases_in_puml(puml: str) -> set[str]:
    return extract_declared_puml_aliases(puml)


@router.get("/api/diagram-entities")
def get_diagram_entities(id: str) -> list[dict[str, Any]]:
    repo = s.get_repo()
    diag_rec = repo.get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {id!r}")
    try:
        puml = diag_rec.path.read_text(encoding="utf-8")
    except OSError:
        return []
    declared_aliases = _declared_aliases_in_puml(puml)
    entities = []
    for rec in repo._entities.values():
        if rec.display_alias and normalize_puml_alias(rec.display_alias) in declared_aliases:
            row = s.entity_to_summary(rec)
            row["display_alias"] = rec.display_alias
            entities.append(row)
    entities.sort(key=lambda e: (
        _DOMAIN_ORDER.index(e["domain"]) if e["domain"] in _DOMAIN_ORDER else 99,
        e["name"],
    ))
    return entities


def _parse_explicit_connection_pairs(puml: str) -> set[tuple[str, str]]:
    """Return (src_alias, tgt_alias) pairs for connection lines explicitly drawn in PUML.

    Skips comment lines and hidden layout links so only visible connections are
    reported. Checks both directions so symmetric connections (association) match
    regardless of which alias appears first.
    """
    _conn_re = re.compile(
        r"^\s*(\w+)\s+"
        r"([-.*|o<>][^\s]*[-.*|o<>])"
        r"\s+(\w+)"
    )
    pairs: set[tuple[str, str]] = set()
    for line in puml.splitlines():
        stripped = line.strip()
        if stripped.startswith("'") or "[hidden]" in stripped:
            continue
        m = _conn_re.match(line)
        if m:
            pairs.add((normalize_puml_alias(m.group(1)), normalize_puml_alias(m.group(3))))
    return pairs


@router.get("/api/diagram-connections")
def get_diagram_connections(id: str) -> list[dict[str, Any]]:
    repo = s.get_repo()
    diag_rec = repo.get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram not found: {id!r}")
    try:
        puml = diag_rec.path.read_text(encoding="utf-8")
    except OSError:
        return []
    declared_aliases = _declared_aliases_in_puml(puml)
    in_diagram = {
        rec.artifact_id: rec
        for rec in repo._entities.values()
        if rec.display_alias and normalize_puml_alias(rec.display_alias) in declared_aliases
    }
    explicit_pairs = _parse_explicit_connection_pairs(puml)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for conn in repo._connections.values():
        if conn.artifact_id in seen:
            continue
        src = in_diagram.get(conn.source)
        tgt = in_diagram.get(conn.target)
        if src and tgt:
            sa = normalize_puml_alias(src.display_alias or "")
            ta = normalize_puml_alias(tgt.display_alias or "")
            if (sa, ta) not in explicit_pairs and (ta, sa) not in explicit_pairs:
                continue
            d = s.connection_to_dict(conn)
            d["source_name"] = src.name
            d["target_name"] = tgt.name
            d["source_alias"] = sa
            d["target_alias"] = ta
            result.append(d)
            seen.add(conn.artifact_id)
    return result


@router.get("/api/diagram-svg")
def get_diagram_svg(id: str) -> Response:
    repo_root = s._repo_root
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    diagram_path = repo_root / "diagram-catalog" / "diagrams" / f"{id}.puml"
    if not diagram_path.exists():
        raise HTTPException(404, f"Diagram '{id}' not found")
    diag_rec = s.get_repo().get_diagram(id)
    if diag_rec:
        svg_name = _rendered_name(diag_rec, ".svg")
        if svg_name:
            svg_path = repo_root / "diagram-catalog" / "rendered" / svg_name
            if svg_path.exists():
                return Response(content=svg_path.read_bytes(), media_type="image/svg+xml")
    from src.tools.diagram_builder import render_puml_svg
    from src.tools.model_write.parse_existing import parse_diagram_file
    parsed = parse_diagram_file(diagram_path)
    svg, warnings = render_puml_svg(parsed.puml_body, repo_root)
    if svg is None:
        raise HTTPException(500, f"SVG render failed: {'; '.join(warnings)}")
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/api/diagram-download")
def download_diagram(id: str, format: Literal["png", "svg"] = "png") -> FileResponse:
    repo_root = s._repo_root
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    diag_rec = s.get_repo().get_diagram(id)
    if diag_rec is None:
        raise HTTPException(404, f"Diagram '{id}' not found")
    rendered_dir = repo_root / "diagram-catalog" / "rendered"
    suffix = ".svg" if format == "svg" else ".png"
    media = "image/svg+xml" if format == "svg" else "image/png"
    fname = _rendered_name(diag_rec, suffix)
    if fname:
        path = rendered_dir / fname
        if path.exists():
            return FileResponse(path, media_type=media,
                                headers={"Content-Disposition": f'attachment; filename="{fname}"'})
    raise HTTPException(404, f"{format.upper()} not yet rendered — save the diagram first")


@router.get("/api/entity-display-search")
def entity_display_search(q: str, limit: int = Query(default=20, le=50)) -> list[dict[str, Any]]:
    import yaml as _yaml
    repo = s.get_repo()
    hits = repo.search_artifacts(q, limit=limit * 3).hits
    items: list[dict[str, Any]] = []
    for h in hits:
        if h.record_type != "entity" or not isinstance(h.record, EntityRecord):
            continue
        rec = h.record
        if rec.artifact_type == "global-entity-reference":
            continue
        arch_data: dict = {}
        arch_block = rec.display_blocks.get("archimate", "")
        if arch_block:
            try:
                arch_data = _yaml.safe_load(arch_block) or {}
            except Exception:  # noqa: BLE001
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


class CreateDiagramGuiBody(BaseModel):
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]
    keywords: list[str] | None = None
    version: str = "0.1.0"
    status: str = "draft"
    dry_run: bool = True


class EditDiagramGuiBody(BaseModel):
    artifact_id: str
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]
    version: str | None = None
    status: str | None = None
    dry_run: bool = True


class DeleteDiagramBody(BaseModel):
    artifact_id: str
    dry_run: bool = True


@router.post("/api/diagram/preview")
def preview_diagram(body: DiagramPreviewBody) -> dict[str, Any]:
    repo_root = s._repo_root
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.tools.diagram_builder import generate_archimate_puml_body, render_puml_preview
    repo = s.get_repo()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(body.name, entities, connections, diagram_type=body.diagram_type)
    image, warnings = render_puml_preview(puml, repo_root)
    return {"puml": puml, "image": image, "warnings": warnings}


@router.post("/api/diagram")
def create_diagram_gui(body: CreateDiagramGuiBody) -> dict[str, Any]:
    from src.common.model_write import generate_entity_id
    from src.tools.diagram_builder import generate_archimate_puml_body
    from src.tools.model_write.diagram import create_diagram
    repo = s.get_repo()
    repo_root, _, verifier = s.get_write_deps()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(body.name, entities, connections, diagram_type=body.diagram_type)
    try:
        result = create_diagram(
            repo_root=repo_root, verifier=verifier, clear_repo_caches=s.clear_caches,
            diagram_type=body.diagram_type, name=body.name, puml=puml,
            artifact_id=generate_entity_id("DIA", body.name), keywords=body.keywords,
            entity_ids_used=body.entity_ids, connection_ids_used=body.connection_ids,
            version=body.version, status=body.status, last_updated=None,
            connection_inference="none", dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/diagram/edit")
def edit_diagram_gui(body: EditDiagramGuiBody) -> dict[str, Any]:
    from src.tools.diagram_builder import generate_archimate_puml_body
    from src.tools.model_write.diagram_edit import edit_diagram
    repo = s.get_repo()
    repo_root, _, verifier = s.get_write_deps()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(body.name, entities, connections, diagram_type=body.diagram_type)
    try:
        result = edit_diagram(
            repo_root=repo_root, verifier=verifier, clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id, puml=puml, name=body.name,
            keywords=..., entity_ids_used=body.entity_ids, connection_ids_used=body.connection_ids,
            version=body.version, status=body.status, dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/diagram/remove")
def delete_diagram_gui(body: DeleteDiagramBody) -> dict[str, Any]:
    repo_root, _registry, _verifier = s.get_write_deps()
    from src.tools.model_write.diagram_delete import delete_diagram
    try:
        result = delete_diagram(
            repo_root=repo_root, clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id, dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)
