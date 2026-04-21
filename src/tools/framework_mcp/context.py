
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from src.common.framework_query import (
    FrameworkKnowledgeIndex,
    _DEFAULT_SCAN_PATHS,
    iter_doc_paths,
)


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_framework_root() -> Path:
    env_root = os.getenv("ARCH_MCP_FRAMEWORK_DOC_ROOT", "")
    if env_root:
        path = Path(env_root).expanduser()
        if not path.is_absolute():
            path = workspace_root() / path
        return path
    return workspace_root()


def resolve_framework_root(*, root: str | None) -> Path:
    if root:
        path = Path(root).expanduser()
        if not path.is_absolute():
            path = workspace_root() / path
        return path
    return default_framework_root()


def _configured_scan_paths() -> list[str]:
    """Read ARCH_MCP_FRAMEWORK_SCAN_DIRS (colon-separated); fall back to defaults."""
    raw = os.getenv("ARCH_MCP_FRAMEWORK_SCAN_DIRS", "").strip()
    if raw:
        return [entry.strip() for entry in raw.split(":") if entry.strip()]
    return list(_DEFAULT_SCAN_PATHS)


def _iter_doc_paths(root: Path) -> list[Path]:
    return iter_doc_paths(root, _configured_scan_paths())


def _mtime_fingerprint(root: Path) -> float:
    latest = 0.0
    for path in _iter_doc_paths(root):
        try:
            latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest


def _ttl_ms() -> int:
    raw = os.getenv("ARCH_MCP_FRAMEWORK_INDEX_TTL_MS", "1500")
    try:
        return max(int(raw), 100)
    except ValueError:
        return 1500


def _poll_interval_s() -> float:
    raw = os.getenv("ARCH_MCP_FRAMEWORK_INDEX_POLL_S", "1.0")
    try:
        return max(float(raw), 0.25)
    except ValueError:
        return 1.0


@dataclass
class _FrameworkIndexHandle:
    index: FrameworkKnowledgeIndex
    root: Path
    scan_paths: list[str]
    lock: threading.Lock
    fingerprint: float
    last_refresh_s: float
    refresh_count: int


_handles_lock = threading.Lock()
_handles: dict[str, _FrameworkIndexHandle] = {}
_pollers: dict[str, threading.Thread] = {}
_stop_events: dict[str, threading.Event] = {}


def _handle_key(root: Path, scan_paths: list[str]) -> str:
    return f"{root.resolve()}||{':'.join(scan_paths)}"


def _watcher_loop(handle_key: str) -> None:
    while True:
        with _handles_lock:
            stop = _stop_events.get(handle_key)
            handle = _handles.get(handle_key)
        if stop is None or handle is None:
            return
        if stop.wait(timeout=_poll_interval_s()):
            return
        fp = _mtime_fingerprint(handle.root)
        if fp <= handle.fingerprint:
            continue
        with handle.lock:
            # Double-check fingerprint inside lock to avoid duplicate refresh.
            current = _mtime_fingerprint(handle.root)
            if current <= handle.fingerprint:
                continue
            handle.index.refresh()
            handle.fingerprint = current
            handle.last_refresh_s = time.time()
            handle.refresh_count += 1


def _ensure_handle(root: Path) -> _FrameworkIndexHandle:
    scan_paths = _configured_scan_paths()
    hkey = _handle_key(root, scan_paths)
    with _handles_lock:
        existing = _handles.get(hkey)
        if existing is not None:
            return existing

        now = time.time()
        fp = _mtime_fingerprint(root)
        handle = _FrameworkIndexHandle(
            index=FrameworkKnowledgeIndex(root, scan_paths),
            root=root,
            scan_paths=scan_paths,
            lock=threading.Lock(),
            fingerprint=fp,
            last_refresh_s=now,
            refresh_count=1,
        )
        _handles[hkey] = handle

        stop = threading.Event()
        _stop_events[hkey] = stop
        thread = threading.Thread(
            target=_watcher_loop,
            args=(hkey,),
            daemon=True,
            name=f"framework-index-watch:{hkey}",
        )
        _pollers[hkey] = thread
        thread.start()
        return handle


def framework_index_cached(root: str) -> FrameworkKnowledgeIndex:
    return _ensure_handle(Path(root)).index


def framework_index_with_freshness(
    root: Path,
    *,
    force_refresh: bool = False,
) -> tuple[FrameworkKnowledgeIndex, dict[str, object]]:
    handle = _ensure_handle(root)
    now = time.time()
    stale_detected = False
    auto_refreshed = False
    root_fp = _mtime_fingerprint(root)
    age_ms = int((now - handle.last_refresh_s) * 1000)
    stale_by_ttl = age_ms > _ttl_ms()
    stale_by_fs = root_fp > handle.fingerprint

    if force_refresh or stale_by_ttl or stale_by_fs:
        stale_detected = not force_refresh
        with handle.lock:
            latest_fp = _mtime_fingerprint(root)
            latest_age_ms = int((time.time() - handle.last_refresh_s) * 1000)
            latest_stale = latest_fp > handle.fingerprint or latest_age_ms > _ttl_ms()
            if force_refresh or latest_stale:
                handle.index.refresh()
                handle.fingerprint = latest_fp
                handle.last_refresh_s = time.time()
                handle.refresh_count += 1
                auto_refreshed = not force_refresh

    freshness: dict[str, object] = {
        "index_version": handle.refresh_count,
        "last_refresh_at": handle.last_refresh_s,
        "index_age_ms": int((time.time() - handle.last_refresh_s) * 1000),
        "stale_detected": stale_detected,
        "auto_refreshed": auto_refreshed,
    }
    return handle.index, freshness


def clear_framework_cache() -> None:
    with _handles_lock:
        for stop in _stop_events.values():
            stop.set()
        for thread in _pollers.values():
            thread.join(timeout=0.5)
        _handles.clear()
        _pollers.clear()
        _stop_events.clear()
