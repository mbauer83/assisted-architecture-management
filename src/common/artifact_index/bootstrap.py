from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from src.common.artifact_types import RepoMount, infer_mount

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


def get_shared_index(factory: type["ArtifactIndex"], repo_root: Path | list[Path] | list[RepoMount]) -> "ArtifactIndex":
    mounts = normalize_mounts(repo_root)
    key = service_key(mounts)
    with _services_mu:
        service = _services.get(key)
        if service is None:
            service = factory(mounts)
            _services[key] = service
        return service
