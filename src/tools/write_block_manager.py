"""Thread-safe per-repo write block manager."""

import threading
from pathlib import Path


_lock = threading.Lock()
_blocked: set[str] = set()


def _key(repo_root: Path) -> str:
    return str(repo_root.resolve())


def block_repo(repo_root: Path) -> None:
    """Block writes to a repository."""
    with _lock:
        _blocked.add(_key(repo_root))


def unblock_repo(repo_root: Path) -> None:
    """Unblock writes to a repository."""
    with _lock:
        _blocked.discard(_key(repo_root))


def is_blocked(repo_root: Path) -> bool:
    """Check whether writes to a repository are blocked."""
    with _lock:
        return _key(repo_root) in _blocked
