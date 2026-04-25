"""MCP write tools: connection creation."""

from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.write._common import (
    RepoPreset,
    WriteRepoScope,
    _out,
    artifact_write_ops,
    clear_caches_for_repo,
    registry_cached,
    repo_cached,
    resolve_repo_roots,
    roots_key,
    verifier_for,
)


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
    last_updated: str | None = None,
    dry_run: bool = True,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    repo_scope: WriteRepoScope = "engagement",
    enterprise_root: str | None = None,
) -> dict[str, object]:
    """Add a connection in the engagement repo.

    Defaults use repos from arch-init workspace config; enterprise_root is optional.
    When source_entity or target_entity is a global (enterprise) entity, a
    global-entity-reference proxy is created or reused automatically so all
    connection endpoints are represented in the engagement repo.
    """
    if repo_scope != "engagement":
        raise ValueError("artifact_add_connection only supports repo_scope='engagement'")

    # Determine scope: only include enterprise root when it was explicitly provided
    # OR when the caller's repo_root matches the init-state engagement root.
    # This prevents registry cache pollution in tests that provide an isolated
    # engagement repo but don't provide an enterprise root.
    scope: WriteRepoScope | Literal["both"]
    if enterprise_root:
        scope = "both"
    elif repo_root or repo_preset:
        # Explicit caller repo — enterprise only if also explicitly given
        scope = "engagement"
    else:
        # Default: use both roots from init-state (normal production path)
        scope = "both"
    both_roots = resolve_repo_roots(
        repo_scope=scope,
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=enterprise_root,
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
        last_updated=last_updated,
        dry_run=dry_run,
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


def register(mcp: FastMCP) -> None:
    from src.infrastructure.mcp.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_add_connection",
        title="Artifact Write: Add Connection",
        description=(
            "Add a connection to an entity's .outgoing.md file. Defaults use repos from "
            "arch-init workspace config (repo_root, enterprise_root optional). "
            "Connecting from/to a global entity automatically creates a per-engagement "
            "proxy (global-entity-reference) if one does not already exist — handles "
            "outgoing, incoming, and symmetric connections transparently. "
            "Optional src_cardinality / tgt_cardinality annotate the source or target end "
            "of the connection (e.g. '1', '0..1', '1..*', '*'). "
            "Junction endpoints: cardinalities prohibited; all connections at a junction "
            "must share the same type (first connection locks it). "
            "dry_run=true returns would-be content without writing."
        ),
        structured_output=True,
    )(queued(artifact_add_connection))
