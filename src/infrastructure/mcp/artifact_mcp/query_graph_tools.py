from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.context import RepoScope, repo_cached, resolve_repo_roots, roots_key
from src.infrastructure.mcp.artifact_mcp.tool_annotations import READ_ONLY


def register_query_graph_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="artifact_query_find_connections_for",
        title="Artifact Query: Find Connections",
        description=(
            "Find connection records that touch a given entity_id. "
            "direction: any|outbound|inbound; optionally filter by conn_type. "
            "Results include source_name and target_name alongside source/target artifact_ids. "
            "fields: optional list of keys to project — e.g. "
            "['source','target','source_name','target_name','conn_type'] for fast dedup checks."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def artifact_query_find_connections_for(
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
        fields: list[str] | None = None,
        repo_root: str | None = None,
        repo_scope: RepoScope = "both",
    ) -> list[dict[str, object]]:
        roots = resolve_repo_roots(
            repo_scope=repo_scope,
            repo_root=repo_root,
            repo_preset=None,
            enterprise_root=None,
        )
        key = roots_key(roots)
        repo = repo_cached(key)

        conns = repo.find_connections_for(
            entity_id,
            direction=direction,
            conn_type=conn_type,
        )

        fields_set = set(fields) if fields else None
        out: list[dict[str, object]] = []
        for c in conns:
            d = repo.read_artifact(c.artifact_id, mode="summary")
            if d is not None:
                src_summary = repo.summarize_artifact(c.source)
                tgt_summary = repo.summarize_artifact(c.target)
                if src_summary is not None:
                    d["source_name"] = src_summary.name
                if tgt_summary is not None:
                    d["target_name"] = tgt_summary.name
                if fields_set:
                    d = {k: v for k, v in d.items() if k in fields_set}
                out.append(d)
        return out

    @mcp.tool(
        name="artifact_query_find_neighbors",
        title="Artifact Query: Find Neighbors",
        description=(
            "Graph traversal: return entity_ids reachable from entity_id within max_hops using connections. "
            "Optionally restrict by conn_type."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def artifact_query_find_neighbors(
        entity_id: str,
        *,
        max_hops: int = 1,
        conn_type: str | None = None,
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

        neighbors = repo.find_neighbors(entity_id, max_hops=max_hops, conn_type=conn_type)
        normalized = {k: sorted(list(v)) for k, v in neighbors.items()}
        return {
            "repo_roots": [str(p) for p in roots],
            "repo_scope": repo_scope,
            "entity_id": entity_id,
            "max_hops": max_hops,
            "neighbors": normalized,
        }
