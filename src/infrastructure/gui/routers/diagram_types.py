"""Diagram-kind discovery endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException

from src.infrastructure.app_bootstrap import get_module_registry

router = APIRouter()


@router.get("/api/diagram-types")
def list_diagram_types() -> list[dict[str, str]]:
    registry = get_module_registry()
    return [
        {
            "key": key,
            "label": kind.ui_config.label,
            "description": kind.ui_config.description,
        }
        for key, kind in sorted(registry.all_diagram_types().items())
    ]


@router.get("/api/diagram-types/{diagram_type}/ui-config")
def read_diagram_kind_ui_config(diagram_type: str) -> dict[str, Any]:
    kind = get_module_registry().find_diagram_type(diagram_type)
    if kind is None:
        raise HTTPException(404, f"Diagram type not found: {diagram_type!r}")
    return asdict(kind.ui_config)
