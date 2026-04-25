"""Shared server state and helper functions for GUI router modules."""

from __future__ import annotations

import threading
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

from src.common.artifact_query import ArtifactRepository
from src.common.artifact_types import ConnectionRecord, DiagramRecord, EntityRecord
from src.infrastructure.artifact_index.coordination import publish_authoritative_mutation


# Module-level server state — set by gui_server.main() before uvicorn starts.
# Guarded by _state_lock so background threads (git sync, refresh workers) can
# safely read these values without racing against init_state().
_state_lock = threading.Lock()
_repo: ArtifactRepository | None = None
_repo_root: Path | None = None          # engagement root — used for writes
_enterprise_root: Path | None = None    # enterprise root — read-only in normal mode
_admin_mode: bool = False               # when True, enterprise writes are permitted via /admin/api/*
_read_only: bool = False                # when True, all engagement writes are blocked


def init_state(
    repo: ArtifactRepository,
    repo_root: Path,
    enterprise_root: Path | None,
    *,
    admin_mode: bool = False,
    read_only: bool = False,
) -> None:
    global _repo, _repo_root, _enterprise_root, _admin_mode, _read_only
    with _state_lock:
        _repo = repo
        _repo_root = repo_root
        _enterprise_root = enterprise_root
        _admin_mode = admin_mode
        _read_only = read_only


def is_admin_mode() -> bool:
    with _state_lock:
        return _admin_mode


def is_read_only() -> bool:
    with _state_lock:
        return _read_only


def get_repo() -> ArtifactRepository:
    with _state_lock:
        repo = _repo
    if repo is None:
        raise HTTPException(500, "Repository not initialized")
    return repo


def maybe_get_repo() -> ArtifactRepository | None:
    with _state_lock:
        return _repo


def maybe_engagement_root() -> Path | None:
    """Return the engagement repository root, or None if not initialised."""
    with _state_lock:
        return _repo_root


def maybe_enterprise_root() -> Path | None:
    """Return the enterprise repository root, or None if not configured."""
    with _state_lock:
        return _enterprise_root


def configured_roots() -> list[Path]:
    with _state_lock:
        roots: list[Path] = []
        if _repo_root is not None:
            roots.append(_repo_root.resolve())
        if _enterprise_root is not None:
            roots.append(_enterprise_root.resolve())
        return roots


def is_global(path: Path) -> bool:
    with _state_lock:
        ent = _enterprise_root
    return ent is not None and path.is_relative_to(ent)


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


def build_conn_counts(repo: ArtifactRepository) -> dict[str, tuple[int, int, int]]:
    return repo.connection_counts()


def resolve_gar(artifact_id: str) -> tuple[str, bool]:
    """If artifact_id is a GAR, return (global_artifact_id, True); else (artifact_id, False)."""
    with _state_lock:
        repo = _repo
    if repo is None:
        return artifact_id, False
    rec = repo.get_entity(artifact_id)
    if rec is not None and rec.artifact_type == "global-artifact-reference":
        gaid = rec.extra.get("global-artifact-id")
        if isinstance(gaid, str) and gaid:
            return gaid, True
    return artifact_id, False


def connection_to_dict(c: ConnectionRecord) -> dict[str, Any]:
    with _state_lock:
        repo = _repo
    resolved_target, via_gar = resolve_gar(c.target)
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
    if via_gar:
        d["gar_artifact_id"] = c.target
    return d


def diagram_to_summary(d: DiagramRecord) -> dict[str, Any]:
    return {
        "artifact_id": d.artifact_id, "name": d.name, "diagram_type": d.diagram_type,
        "version": d.version, "status": d.status, "path": str(d.path),
    }


def get_write_deps() -> tuple[Path, Any, Any]:
    """Return (engagement_root, registry, verifier). Registry spans both repos."""
    from src.common.artifact_verifier import ArtifactVerifier
    from src.common.artifact_verifier_registry import ArtifactRegistry
    with _state_lock:
        repo_root = _repo_root
        enterprise_root = _enterprise_root
    if repo_root is None:
        raise HTTPException(500, "Repository not initialized")
    roots: list[Path] = [repo_root]
    if enterprise_root is not None:
        roots.append(enterprise_root)
    registry = ArtifactRegistry(roots)
    return repo_root, registry, ArtifactVerifier(registry)


def get_admin_write_deps() -> tuple[Path, Any, Any]:
    """Return (enterprise_root, registry, verifier) for admin-mode writes.

    Raises 403 when admin mode is not enabled, 500 when enterprise root is
    not configured.  Registry spans both repos so cross-repo entity references
    in outgoing files validate correctly.
    """
    from src.common.artifact_verifier import ArtifactVerifier
    from src.common.artifact_verifier_registry import ArtifactRegistry
    with _state_lock:
        admin_mode = _admin_mode
        enterprise_root = _enterprise_root
        repo_root = _repo_root
    if not admin_mode:
        raise HTTPException(403, "Admin mode is not enabled")
    if enterprise_root is None:
        raise HTTPException(500, "Enterprise repository not configured")
    roots: list[Path] = [enterprise_root]
    if repo_root is not None:
        roots.append(repo_root)
    registry = ArtifactRegistry(roots)
    return enterprise_root, registry, ArtifactVerifier(registry)


def clear_caches(path: Path | list[Path]) -> None:
    with _state_lock:
        repo = _repo
    if repo is not None:
        changed_paths = path if isinstance(path, list) else [path]
        version = repo.apply_file_changes(changed_paths)
        roots = configured_roots()
        if roots:
            publish_authoritative_mutation(roots, changed_paths=changed_paths, version=version)


def refresh_now() -> None:
    with _state_lock:
        repo = _repo
    if repo is not None:
        repo.refresh()


def run_serialized_write(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    from src.tools.artifact_mcp.write_queue import run_sync
    from src.tools.write_block_manager import is_blocked

    # Check write-block state before passing to queue
    target_root = kwargs.get("repo_root") or (args[0] if args else None)
    if target_root is not None and is_blocked(Path(str(target_root))):
        raise HTTPException(503, "Writes are temporarily blocked (sync in progress or read-only mode)")

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
