"""Promotion endpoints — plan and execute entity promotion to enterprise repo."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.tools.gui_routers import state as s

router = APIRouter()


class PromotionPlanBody(BaseModel):
    entity_id: str | None = None
    entity_ids: list[str] = []
    connection_ids: list[str] = []
    exclude_entity_ids: list[str] = []
    exclude_connection_ids: list[str] = []


class ConflictResolutionBody(BaseModel):
    engagement_id: str
    strategy: Literal["accept_engagement", "accept_enterprise", "merge"]
    merged_fields: dict[str, Any] | None = None


class PromotionExecuteBody(BaseModel):
    entity_id: str | None = None
    entity_ids: list[str] = []
    connection_ids: list[str] = []
    exclude_entity_ids: list[str] = []
    exclude_connection_ids: list[str] = []
    conflict_resolutions: list[ConflictResolutionBody] = []
    dry_run: bool = True


@router.post("/api/promote/plan")
def promotion_plan(body: PromotionPlanBody) -> dict[str, Any]:
    """Compute the promotion plan for an explicit selection of entities and connections."""
    from src.common.artifact_verifier_registry import ArtifactRegistry
    from src.tools.artifact_write.promote_to_enterprise import plan_promotion

    eng_root, ent_root = s.get_both_roots()
    registry = ArtifactRegistry([eng_root, ent_root])
    repo = s.get_repo()
    try:
        plan = plan_promotion(
            body.entity_id, registry, repo,
            entity_ids=body.entity_ids or None,
            connection_ids=set(body.connection_ids) or None,
            exclude_entity_ids=set(body.exclude_entity_ids) or None,
            exclude_connection_ids=set(body.exclude_connection_ids) or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "entity_id": body.entity_id or (body.entity_ids[0] if body.entity_ids else ""),
        "entities_to_add": plan.entities_to_add,
        "conflicts": [
            {
                "engagement_id": c.engagement_id, "enterprise_id": c.enterprise_id,
                "artifact_type": c.artifact_type,
                "engagement_name": c.engagement_name, "enterprise_name": c.enterprise_name,
                "engagement_fields": c.engagement_fields, "enterprise_fields": c.enterprise_fields,
            }
            for c in plan.conflicts
        ],
        "connection_ids": plan.connection_ids,
        "already_in_enterprise": plan.already_in_enterprise,
        "warnings": plan.warnings,
    }


@router.post("/api/promote/execute")
def promotion_execute(body: PromotionExecuteBody) -> dict[str, Any]:
    """Execute a promotion plan built from an explicit selection of entities and connections."""
    from src.common.artifact_verifier import ArtifactVerifier
    from src.common.artifact_verifier_registry import ArtifactRegistry
    from src.tools.artifact_write.promote_execute import execute_promotion
    from src.tools.artifact_write.promote_to_enterprise import ConflictResolution, plan_promotion

    eng_root, ent_root = s.get_both_roots()
    registry = ArtifactRegistry([eng_root, ent_root])
    repo = s.get_repo()
    try:
        plan = plan_promotion(
            body.entity_id, registry, repo,
            entity_ids=body.entity_ids or None,
            connection_ids=set(body.connection_ids) or None,
            exclude_entity_ids=set(body.exclude_entity_ids) or None,
            exclude_connection_ids=set(body.exclude_connection_ids) or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if body.dry_run:
        return {
            "dry_run": True, "executed": False,
            "copied_files": [], "updated_files": [],
            "verification_errors": [], "rolled_back": False,
        }

    resolutions = [
        ConflictResolution(
            engagement_id=r.engagement_id, strategy=r.strategy, merged_fields=r.merged_fields,
        )
        for r in body.conflict_resolutions
    ]
    result = execute_promotion(
        plan, eng_root, ent_root, ArtifactVerifier(registry), registry,
        conflict_resolutions=resolutions,
    )
    if result.executed:
        repo.refresh()
    return {
        "dry_run": False, "executed": result.executed,
        "copied_files": result.copied_files, "updated_files": result.updated_files,
        "verification_errors": result.verification_errors, "rolled_back": result.rolled_back,
    }
