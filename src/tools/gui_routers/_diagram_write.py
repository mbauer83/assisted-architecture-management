"""Diagram write (POST) endpoints for the diagram GUI router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.tools.gui_routers import state as s

router = APIRouter()


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
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.tools.diagram_builder import generate_archimate_puml_body, render_puml_preview

    repo = s.get_repo()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(
        body.name, entities, connections, diagram_type=body.diagram_type
    )
    image, warnings = render_puml_preview(puml, repo_root)
    return {"puml": puml, "image": image, "warnings": warnings}


@router.post("/api/diagram")
def create_diagram_gui(body: CreateDiagramGuiBody) -> dict[str, Any]:
    from src.common.artifact_write import generate_entity_id
    from src.tools.artifact_write.diagram import create_diagram
    from src.tools.diagram_builder import generate_archimate_puml_body

    repo = s.get_repo()
    repo_root, _, verifier = s.get_write_deps()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(
        body.name, entities, connections, diagram_type=body.diagram_type
    )
    try:
        result = s.run_serialized_write(
            create_diagram,
            repo_root=repo_root,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            diagram_type=body.diagram_type,
            name=body.name,
            puml=puml,
            artifact_id=generate_entity_id("DIA", body.name),
            keywords=body.keywords,
            entity_ids_used=body.entity_ids,
            connection_ids_used=body.connection_ids,
            version=body.version,
            status=body.status,
            last_updated=None,
            connection_inference="none",
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/diagram/edit")
def edit_diagram_gui(body: EditDiagramGuiBody) -> dict[str, Any]:
    from src.tools.artifact_write.diagram_edit import edit_diagram
    from src.tools.diagram_builder import generate_archimate_puml_body

    repo = s.get_repo()
    repo_root, _, verifier = s.get_write_deps()
    entities = [e for eid in body.entity_ids if (e := repo.get_entity(eid)) is not None]
    connections = [c for cid in body.connection_ids if (c := repo.get_connection(cid)) is not None]
    puml = generate_archimate_puml_body(
        body.name, entities, connections, diagram_type=body.diagram_type
    )
    try:
        result = s.run_serialized_write(
            edit_diagram,
            repo_root=repo_root,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id,
            puml=puml,
            name=body.name,
            keywords=...,
            entity_ids_used=body.entity_ids,
            connection_ids_used=body.connection_ids,
            version=body.version,
            status=body.status,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/diagram/remove")
def delete_diagram_gui(body: DeleteDiagramBody) -> dict[str, Any]:
    from src.tools.artifact_write.diagram_delete import delete_diagram

    repo_root, _registry, _verifier = s.get_write_deps()
    try:
        result = s.run_serialized_write(
            delete_diagram,
            repo_root=repo_root,
            clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)
