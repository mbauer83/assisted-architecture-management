"""MCP tool definitions for editing entities, connections, and diagrams."""

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.application.verification.artifact_verifier import ArtifactVerifier
from src.application.verification.artifact_verifier_registry import ArtifactRegistry
from src.infrastructure.mcp.artifact_mcp.context import (
    clear_caches_for_repo,
    registry_cached,
    resolve_repo_roots,
    roots_key,
    verifier_for,
)
from src.infrastructure.mcp.artifact_mcp.tool_annotations import DESTRUCTIVE_LOCAL_WRITE, LOCAL_WRITE
from src.infrastructure.mcp.artifact_mcp.write._common import _out
from src.infrastructure.write import artifact_write_ops


def _result_dict(dry_run: bool, result: artifact_write_ops.WriteResult) -> dict[str, object]:
    return _out(result, dry_run=dry_run)


def _resolve(
    repo_root: str | None, *, need_registry: bool
) -> tuple[Path, ArtifactRegistry | None, ArtifactVerifier]:
    roots = resolve_repo_roots(
        repo_scope="engagement",
        repo_root=repo_root,
        repo_preset=None,
        enterprise_root=None,
    )
    key = roots_key(roots)
    registry = registry_cached(key) if need_registry else None
    verifier = verifier_for(key, include_registry=need_registry)
    return roots[0], registry, verifier


def _require_registry(registry: ArtifactRegistry | None) -> ArtifactRegistry:
    if registry is None:
        raise RuntimeError("Registry is required for this operation")
    return registry


def artifact_edit_entity(
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
) -> dict[str, object]:
    root, registry, verifier = _resolve(repo_root, need_registry=True)
    registry = _require_registry(registry)

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

    result = artifact_write_ops.edit_entity(
        repo_root=root,
        registry=registry,
        verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id,
        dry_run=dry_run,
        **kwargs,
    )
    return _result_dict(dry_run, result)


_EDIT_CONN_UNSET = object()


def artifact_edit_connection(
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
) -> dict[str, object]:
    """Edit or remove a connection.

    For operation='update': description, src_cardinality, tgt_cardinality are
    applied. Pass "" for a cardinality to remove it; omit (None) to preserve it.
    """
    root, registry, verifier = _resolve(repo_root, need_registry=True)
    registry = _require_registry(registry)

    if operation == "remove":
        result = artifact_write_ops.remove_connection(
            repo_root=root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=clear_caches_for_repo,
            source_entity=source_entity,
            target_entity=target_entity,
            connection_type=connection_type,
            dry_run=dry_run,
        )
    else:
        from src.infrastructure.write.artifact_write.connection_edit import _UNSET

        result = artifact_write_ops.edit_connection(
            repo_root=root,
            registry=registry,
            verifier=verifier,
            clear_repo_caches=clear_caches_for_repo,
            source_entity=source_entity,
            target_entity=target_entity,
            connection_type=connection_type,
            description=description,
            src_cardinality=src_cardinality if src_cardinality is not None else _UNSET,
            tgt_cardinality=tgt_cardinality if tgt_cardinality is not None else _UNSET,
            dry_run=dry_run,
        )
    return _result_dict(dry_run, result)


def artifact_edit_diagram(
    *,
    artifact_id: str,
    puml: str | None = None,
    name: str | None = None,
    keywords: list[str] | None = None,
    version: str | None = None,
    status: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    root, _registry, verifier = _resolve(repo_root, need_registry=True)

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

    result = artifact_write_ops.edit_diagram(
        repo_root=root,
        verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id,
        dry_run=dry_run,
        **kwargs,
    )
    return _result_dict(dry_run, result)


def artifact_edit_connection_associations(
    *,
    source_entity: str,
    connection_type: str,
    target_entity: str,
    add_entities: list[str] | None = None,
    remove_entities: list[str] | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    """Add or remove second-order association entity IDs from a connection."""
    root, registry, verifier = _resolve(repo_root, need_registry=True)
    registry = _require_registry(registry)
    from src.infrastructure.write.artifact_write.connection_edit import edit_connection_associations

    result = edit_connection_associations(
        repo_root=root,
        registry=registry,
        verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        source_entity=source_entity,
        connection_type=connection_type,
        target_entity=target_entity,
        add_entities=add_entities,
        remove_entities=remove_entities,
        dry_run=dry_run,
    )
    return _result_dict(dry_run, result)


def artifact_delete_entity(
    *,
    artifact_id: str,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    root, registry, _verifier = _resolve(repo_root, need_registry=True)
    registry = _require_registry(registry)
    result = artifact_write_ops.delete_entity(
        repo_root=root,
        registry=registry,
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )
    return _result_dict(dry_run, result)


def artifact_delete_diagram(
    *,
    artifact_id: str,
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    root, _registry, _verifier = _resolve(repo_root, need_registry=False)
    result = artifact_write_ops.delete_diagram(
        repo_root=root,
        clear_repo_caches=clear_caches_for_repo,
        artifact_id=artifact_id,
        dry_run=dry_run,
    )
    return _result_dict(dry_run, result)


def register_edit_tools(mcp: FastMCP) -> None:
    from src.infrastructure.mcp.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_edit_entity",
        title="Artifact Write: Edit Entity",
        description=(
            "Edit an existing entity. Pass only fields to change; omitted fields are preserved. "
            "Supports name, summary, properties, notes, keywords, version, status. "
            "Bumps last-updated automatically. Regenerates macros if name changes."
        ),
        annotations=LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_edit_entity))

    mcp.tool(
        name="artifact_edit_connection",
        title="Artifact Write: Edit/Remove Connection",
        description=(
            "Edit or remove a connection in an .outgoing.md file. "
            "Identify by source_entity + target_entity + connection_type. "
            "operation='update' (default) changes description, src_cardinality, and/or "
            "tgt_cardinality; pass '' to remove an existing cardinality, omit (null) to "
            "preserve it. operation='remove' deletes the connection."
        ),
        annotations=DESTRUCTIVE_LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_edit_connection))

    mcp.tool(
        name="artifact_edit_diagram",
        title="Artifact Write: Edit Diagram",
        description=(
            "Edit an existing diagram. If puml is provided, replaces PUML body with "
            "auto-layout re-applied. Frontmatter fields (name, keywords, version, status) "
            "updated if provided. Re-verifies and re-renders PNG."
        ),
        annotations=LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_edit_diagram))

    mcp.tool(
        name="artifact_edit_connection_associations",
        title="Artifact Write: Edit Connection Associations",
        description=(
            "Add or remove second-order association entity IDs from a connection. "
            "Associations link a connection to additional entities beyond source and target "
            "(stored as <!-- §assoc ENTITY_ID --> annotations). "
            "add_entities and remove_entities may both be provided in one call."
        ),
        annotations=LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_edit_connection_associations))
