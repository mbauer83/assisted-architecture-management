"""Group lifecycle REST endpoints (T7.3.1)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.infrastructure.gui.routers import state as s

router = APIRouter()


class CreateGroupBody(BaseModel):
    kind: str
    slug: str
    name: str
    description: str = ""
    order: int = 0
    meta_ontology: str = ""
    type_filter: list[str] = []


class RenameGroupBody(BaseModel):
    kind: str
    target: str
    name: str | None = None
    new_slug: str | None = None


class ArchiveGroupBody(BaseModel):
    kind: str
    target: str
    confirm: str | None = None


class UnarchiveGroupBody(BaseModel):
    kind: str
    target: str


class UpdateGroupBody(BaseModel):
    kind: str
    target: str
    name: str | None = None
    description: str | None = None
    meta_ontology: str | None = None
    type_filter: list[str] | None = None


def _entry_dict(e: Any) -> dict[str, Any]:
    return {
        "slug": e.slug,
        "id": e.id,
        "name": e.name,
        "description": e.description,
        "order": e.order,
        "archived": e.archived,
        "default": e.default,
        "meta_ontology": e.meta_ontology,
        "type_filter": list(e.type_filter),
    }


@router.get("/api/groups")
def list_groups(kind: str | None = None) -> dict[str, Any]:
    """Return groups from the registry, optionally filtered by axis."""
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.application.group_registry import load_group_registry  # noqa: PLC0415

    registry = load_group_registry(repo_root)
    result: dict[str, Any] = {}
    if kind is None or kind == "model-project":
        result["model-projects"] = [_entry_dict(e) for e in registry.list_axis("model-project")]
    if kind is None or kind == "diagram-collection":
        result["diagram-collections"] = [_entry_dict(e) for e in registry.list_axis("diagram-collection")]
    if kind is None or kind == "document-collection":
        result["document-collections"] = [_entry_dict(e) for e in registry.list_axis("document-collection")]
    return result


async def _exec_op(**kwargs: Any) -> dict[str, Any]:
    if s.is_read_only():
        raise HTTPException(403, "Repository is in read-only mode")
    repo_root = s.maybe_engagement_root()
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.infrastructure.write.artifact_write.group_ops import GroupOpError, group_op  # noqa: PLC0415

    try:
        result = await asyncio.to_thread(group_op, repo_root, **kwargs)
    except GroupOpError as exc:
        raise HTTPException(400, str(exc))
    await asyncio.to_thread(s.refresh_now)
    from src.infrastructure.gui.routers.events import event_bus  # noqa: PLC0415

    await event_bus.publish({"type": "artifact_write_completed"})
    return dict(result)


@router.post("/api/group")
async def create_group(body: CreateGroupBody) -> dict[str, Any]:
    return await _exec_op(
        axis=body.kind,
        action="create",
        target=body.slug,
        name=body.name,
        description=body.description,
        order=body.order,
        meta_ontology=body.meta_ontology,
        type_filter=body.type_filter or None,
    )


@router.put("/api/group")
async def rename_group(body: RenameGroupBody) -> dict[str, Any]:
    return await _exec_op(
        axis=body.kind,
        action="rename",
        target=body.target,
        name=body.name,
        new_slug=body.new_slug,
    )


@router.post("/api/group/archive")
async def archive_group(body: ArchiveGroupBody) -> dict[str, Any]:
    return await _exec_op(axis=body.kind, action="archive", target=body.target, confirm=body.confirm)


@router.post("/api/group/unarchive")
async def unarchive_group(body: UnarchiveGroupBody) -> dict[str, Any]:
    return await _exec_op(axis=body.kind, action="unarchive", target=body.target)


@router.patch("/api/group")
async def update_group(body: UpdateGroupBody) -> dict[str, Any]:
    return await _exec_op(
        axis=body.kind,
        action="update",
        target=body.target,
        name=body.name,
        description=body.description,
        meta_ontology=body.meta_ontology or "",
        type_filter=body.type_filter,
    )


@router.delete("/api/group")
async def delete_group(
    kind: str = Query(...),
    target: str = Query(...),
    confirm: str | None = Query(default=None),
) -> dict[str, Any]:
    return await _exec_op(axis=kind, action="delete", target=target, confirm=confirm)
