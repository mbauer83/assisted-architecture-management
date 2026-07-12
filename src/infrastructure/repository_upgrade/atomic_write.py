"""Shared temp-file + rename primitive for repository-upgrade writes, so a crash mid-write never leaves a
half-written file — and one glob pattern can find every stray temp file, regardless of which
writer left it behind, for `sweep_stale_tmp_files` to clean up on the next `--commit`."""

from __future__ import annotations

import os
from pathlib import Path

_TMP_GLOB = "*.tmp-*"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def sweep_stale_tmp_files(repo_root: Path) -> list[str]:
    """Remove orphaned `write_atomic` temp files left by a process killed mid-write.

    Safe to call whenever no other upgrade process can be writing concurrently (i.e. after
    the backend-not-serving guard has passed) — a live writer's own in-progress temp file
    would only ever be visible here after that writer has already died.
    """
    removed: list[str] = []
    for tmp_path in repo_root.rglob(_TMP_GLOB):
        if tmp_path.is_file():
            tmp_path.unlink()
            removed.append(str(tmp_path.relative_to(repo_root)))
    return removed
