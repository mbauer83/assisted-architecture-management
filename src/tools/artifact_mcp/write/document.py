"""MCP write tools: document create, edit, delete."""
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.tools.artifact_mcp.write._common import (
    _out, clear_caches_for_repo, artifact_write_ops,
    resolve_repo_roots, roots_key, verifier_for,
)


def artifact_create_document(
    *,
    doc_type: str,
    title: str,
    body: str | None = None,
    keywords: list[str] | None = None,
    extra_frontmatter: dict[str, object] | None = None,
    artifact_id: str | None = None,
    version: str = "0.1.0",
    status: str = "draft",
    last_updated: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    roots = resolve_repo_roots(
        repo_scope="engagement", repo_root=repo_root,
        repo_preset=None, enterprise_root=None,
    )
    result = artifact_write_ops.create_document(
        repo_root=roots[0],
        verifier=verifier_for(roots_key(roots), include_registry=False),
        clear_repo_caches=clear_caches_for_repo,
        doc_type=doc_type,
        title=title,
        body=body,
        keywords=keywords,
        extra_frontmatter=extra_frontmatter,
        artifact_id=artifact_id,
        version=version,
        status=status,
        last_updated=last_updated,
        dry_run=dry_run,
    )
    return _out(result, dry_run=dry_run)


def artifact_edit_document(
    *,
    artifact_id: str,
    title: str | None = None,
    body: str | None = None,
    keywords: list[str] | None = None,
    extra_frontmatter: dict[str, object] | None = None,
    status: str | None = None,
    version: str | None = None,
    last_updated: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    roots = resolve_repo_roots(
        repo_scope="engagement", repo_root=repo_root,
        repo_preset=None, enterprise_root=None,
    )
    result = artifact_write_ops.edit_document(
        repo_root=roots[0],
        verifier=verifier_for(roots_key(roots), include_registry=False),
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id,
        title=title,
        body=body,
        keywords=keywords,
        extra_frontmatter=extra_frontmatter,
        status=status,
        version=version,
        last_updated=last_updated,
        dry_run=dry_run,
    )
    return _out(result, dry_run=dry_run)


def artifact_delete_document(
    *,
    artifact_id: str,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    roots = resolve_repo_roots(
        repo_scope="engagement", repo_root=repo_root,
        repo_preset=None, enterprise_root=None,
    )
    result = artifact_write_ops.delete_document(
        repo_root=roots[0],
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )
    return _out(result, dry_run=dry_run)


def register(mcp: FastMCP) -> None:
    from src.tools.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_create_document",
        title="Artifact Write: Create Document",
        description=(
            "Create a new architecture document (e.g. ADR, RFC). "
            "doc_type must match a schema in .arch-repo/documents/. "
            "body is the full markdown body after the frontmatter; if omitted, "
            "placeholder sections are generated from the schema's required_sections. "
            "Set dry_run=false to write the file."
        ),
        structured_output=True,
    )(queued(artifact_create_document))

    mcp.tool(
        name="artifact_edit_document",
        title="Artifact Write: Edit Document",
        description=(
            "Edit an existing architecture document's frontmatter or body. "
            "All fields are optional — supply only those that should change. "
            "body replaces the entire body when supplied. "
            "Set dry_run=false to write the file."
        ),
        structured_output=True,
    )(queued(artifact_edit_document))

    mcp.tool(
        name="artifact_delete_document",
        title="Artifact Write: Delete Document",
        description=(
            "Delete an architecture document by artifact_id. "
            "Set dry_run=false to perform the deletion."
        ),
        structured_output=True,
    )(queued(artifact_delete_document))
