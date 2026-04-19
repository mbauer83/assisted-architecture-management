"""MCP write tools: connection creation."""
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.tools.model_mcp.write._common import (
    WriteRepoScope, _out, clear_caches_for_repo, model_write_ops,
    registry_cached, repo_cached, resolve_repo_roots, roots_key, verifier_for, RepoPreset,
)


def model_add_connection(
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
        raise ValueError("model_add_connection only supports repo_scope='engagement'")

    from src.tools.model_mcp.context import resolve_enterprise_repo_root
    # Determine scope: only include enterprise root when it was explicitly provided
    # OR when the caller's repo_root matches the init-state engagement root.
    # This prevents registry cache pollution in tests that provide an isolated
    # engagement repo but don't provide an enterprise root.
    scope: str
    if enterprise_root:
        scope = "both"
    elif repo_root or repo_preset:
        # Explicit caller repo — enterprise only if also explicitly given
        scope = "engagement"
    else:
        # Default: use both roots from init-state (normal production path)
        scope = "both"
    both_roots = resolve_repo_roots(
        repo_scope=scope, repo_root=repo_root,
        repo_preset=repo_preset, enterprise_root=enterprise_root,
    )
    both_key = roots_key(both_roots)
    registry = registry_cached(both_key)
    verifier = verifier_for(both_key, include_registry=True)
    eng_root = both_roots[0]

    effective_source = source_entity
    effective_target = target_entity
    grf_source_id: str | None = None
    grf_artifact_id: str | None = None
    warnings: list[str] = []

    def _ensure_grf(global_id: str) -> str:
        nonlocal registry, verifier
        from src.tools.model_write.global_entity_reference import ensure_global_entity_reference
        full_repo = repo_cached(both_key)
        rec = full_repo.get_entity(global_id)
        name = rec.name if rec else global_id
        eng_repo = repo_cached(roots_key(both_roots[:1]))
        grf_result = ensure_global_entity_reference(
            engagement_repo=eng_repo, engagement_root=eng_root, verifier=verifier,
            clear_repo_caches=clear_caches_for_repo,
            global_entity_id=global_id, global_entity_name=name, dry_run=dry_run,
        )
        if grf_result.wrote:
            warnings.append(f"Created GRF proxy {grf_result.artifact_id} for {global_id}")
            clear_caches_for_repo(eng_root)
            registry = registry_cached(both_key)
            verifier = verifier_for(both_key, include_registry=True)
        else:
            warnings.append(f"Routed via existing GRF proxy {grf_result.artifact_id}")
        return grf_result.artifact_id

    if source_entity in registry.enterprise_entity_ids():
        grf_source_id = _ensure_grf(source_entity)
        effective_source = grf_source_id

    if target_entity in registry.enterprise_entity_ids():
        grf_artifact_id = _ensure_grf(target_entity)
        effective_target = grf_artifact_id

    result = model_write_ops.add_connection(
        repo_root=eng_root, registry=registry, verifier=verifier,
        clear_repo_caches=clear_caches_for_repo,
        source_entity=effective_source, connection_type=connection_type,
        target_entity=effective_target, description=description,
        src_cardinality=src_cardinality, tgt_cardinality=tgt_cardinality,
        version=version, status=status, last_updated=last_updated, dry_run=dry_run,
    )
    out = _out(result, dry_run=dry_run)
    if grf_source_id:
        out["grf_source_id"] = grf_source_id
        out["original_source"] = source_entity
    if grf_artifact_id:
        out["grf_artifact_id"] = grf_artifact_id
        out["original_target"] = target_entity
    all_warnings = warnings + list(result.warnings or [])
    if all_warnings:
        out["warnings"] = all_warnings
    return out


def register(mcp: FastMCP) -> None:
    from src.tools.model_mcp.write_queue import queued

    mcp.tool(
        name="model_add_connection", title="Model Write: Add Connection",
        description=(
            "Add a connection to an entity's .outgoing.md file. Defaults use repos from "
            "arch-init workspace config (repo_root, enterprise_root optional). "
            "Connecting from/to a global entity automatically creates a per-engagement "
            "proxy (global-entity-reference) if one does not already exist — handles "
            "outgoing, incoming, and symmetric connections transparently. "
            "Optional src_cardinality / tgt_cardinality annotate the source or target end "
            "of the connection (e.g. '1', '0..1', '1..*', '*'). Not permitted on junctions. "
            "dry_run=true returns would-be content without writing."
        ),
        structured_output=True,
    )(queued(model_add_connection))
