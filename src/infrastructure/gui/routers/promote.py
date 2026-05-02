"""Promotion endpoints — plan and execute entity promotion to enterprise repo."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.infrastructure.gui.routers import state as s

router = APIRouter()


class PromotionPlanBody(BaseModel):
    entity_id: str | None = None
    entity_ids: list[str] = []
    connection_ids: list[str] = []
    exclude_entity_ids: list[str] = []
    exclude_connection_ids: list[str] = []
    document_ids: list[str] = []
    diagram_ids: list[str] = []


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
    document_ids: list[str] = []
    diagram_ids: list[str] = []
    conflict_resolutions: list[ConflictResolutionBody] = []
    dry_run: bool = True


@router.post("/api/promote/plan")
def promotion_plan(body: PromotionPlanBody) -> dict[str, Any]:
    """Compute the promotion plan for an explicit selection of entities and connections."""
    from src.application.verification.artifact_verifier_registry import ArtifactRegistry
    from src.infrastructure.artifact_index import shared_artifact_index
    from src.infrastructure.write.artifact_write.promote_to_enterprise import plan_promotion

    eng_root, ent_root = s.get_both_roots()
    registry = ArtifactRegistry(shared_artifact_index([eng_root, ent_root]))
    repo = s.get_repo()
    try:
        plan = plan_promotion(
            body.entity_id,
            registry,
            repo,
            entity_ids=body.entity_ids or None,
            connection_ids=set(body.connection_ids) or None,
            exclude_entity_ids=set(body.exclude_entity_ids) or None,
            exclude_connection_ids=set(body.exclude_connection_ids) or None,
            document_ids=body.document_ids or None,
            diagram_ids=body.diagram_ids or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "entity_id": body.entity_id or (body.entity_ids[0] if body.entity_ids else ""),
        "entities_to_add": plan.entities_to_add,
        "conflicts": [
            {
                "engagement_id": c.engagement_id,
                "enterprise_id": c.enterprise_id,
                "artifact_type": c.artifact_type,
                "engagement_name": c.engagement_name,
                "enterprise_name": c.enterprise_name,
                "engagement_fields": c.engagement_fields,
                "enterprise_fields": c.enterprise_fields,
            }
            for c in plan.conflicts
        ],
        "connection_ids": plan.connection_ids,
        "already_in_enterprise": plan.already_in_enterprise,
        "documents_to_add": plan.documents_to_add,
        "diagrams_to_add": plan.diagrams_to_add,
        "doc_conflicts": [
            {
                "engagement_id": c.engagement_id,
                "enterprise_id": c.enterprise_id,
                "doc_type": c.doc_type,
                "engagement_title": c.engagement_title,
                "enterprise_title": c.enterprise_title,
            }
            for c in plan.doc_conflicts
        ],
        "diagram_conflicts": [
            {
                "engagement_id": c.engagement_id,
                "enterprise_id": c.enterprise_id,
                "diagram_type": c.diagram_type,
                "engagement_name": c.engagement_name,
                "enterprise_name": c.enterprise_name,
            }
            for c in plan.diagram_conflicts
        ],
        "warnings": plan.warnings,
        "schema_errors": plan.schema_errors,
    }


@router.post("/api/promote/execute")
def promotion_execute(body: PromotionExecuteBody) -> dict[str, Any]:
    """Execute a promotion plan built from an explicit selection of entities and connections."""
    from src.application.verification.artifact_verifier import ArtifactVerifier
    from src.application.verification.artifact_verifier_registry import ArtifactRegistry
    from src.infrastructure.artifact_index import shared_artifact_index
    from src.infrastructure.write.artifact_write.promote_execute import execute_promotion
    from src.infrastructure.write.artifact_write.promote_to_enterprise import ConflictResolution, plan_promotion

    eng_root, ent_root = s.get_both_roots()
    registry = ArtifactRegistry(shared_artifact_index([eng_root, ent_root]))
    repo = s.get_repo()
    try:
        plan = plan_promotion(
            body.entity_id,
            registry,
            repo,
            entity_ids=body.entity_ids or None,
            connection_ids=set(body.connection_ids) or None,
            exclude_entity_ids=set(body.exclude_entity_ids) or None,
            exclude_connection_ids=set(body.exclude_connection_ids) or None,
            document_ids=body.document_ids or None,
            diagram_ids=body.diagram_ids or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if body.dry_run:
        return {
            "dry_run": True,
            "executed": False,
            "copied_files": [],
            "updated_files": [],
            "verification_errors": [],
            "rolled_back": False,
        }

    from src.infrastructure.git.enterprise_git_ops import ensure_working_branch

    ensure_working_branch(ent_root)

    resolutions = [
        ConflictResolution(
            engagement_id=r.engagement_id,
            strategy=r.strategy,
            merged_fields=r.merged_fields,
        )
        for r in body.conflict_resolutions
    ]
    result = execute_promotion(
        plan,
        eng_root,
        ent_root,
        registry,
        conflict_resolutions=resolutions,
    )
    if result.executed:
        repo.refresh()
    return {
        "dry_run": False,
        "executed": result.executed,
        "copied_files": result.copied_files,
        "updated_files": result.updated_files,
        "verification_errors": result.verification_errors,
        "rolled_back": result.rolled_back,
    }
