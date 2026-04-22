
from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.artifact_mcp.context import RepoPreset, RepoScope, repo_cached, resolve_repo_roots, roots_key


def register_query_stats_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="artifact_query_stats",
        title="Artifact Query: Stats",
        description=(
            "Return model statistics: total entity/connection/diagram counts and breakdowns "
            "by domain and connection type. Use this first to confirm the server is pointed "
            "at the expected repo. "
            "Pass group_by='artifact_type'|'diagram_type'|'domain' to get a filtered count "
            "breakdown instead of the default summary."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        structured_output=True,
    )
    def artifact_query_stats(
        *,
        group_by: Literal["artifact_type", "diagram_type", "domain"] | None = None,
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_connections: bool = True,
        include_diagrams: bool = True,
        repo_root: str | None = None,
        repo_preset: RepoPreset | None = None,
        enterprise_root: str | None = None,
        repo_scope: RepoScope = "both",
        refresh: bool = False,
    ) -> dict[str, object]:
        roots = resolve_repo_roots(
            repo_scope=repo_scope,
            repo_root=repo_root,
            repo_preset=repo_preset,
            enterprise_root=enterprise_root,
        )
        key = roots_key(roots)
        repo = repo_cached(key)
        if refresh:
            repo.refresh()
        if group_by is not None:
            counts = repo.count_artifacts_by(
                group_by,
                artifact_type=artifact_type,
                domain=domain,
                status=status,
                include_connections=include_connections,
                include_diagrams=include_diagrams,
            )
            return {
                "repo_roots": [str(p) for p in roots],
                "repo_scope": repo_scope,
                "group_by": group_by,
                "counts": counts,
            }
        stats = repo.stats()
        stats["repo_roots"] = [str(p) for p in roots]
        stats["repo_scope"] = repo_scope
        return stats
