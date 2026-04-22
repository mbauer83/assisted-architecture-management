
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.artifact_mcp.context import RepoPreset, RepoScope, resolve_repo_roots, roots_key, verifier_for
from src.tools.artifact_mcp.formatting import as_verification_result_dict


def artifact_verify(
    path: str | None = None,
    *,
    file_type: Literal["entity", "connection", "diagram"] | None = None,
    include_diagrams: bool = True,
    include_registry: bool = True,
    return_mode: Literal["summary", "full"] = "summary",
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    enterprise_root: str | None = None,
    repo_scope: RepoScope = "both",
) -> dict[str, Any]:
    roots = resolve_repo_roots(
        repo_scope=repo_scope,
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=enterprise_root,
    )
    key = roots_key(roots)
    engagement_root = roots[0]
    verifier = verifier_for(key, include_registry=include_registry)

    if path is not None:
        from pathlib import Path
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = engagement_root / p
        inferred = file_type
        if inferred is None:
            if p.suffix == ".puml" or (
                p.suffix == ".md" and "diagram-catalog" in p.parts and "diagrams" in p.parts
            ):
                inferred = "diagram"
            else:
                inferred = "connection" if "connections" in p.parts else "entity"
        match inferred:
            case "entity":
                result = verifier.verify_entity_file(p)
            case "connection":
                result = verifier.verify_connection_file(p)
            case "diagram":
                result = verifier.verify_matrix_diagram_file(p) if p.suffix == ".md" else verifier.verify_diagram_file(p)
        out = as_verification_result_dict(result)
        out["repo_roots"] = [str(r) for r in roots]
        out["repo_scope"] = repo_scope
        return out

    # Batch verify all
    results = verifier.verify_all(engagement_root, include_diagrams=include_diagrams)
    total = len(results)
    total_valid = sum(1 for r in results if r.valid)
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)
    if return_mode == "full":
        payload: Any = [as_verification_result_dict(r) for r in results if r.issues]
    else:
        payload = [
            {
                "path": str(r.path),
                "file_type": r.file_type,
                "valid": r.valid,
                "issues": [
                    {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
                    for i in r.issues
                ],
            }
            for r in results
            if r.issues
        ]
    return {
        "repo_roots": [str(r) for r in roots],
        "repo_scope": repo_scope,
        "include_diagrams": include_diagrams,
        "include_registry": include_registry,
        "counts": {
            "files": total,
            "valid_files": total_valid,
            "invalid_files": total - total_valid,
            "errors": total_errors,
            "warnings": total_warnings,
        },
        "results": payload,
    }


# Keep the original functions as thin aliases for direct callers / tests.
def artifact_verify_file(
    path: str,
    *,
    file_type: Literal["entity", "connection", "diagram"] | None = None,
    include_registry: bool = True,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    enterprise_root: str | None = None,
    repo_scope: RepoScope = "both",
) -> dict[str, Any]:
    return artifact_verify(
        path,
        file_type=file_type,
        include_registry=include_registry,
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=enterprise_root,
        repo_scope=repo_scope,
    )


def artifact_verify_all(
    *,
    include_diagrams: bool = True,
    include_registry: bool = True,
    return_mode: Literal["summary", "full"] = "summary",
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    enterprise_root: str | None = None,
    repo_scope: RepoScope = "both",
) -> dict[str, Any]:
    return artifact_verify(
        include_diagrams=include_diagrams,
        include_registry=include_registry,
        return_mode=return_mode,
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=enterprise_root,
        repo_scope=repo_scope,
    )


def register_verify_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="artifact_verify",
        title="Artifact Verifier",
        description=(
            "Verify one file or all model files. "
            "Pass path= to verify a single entity/connection/diagram file (absolute or relative to repo_root; "
            "file_type is inferred if omitted). "
            "Omit path to verify the entire repository — returns issue counts and a list of files with errors/warnings. "
            "return_mode='summary' (default) gives compact issue lines; 'full' gives per-issue detail."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        structured_output=True,
    )(artifact_verify)
