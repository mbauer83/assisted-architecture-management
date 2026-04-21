"""Shared server state and helper functions for GUI router modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from fastapi import HTTPException
except ModuleNotFoundError:  # pragma: no cover - test env without GUI deps
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

from src.common.model_query import ModelRepository
from src.common.model_query_types import ConnectionRecord, DiagramRecord, EntityRecord


# Module-level server state — set by gui_server.main() before uvicorn starts.
_repo: ModelRepository | None = None
_repo_root: Path | None = None          # engagement root — used for writes
_enterprise_root: Path | None = None    # enterprise root — read-only in normal mode
_admin_mode: bool = False               # when True, enterprise writes are permitted via /admin/api/*


def init_state(
    repo: ModelRepository,
    repo_root: Path,
    enterprise_root: Path | None,
    *,
    admin_mode: bool = False,
) -> None:
    global _repo, _repo_root, _enterprise_root, _admin_mode
    _repo = repo
    _repo_root = repo_root
    _enterprise_root = enterprise_root
    _admin_mode = admin_mode


def is_admin_mode() -> bool:
    return _admin_mode


def get_repo() -> ModelRepository:
    if _repo is None:
        raise HTTPException(500, "Repository not initialized")
    return _repo


def maybe_get_repo() -> ModelRepository | None:
    return _repo


def configured_roots() -> list[Path]:
    roots: list[Path] = []
    if _repo_root is not None:
        roots.append(_repo_root.resolve())
    if _enterprise_root is not None:
        roots.append(_enterprise_root.resolve())
    return roots


def is_global(path: Path) -> bool:
    return _enterprise_root is not None and path.is_relative_to(_enterprise_root)


def entity_to_summary(
    e: EntityRecord,
    conn_counts: dict[str, tuple[int, int, int]] | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "artifact_id": e.artifact_id, "artifact_type": e.artifact_type,
        "name": e.name, "version": e.version, "status": e.status,
        "domain": e.domain, "subdomain": e.subdomain, "path": str(e.path),
        "is_global": is_global(e.path),
    }
    if conn_counts is not None:
        inc, sym, out = conn_counts.get(e.artifact_id, (0, 0, 0))
        d["conn_in"] = inc
        d["conn_sym"] = sym
        d["conn_out"] = out
    return d


def build_conn_counts(repo: ModelRepository) -> dict[str, tuple[int, int, int]]:
    from src.common.ontology_loader import SYMMETRIC_CONNECTIONS
    counts: dict[str, list[int]] = {}
    for rec in repo._connections.values():
        is_sym = rec.conn_type in SYMMETRIC_CONNECTIONS
        src = counts.setdefault(rec.source, [0, 0, 0])
        tgt = counts.setdefault(rec.target, [0, 0, 0])
        if is_sym:
            src[1] += 1
            if rec.target != rec.source:
                tgt[1] += 1
        else:
            src[2] += 1
            tgt[0] += 1
    return {k: (v[0], v[1], v[2]) for k, v in counts.items()}


def resolve_grf(artifact_id: str) -> tuple[str, bool]:
    """If artifact_id is a GRF, return (global_entity_id, True); else (artifact_id, False)."""
    repo = _repo
    if repo is None:
        return artifact_id, False
    rec = repo.get_entity(artifact_id)
    if rec is not None and rec.artifact_type == "global-entity-reference":
        geid = rec.extra.get("global-entity-id")
        if isinstance(geid, str) and geid:
            return geid, True
    return artifact_id, False


def connection_to_dict(c: ConnectionRecord) -> dict[str, Any]:
    repo = _repo
    resolved_target, via_grf = resolve_grf(c.target)
    src_name = c.source
    tgt_name = resolved_target
    if repo is not None:
        src_rec = repo.get_entity(c.source)
        tgt_rec = repo.get_entity(resolved_target)
        if src_rec is not None and src_rec.name:
            src_name = src_rec.name
        if tgt_rec is not None and tgt_rec.name:
            tgt_name = tgt_rec.name
    d: dict[str, Any] = {
        "artifact_id": c.artifact_id, "source": c.source, "target": resolved_target,
        "conn_type": c.conn_type, "version": c.version, "status": c.status,
        "path": str(c.path), "content_text": c.content_text,
        "associated_entities": list(c.associated_entities),
        "src_cardinality": c.src_cardinality,
        "tgt_cardinality": c.tgt_cardinality,
        "source_name": src_name,
        "target_name": tgt_name,
    }
    if via_grf:
        d["grf_artifact_id"] = c.target
    return d


def diagram_to_summary(d: DiagramRecord) -> dict[str, Any]:
    return {
        "artifact_id": d.artifact_id, "name": d.name, "diagram_type": d.diagram_type,
        "version": d.version, "status": d.status, "path": str(d.path),
    }


def get_write_deps() -> tuple[Path, Any, Any]:
    """Return (engagement_root, registry, verifier). Registry spans both repos."""
    if _repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    from src.common.model_verifier import ModelVerifier
    from src.common.model_verifier_registry import ModelRegistry
    roots: list[Path] = [_repo_root]
    if _enterprise_root is not None:
        roots.append(_enterprise_root)
    registry = ModelRegistry(roots)
    return _repo_root, registry, ModelVerifier(registry)


def get_admin_write_deps() -> tuple[Path, Any, Any]:
    """Return (enterprise_root, registry, verifier) for admin-mode writes.

    Raises 403 when admin mode is not enabled, 500 when enterprise root is
    not configured.  Registry spans both repos so cross-repo entity references
    in outgoing files validate correctly.
    """
    if not _admin_mode:
        raise HTTPException(403, "Admin mode is not enabled")
    if _enterprise_root is None:
        raise HTTPException(500, "Enterprise repository not configured")
    from src.common.model_verifier import ModelVerifier
    from src.common.model_verifier_registry import ModelRegistry
    roots: list[Path] = [_enterprise_root]
    if _repo_root is not None:
        roots.append(_repo_root)
    registry = ModelRegistry(roots)
    return _enterprise_root, registry, ModelVerifier(registry)


def clear_caches(_: Path) -> None:
    if _repo is not None:
        _repo.refresh()
        try:
            from src.tools.model_mcp.watch_tools import schedule_refresh
        except Exception:  # noqa: BLE001
            return
        roots = configured_roots()
        if roots:
            schedule_refresh(roots)


def refresh_now() -> None:
    if _repo is not None:
        _repo.refresh()


def run_serialized_write(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    from src.tools.model_mcp.write_queue import run_sync

    return run_sync(fn, *args, **kwargs)


def write_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "wrote": bool(result.wrote), "path": str(result.path),
        "artifact_id": result.artifact_id,
        "content": result.content, "warnings": result.warnings,
        "verification": result.verification,
    }


def get_both_roots() -> tuple[Path, Path]:
    if _repo_root is None or _enterprise_root is None:
        raise HTTPException(500, "Both engagement and enterprise repos must be initialized")
    return _repo_root, _enterprise_root
