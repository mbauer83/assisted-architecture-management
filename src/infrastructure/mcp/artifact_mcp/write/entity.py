"""MCP write tools: entity creation and catalog help."""

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.tool_annotations import LOCAL_WRITE, READ_ONLY
from src.infrastructure.mcp.artifact_mcp.write._common import (
    _out,
    artifact_write_ops,
    authoritative_callbacks_for,
    resolve_repo_roots,
    roots_key,
    verifier_for,
)


def artifact_help() -> dict[str, object]:
    return artifact_write_ops.write_help()


def artifact_authoring_guidance(
    filter: list[str] | None = None,  # noqa: A002
    diagram_type: str | None = None,
) -> dict[str, object]:
    return artifact_write_ops.get_type_guidance(filter=filter, diagram_type=diagram_type)


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
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    roots = resolve_repo_roots(
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=None,
        enterprise_root=None,
    )
    mutation_context, clear_repo_caches = authoritative_callbacks_for(roots)
    result = artifact_write_ops.create_entity(
        repo_root=roots[0],
        verifier=verifier_for(roots_key(roots), include_registry=False),
        clear_repo_caches=clear_repo_caches,
        artifact_type=artifact_type,
        name=name,
        summary=summary,
        properties=properties,
        notes=notes,
        keywords=keywords,
        artifact_id=artifact_id,
        version=version,
        status=status,
        last_updated=None,
        dry_run=dry_run,
    )
    if result.wrote and not dry_run:
        mutation_context.finalize()
    return _out(result, dry_run=dry_run)


def register(mcp: FastMCP) -> None:
    from src.infrastructure.mcp.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_help",
        title="Artifact: Type Catalog",
        description=(
            "Return the full catalog of artifact types, entity types (by domain), connection types "
            "(by language), and diagram types (with accepted domains). "
            "Call this first to discover valid type names — guessing them causes validation errors. "
            "For detailed authoring guidance call artifact_authoring_guidance."
        ),
        annotations=READ_ONLY,
        structured_output=False,
    )(artifact_help)

    mcp.tool(
        name="artifact_authoring_guidance",
        title="Artifact: Authoring Guidance",
        description=(
            "Return authoring guidance before creating entities or diagrams. "
            "Two independent params (usable separately or together):\n"
            "• diagram_type (str): diagram type block — when_to_use, when_not_to_use, "
            "accepted_domains, own entity types, diagram_entities schema, and optional puml_notes.\n"
            "• filter (list[str]): entity type guidance — create_when, never_create_when, "
            "permitted_connections. Pass type names (e.g. ['requirement', 'goal']) "
            "or domain names (e.g. ['motivation', 'strategy']) — not mixed.\n"
            "Omit both to return all entity type guidance (large; prefer filtering)."
        ),
        annotations=READ_ONLY,
        structured_output=False,
    )(artifact_authoring_guidance)

    mcp.tool(
        name="artifact_create_entity",
        title="Artifact Write: Create Entity",
        description=(
            "Create a model entity file. Defaults to the engagement repo from arch-init workspace "
            "config (repo_root optional). dry_run=true validates without writing."
        ),
        annotations=LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_create_entity))
