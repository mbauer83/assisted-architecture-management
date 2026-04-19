"""MCP tool definitions for editing entities, connections, and diagrams."""

from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools import model_write_ops
from src.tools.model_mcp.context import (
    RepoPreset,
    clear_caches_for_repo,
    registry_cached,
    resolve_repo_roots,
    roots_key,
    verifier_for,
)

WriteRepoScope = model_write_ops.WriteRepoScope


def _result_dict(dry_run: bool, result: model_write_ops.WriteResult) -> dict[str, object]:
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


def _resolve(repo_root, repo_preset, *, need_registry: bool):
    roots = resolve_repo_roots(
        repo_scope="engagement", repo_root=repo_root,
        repo_preset=repo_preset, enterprise_root=None,
    )
    key = roots_key(roots)
    registry = registry_cached(key) if need_registry else None
    verifier = verifier_for(key, include_registry=need_registry)
    return roots[0], registry, verifier


def model_edit_entity(
    *,
    artifact_id: str,
    name: str | None = None,
    summary: str | None = None,
    properties: dict[str, str] | None = None,
    notes: str | None = None,
    keywords: list[str] | None = None,
    version: str | None = None,
    status: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
) -> dict[str, object]:
    if repo_scope != "engagement":
        raise ValueError("model_edit_entity only supports repo_scope='engagement'")

    root, registry, verifier = _resolve(repo_root, repo_preset, need_registry=True)

    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if summary is not None:
        kwargs["summary"] = summary
    if properties is not None:
        kwargs["properties"] = properties
    if notes is not None:
        kwargs["notes"] = notes
    if keywords is not None:
        kwargs["keywords"] = keywords
    if version is not None:
        kwargs["version"] = version
    if status is not None:
        kwargs["status"] = status

    result = model_write_ops.edit_entity(
        repo_root=root, registry=registry, verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id, dry_run=dry_run, **kwargs,
    )
    return _result_dict(dry_run, result)


_EDIT_CONN_UNSET = object()


def model_edit_connection(
    *,
    source_entity: str,
    target_entity: str,
    connection_type: str,
    operation: str = "update",
    description: str | None = None,
    src_cardinality: str | None = None,
    tgt_cardinality: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
) -> dict[str, object]:
    """Edit or remove a connection.

    For operation='update': description, src_cardinality, tgt_cardinality are
    applied. Pass "" for a cardinality to remove it; omit (None) to preserve it.
    """
    if repo_scope != "engagement":
        raise ValueError("model_edit_connection only supports repo_scope='engagement'")

    root, registry, verifier = _resolve(repo_root, repo_preset, need_registry=True)

    if operation == "remove":
        result = model_write_ops.remove_connection(
            repo_root=root, registry=registry, verifier=verifier,
            clear_repo_caches=clear_caches_for_repo,
            source_entity=source_entity, target_entity=target_entity,
            connection_type=connection_type, dry_run=dry_run,
        )
    else:
        from src.tools.model_write.connection_edit import _UNSET
        result = model_write_ops.edit_connection(
            repo_root=root, registry=registry, verifier=verifier,
            clear_repo_caches=clear_caches_for_repo,
            source_entity=source_entity, target_entity=target_entity,
            connection_type=connection_type, description=description,
            src_cardinality=src_cardinality if src_cardinality is not None else _UNSET,
            tgt_cardinality=tgt_cardinality if tgt_cardinality is not None else _UNSET,
            dry_run=dry_run,
        )
    return _result_dict(dry_run, result)


def model_edit_diagram(
    *,
    artifact_id: str,
    puml: str | None = None,
    name: str | None = None,
    keywords: list[str] | None = None,
    version: str | None = None,
    status: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
) -> dict[str, object]:
    if repo_scope != "engagement":
        raise ValueError("model_edit_diagram only supports repo_scope='engagement'")

    root, _registry, verifier = _resolve(repo_root, repo_preset, need_registry=True)

    kwargs: dict[str, Any] = {}
    if puml is not None:
        kwargs["puml"] = puml
    if name is not None:
        kwargs["name"] = name
    if keywords is not None:
        kwargs["keywords"] = keywords
    if version is not None:
        kwargs["version"] = version
    if status is not None:
        kwargs["status"] = status

    result = model_write_ops.edit_diagram(
        repo_root=root, verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id, dry_run=dry_run, **kwargs,
    )
    return _result_dict(dry_run, result)


def register_edit_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="model_edit_entity",
        title="Model Write: Edit Entity",
        description=(
            "Edit an existing entity. Pass only fields to change; omitted fields are preserved. "
            "Supports name, summary, properties, notes, keywords, version, status. "
            "Bumps last-updated automatically. Regenerates macros if name changes."
        ),
        structured_output=True,
    )(model_edit_entity)

    mcp.tool(
        name="model_edit_connection",
        title="Model Write: Edit/Remove Connection",
        description=(
            "Edit or remove a connection in an .outgoing.md file. "
            "Identify by source_entity + target_entity + connection_type. "
            "operation='update' (default) changes description, src_cardinality, and/or "
            "tgt_cardinality; pass '' to remove an existing cardinality, omit (null) to "
            "preserve it. operation='remove' deletes the connection."
        ),
        structured_output=True,
    )(model_edit_connection)

    mcp.tool(
        name="model_edit_diagram",
        title="Model Write: Edit Diagram",
        description=(
            "Edit an existing diagram. If puml is provided, replaces PUML body with "
            "auto-layout re-applied. Frontmatter fields (name, keywords, version, status) "
            "updated if provided. Re-verifies and re-renders PNG."
        ),
        structured_output=True,
    )(model_edit_diagram)
