"""Diagram-kind discovery endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.application.runtime_catalogs import RuntimeCatalogs
from src.infrastructure.app_bootstrap import runtime_catalogs_dependency

router = APIRouter()


@router.get("/api/diagram-types")
def list_diagram_types(catalogs: RuntimeCatalogs = Depends(runtime_catalogs_dependency)) -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "label": kind.ui_config.label,
            "description": kind.ui_config.description,
        }
        for key, kind in sorted(catalogs.diagram_types.all_diagram_types().items())
    ]


@router.get("/api/diagram-types/{diagram_type}/ui-config")
def read_diagram_kind_ui_config(
    diagram_type: str,
    catalogs: RuntimeCatalogs = Depends(runtime_catalogs_dependency),
) -> dict[str, Any]:
    kind = catalogs.diagram_types.find_diagram_type(diagram_type)
    if kind is None:
        raise HTTPException(404, f"Diagram type not found: {diagram_type!r}")
    return asdict(kind.ui_config)
