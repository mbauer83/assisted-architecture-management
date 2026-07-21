"""Read-only REST access to entity/diagram-type authoring guidance.

Exposes the same ``create_when``/``never_create_when``/permitted-connection/pair-legality
guidance MCP's ``artifact_authoring_guidance`` returns (``get_type_guidance``), for
REST-only frontend consumers (the guided modeling wizard) that have no MCP client.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.application.runtime_catalogs import RuntimeCatalogs
from src.infrastructure.app_bootstrap import runtime_catalogs_dependency
from src.infrastructure.gui.routers._entity_filter import parse_csv_filter
from src.infrastructure.write import artifact_write_ops

router = APIRouter()


@router.get("/api/authoring-guidance")
def read_authoring_guidance(
    entity_type: str | None = None,
    domain: str | None = None,
    diagram_type: str | None = None,
    target: str | None = None,
    catalogs: RuntimeCatalogs = Depends(runtime_catalogs_dependency),
) -> dict[str, Any]:
    terms = parse_csv_filter(entity_type) | parse_csv_filter(domain)
    return artifact_write_ops.get_type_guidance(
        filter=sorted(terms) if terms else None,
        diagram_type=diagram_type,
        target=target,
        catalogs=catalogs,
    )
