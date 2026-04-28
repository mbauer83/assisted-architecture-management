from __future__ import annotations

import filecmp
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.config.repo_paths import DIAGRAM_CATALOG, DOCS, MODEL

_MANAGED_SUBTREES = (MODEL, DOCS, DIAGRAM_CATALOG)


@dataclass(frozen=True)
class BatchCommitResult:
    changed_paths: list[Path]
    deleted_paths: list[Path]


def create_staging_repo(repo_root: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    staging_dir = tempfile.TemporaryDirectory(prefix="artifact-batch-", dir="/tmp")
    staged_root = Path(staging_dir.name) / repo_root.name
    shutil.copytree(repo_root, staged_root, dirs_exist_ok=True)
    return staging_dir, staged_root


def commit_staged_repo(*, live_root: Path, staged_root: Path) -> BatchCommitResult:
    changed_paths: list[Path] = []
    deleted_paths: list[Path] = []

    live_files = _managed_files(live_root)
    staged_files = _managed_files(staged_root)

    for relpath in sorted(staged_files):
        staged_path = staged_root / relpath
        live_path = live_root / relpath
        if relpath in live_files and filecmp.cmp(live_path, staged_path, shallow=False):
            continue
        live_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_path, live_path)
        changed_paths.append(live_path)

    for relpath in sorted(live_files - staged_files):
        live_path = live_root / relpath
        if live_path.exists():
            live_path.unlink()
            deleted_paths.append(live_path)

    return BatchCommitResult(changed_paths=changed_paths, deleted_paths=deleted_paths)


def _managed_files(repo_root: Path) -> set[Path]:
    files: set[Path] = set()
    for subtree in _MANAGED_SUBTREES:
        root = repo_root / subtree
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                files.add(path.relative_to(repo_root))
    return files
