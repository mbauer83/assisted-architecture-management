from functools import lru_cache
from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.context import (
    RepoScope,
    expand_artifact_id,
    repo_cached,
    resolve_repo_roots,
    roots_key,
)
from src.infrastructure.mcp.artifact_mcp.tool_annotations import READ_ONLY


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def _allowed_bindings_for(diagram_type: str | None):  # type: ignore[return]
    """Return AllowedBindingsSpec for diagram_type, or None if not found / empty."""
    if not diagram_type:
        return None
    mod = _registry().find_diagram_type(diagram_type)
    if mod is None:
        return None
    guidance = mod.write_guidance()
    ab = guidance.allowed_bindings
    return ab if (ab is not None and not ab.is_empty()) else None


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
            "\n\nAccepts both full (PREFIX@epoch.random.slug) and short (PREFIX@epoch.random) form."
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
        entity_id = expand_artifact_id(repo, entity_id)

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
            "Optionally restrict by conn_type. "
            "Pass diagram_type to receive binding_guidance for each neighbor — lists admissible "
            "diagram entity types, default and admissible correspondence kinds — so results can be "
            "used directly as binding proposals without a separate propose-bindings call."
            "\n\nAccepts both full (PREFIX@epoch.random.slug) and short (PREFIX@epoch.random) form."
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
        diagram_type: str | None = None,
        repo_root: str | None = None,
        repo_scope: RepoScope = "both",
    ) -> dict[str, object]:
        from src.application.derivation.binding_proposals import entity_binding_guidance  # noqa: PLC0415

        roots = resolve_repo_roots(
            repo_scope=repo_scope,
            repo_root=repo_root,
            repo_preset=None,
            enterprise_root=None,
        )
        key = roots_key(roots)
        repo = repo_cached(key)
        entity_id = expand_artifact_id(repo, entity_id)

        neighbors = repo.find_neighbors(entity_id, max_hops=max_hops, conn_type=conn_type)
        normalized = {k: sorted(list(v)) for k, v in neighbors.items()}

        ab = _allowed_bindings_for(diagram_type)
        result: dict[str, object] = {
            "repo_roots": [str(p) for p in roots],
            "repo_scope": repo_scope,
            "entity_id": entity_id,
            "max_hops": max_hops,
            "neighbors": normalized,
        }
        if ab is not None:
            result["diagram_type"] = diagram_type
            guidance: dict[str, list[dict[str, object]]] = {}
            for hop_eids in normalized.values():
                for eid in hop_eids:
                    if eid in guidance:
                        continue
                    summary = repo.summarize_artifact(eid)
                    etype = summary.artifact_type if summary is not None else ""
                    candidates = entity_binding_guidance(etype, ab)
                    if candidates:
                        guidance[eid] = candidates
            result["binding_guidance"] = guidance
        return result
