"""Diagram write (POST) endpoints for the diagram GUI router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infrastructure.gui.routers import state as s
from src.infrastructure.gui.routers._diagram_selection import resolve_diagram_selection

router = APIRouter()


def _split_diagram_entities(
    diagram_entities: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None]:
    """Separate the transport-only `_connections` key from entity data."""
    if diagram_entities is None:
        return None, None
    conns = diagram_entities.get("_connections")
    if conns is None:
        return diagram_entities, None
    clean = {k: v for k, v in diagram_entities.items() if k != "_connections"}
    return clean or None, conns if isinstance(conns, list) else None


class DiagramPreviewBody(BaseModel):
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]
    diagram_entities: dict[str, Any] | None = None


class CreateDiagramGuiBody(BaseModel):
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]
    keywords: list[str] | None = None
    diagram_entities: dict[str, Any] | None = None
    version: str = "0.1.0"
    status: str = "draft"
    dry_run: bool = True


class EditDiagramGuiBody(BaseModel):
    artifact_id: str
    diagram_type: str
    name: str
    entity_ids: list[str]
    connection_ids: list[str]
    diagram_entities: dict[str, Any] | None = None
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
    from src.infrastructure.rendering.diagram_builder import generate_archimate_puml_body, render_puml_preview

    repo = s.get_repo()
    entities, connections, _, _ = resolve_diagram_selection(repo, body.entity_ids, body.connection_ids)
    de, dc = _split_diagram_entities(body.diagram_entities)
    puml = generate_archimate_puml_body(
        body.name,
        entities,
        connections,
        diagram_type=body.diagram_type,
        repo_root=repo_root,
        diagram_entities=de,
        diagram_connections=dc,
    )
    image, warnings = render_puml_preview(puml, repo_root, body.diagram_type)

    from src.infrastructure.diagram_types import get_diagram_type
    derived_entities = get_diagram_type(body.diagram_type).collect_derived_items(
        body.diagram_type, repo_root, diagram_entities=de,
    )

    return {"puml": puml, "image": image, "warnings": warnings, "derived_entities": derived_entities}


@router.post("/api/diagram")
def create_diagram_gui(body: CreateDiagramGuiBody) -> dict[str, Any]:
    from src.application.modeling.artifact_write import generate_diagram_id
    from src.infrastructure.rendering.diagram_builder import generate_archimate_puml_body
    from src.infrastructure.write.artifact_write.diagram import create_diagram

    repo = s.get_repo()
    repo_root, _, verifier = s.get_write_deps()
    entities, connections, entity_ids_used, connection_ids_used = resolve_diagram_selection(
        repo,
        body.entity_ids,
        body.connection_ids,
    )
    de, dc = _split_diagram_entities(body.diagram_entities)
    puml = generate_archimate_puml_body(
        body.name,
        entities,
        connections,
        diagram_type=body.diagram_type,
        repo_root=repo_root,
        diagram_entities=de,
        diagram_connections=dc,
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
            artifact_id=generate_diagram_id(body.diagram_type, body.name),
            keywords=body.keywords,
            diagram_entities=de,
            diagram_connections=dc,
            entity_ids_used=entity_ids_used,
            connection_ids_used=connection_ids_used,
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
    from src.infrastructure.rendering.diagram_builder import generate_archimate_puml_body
    from src.infrastructure.write.artifact_write.diagram_edit import edit_diagram

    repo = s.get_repo()
    repo_root, _, verifier = s.get_write_deps()
    entities, connections, entity_ids_used, connection_ids_used = resolve_diagram_selection(
        repo,
        body.entity_ids,
        body.connection_ids,
    )
    de, dc = _split_diagram_entities(body.diagram_entities)
    puml = generate_archimate_puml_body(
        body.name,
        entities,
        connections,
        diagram_type=body.diagram_type,
        repo_root=repo_root,
        diagram_entities=de,
        diagram_connections=dc,
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
            diagram_entities=de,
            diagram_connections=dc,
            entity_ids_used=entity_ids_used,
            connection_ids_used=connection_ids_used,
            version=body.version,
            status=body.status,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


class MatrixPreviewBody(BaseModel):
    entity_ids: list[str]
    conn_type_configs: list[dict[str, object]]
    combined: bool = False
    from_entity_ids: list[str] | None = None
    to_entity_ids: list[str] | None = None


class CreateMatrixBody(BaseModel):
    name: str
    entity_ids: list[str]
    conn_type_configs: list[dict[str, object]]
    combined: bool = False
    keywords: list[str] | None = None
    version: str = "0.1.0"
    status: str = "draft"
    dry_run: bool = True
    from_entity_ids: list[str] | None = None
    to_entity_ids: list[str] | None = None


class EditMatrixBody(BaseModel):
    artifact_id: str
    name: str
    entity_ids: list[str]
    conn_type_configs: list[dict[str, object]]
    combined: bool = False
    version: str | None = None
    status: str | None = None
    dry_run: bool = True
    from_entity_ids: list[str] | None = None
    to_entity_ids: list[str] | None = None


def _build_matrix_markdown(
    entity_ids: list[str],
    conn_type_configs: list[dict[str, object]],
    combined: bool,
    repo: Any,
    from_entity_ids: list[str] | None = None,
    to_entity_ids: list[str] | None = None,
) -> str:
    from src.application.modeling.matrix_builder import ConnTypeConfig, build_matrix_tables

    all_ids = list(set(from_entity_ids or entity_ids) | set(to_entity_ids or entity_ids))
    entity_names: dict[str, str] = {}
    for eid in all_ids:
        rec = repo.get_entity(eid)
        entity_names[eid] = rec.name if rec else eid

    connections = repo.candidate_connections_for_entities(all_ids)
    configs = [
        ConnTypeConfig(conn_type=str(c["conn_type"]), active=bool(c.get("active", True))) for c in conn_type_configs
    ]
    return build_matrix_tables(
        entity_ids=entity_ids,
        conn_type_configs=configs,
        combined=combined,
        entity_names=entity_names,
        connections=connections,
        from_entity_ids=from_entity_ids,
        to_entity_ids=to_entity_ids,
    )


@router.post("/api/matrix/preview")
def preview_matrix(body: MatrixPreviewBody) -> dict[str, Any]:
    repo = s.get_repo()
    repo_root, registry, _ = s.get_write_deps()
    from src.infrastructure.write.artifact_write.matrix import _linkify_matrix_ids

    md = _build_matrix_markdown(
        body.entity_ids,
        body.conn_type_configs,
        body.combined,
        repo,
        from_entity_ids=body.from_entity_ids,
        to_entity_ids=body.to_entity_ids,
    )
    all_ids = list(set(body.from_entity_ids or body.entity_ids) | set(body.to_entity_ids or body.entity_ids))
    linked, _ = _linkify_matrix_ids(
        repo_root=repo_root,
        registry=registry,
        matrix_markdown=md,
        candidate_entity_ids=all_ids,
    )
    return {"markdown": linked}


@router.post("/api/matrix")
def create_matrix_gui(body: CreateMatrixBody) -> dict[str, Any]:
    from src.infrastructure.write.artifact_write.matrix import create_matrix

    repo = s.get_repo()
    repo_root, registry, verifier = s.get_write_deps()
    md = _build_matrix_markdown(
        body.entity_ids,
        body.conn_type_configs,
        body.combined,
        repo,
        from_entity_ids=body.from_entity_ids,
        to_entity_ids=body.to_entity_ids,
    )
    try:
        result = s.run_serialized_write(
            create_matrix,
            repo_root=repo_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            name=body.name,
            matrix_markdown=md,
            artifact_id=None,
            keywords=body.keywords,
            version=body.version,
            status=body.status,
            entity_ids=body.entity_ids,
            from_entity_ids=body.from_entity_ids,
            to_entity_ids=body.to_entity_ids,
            conn_type_configs=body.conn_type_configs,
            combined=body.combined,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


@router.post("/api/matrix/edit")
def edit_matrix_gui(body: EditMatrixBody) -> dict[str, Any]:
    from src.infrastructure.write.artifact_write.matrix import create_matrix

    repo = s.get_repo()
    repo_root, registry, verifier = s.get_write_deps()
    md = _build_matrix_markdown(
        body.entity_ids,
        body.conn_type_configs,
        body.combined,
        repo,
        from_entity_ids=body.from_entity_ids,
        to_entity_ids=body.to_entity_ids,
    )
    diag = repo.get_diagram(body.artifact_id)
    try:
        result = s.run_serialized_write(
            create_matrix,
            repo_root=repo_root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            name=body.name,
            matrix_markdown=md,
            artifact_id=body.artifact_id,
            keywords=None,
            version=body.version or (diag.version if diag else "0.1.0"),
            status=body.status or (diag.status if diag else "draft"),
            entity_ids=body.entity_ids,
            from_entity_ids=body.from_entity_ids,
            to_entity_ids=body.to_entity_ids,
            conn_type_configs=body.conn_type_configs,
            combined=body.combined,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)


class SyncDiagramToModelBody(BaseModel):
    artifact_id: str
    dry_run: bool = True


@router.post("/api/diagram/sync")
def sync_diagram_to_model_gui(body: SyncDiagramToModelBody) -> dict[str, Any]:
    from src.infrastructure.write.artifact_write.diagram_sync import sync_diagram_to_model

    repo = s.get_repo()
    repo_root, _, verifier = s.get_write_deps()
    try:
        result = s.run_serialized_write(
            sync_diagram_to_model,
            repo_root=repo_root,
            store=repo,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    d = s.write_result_to_dict(result)
    d["removed_entity_ids"] = result.removed_entity_ids
    d["removed_connection_ids"] = result.removed_connection_ids
    return d


@router.post("/api/diagram/remove")
def delete_diagram_gui(body: DeleteDiagramBody) -> dict[str, Any]:
    from src.infrastructure.write.artifact_write.diagram_delete import delete_diagram

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
