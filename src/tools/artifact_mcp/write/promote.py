"""MCP write tools: promotion to enterprise."""
from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]
from src.tools.artifact_mcp.write._common import (
    clear_caches_for_repo, registry_cached, repo_cached,
    resolve_repo_roots, roots_key, verifier_for, RepoPreset,
)


def artifact_promote_to_enterprise(
    *,
    entity_id: str,
    entity_ids: list[str] | None = None,
    connection_ids: list[str] | None = None,
    document_ids: list[str] | None = None,
    diagram_ids: list[str] | None = None,
    dry_run: bool = True,
    conflict_resolutions: list[dict[str, object]] | None = None,
    exclude_entities: list[str] | None = None,
    exclude_connections: list[str] | None = None,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    enterprise_root: str | None = None,
) -> dict[str, object]:
    """Promote entities, connections, documents, and diagrams from engagement to enterprise repo.

    Defaults use repos from arch-init workspace config (repo_root, enterprise_root optional).
    Promotion is explicit: only the selected artifacts are promoted.
    After promotion, promoted engagement artifacts are replaced by GAR proxies.
    dry_run=true returns the plan without modifying any files.
    """
    from src.tools.artifact_mcp.context import resolve_enterprise_repo_root
    from src.tools.artifact_write.promote_to_enterprise import ConflictResolution, plan_promotion
    from src.tools.artifact_write.promote_execute import execute_promotion

    eng_root = resolve_repo_roots(
        repo_scope="engagement", repo_root=repo_root,
        repo_preset=repo_preset, enterprise_root=None,
    )[0]
    ent_root = resolve_enterprise_repo_root(enterprise_root=enterprise_root)
    both_roots = resolve_repo_roots(
        repo_scope="both", repo_root=repo_root,
        repo_preset=repo_preset, enterprise_root=enterprise_root,
    )
    both_key = roots_key(both_roots)
    registry = registry_cached(both_key)
    repo = repo_cached(both_key)

    plan = plan_promotion(
        entity_id, registry, repo,
        entity_ids=entity_ids or [entity_id],
        connection_ids=set(connection_ids) if connection_ids else None,
        exclude_entity_ids=set(exclude_entities) if exclude_entities else None,
        exclude_connection_ids=set(exclude_connections) if exclude_connections else None,
        document_ids=document_ids or None,
        diagram_ids=diagram_ids or None,
    )

    out: dict[str, object] = {
        "dry_run": dry_run, "entity_id": entity_id,
        "entities_to_add": plan.entities_to_add,
        "conflicts": [
            {
                "engagement_id": c.engagement_id, "enterprise_id": c.enterprise_id,
                "artifact_type": c.artifact_type,
                "engagement_name": c.engagement_name, "enterprise_name": c.enterprise_name,
                "engagement_fields": c.engagement_fields, "enterprise_fields": c.enterprise_fields,
            }
            for c in plan.conflicts
        ],
        "connections_to_promote": plan.connection_ids,
        "already_in_enterprise": plan.already_in_enterprise,
        "documents_to_add": plan.documents_to_add,
        "diagrams_to_add": plan.diagrams_to_add,
        "doc_conflicts": [
            {"engagement_id": c.engagement_id, "enterprise_id": c.enterprise_id,
             "doc_type": c.doc_type,
             "engagement_title": c.engagement_title, "enterprise_title": c.enterprise_title}
            for c in plan.doc_conflicts
        ],
        "diagram_conflicts": [
            {"engagement_id": c.engagement_id, "enterprise_id": c.enterprise_id,
             "diagram_type": c.diagram_type,
             "engagement_name": c.engagement_name, "enterprise_name": c.enterprise_name}
            for c in plan.diagram_conflicts
        ],
        "warnings": plan.warnings,
        "schema_errors": plan.schema_errors,
    }

    if not dry_run:
        from src.tools.enterprise_git_ops import ensure_working_branch
        ensure_working_branch(ent_root)

        resolutions = [
            ConflictResolution(
                engagement_id=str(r["engagement_id"]),
                strategy=r["strategy"],  # type: ignore[arg-type]
                merged_fields=r.get("merged_fields"),  # type: ignore[arg-type]
            )
            for r in (conflict_resolutions or [])
        ]
        result = execute_promotion(
            plan, eng_root, ent_root,
            verifier_for(both_key, include_registry=True), registry,
            conflict_resolutions=resolutions,
        )
        out.update({
            "executed": result.executed,
            "copied_files": result.copied_files,
            "updated_files": result.updated_files,
            "verification_errors": result.verification_errors,
            "rolled_back": result.rolled_back,
        })
        if result.executed:
            clear_caches_for_repo(eng_root)

    return out


def register(mcp: FastMCP) -> None:
    from src.tools.artifact_mcp.write_queue import queued

    mcp.tool(
        name="artifact_promote_to_enterprise", title="Artifact Write: Promote to Enterprise",
        description=(
            "Promote an explicit set of selected entities and connections from the engagement "
            "repo to the enterprise repo. Defaults use arch-init workspace config. "
            "After successful promotion the entity is replaced by a GRF proxy in the "
            "engagement repo. dry_run=true returns the plan without modifying files. "
            "exclude_entities / exclude_connections prune the explicit selection."
        ),
        structured_output=True,
    )(queued(artifact_promote_to_enterprise))
