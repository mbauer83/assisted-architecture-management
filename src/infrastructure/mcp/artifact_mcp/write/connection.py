"""MCP write tools: connection creation."""

from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.tool_annotations import LOCAL_WRITE
from src.infrastructure.mcp.artifact_mcp.write._common import (
    _out,
    artifact_write_ops,
    clear_caches_for_repo,
    registry_cached,
    repo_cached,
    resolve_repo_roots,
    roots_key,
    verifier_for,
)


def _add_connection_impl(
    *,
    source_entity: str,
    connection_type: str,
    target_entity: str,
    description: str | None,
    src_cardinality: str | None,
    tgt_cardinality: str | None,
    version: str,
    status: str,
    dry_run: bool,
    repo_root: str | None,
    provisional_ids: frozenset[str],
) -> dict[str, object]:
    """Internal implementation shared by the MCP tool and bulk_write."""
    scope: Literal["engagement", "both"] = "engagement" if repo_root else "both"
    both_roots = resolve_repo_roots(
        repo_scope=scope,
        repo_root=repo_root,
        repo_preset=None,
        enterprise_root=None,
    )
    both_key = roots_key(both_roots)
    registry = registry_cached(both_key)
    verifier = verifier_for(both_key, include_registry=True)
    eng_root = both_roots[0]

    effective_source = source_entity
    effective_target = target_entity
    gar_source_id: str | None = None
    gar_artifact_id: str | None = None
    warnings: list[str] = []

    def _ensure_gar(global_id: str) -> str:
        nonlocal registry, verifier
        from src.infrastructure.write.artifact_write.global_artifact_reference import (
            ensure_global_artifact_reference,
        )

        full_repo = repo_cached(both_key)
        rec = full_repo.get_entity(global_id)
        name = rec.name if rec else global_id
        entity_type = rec.artifact_type if rec else None
        eng_repo = repo_cached(roots_key(both_roots[:1]))
        gar_result = ensure_global_artifact_reference(
            engagement_repo=eng_repo,
            engagement_root=eng_root,
            verifier=verifier,
            clear_repo_caches=clear_caches_for_repo,
            global_artifact_id=global_id,
            global_artifact_name=name,
            global_artifact_type="entity",
            global_artifact_entity_type=entity_type,
            dry_run=dry_run,
        )
        if gar_result.wrote:
            warnings.append(f"Created GAR proxy {gar_result.artifact_id} for {global_id}")
            clear_caches_for_repo(eng_root)
        else:
            warnings.append(f"Routed via existing GAR proxy {gar_result.artifact_id}")
        full_repo.refresh()
        eng_repo.refresh()
        registry.refresh()
        verifier = verifier_for(both_key, include_registry=True)
        return gar_result.artifact_id

    if source_entity in registry.enterprise_entity_ids():
        gar_source_id = _ensure_gar(source_entity)
        effective_source = gar_source_id

    if target_entity in registry.enterprise_entity_ids():
        gar_artifact_id = _ensure_gar(target_entity)
        effective_target = gar_artifact_id

    result = artifact_write_ops.add_connection(
        repo_root=eng_root,
        registry=registry,
        verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        source_entity=effective_source,
        connection_type=connection_type,
        target_entity=effective_target,
        description=description,
        src_cardinality=src_cardinality,
        tgt_cardinality=tgt_cardinality,
        version=version,
        status=status,
        last_updated=None,
        dry_run=dry_run,
        extra_known_ids=provisional_ids,
    )
    out = _out(result, dry_run=dry_run)
    if gar_source_id:
        out["gar_source_id"] = gar_source_id
        out["original_source"] = source_entity
    if gar_artifact_id:
        out["gar_artifact_id"] = gar_artifact_id
        out["original_target"] = target_entity
    all_warnings = warnings + list(result.warnings or [])
    if all_warnings:
        out["warnings"] = all_warnings
    return out


def artifact_add_connection(
    *,
    source_entity: str,
    connection_type: str,
    target_entity: str,
    description: str | None = None,
    src_cardinality: str | None = None,
    tgt_cardinality: str | None = None,
    version: str = "0.1.0",
    status: str = "draft",
    dry_run: bool = True,
    repo_root: str | None = None,
) -> dict[str, object]:
    """Add a connection in the engagement repo.

    Defaults use repos from arch-init workspace config.
    When source_entity or target_entity is a global (enterprise) entity, a
    global-entity-reference proxy is created or reused automatically so all
    connection endpoints are represented in the engagement repo.
    """
    return _add_connection_impl(
        source_entity=source_entity,
        connection_type=connection_type,
        target_entity=target_entity,
        description=description,
        src_cardinality=src_cardinality,
        tgt_cardinality=tgt_cardinality,
        version=version,
        status=status,
        dry_run=dry_run,
        repo_root=repo_root,
        provisional_ids=frozenset(),
    )


def register(mcp: FastMCP) -> None:
    from src.infrastructure.mcp.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_add_connection",
        title="Artifact Write: Add Connection",
        description=(
            "Add a connection to an entity's .outgoing.md file. Defaults use repos from "
            "arch-init workspace config (repo_root optional). "
            "Connecting from/to a global entity automatically creates a per-engagement "
            "proxy (global-entity-reference) if one does not already exist — handles "
            "outgoing, incoming, and symmetric connections transparently. "
            "Optional src_cardinality / tgt_cardinality annotate the source or target end "
            "of the connection (e.g. '1', '0..1', '1..*', '*'). "
            "Junction endpoints: cardinalities prohibited; all connections at a junction "
            "must share the same type (first connection locks it). "
            "dry_run=true returns would-be content without writing."
        ),
        annotations=LOCAL_WRITE,
        structured_output=True,
    )(queued(artifact_add_connection))
