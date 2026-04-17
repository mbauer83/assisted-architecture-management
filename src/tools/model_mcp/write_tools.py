
from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools import model_write_ops
from src.tools.model_mcp.context import RepoPreset, RepoScope, registry_cached, repo_cached, resolve_repo_roots, roots_key, verifier_for, clear_caches_for_repo


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


def model_promote_to_enterprise(
    *,
    entity_id: str,
    include_transitive: bool = True,
    dry_run: bool = True,
    conflict_resolutions: list[dict[str, object]] | None = None,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    enterprise_root: str | None = None,
) -> dict[str, object]:
    """Promote entity (+ transitive closure) from engagement to enterprise.

    dry_run=true returns the plan including detected conflicts.
    Conflicts are entities with matching (artifact_type, name) already in
    enterprise under a different artifact_id.

    To execute with conflicts, provide conflict_resolutions — a list of
    ``{"engagement_id": "...", "strategy": "accept_engagement"|"accept_enterprise"|"merge",
       "merged_fields": {...}}`` dicts.
    """
    from src.tools.model_mcp.context import resolve_enterprise_repo_root
    from src.tools.model_write.promote_to_enterprise import (
        ConflictResolution, plan_promotion,
    )
    from src.tools.model_write.promote_execute import execute_promotion

    eng_roots = resolve_repo_roots(
        repo_scope="engagement", repo_root=repo_root,
        repo_preset=repo_preset, enterprise_root=None,
    )
    eng_root = eng_roots[0]
    ent_root = resolve_enterprise_repo_root(enterprise_root=enterprise_root)

    both_roots = resolve_repo_roots(
        repo_scope="both", repo_root=repo_root,
        repo_preset=repo_preset, enterprise_root=enterprise_root,
    )
    both_key = roots_key(both_roots)
    registry = registry_cached(both_key)
    repo = repo_cached(both_key)

    plan = plan_promotion(entity_id, registry, repo, include_transitive=include_transitive)

    out: dict[str, object] = {
        "dry_run": dry_run,
        "entity_id": entity_id,
        "entities_to_add": plan.entities_to_add,
        "conflicts": [
            {
                "engagement_id": c.engagement_id,
                "enterprise_id": c.enterprise_id,
                "artifact_type": c.artifact_type,
                "engagement_name": c.engagement_name,
                "enterprise_name": c.enterprise_name,
                "engagement_fields": c.engagement_fields,
                "enterprise_fields": c.enterprise_fields,
            }
            for c in plan.conflicts
        ],
        "connections_to_promote": plan.connection_ids,
        "already_in_enterprise": plan.already_in_enterprise,
        "warnings": plan.warnings,
    }

    if not dry_run:
        resolutions = [
            ConflictResolution(
                engagement_id=str(r["engagement_id"]),
                strategy=r["strategy"],  # type: ignore[arg-type]
                merged_fields=r.get("merged_fields"),  # type: ignore[arg-type]
            )
            for r in (conflict_resolutions or [])
        ]
        verifier = verifier_for(both_key, include_registry=True)
        result = execute_promotion(
            plan, eng_root, ent_root, verifier, registry,
            conflict_resolutions=resolutions,
        )
        out["executed"] = result.executed
        out["copied_files"] = result.copied_files
        out["updated_files"] = result.updated_files
        out["verification_errors"] = result.verification_errors
        out["rolled_back"] = result.rolled_back
        if result.executed:
            clear_caches_for_repo(eng_root)

    return out


def register_write_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="model_write_help",
        title="Model Write: Type Catalog",
        description=(
            "Return the full catalog of valid artifact_type and connection_type values. "
            "Call this before model_create_entity or model_add_connection — type names "
            "are non-obvious identifiers (e.g. 'archimate-influence', not 'influence') "
            "and guessing them without this catalog will cause validation errors."
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
            "Create an ArchiMate diagram from a complete PlantUML body. "
            "puml must be a full @startuml…@enduml block using entity display_alias values "
            "as element identifiers (e.g. 'rectangle \"<$archimate_BusinessActor{scale=1.5}> Name\" "
            "<<BusinessActor>> as ACT_Xx1Yy1'). "
            "Read each entity with model_query_read_artifact(mode='full') to get its display_alias "
            "and archimate display block before writing the PUML. "
            "auto_include_stereotypes=true (default) injects the !include directives automatically. "
            "Renders PNG after write. Use dry_run=true to validate before committing."
        ),
        structured_output=True,
    )(model_create_diagram)

    mcp.tool(
        name="model_promote_to_enterprise",
        title="Model Write: Promote to Enterprise",
        description=(
            "Promote an entity (and its transitive closure of connected entities) "
            "from the engagement repo to the enterprise repo. "
            "dry_run=true returns the promotion plan without copying files."
        ),
        structured_output=True,
    )(model_promote_to_enterprise)
