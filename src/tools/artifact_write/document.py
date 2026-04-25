from collections.abc import Callable
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.common.artifact_document_schema import get_document_schema, get_document_subdirectory
from src.common.artifact_verifier import ArtifactVerifier
from src.common.artifact_write import generate_entity_id
from src.common.repo_paths import DOCS

from .boundary import assert_engagement_write_root, today_iso
from .coerce import as_optional_str_list
from .types import WriteResult
from .verify import verify_content_in_temp_path


def _dump_yaml_text(data: object) -> str:
    dumped = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    if not isinstance(dumped, str):
        raise TypeError("yaml.dump returned non-string output")
    return dumped.rstrip()


def _generate_document_id(abbreviation: str, title: str) -> str:
    return generate_entity_id(abbreviation, title)


def _format_document_markdown(
    *,
    artifact_id: str,
    doc_type: str,
    title: str,
    status: str,
    version: str,
    last_updated: str,
    keywords: list[str] | None,
    extra_frontmatter: dict[str, object] | None,
    body: str,
) -> str:
    fm: dict[str, object] = {
        "artifact-id": artifact_id,
        "artifact-type": "document",
        "doc-type": doc_type,
        "title": title,
        "status": status,
        "version": version,
        "last-updated": last_updated,
    }
    if keywords:
        fm["keywords"] = keywords
    if extra_frontmatter:
        fm.update({k: v for k, v in extra_frontmatter.items() if k not in fm})
    frontmatter = _dump_yaml_text(fm)
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n"


def _build_placeholder_body(required_sections: list[str]) -> str:
    parts = []
    for section in required_sections:
        parts.append(f"## {section}\n\n<!-- Add content here -->\n")
    return "\n".join(parts)


def _doc_dir(repo_root: Path, doc_subdirectory: str) -> Path:
    return repo_root / DOCS / Path(doc_subdirectory)


def _verification_to_document_dict(path: Path, res) -> dict[str, object]:
    return {
        "path": str(path),
        "file_type": "document",
        "valid": res.valid,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
            for i in res.issues
        ],
    }


def _document_write_allowed(res) -> bool:
    return res.valid and not res.issues


def create_document(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    doc_type: str,
    title: str,
    body: str | None,
    keywords: list[str] | None,
    extra_frontmatter: dict[str, object] | None,
    artifact_id: str | None,
    version: str,
    status: str,
    last_updated: str | None,
    dry_run: bool,
) -> WriteResult:
    assert_engagement_write_root(repo_root)

    schema = get_document_schema(repo_root, doc_type)
    if schema is None:
        raise ValueError(
            f"Unknown doc-type: {doc_type!r}. "
            f"No schema found at .arch-repo/documents/{doc_type}.json"
        )

    abbreviation: str = schema.get("abbreviation") or doc_type.upper()
    doc_subdirectory = get_document_subdirectory(schema, doc_type)
    required_sections: list[str] = schema.get("required_sections") or []

    last = last_updated or today_iso()
    doc_id = artifact_id or _generate_document_id(abbreviation, title)
    doc_dir = _doc_dir(repo_root, doc_subdirectory)
    path = doc_dir / f"{doc_id}.md"

    actual_body = body or _build_placeholder_body(required_sections)
    content = _format_document_markdown(
        artifact_id=doc_id,
        doc_type=doc_type,
        title=title,
        status=status,
        version=version,
        last_updated=last,
        keywords=keywords,
        extra_frontmatter=extra_frontmatter,
        body=actual_body,
    )

    preview_res = verify_content_in_temp_path(
        verifier=verifier,
        file_type="document",
        desired_name=f"{doc_subdirectory}/{path.name}",
        content=content,
        support_repo_root=repo_root,
    )
    verification = _verification_to_document_dict(path, preview_res)

    if dry_run or not _document_write_allowed(preview_res):
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=doc_id,
            content=content,
            warnings=[],
            verification=verification,
        )

    if not dry_run:
        doc_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        clear_repo_caches(path)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=doc_id,
        content=None,
        warnings=[],
        verification=verification,
    )


