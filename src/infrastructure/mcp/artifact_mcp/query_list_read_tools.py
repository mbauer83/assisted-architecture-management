from dataclasses import asdict
from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.infrastructure.mcp.artifact_mcp.context import RepoScope, repo_cached, resolve_repo_roots, roots_key
from src.infrastructure.mcp.artifact_mcp.tool_annotations import READ_ONLY


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
            "include_record_types defaults to ['entities']. "
            "Pass fields=[...] to project only the keys you need. "
            "Domain values (case-insensitive): 'common', 'motivation', 'strategy', 'business', "
            "'application', 'technology', 'implementation'; "
            "for diagram-only types, domain = diagram type name (e.g. 'activity')."
            "\n\nhost_diagram_id in results: null = model entity (standalone file, shareable). "
            "non-null = diagram-only entity (no file; lives in that diagram's diagram-entities; "
            "path → diagram file; edit via artifact_edit_diagram)."
            "\n\nrepo_scope defaults to both (engagement + enterprise)."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )
    def artifact_query_list_artifacts(
        *,
        repo_root: str | None = None,
        repo_scope: RepoScope = "both",
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_record_types: list[Literal["entities", "connections", "diagrams", "documents"]] | None = None,
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
            "mode='summary': frontmatter + content snippet. "
            "mode='full': full content and display blocks. "
            "section= (documents only): return a specific ## section."
            "\n\nDiagram-only entities (host_diagram_id present): no standalone file; "
            "lives inside that diagram's diagram-entities only. "
            "Edit via artifact_edit_diagram on the owning diagram."
            "\n\nrepo_scope defaults to both (engagement + enterprise)."
        ),
        annotations=READ_ONLY,
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
        if result.get("record_type") == "diagram":
            extra = result.get("extra")
            if isinstance(extra, dict):
                result["diagram_entities"] = extra.get("diagram-entities")
        result["repo_roots"] = [str(p) for p in roots]
        result["repo_scope"] = repo_scope
        return result
