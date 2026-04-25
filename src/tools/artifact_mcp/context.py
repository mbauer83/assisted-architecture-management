"""context.py — shared MCP server context for model query/verify/write tools.

Keeps mcp_model_server.py small by factoring out:
- repo root resolution
- cache keys and cached ArtifactRepository/ArtifactRegistry
- verifier construction and cache clearing

This module contains no FastMCP tool registrations.
"""

import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from src.common.artifact_query import ArtifactRepository, shared_artifact_index
from src.common.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.common.repo_paths import MODEL
from src.common.workspace_paths import resolve_workspace_repo_roots
from src.infrastructure.artifact_index.coordination import (
    publish_background_refresh_completed,
    wait_for_write_queue_drain,
)
from src.infrastructure.artifact_index.versioning import ReadModelVersion

RepoPreset = Literal[
    "engagement",
    "enterprise",
]

RepoScope = Literal["engagement", "enterprise", "both"]


def workspace_root() -> Path:
    # .../src/tools/model_mcp/context.py -> parents[0]=model_mcp, [1]=tools, [2]=src, [3]=repo root
    return Path(__file__).resolve().parents[3]


def _workspace_repo_roots() -> tuple[Path, Path] | None:
    return resolve_workspace_repo_roots(workspace_root())


def default_engagement_repo_root() -> Path:
    import os

    env = os.getenv("ARCH_MCP_MODEL_REPO_ROOT")
    if env:
        return Path(env).expanduser()
    roots = _workspace_repo_roots()
    if roots is None:
        raise RuntimeError(
            "Could not resolve engagement repo root. "
            "Run `arch-init` or provide arch-workspace.yaml / ARCH_MCP_MODEL_REPO_ROOT."
        )
    return roots[0]


def default_enterprise_repo_root() -> Path:
    roots = _workspace_repo_roots()
    if roots is None:
        raise RuntimeError(
            "Could not resolve enterprise repo root. "
            "Run `arch-init` or provide arch-workspace.yaml."
        )
    return roots[1]


def repo_root_from_preset(preset: RepoPreset) -> Path:
    roots = _workspace_repo_roots()
    if roots is None:
        raise RuntimeError(
            "Could not resolve workspace repo roots for repo_preset. "
            "Run `arch-init` or provide arch-workspace.yaml."
        )
    match preset:
        case "engagement":
            return roots[0]
        case "enterprise":
            return roots[1]


def resolve_repo_root(*, repo_root: str | None, repo_preset: RepoPreset | None) -> Path:
    if repo_root:
        p = Path(repo_root).expanduser()
        if not p.is_absolute():
            p = workspace_root() / p
        return p
    if repo_preset:
        return repo_root_from_preset(repo_preset)
    p = default_engagement_repo_root()
    if not p.is_absolute():
        p = workspace_root() / p
    return p


def resolve_enterprise_repo_root(*, enterprise_root: str | None) -> Path:
    if enterprise_root:
        p = Path(enterprise_root).expanduser()
        if not p.is_absolute():
            p = workspace_root() / p
        return p
    return default_enterprise_repo_root()


def resolve_repo_roots(
    *,
    repo_scope: RepoScope,
    repo_root: str | None,
    repo_preset: RepoPreset | None,
    enterprise_root: str | None,
) -> list[Path]:
    engagement = resolve_repo_root(repo_root=repo_root, repo_preset=repo_preset)
    enterprise = resolve_enterprise_repo_root(enterprise_root=enterprise_root)
    roots: list[Path] = []
    if repo_scope in ("engagement", "both"):
        roots.append(engagement)
    if repo_scope in ("enterprise", "both"):
        roots.append(enterprise)
    return roots


def roots_key(roots: list[Path]) -> str:
    return "|".join(str(p.resolve()) for p in roots)


def _shared_state_repo_for_roots(roots: list[Path]) -> ArtifactRepository | None:
    try:
        from src.tools.gui_routers import state as gui_state
    except Exception:  # noqa: BLE001
        return None

    repo = gui_state.maybe_get_repo()
    if repo is None:
        return None
    configured = gui_state.configured_roots()
    wanted = [p.resolve() for p in roots]
    if configured == wanted:
        return repo
    return None


@lru_cache(maxsize=8)
def repo_cached(roots_key_str: str) -> ArtifactRepository:
    roots = [Path(p) for p in roots_key_str.split("|") if p]
    shared = _shared_state_repo_for_roots(roots)
    if shared is not None:
        return shared
    return ArtifactRepository(shared_artifact_index(roots))


@lru_cache(maxsize=8)
def registry_cached(roots_key_str: str) -> ArtifactRegistry:
    roots = [Path(p) for p in roots_key_str.split("|") if p]
    return ArtifactRegistry(shared_artifact_index(roots))


def verifier_for(roots_key_str: str, *, include_registry: bool) -> ArtifactVerifier:
    if include_registry:
        return ArtifactVerifier(registry_cached(roots_key_str))
    return ArtifactVerifier(None)


