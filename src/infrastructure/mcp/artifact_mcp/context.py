"""context.py — shared MCP server context for model query/verify/write tools.

Keeps mcp_model_server.py small by factoring out:
- repo root resolution
- cache keys and cached ArtifactRepository/ArtifactRegistry
- verifier construction and cache clearing

This module contains no FastMCP tool registrations.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from src.application.artifact_query import ArtifactRepository
from src.application.read_models import ReadModelVersion
from src.application.verification.artifact_verifier import ArtifactRegistry, ArtifactVerifier
from src.config.repo_paths import MODEL
from src.config.workspace_paths import resolve_workspace_repo_roots
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.artifact_index.coordination import (
    publish_authoritative_mutation,
    publish_background_refresh_completed,
    wait_for_write_queue_drain,
)

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
        raise RuntimeError("Could not resolve enterprise repo root. Run `arch-init` or provide arch-workspace.yaml.")
    return roots[1]


def repo_root_from_preset(preset: RepoPreset) -> Path:
    roots = _workspace_repo_roots()
    if roots is None:
        raise RuntimeError(
            "Could not resolve workspace repo roots for repo_preset. Run `arch-init` or provide arch-workspace.yaml."
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
        from src.infrastructure.gui.routers import state as gui_state
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
    # Operate directly on the shared index — the ArtifactRepository is a thin
    # wrapper and both would resolve to the same ArtifactIndex instance, so
    # calling through both used to trigger two full refreshes under the lock.
    index = shared_artifact_index(roots)
    index.refresh()
    registry_cached.cache_clear()
    return index.read_model_version()


def _apply_paths_now(roots: list[Path], paths: list[Path]) -> ReadModelVersion:
    index = shared_artifact_index(roots)
    version = index.apply_file_changes(paths)
    registry_cached.cache_clear()
    return version


def _regenerate_macros(roots: list[Path]) -> None:
    try:
        from src.infrastructure.rendering.generate_macros import generate_macros
    except Exception:  # noqa: BLE001
        return
    for root in roots:
        if (root / MODEL).is_dir():
            try:
                generate_macros(root)
            except Exception:  # noqa: BLE001
                pass


def _normalize_roots(root_or_roots: Path | list[Path]) -> list[Path]:
    roots = root_or_roots if isinstance(root_or_roots, list) else [root_or_roots]
    return [root.resolve() for root in roots]


def _infer_repo_roots_from_paths(paths: list[Path]) -> list[Path]:
    inferred: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        for candidate in (resolved, *resolved.parents):
            if (candidate / MODEL).is_dir():
                root = candidate.resolve()
                if root not in seen:
                    inferred.append(root)
                    seen.add(root)
                break
    return inferred


def apply_authoritative_changes(changed_paths: list[Path], repo_roots: list[Path]) -> ReadModelVersion | None:
    if not changed_paths:
        return None
    roots = _normalize_roots(repo_roots)
    paths = [path.resolve() for path in changed_paths]
    version = _apply_paths_now(roots, paths)
    publish_authoritative_mutation(roots, changed_paths=paths, version=version)
    return version


def enqueue_background_refresh(
    repo_roots: list[Path],
    *,
    changed_paths: list[Path] | None = None,
    full_refresh: bool,
) -> None:
    roots = _normalize_roots(repo_roots)
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


@dataclass
class AuthoritativeMutationContext:
    repo_roots: list[Path]
    changed_paths: set[Path] = field(default_factory=set)
    macro_roots: set[Path] = field(default_factory=set)

    def record_changed(self, path: Path) -> None:
        self.changed_paths.add(path.resolve())

    def mark_macros_dirty(self, repo_root: Path) -> None:
        self.macro_roots.add(repo_root.resolve())

    def finalize(self) -> ReadModelVersion | None:
        roots = _normalize_roots(self.repo_roots)
        if self.macro_roots:
            _regenerate_macros(sorted(self.macro_roots))
        if not self.changed_paths:
            return None
        return apply_authoritative_changes(sorted(self.changed_paths), roots)


def mutation_context_for(
    root_or_roots: Path | list[Path],
) -> AuthoritativeMutationContext:
    return AuthoritativeMutationContext(repo_roots=_normalize_roots(root_or_roots))


def authoritative_callbacks_for(
    root_or_roots: Path | list[Path],
) -> tuple[AuthoritativeMutationContext, Callable[[Path], None], Callable[[Path], None]]:
    context = mutation_context_for(root_or_roots)
    return context, context.record_changed, context.mark_macros_dirty


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
            publish_background_refresh_completed(roots, full_refresh=True, changed_paths=[], version=version)
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


def sync_refresh_for_roots(root_or_roots: Path | list[Path]) -> None:
    roots = _normalize_roots(root_or_roots)
    wait_for_write_queue_drain()
    version = _refresh_repo_now(roots)
    _regenerate_macros(roots)
    publish_background_refresh_completed(roots, full_refresh=True, changed_paths=[], version=version)


def refresh_caches_for_repo(root_or_roots: Path | list[Path]) -> None:
    sync_refresh_for_roots(root_or_roots)


def clear_caches_for_repo(root_or_roots: Path | list[Path]) -> None:
    paths = root_or_roots if isinstance(root_or_roots, list) else [root_or_roots]
    repo_roots = _infer_repo_roots_from_paths(paths)
    if not repo_roots:
        repo_roots = [path.resolve() for path in paths]
    apply_authoritative_changes(paths, repo_roots)


@dataclass(frozen=True)
class ResolvedRepo:
    roots: list[Path]

    @property
    def key(self) -> str:
        return roots_key(self.roots)

    @property
    def engagement_root(self) -> Path:
        return self.roots[0]
