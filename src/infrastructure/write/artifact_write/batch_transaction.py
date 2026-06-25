from __future__ import annotations

import filecmp
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.config.repo_paths import DIAGRAM_CATALOG, DOCS, MODEL

from .m4_transaction import (
    ChangeKind,
    GitRefTransition,
    ManifestEntry,
    TransactionManifest,
    fsync_directory,
    hash_file,
    publish_transaction,
    write_transaction_intent,
)

_MANAGED_SUBTREES = (MODEL, DOCS, DIAGRAM_CATALOG)
_TRANSACTIONS = Path(".arch-repo") / "transactions"


@dataclass(frozen=True)
class BatchCommitResult:
    changed_paths: list[Path]
    deleted_paths: list[Path]


@dataclass(frozen=True)
class StagingDirectory:
    path: Path

    def cleanup(self) -> None:
        if (self.path / "intent").exists():
            return
        shutil.rmtree(self.path, ignore_errors=True)
        fsync_directory(self.path.parent)


def create_staging_repo(
    repo_root: Path,
    *,
    on_boundary: Callable[[str], None] | None = None,
) -> tuple[StagingDirectory, Path]:
    transactions = repo_root / _TRANSACTIONS
    transactions.mkdir(parents=True, exist_ok=True)
    fsync_directory(transactions.parent)
    transaction_dir = transactions / uuid.uuid4().hex
    transaction_dir.mkdir()
    fsync_directory(transactions)
    if on_boundary is not None:
        on_boundary("transaction_dir_created")

    staged_root = transaction_dir / "staged"
    shutil.copytree(repo_root, staged_root, ignore=_ignore_transaction_storage)
    return StagingDirectory(transaction_dir), staged_root


def commit_staged_repo(
    *,
    live_root: Path,
    staged_root: Path,
    rebuild_index: Callable[[BatchCommitResult], object],
    ref_transition: GitRefTransition | None = None,
    on_boundary: Callable[[str], None] | None = None,
) -> BatchCommitResult:
    transaction_dir = staged_root.parent
    entries, result = _derive_manifest(live_root=live_root, staged_root=staged_root)
    manifest = TransactionManifest(entries=entries, ref=ref_transition)
    write_transaction_intent(
        repo_root=live_root,
        transaction_dir=transaction_dir,
        staged_root=staged_root,
        manifest=manifest,
        on_boundary=on_boundary,
    )
    publish_transaction(
        repo_root=live_root,
        transaction_dir=transaction_dir,
        manifest=manifest,
        rebuild_index=lambda: rebuild_index(result),
        on_boundary=on_boundary,
    )
    return result


def _derive_manifest(
    *,
    live_root: Path,
    staged_root: Path,
) -> tuple[list[ManifestEntry], BatchCommitResult]:
    live_files = _managed_files(live_root)
    staged_files = _managed_files(staged_root)
    entries: list[ManifestEntry] = []
    changed_paths: list[Path] = []
    deleted_paths: list[Path] = []

    for relpath in sorted(staged_files):
        staged_path = staged_root / relpath
        live_path = live_root / relpath
        if relpath in live_files and filecmp.cmp(live_path, staged_path, shallow=False):
            continue
        prior = hash_file(live_path) if live_path.exists() else "absent"
        kind: ChangeKind = "replace" if live_path.exists() else "create"
        entries.append(
            ManifestEntry(
                kind=kind,
                dest=relpath.as_posix(),
                target_hash=hash_file(staged_path),
                prior_hash_or_absent=prior,
                payload=f"payloads/{len(entries):06d}",
            )
        )
        changed_paths.append(live_path)

    for relpath in sorted(live_files - staged_files):
        live_path = live_root / relpath
        entries.append(
            ManifestEntry(
                kind="delete",
                dest=relpath.as_posix(),
                target_hash="absent",
                prior_hash_or_absent=hash_file(live_path),
                payload=None,
            )
        )
        deleted_paths.append(live_path)

    return entries, BatchCommitResult(changed_paths=changed_paths, deleted_paths=deleted_paths)


def _managed_files(repo_root: Path) -> set[Path]:
    files: set[Path] = set()
    for subtree in _MANAGED_SUBTREES:
        root = repo_root / subtree
        if not root.exists():
            continue
        files.update(path.relative_to(repo_root) for path in root.rglob("*") if path.is_file())
    return files


def _ignore_transaction_storage(directory: str, names: list[str]) -> set[str]:
    path = Path(directory)
    if path.name == ".arch-repo":
        return {"transactions"} & set(names)
    return set()
