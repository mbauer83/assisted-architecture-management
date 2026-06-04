"""Docs and diagrams sub-plan helpers for plan_promotion."""

from __future__ import annotations

from typing import Any

from src.infrastructure.write.artifact_write.promote_to_enterprise import (
    DiagramPromotionConflict,
    DocPromotionConflict,
)


def plan_docs(
    document_ids: list[str] | None,
    repo: Any,
    registry: Any,
    already: list[str],
    warnings: list[str],
) -> tuple[list[str], list[DocPromotionConflict]]:
    from src.infrastructure.write.artifact_write.promote_to_enterprise import _normalize_name  # noqa: PLC0415

    docs_to_add: list[str] = []
    doc_conflicts: list[DocPromotionConflict] = []
    enterprise_doc_ids = registry.enterprise_document_ids()
    index: dict[tuple[str, str], Any] = {}
    for rec in repo.list_documents():
        if rec.artifact_id in enterprise_doc_ids:
            index[(rec.doc_type, _normalize_name(rec.title))] = rec
    for did in document_ids or []:
        doc = repo.get_document(did)
        if doc is None:
            warnings.append(f"Document not found: {did}")
            continue
        if did in enterprise_doc_ids:
            already.append(did)
            continue
        ent = index.get((doc.doc_type, _normalize_name(doc.title)))
        if ent is not None:
            doc_conflicts.append(DocPromotionConflict(
                engagement_id=did, enterprise_id=ent.artifact_id,
                doc_type=doc.doc_type, engagement_title=doc.title, enterprise_title=ent.title,
            ))
        else:
            docs_to_add.append(did)
    return docs_to_add, doc_conflicts


def plan_diagrams(
    diagram_ids: list[str] | None,
    repo: Any,
    registry: Any,
    already: list[str],
    warnings: list[str],
) -> tuple[list[str], list[DiagramPromotionConflict]]:
    from src.infrastructure.write.artifact_write.promote_to_enterprise import _normalize_name  # noqa: PLC0415

    diags_to_add: list[str] = []
    diagram_conflicts: list[DiagramPromotionConflict] = []
    enterprise_diag_ids = registry.enterprise_diagram_ids()
    index: dict[tuple[str, str], Any] = {}
    for rec in repo.list_diagrams():
        if rec.artifact_id in enterprise_diag_ids:
            index[(rec.diagram_type, _normalize_name(rec.name))] = rec
    for did in diagram_ids or []:
        diag = repo.get_diagram(did)
        if diag is None:
            warnings.append(f"Diagram not found: {did}")
            continue
        if did in enterprise_diag_ids:
            already.append(did)
            continue
        ent = index.get((diag.diagram_type, _normalize_name(diag.name)))
        if ent is not None:
            diagram_conflicts.append(DiagramPromotionConflict(
                engagement_id=did, enterprise_id=ent.artifact_id,
                diagram_type=diag.diagram_type, engagement_name=diag.name, enterprise_name=ent.name,
            ))
        else:
            diags_to_add.append(did)
    return diags_to_add, diagram_conflicts
