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


def register_query_search_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="artifact_query_search_artifacts",
        title="Artifact Query: Search Artifacts",
        description=(
            "Search artifacts by text query (keyword-scored; may include semantic supplement if configured). "
            "Returns ranked hits as (score + summary record). "
            "\n\nFilters: limit, domain, artifact_type, include_record_types, prefer_record_type, strict_record_type. "
            "Domain filter is case-insensitive; canonical lowercase values: "
            '"common", "motivation", "strategy", "business", "application", "technology", "implementation".'
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        structured_output=True,
    )
    def artifact_query_search_artifacts(
        query: str,
        *,
        limit: int = 10,
        domain: str | list[str] | None = None,
        artifact_type: str | list[str] | None = None,
        include_record_types: list[Literal["entities", "connections", "diagrams", "documents"]]
        | None = None,
        prefer_record_type: Literal["entity", "connection", "diagram", "document"] | None = None,
        strict_record_type: bool = False,
        fields: list[str] | None = None,
        repo_root: str | None = None,
        repo_scope: RepoScope = "both",
    ) -> dict[str, object]:
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
            default=("entities", "diagrams", "documents"),
        )

        result = repo.search_artifacts(
            query,
            limit=limit,
            domain=domain,
            artifact_type=artifact_type,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
            prefer_record_type=prefer_record_type,
            strict_record_type=strict_record_type,
        )

        hits: list[dict[str, object]] = []
        for h in result.hits:
            aid = getattr(h.record, "artifact_id", "")
            summary = repo.summarize_artifact(aid) if aid else None
            record = {
                "score": h.score,
                "record_type": h.record_type,
                "artifact_id": aid,
            }
            if summary is not None:
                summary_dict = asdict(summary)
                summary_dict["path"] = str(summary.path)
                record.update(summary_dict)
            hits.append(_project(record, fields))

        return {
            "repo_roots": [str(p) for p in roots],
            "repo_scope": repo_scope,
            "query": result.query,
            "hits": hits,
        }
