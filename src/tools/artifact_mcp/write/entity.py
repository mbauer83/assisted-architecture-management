"""MCP write tools: entity creation and catalog help."""
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.tools.artifact_mcp.write._common import (
    _out, clear_caches_for_repo, artifact_write_ops,
    resolve_repo_roots, roots_key, verifier_for,
)


def artifact_write_help() -> dict[str, object]:
    return artifact_write_ops.write_help()


def artifact_write_modeling_guidance(
    filter: list[str] | None = None,  # noqa: A002
) -> dict[str, object]:
    """Return focused modeling guidelines for the specified entity types or domains."""
    return artifact_write_ops.get_type_guidance(filter=filter)


def artifact_create_entity(
    *,
    artifact_type: str,
    name: str,
    summary: str | None = None,
    properties: dict[str, str] | None = None,
    notes: str | None = None,
    keywords: list[str] | None = None,
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
    result = artifact_write_ops.create_entity(
        repo_root=roots[0], verifier=verifier_for(roots_key(roots), include_registry=False),
        clear_repo_caches=clear_caches_for_repo,
        artifact_type=artifact_type, name=name, summary=summary, properties=properties,
        notes=notes, keywords=keywords, artifact_id=artifact_id,
        version=version, status=status, last_updated=last_updated, dry_run=dry_run,
    )
    return _out(result, dry_run=dry_run)


def register(mcp: FastMCP) -> None:
    from src.tools.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_write_help", title="Artifact Write: Type Catalog",
        description=(
            "Return the full catalog of valid artifact_type and connection_type values. "
            "Call this before artifact_create_entity or artifact_add_connection — type names "
            "are non-obvious identifiers and guessing them causes validation errors."
        ),
        structured_output=True,
    )(artifact_write_help)

    mcp.tool(
        name="artifact_write_modeling_guidance", title="Artifact Write: Modeling Guidelines",
        description=(
            "Return focused modeling guidelines for a selectable subset of ArchiMate entity "
            "types or domains. Includes for each type: name, prefix, archimate_domain "
            "(omitted when filtering by domain), element_classes, create_when, "
            "never_create_when, and permitted_connections (outgoing/incoming/symmetric "
            "classified by connection type and counterpart entity type). "
            "filter accepts either entity-type names (e.g. ['requirement', 'goal']) or "
            "domain names (e.g. ['Motivation', 'Strategy']) — never mixed. "
            "Omit filter to return guidance for all entity types."
        ),
        structured_output=True,
    )(artifact_write_modeling_guidance)

    mcp.tool(
        name="artifact_create_entity", title="Artifact Write: Create Entity",
        description=(
            "Create a model entity file. Defaults to the engagement repo from arch-init workspace "
            "config (repo_root optional). dry_run=true validates without writing."
        ),
        structured_output=True,
    )(queued(artifact_create_entity))
