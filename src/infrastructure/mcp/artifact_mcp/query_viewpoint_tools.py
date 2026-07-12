"""MCP read tool: ``artifact_query_viewpoint`` (companion plan §9, §9.1) — browse the
effective merged viewpoint catalog or execute a definition/ad-hoc query, calling the same
``EvaluateViewpoint`` use case as REST (WU-E7) and MCP write's ``artifact_viewpoint``
(WU-E6a). No presentation/styling/column parameters exist on this tool — the locked D15
MCP boundary; the full query grammar lives in ``artifact_help``'s ``viewpoints`` topic.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.application.viewpoints.evaluate_viewpoint import (
    UnknownViewpointSlugError,
    ViewpointExecutionRequest,
    evaluate_viewpoint,
)
from src.application.viewpoints.registry_snapshot import build_registry_snapshot
from src.config.settings import (
    viewpoints_execution_default_entity_limit_mcp,
    viewpoints_execution_max_entities,
    viewpoints_execution_timeout_seconds,
)
from src.domain.viewpoint_query_parsing import query_from_mapping
from src.domain.viewpoint_summary import render_query_summary
from src.domain.viewpoints import ViewpointDefinition
from src.infrastructure.mcp.artifact_mcp.context import (
    RepoScope,
    repo_cached,
    resolve_repo_roots,
    roots_key,
    runtime_catalogs,
)
from src.infrastructure.mcp.artifact_mcp.tool_annotations import READ_ONLY
from src.infrastructure.viewpoint_declarations import load_effective_viewpoint_catalog
from src.infrastructure.write.artifact_write.viewpoint_type_guidance import summarize_scope


def _list_entry(definition: ViewpointDefinition) -> dict[str, object]:
    return {
        "slug": definition.slug,
        "version": definition.version,
        "name": definition.name,
        "description": definition.description,
        "purpose": list(definition.purpose),
        "content": list(definition.content),
        "stakeholders": list(definition.stakeholders),
        "concerns": list(definition.concerns),
        "scope_summary": summarize_scope(definition.scope),
        "query_summary": render_query_summary(definition.query) if definition.query is not None else None,
    }


def register_query_viewpoint_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="artifact_query_viewpoint",
        title="Artifact Query: Viewpoints",
        description=(
            "action='list': browse the effective merged viewpoint catalog — slug/version/name/"
            "purpose/content/stakeholders/concerns, a scope summary, and a plain-language "
            "query_summary so you see what a viewpoint means, not just that it exists. "
            "action='execute': run a definition's query (slug=...) or an ad-hoc query "
            "(query=..., Appendix-A shape — see artifact_help's 'viewpoints' topic for the "
            "grammar); returns sorted entity/connection ids with fixed summaries, four counts, "
            "truncation, matrix_axes (criteria-axes matrix only), warnings, and the echoed "
            "query_summary. No presentation/styling/column parameters exist here. "
            "limit (execute only) is entity-denominated, defaults small to protect context, "
            "clamped to the hard cap."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def artifact_query_viewpoint(
        action: Literal["list", "execute"],
        slug: str | None = None,
        query: dict[str, object] | None = None,
        limit: int | None = None,
        repo_root: str | None = None,
        repo_scope: RepoScope = "both",
    ) -> dict[str, object]:
        roots = resolve_repo_roots(repo_scope=repo_scope, repo_root=repo_root, repo_preset=None, enterprise_root=None)
        merged_catalog = load_effective_viewpoint_catalog(roots)

        if action == "list":
            entries = [_list_entry(d) for d in sorted(merged_catalog.entries, key=lambda d: d.slug)]
            return {"viewpoints": entries}

        if (slug is None) == (query is None):
            raise ValueError("action='execute' requires exactly one of 'slug' or 'query'")
        parsed_query = query_from_mapping(query, label="query") if query is not None else None
        request = ViewpointExecutionRequest(slug=slug, query=parsed_query, limit=limit)

        catalogs = runtime_catalogs()
        repo = repo_cached(roots_key(roots))
        registries = build_registry_snapshot(catalogs, repo.repo_roots)
        try:
            result = evaluate_viewpoint(
                request,
                catalog=merged_catalog,
                read_access=repo,
                registries=registries,
                index_generation=repo.read_model_version().generation,
                max_entities=viewpoints_execution_max_entities(),
                default_limit=viewpoints_execution_default_entity_limit_mcp(),
                timeout_seconds=viewpoints_execution_timeout_seconds(),
            )
        except UnknownViewpointSlugError as exc:
            raise ValueError(str(exc)) from exc
        return asdict(result)