def _refresh_repo_now(roots: list[Path]) -> ReadModelVersion:
    from src.infrastructure.artifact_index import shared_artifact_index
    key = roots_key(roots)
    shared = _shared_state_repo_for_roots(roots)
    if shared is not None:
        shared.refresh()
        version = shared.read_model_version()
    else:
        repo = repo_cached(key)
        repo.refresh()
        version = repo.read_model_version()
    shared_artifact_index(roots).refresh()
    registry_cached.cache_clear()
    return version


def _apply_paths_now(roots: list[Path], paths: list[Path]) -> ReadModelVersion:
    from src.infrastructure.artifact_index import shared_artifact_index
    key = roots_key(roots)
    shared = _shared_state_repo_for_roots(roots)
    repo = shared if shared is not None else repo_cached(key)
    version = repo.apply_file_changes(paths)
    shared_artifact_index(roots).apply_file_changes(paths)
    registry_cached.cache_clear()
    return version


def _regenerate_macros(roots: list[Path]) -> None:
    try:
        from src.tools.generate_macros import generate_macros
    except Exception:  # noqa: BLE001
        return
    for root in roots:
        if (root / MODEL).is_dir():
            try:
                generate_macros(root)
            except Exception:  # noqa: BLE001
                pass


@dataclass
class _RefreshQueue:
    cond: threading.Condition
    pending_full: bool = False
    pending_paths: set[Path] | None = None
    next_due_monotonic: float = 0.0
    worker: threading.Thread | None = None


_queues: dict[str, _RefreshQueue] = {}
_queues_mu = threading.Lock()
_REFRESH_DEBOUNCE_S = 0.20


def _queue_for(roots: list[Path]) -> _RefreshQueue:
    key = roots_key(roots)
    with _queues_mu:
        queue = _queues.get(key)
        if queue is None:
            queue = _RefreshQueue(cond=threading.Condition(), pending_paths=set())
            _queues[key] = queue
        return queue


def _refresh_worker(roots: list[Path], queue: _RefreshQueue) -> None:
    while True:
        with queue.cond:
            while not queue.pending_full and not queue.pending_paths:
                queue.worker = None
                return
            delay = max(0.0, queue.next_due_monotonic - time.monotonic())
            if delay > 0:
                queue.cond.wait(timeout=delay)
                continue
            pending_full = queue.pending_full
            pending_paths = sorted(queue.pending_paths or [])
            queue.pending_full = False
            queue.pending_paths = set()
        wait_for_write_queue_drain()
        if pending_full:
            version = _refresh_repo_now(roots)
            publish_background_refresh_completed(
                roots, full_refresh=True, changed_paths=[], version=version
            )
            _regenerate_macros(roots)
            continue
        if pending_paths:
            version = _apply_paths_now(roots, pending_paths)
            publish_background_refresh_completed(
                roots,
                full_refresh=False,
                changed_paths=pending_paths,
                version=version,
            )
            _regenerate_macros(roots)


def enqueue_refresh_for_roots(
    root_or_roots: Path | list[Path],
    *,
    changed_paths: list[Path] | None = None,
    full_refresh: bool = False,
) -> None:
    roots = root_or_roots if isinstance(root_or_roots, list) else [root_or_roots]
    queue = _queue_for(roots)
    with queue.cond:
        if full_refresh:
            queue.pending_full = True
            queue.pending_paths = set()
        elif changed_paths:
            if queue.pending_paths is None:
                queue.pending_paths = set()
            queue.pending_paths.update(path.resolve() for path in changed_paths)
        queue.next_due_monotonic = time.monotonic() + _REFRESH_DEBOUNCE_S
        if queue.worker is None or not queue.worker.is_alive():
            queue.worker = threading.Thread(
                target=_refresh_worker,
                args=(roots, queue),
                daemon=True,
                name=f"model-refresh:{roots_key(roots)}",
            )
            queue.worker.start()
        queue.cond.notify_all()


def sync_refresh_for_roots(root_or_roots: Path | list[Path]) -> None:
    roots = root_or_roots if isinstance(root_or_roots, list) else [root_or_roots]
    wait_for_write_queue_drain()
    version = _refresh_repo_now(roots)
    _regenerate_macros(roots)
    publish_background_refresh_completed(
        roots, full_refresh=True, changed_paths=[], version=version
    )


def refresh_caches_for_repo(root_or_roots: Path | list[Path]) -> None:
    sync_refresh_for_roots(root_or_roots)


def clear_caches_for_repo(root_or_roots: Path | list[Path]) -> None:
    from src.infrastructure.artifact_index import notify_paths_changed
    paths = root_or_roots if isinstance(root_or_roots, list) else [root_or_roots]
    notify_paths_changed(paths)
    enqueue_refresh_for_roots(root_or_roots, full_refresh=True)


@dataclass(frozen=True)
class ResolvedRepo:
    roots: list[Path]

    @property
    def key(self) -> str:
        return roots_key(self.roots)

    @property
    def engagement_root(self) -> Path:
        return self.roots[0]
