"""Shared imports and helpers for MCP write submodules."""
from src.tools import artifact_write_ops
from src.tools.artifact_mcp.context import (
    RepoPreset,
    clear_caches_for_repo,
    registry_cached,
    repo_cached,
    resolve_repo_roots,
    roots_key,
    verifier_for,
)

WriteRepoScope = artifact_write_ops.WriteRepoScope
DiagramConnectionInferenceMode = artifact_write_ops.DiagramConnectionInferenceMode


def _out(result, *, dry_run: bool) -> dict[str, object]:
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
