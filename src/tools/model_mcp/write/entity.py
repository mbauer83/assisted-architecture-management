"""MCP write tools: entity creation and catalog help."""
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.tools.model_mcp.write._common import (
    WriteRepoScope, _out, clear_caches_for_repo, model_write_ops,
    resolve_repo_roots, roots_key, verifier_for, RepoPreset,
)


def model_write_help() -> dict[str, object]:
    return model_write_ops.write_help()


def model_write_modeling_guidance(
    filter: list[str] | None = None,  # noqa: A002
) -> dict[str, object]:
    """Return focused modeling guidelines for the specified entity types or domains."""
    return model_write_ops.get_type_guidance(filter=filter)


def model_create_entity(
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
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
) -> dict[str, object]:
    if repo_scope != "engagement":
        raise ValueError("model_create_entity only supports repo_scope='engagement'")
    roots = resolve_repo_roots(
        repo_scope="engagement", repo_root=repo_root,
        repo_preset=repo_preset, enterprise_root=None,
    )
    result = model_write_ops.create_entity(
        repo_root=roots[0], verifier=verifier_for(roots_key(roots), include_registry=False),
        clear_repo_caches=clear_caches_for_repo,
        artifact_type=artifact_type, name=name, summary=summary, properties=properties,
        notes=notes, keywords=keywords, artifact_id=artifact_id,
        version=version, status=status, last_updated=last_updated, dry_run=dry_run,
    )
    return _out(result, dry_run=dry_run)


def register(mcp: FastMCP) -> None:
    mcp.tool(
        name="model_write_help", title="Model Write: Type Catalog",
        description=(
            "Return the full catalog of valid artifact_type and connection_type values. "
            "Call this before model_create_entity or model_add_connection — type names "
            "are non-obvious identifiers and guessing them causes validation errors."
        ),
        structured_output=True,
    )(model_write_help)

    mcp.tool(
        name="model_write_modeling_guidance", title="Model Write: Modeling Guidelines",
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
    )(model_write_modeling_guidance)

    mcp.tool(
        name="model_create_entity", title="Model Write: Create Entity",
        description=(
            "Create a model entity file. Defaults to the engagement repo from arch-init workspace "
            "config (repo_root optional). dry_run=true validates without writing."
        ),
        structured_output=True,
    )(model_create_entity)
