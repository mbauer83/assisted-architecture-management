from dataclasses import asdict
from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.artifact_mcp.context import RepoScope, repo_cached, resolve_repo_roots, roots_key


def _project(record: dict[str, object], fields: list[str] | None) -> dict[str, object]:
    if not fields:
        return record
    return {field: record[field] for field in fields if field in record}


def _include_flags(
    include_record_types: list[Literal["entities", "connections", "diagrams", "documents"]] | None,
    *,
    default: tuple[str, ...],
) -> tuple[bool, bool, bool]:
    selected = set(include_record_types or default)
    return (
        "connections" in selected,
        "diagrams" in selected,
        "documents" in selected,
    )


def register_query_list_read_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="artifact_query_list_artifacts",
        title="Artifact Query: List Artifacts",
        description=(
            "List artifacts (metadata-only) with AND-semantics filters. "
            "Returns lightweight summaries; use artifact_type, domain, "
            "or status to narrow results. "
            "Pass fields=[...] to project only the keys you need. "
            "include_record_types defaults to ['entities']. "
            "Domain filter is case-insensitive; canonical lowercase values: "
            '"common", "motivation", "strategy", "business", "application", "technology", "implementation".'
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        structured_output=True,
    )
    def artifact_query_list_artifacts(
        *,
        repo_root: str | None = None,
        repo_scope: RepoScope = "both",
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_record_types: list[Literal["entities", "connections", "diagrams", "documents"]]
        | None = None,
        fields: list[str] | None = None,
    ) -> list[dict[str, object]]:
        roots = resolve_repo_roots(
            repo_scope=repo_scope,
            repo_root=repo_root,
            repo_preset=None,
            enterprise_root=None,
        )
        key = roots_key(roots)
        repo = repo_cached(key)
        include_connections, include_diagrams, include_documents = _include_flags(
            include_record_types,
            default=("entities",),
        )
        summaries = repo.list_artifacts(
            artifact_type=artifact_type,
            domain=domain,
            status=status,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
        )
        out: list[dict[str, object]] = []
        for s in summaries:
            d = asdict(s)
            d["path"] = str(s.path)
            d["repo_scope"] = repo_scope
            out.append(_project(d, fields))
        return out

    @mcp.tool(
        name="artifact_query_read_artifact",
        title="Artifact Query: Read Artifact",
        description=(
            "Read one artifact by artifact_id. "
            "mode='summary' returns frontmatter + a short content snippet; "
            "mode='full' returns full content and display blocks. "
            "For documents, supply section= to return only the content "
            "of a specific ## section (e.g. section='Context')."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        structured_output=True,
    )
    def artifact_query_read_artifact(
        artifact_id: str,
        *,
        mode: Literal["summary", "full"] = "summary",
        section: str | None = None,
        repo_root: str | None = None,
        repo_scope: RepoScope = "both",
    ) -> dict[str, object] | None:
        roots = resolve_repo_roots(
            repo_scope=repo_scope,
            repo_root=repo_root,
            repo_preset=None,
            enterprise_root=None,
        )
        key = roots_key(roots)
        repo = repo_cached(key)
        result = repo.read_artifact(artifact_id, mode=mode, section=section)
        if result is None:
            return None
        result["repo_roots"] = [str(p) for p in roots]
        result["repo_scope"] = repo_scope
        return result