def edit_document(
    *,
    repo_root: Path,
    verifier: ArtifactVerifier,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    title: str | None,
    body: str | None,
    keywords: list[str] | None,
    extra_frontmatter: dict[str, object] | None,
    status: str | None,
    version: str | None,
    last_updated: str | None,
    dry_run: bool,
) -> WriteResult:
    assert_engagement_write_root(repo_root)

    docs_root = repo_root / DOCS
    candidates = list(docs_root.rglob(f"{artifact_id}.md")) if docs_root.exists() else []
    if not candidates:
        raise ValueError(f"Document '{artifact_id}' not found under {docs_root}")
    path = candidates[0]

    raw = path.read_text(encoding="utf-8")
    # Split frontmatter / body
    if not raw.startswith("---"):
        raise ValueError(f"Document at {path} has no YAML frontmatter")
    end = raw.find("\n---", 3)
    if end == -1:
        raise ValueError(f"Document at {path} has malformed YAML frontmatter")
    fm: dict[str, object] = yaml.safe_load(raw[3:end].strip()) or {}
    existing_body = raw[end + 4 :].lstrip("\n")

    if title is not None:
        fm["title"] = title
    if status is not None:
        fm["status"] = status
    if version is not None:
        fm["version"] = version
    if last_updated is not None:
        fm["last-updated"] = last_updated
    else:
        fm["last-updated"] = today_iso()
    if keywords is not None:
        fm["keywords"] = keywords
    if extra_frontmatter:
        fm.update(extra_frontmatter)

    new_body = body if body is not None else existing_body
    content = _format_document_markdown(
        artifact_id=str(fm.get("artifact-id", artifact_id)),
        doc_type=str(fm.get("doc-type", "")),
        title=str(fm.get("title", "")),
        status=str(fm.get("status", "draft")),
        version=str(fm.get("version", "")),
        last_updated=str(fm.get("last-updated", today_iso())),
        keywords=as_optional_str_list(fm.get("keywords")),
        extra_frontmatter={
            k: v
            for k, v in fm.items()
            if k
            not in {
                "artifact-id",
                "artifact-type",
                "doc-type",
                "title",
                "status",
                "version",
                "last-updated",
                "keywords",
            }
        },
        body=new_body,
    )

    relative_path = path.relative_to(repo_root / DOCS).as_posix()
    preview_res = verify_content_in_temp_path(
        verifier=verifier,
        file_type="document",
        desired_name=relative_path,
        content=content,
        support_repo_root=repo_root,
    )
    verification = _verification_to_document_dict(path, preview_res)

    if dry_run or not _document_write_allowed(preview_res):
        return WriteResult(
            wrote=False,
            path=path,
            artifact_id=artifact_id,
            content=content,
            warnings=[],
            verification=verification,
        )

    if not dry_run:
        path.write_text(content, encoding="utf-8")
        clear_repo_caches(path)

    return WriteResult(
        wrote=True,
        path=path,
        artifact_id=artifact_id,
        content=None,
        warnings=[],
        verification=verification,
    )


def delete_document(
    *,
    repo_root: Path,
    clear_repo_caches: Callable[[Path], None],
    artifact_id: str,
    dry_run: bool,
) -> WriteResult:
    assert_engagement_write_root(repo_root)

    docs_root = repo_root / DOCS
    candidates = list(docs_root.rglob(f"{artifact_id}.md")) if docs_root.exists() else []
    if not candidates:
        raise ValueError(f"Document '{artifact_id}' not found under {docs_root}")
    path = candidates[0]

    if not dry_run:
        path.unlink()
        clear_repo_caches(path)

    return WriteResult(
        wrote=not dry_run,
        path=path,
        artifact_id=artifact_id,
        content=None,
        warnings=[],
        verification={"valid": True, "issues": []},
    )
