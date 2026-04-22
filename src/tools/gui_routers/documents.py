"""Document read and write endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.common.artifact_document_schema import get_document_subdirectory, load_document_schemata
from src.tools.gui_routers import state as s

router = APIRouter()


class CreateDocumentRequest(BaseModel):
    doc_type: str
    title: str
    body: str | None = None
    keywords: list[str] | None = None
    extra_frontmatter: dict[str, object] | None = None
    version: str = "0.1.0"
    status: str = "draft"
    last_updated: str | None = None
    dry_run: bool = False


class EditDocumentRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    keywords: list[str] | None = None
    extra_frontmatter: dict[str, object] | None = None
    status: str | None = None
    version: str | None = None
    last_updated: str | None = None
    dry_run: bool = False


def _get_engagement_root() -> Any:
    repo_root, _, _ = s.get_write_deps()
    return repo_root


@router.get("/api/document-types")
def list_document_types() -> list[dict[str, object]]:
    repo_root = _get_engagement_root()
    schemata = load_document_schemata(repo_root)
    return [
        {
            "doc_type": doc_type,
            "abbreviation": schema.get("abbreviation", doc_type.upper()),
            "name": schema.get("name", doc_type),
            "subdirectory": get_document_subdirectory(schema, doc_type),
            "required_sections": schema.get("required_sections", []),
        }
        for doc_type, schema in sorted(schemata.items())
    ]


@router.get("/api/document-schemata")
def get_document_schemata() -> dict[str, Any]:
    repo_root = _get_engagement_root()
    return load_document_schemata(repo_root)


@router.get("/api/documents")
def list_documents(
    doc_type: str | None = None,
    status: str | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
) -> dict[str, Any]:
    repo = s.get_repo()
    docs = repo.list_documents(doc_type=doc_type, status=status)
    page = docs[offset: offset + limit]
    return {
        "total": len(docs),
        "items": [
            {
                "artifact_id": d.artifact_id,
                "doc_type": d.doc_type,
                "title": d.title,
                "status": d.status,
                "path": str(d.path),
                "keywords": list(d.keywords),
                "sections": list(d.sections),
            }
            for d in page
        ],
    }


@router.get("/api/document")
def read_document(id: str) -> dict[str, Any]:
    repo = s.get_repo()
    result = repo.read_artifact(id, mode="full")
    if result is None:
        raise HTTPException(404, f"Not found: {id!r}")
    return result


@router.post("/api/document")
def create_document(req: CreateDocumentRequest) -> dict[str, Any]:
    from src.tools.artifact_write.document import create_document as _create
    repo_root, _, verifier = s.get_write_deps()

    result = _create(
        repo_root=repo_root,
        verifier=verifier,
        clear_repo_caches=s.clear_caches,
        doc_type=req.doc_type,
        title=req.title,
        body=req.body,
        keywords=req.keywords,
        extra_frontmatter=req.extra_frontmatter,
        artifact_id=None,
        version=req.version,
        status=req.status,
        last_updated=req.last_updated,
        dry_run=req.dry_run,
    )
    return {
        "wrote": result.wrote,
        "artifact_id": result.artifact_id,
        "path": str(result.path),
        "content": result.content,
        "warnings": result.warnings,
        "verification": result.verification,
    }


@router.put("/api/document/{artifact_id}")
def edit_document(artifact_id: str, req: EditDocumentRequest) -> dict[str, Any]:
    from src.tools.artifact_write.document import edit_document as _edit
    repo_root, _, verifier = s.get_write_deps()

    result = _edit(
        repo_root=repo_root,
        verifier=verifier,
        clear_repo_caches=s.clear_caches,
        artifact_id=artifact_id,
        title=req.title,
        body=req.body,
        keywords=req.keywords,
        extra_frontmatter=req.extra_frontmatter,
        status=req.status,
        version=req.version,
        last_updated=req.last_updated,
        dry_run=req.dry_run,
    )
    return {
        "wrote": result.wrote,
        "artifact_id": result.artifact_id,
        "path": str(result.path),
        "content": result.content,
        "warnings": result.warnings,
        "verification": result.verification,
    }


@router.delete("/api/document/{artifact_id}")
def delete_document(artifact_id: str, dry_run: bool = False) -> dict[str, Any]:
    from src.tools.artifact_write.document import delete_document as _delete
    repo_root, _, _ = s.get_write_deps()

    result = _delete(
        repo_root=repo_root,
        clear_repo_caches=s.clear_caches,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )
    return {
        "wrote": result.wrote,
        "artifact_id": result.artifact_id,
        "path": str(result.path),
        "content": result.content,
        "warnings": result.warnings,
        "verification": result.verification,
    }
