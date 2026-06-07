"""Edge-label override endpoint for the diagram GUI router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infrastructure.gui.routers import state as s

router = APIRouter()


class SetEdgeLabelBody(BaseModel):
    artifact_id: str
    edge_key: str
    label: str | None = None
    dry_run: bool = True


@router.put("/api/diagram/edge-label")
def set_edge_label_gui(body: SetEdgeLabelBody) -> dict[str, Any]:
    from src.infrastructure.write.artifact_write.diagram_edit import set_diagram_edge_label

    repo_root, _, verifier = s.get_write_deps()
    try:
        result = s.run_serialized_write(
            set_diagram_edge_label,
            repo_root=repo_root,
            verifier=verifier,
            clear_repo_caches=s.clear_caches,
            artifact_id=body.artifact_id,
            edge_key=body.edge_key,
            label=body.label,
            dry_run=body.dry_run,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.write_result_to_dict(result)
