"""MCP write tools: matrix and diagram creation."""

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.write._common import (
    DiagramConnectionInferenceMode,
    _out,
    artifact_write_ops,
    clear_caches_for_repo,
    registry_cached,
    resolve_repo_roots,
    roots_key,
    verifier_for,
)


def artifact_create_matrix(
    *,
    name: str,
    purpose: str,
    matrix_markdown: str,
    artifact_id: str,
    keywords: list[str] | None = None,
    version: str = "0.1.0",
    status: str = "draft",
    last_updated: str | None = None,
    infer_entity_ids: bool = True,
    auto_link_entity_ids: bool = True,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    roots = resolve_repo_roots(
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=None,
        enterprise_root=None,
    )
    key = roots_key(roots)
    result = artifact_write_ops.create_matrix(
        repo_root=roots[0],
        registry=registry_cached(key),
        verifier=verifier_for(key, include_registry=True),
        clear_repo_caches=clear_caches_for_repo,
        name=name,
        purpose=purpose,
        matrix_markdown=matrix_markdown,
        artifact_id=artifact_id,
        keywords=keywords,
        version=version,
        status=status,
        last_updated=last_updated,
        infer_entity_ids=infer_entity_ids,
        auto_link_entity_ids=auto_link_entity_ids,
        dry_run=dry_run,
    )
    return _out(result, dry_run=dry_run)


def artifact_create_diagram(
    *,
    diagram_type: str,
    name: str,
    puml: str,
    artifact_id: str | None = None,
    keywords: list[str] | None = None,
    version: str = "0.1.0",
    status: str = "draft",
    last_updated: str | None = None,
    connection_inference: DiagramConnectionInferenceMode = "none",
    auto_include_stereotypes: bool = True,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    roots = resolve_repo_roots(
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=None,
        enterprise_root=None,
    )
    key = roots_key(roots)
    result = artifact_write_ops.create_diagram(
        repo_root=roots[0],
        verifier=verifier_for(key, include_registry=True),
        clear_repo_caches=clear_caches_for_repo,
        diagram_type=diagram_type,
        name=name,
        puml=puml,
        artifact_id=artifact_id,
        keywords=keywords,
        version=version,
        status=status,
        last_updated=last_updated,
        connection_inference=connection_inference,
        auto_include_stereotypes=auto_include_stereotypes,
        dry_run=dry_run,
    )
    return _out(result, dry_run=dry_run)


def register(mcp: FastMCP) -> None:
    from src.infrastructure.mcp.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_create_matrix",
        title="Artifact Write: Create Connection Matrix",
        description=(
            "Create a markdown connection-matrix diagram. Defaults to engagement repo from "
            "arch-init config. dry_run=true returns would-be content without writing."
        ),
        structured_output=True,
    )(queued(artifact_create_matrix))

    mcp.tool(
        name="artifact_create_diagram",
        title="Artifact Write: Create Diagram",
        description=(
            "Create an ArchiMate diagram from a complete PlantUML body. "
            "Defaults to engagement repo from arch-init config. "
            "Read each entity with artifact_query_read_artifact(mode='full') to get display_alias. "
            "auto_include_stereotypes=true injects !include directives automatically. "
            "dry_run=true validates without writing."
        ),
        structured_output=True,
    )(queued(artifact_create_diagram))
