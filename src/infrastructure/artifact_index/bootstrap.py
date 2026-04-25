from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from src.domain.artifact_types import RepoMount, infer_mount

if TYPE_CHECKING:
    from .service import ArtifactIndex


def normalize_mounts(repo_root: Path | list[Path] | list[RepoMount]) -> list[RepoMount]:
    if isinstance(repo_root, Path):
        mounts: list[RepoMount] = [infer_mount(repo_root)]
    else:
        mounts = [m if isinstance(m, RepoMount) else infer_mount(m) for m in repo_root]
    roots = [m.root for m in mounts]
    if len(set(map(str, roots))) != len(roots):
        raise ValueError("Duplicate repo root in ArtifactIndex mounts")
    return mounts


def service_key(mounts: list[RepoMount]) -> str:
    return "|".join(str(m.root.resolve()) for m in mounts)


_services: dict[str, "ArtifactIndex"] = {}
_services_mu = threading.Lock()


def get_shared_index(
    factory: type["ArtifactIndex"], repo_root: Path | list[Path] | list[RepoMount]
) -> "ArtifactIndex":
    mounts = normalize_mounts(repo_root)
    key = service_key(mounts)
    with _services_mu:
        service = _services.get(key)
        if service is None:
            service = factory(mounts)
            _services[key] = service
        return service


def notify_paths_changed(paths: list[Path]) -> None:
    """Notify all loaded indexes of changed paths for incremental re-indexing.

    Called synchronously by write operations so the index is immediately consistent
    without waiting for the background refresh queue.
    """
    resolved = [p.resolve() for p in paths]
    with _services_mu:
        active = list(_services.values())
    for idx in active:
        roots = [m.root.resolve() for m in idx.repo_mounts]
        relevant = [
            p for p in resolved if any(p == r or str(p).startswith(str(r) + "/") for r in roots)
        ]
        if relevant:
            idx.apply_file_changes(relevant)
