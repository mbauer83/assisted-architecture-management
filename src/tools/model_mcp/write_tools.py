
from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools import model_write_ops
from src.tools.model_mcp.context import RepoPreset, RepoScope, registry_cached, resolve_repo_roots, roots_key, verifier_for, clear_caches_for_repo


WriteRepoScope = model_write_ops.WriteRepoScope
DiagramConnectionInferenceMode = model_write_ops.DiagramConnectionInferenceMode


def model_write_help() -> dict[str, object]:
    return model_write_ops.write_help()


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
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=None,
    )
    key = roots_key(roots)
    verifier = verifier_for(key, include_registry=False)

    result = model_write_ops.create_entity(
        repo_root=roots[0],
        verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        artifact_type=artifact_type,
        name=name,
        summary=summary,
        properties=properties,
        notes=notes,
        keywords=keywords,
        artifact_id=artifact_id,
        version=version,
        status=status,
        last_updated=last_updated,
        dry_run=dry_run,
    )

    out: dict[str, object] = {
        "dry_run": dry_run,
        "wrote": bool(result.wrote),
        "path": str(result.path),
        "artifact_id": result.artifact_id,
        "verification": result.verification,
    }
    if result.content is not None:
        out["content"] = result.content
    if result.warnings:
        out["warnings"] = result.warnings
    return out


def model_add_connection(
    *,
    source_entity: str,
    connection_type: str,
    target_entity: str,
    description: str | None = None,
    version: str = "0.1.0",
    status: str = "draft",
    last_updated: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
) -> dict[str, object]:
    if repo_scope != "engagement":
        raise ValueError("model_add_connection only supports repo_scope='engagement'")

    roots = resolve_repo_roots(
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=None,
    )
    key = roots_key(roots)
    registry = registry_cached(key)
    verifier = verifier_for(key, include_registry=True)

    result = model_write_ops.add_connection(
        repo_root=roots[0],
        registry=registry,
        verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        source_entity=source_entity,
        connection_type=connection_type,
        target_entity=target_entity,
        description=description,
        version=version,
        status=status,
        last_updated=last_updated,
        dry_run=dry_run,
    )

    out: dict[str, object] = {
        "dry_run": dry_run,
        "wrote": bool(result.wrote),
        "path": str(result.path),
        "artifact_id": result.artifact_id,
        "verification": result.verification,
    }
    if result.content is not None:
        out["content"] = result.content
    if result.warnings:
        out["warnings"] = result.warnings
    return out


def model_create_matrix(
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
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
) -> dict[str, object]:
    if repo_scope != "engagement":
        raise ValueError("model_create_matrix only supports repo_scope='engagement'")

    roots = resolve_repo_roots(
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=None,
    )
    key = roots_key(roots)
    registry = registry_cached(key)
    verifier = verifier_for(key, include_registry=True)

    result = model_write_ops.create_matrix(
        repo_root=roots[0],
        registry=registry,
        verifier=verifier,
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

    out: dict[str, object] = {
        "dry_run": dry_run,
        "wrote": bool(result.wrote),
        "path": str(result.path),
        "artifact_id": result.artifact_id,
        "verification": result.verification,
    }
    if result.content is not None:
        out["content"] = result.content
    if result.warnings:
        out["warnings"] = result.warnings
    return out


def model_create_diagram(
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
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
) -> dict[str, object]:
    if repo_scope != "engagement":
        raise ValueError("model_create_diagram only supports repo_scope='engagement'")

    roots = resolve_repo_roots(
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=None,
    )
    key = roots_key(roots)
    verifier = verifier_for(key, include_registry=True)

    result = model_write_ops.create_diagram(
        repo_root=roots[0],
        verifier=verifier,
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

    out: dict[str, object] = {
        "dry_run": dry_run,
        "wrote": bool(result.wrote),
        "path": str(result.path),
        "artifact_id": result.artifact_id,
        "verification": result.verification,
    }
    if result.content is not None:
        out["content"] = result.content
    if result.warnings:
        out["warnings"] = result.warnings
    return out


def register_write_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="model_write_help",
        title="Model Write: Type Catalog",
        description=(
            "Return valid entity types (by domain) and connection types (by language) "
            "for use with create/edit tools. Call this to discover valid artifact_type "
            "and connection_type values."
        ),
        structured_output=True,
    )(model_write_help)

    mcp.tool(
        name="model_create_entity",
        title="Model Write: Create Entity",
        description=(
            "Create a model entity file with frontmatter, content, and display blocks. "
            "If dry_run=true, returns would-be path/content and verification results without writing."
        ),
        structured_output=True,
    )(model_create_entity)

    mcp.tool(
        name="model_add_connection",
        title="Model Write: Add Connection",
        description=(
            "Add a connection to an entity's .outgoing.md file. "
            "Creates the file if it doesn't exist, or appends the connection section. "
            "If dry_run=true, returns would-be content without writing."
        ),
        structured_output=True,
    )(model_add_connection)

    mcp.tool(
        name="model_create_matrix",
        title="Model Write: Create Connection Matrix",
        description=(
            "Create a markdown-based connection matrix diagram. "
            "Use this instead of PUML diagrams when a large number of connections must be shown. "
            "Matrix cells contain markdown links to entity files. "
            "If dry_run=true, returns would-be content without writing."
        ),
        structured_output=True,
    )(model_create_matrix)

    mcp.tool(
        name="model_create_diagram",
        title="Model Write: Create Diagram",
        description=(
            "Create a diagram .puml file with YAML frontmatter. "
            "Renders PNG after successful write. Supports dry_run for safe iteration."
        ),
        structured_output=True,
    )(model_create_diagram)
