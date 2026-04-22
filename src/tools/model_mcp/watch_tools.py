
import threading
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.model_mcp.context import (
    RepoPreset,
    RepoScope,
    enqueue_refresh_for_roots,
    resolve_repo_roots,
    sync_refresh_for_roots,
)
from src.common.model_index.coordination import suppress_redundant_refresh_paths


# ---------------------------------------------------------------------------
# Snapshotting
# ---------------------------------------------------------------------------

def _repo_state_snapshot(repo_path: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for sub in ("model", "diagram-catalog/diagrams"):
        root = repo_path / sub
        if not root.exists():
            continue
        for p in root.rglob("*"):
            try:
                if p.is_file():
                    st = p.stat()
                    rel = p.relative_to(repo_path).as_posix()
                    snapshot[rel] = (int(st.st_mtime_ns), int(st.st_size))
            except OSError:
                continue
    return snapshot


def _roots_state_snapshot(roots: list[Path]) -> dict[Path, dict[str, tuple[int, int]]]:
    return {root.resolve(): _repo_state_snapshot(root) for root in roots}


def _diff_snapshots(
    previous: dict[Path, dict[str, tuple[int, int]]],
    current: dict[Path, dict[str, tuple[int, int]]],
) -> tuple[list[Path], bool]:
    changed: list[Path] = []
    missing_roots = set(previous) ^ set(current)
    if missing_roots:
        return [], True
    for root, current_files in current.items():
        previous_files = previous.get(root, {})
        rels = set(previous_files) | set(current_files)
        for rel in rels:
            if previous_files.get(rel) != current_files.get(rel):
                changed.append(root / rel)
    return changed, False


def _roots_key(roots: list[Path]) -> str:
    return "|".join(str(p.resolve()) for p in roots)


# ---------------------------------------------------------------------------
# Refresh queue wrappers
# ---------------------------------------------------------------------------


def schedule_refresh(roots: list[Path]) -> None:
    enqueue_refresh_for_roots(roots, full_refresh=True)


def sync_refresh(roots: list[Path]) -> None:
    sync_refresh_for_roots(roots)


# ---------------------------------------------------------------------------
# Watcher
# ---------------------------------------------------------------------------

_watch_lock = threading.Lock()
_watch_threads: dict[str, threading.Thread] = {}
_watch_stop: dict[str, threading.Event] = {}
_watch_state: dict[str, dict[str, object]] = {}


def _watcher_loop(
    roots: list[Path],
    interval_s: float,
    stop: threading.Event,
    periodic_refresh_s: float | None = None,
) -> None:
    repo_key = _roots_key(roots)
    last_snapshot = _roots_state_snapshot(roots)
    last_periodic = time.monotonic()
    with _watch_lock:
        _watch_state[repo_key] = {
            "repo_roots": [str(r) for r in roots],
            "interval_s": interval_s,
            "periodic_refresh_s": periodic_refresh_s,
            "running": True,
            "last_fingerprint": f"{sum(len(files) for files in last_snapshot.values())} files",
            "last_refresh_time": None,
            "refresh_count": 0,
        }

    while not stop.is_set():
        time.sleep(interval_s)
        try:
            now = time.monotonic()
            snapshot = _roots_state_snapshot(roots)
            changed_paths, must_full_refresh = _diff_snapshots(last_snapshot, snapshot)
            if changed_paths and not must_full_refresh:
                changed_paths = suppress_redundant_refresh_paths(roots, changed_paths)
            force = (
                periodic_refresh_s is not None
                and (now - last_periodic) >= periodic_refresh_s
            )
            if changed_paths or force or must_full_refresh:
                if force or must_full_refresh or len(changed_paths) > 64:
                    enqueue_refresh_for_roots(roots, full_refresh=True)
                else:
                    enqueue_refresh_for_roots(roots, changed_paths=changed_paths)
                last_snapshot = snapshot
                if force:
                    last_periodic = now
                with _watch_lock:
                    st = _watch_state.get(repo_key, {})
                    st["last_fingerprint"] = f"{sum(len(files) for files in snapshot.values())} files"
                    st["last_refresh_time"] = time.time()
                    prev = st.get("refresh_count", 0)
                    st["refresh_count"] = (prev + 1) if isinstance(prev, int) else 1
                    _watch_state[repo_key] = st
        except Exception:  # noqa: BLE001
            pass  # Transient OS/lock errors must not kill the watcher thread

    with _watch_lock:
        st = _watch_state.get(repo_key, {})
        st["running"] = False
        _watch_state[repo_key] = st


def _start_watcher(
    roots: list[Path],
    *,
    interval_s: float,
    periodic_refresh_s: float | None = None,
) -> dict[str, Any]:
    repo_key = _roots_key(roots)
    with _watch_lock:
        if repo_key in _watch_threads and _watch_threads[repo_key].is_alive():
            return {"repo_roots": [str(r) for r in roots], "started": False, "reason": "already_running"}
        snapshot = _roots_state_snapshot(roots)
        _watch_state[repo_key] = {
            "repo_roots": [str(r) for r in roots],
            "interval_s": interval_s,
            "periodic_refresh_s": periodic_refresh_s,
            "running": True,
            "last_fingerprint": f"{sum(len(files) for files in snapshot.values())} files",
            "last_refresh_time": None,
            "refresh_count": 0,
        }
        stop = threading.Event()
        t = threading.Thread(
            target=_watcher_loop,
            args=(roots, interval_s, stop, periodic_refresh_s),
            daemon=True,
            name=f"model-repo-watch:{repo_key}",
        )
        _watch_stop[repo_key] = stop
        _watch_threads[repo_key] = t
        t.start()
        state = dict(_watch_state.get(repo_key, {}))
    return {"repo_roots": [str(r) for r in roots], "started": True, "state": state}


def auto_start_default_watcher(
    *,
    interval_s: float = 2.0,
    periodic_refresh_s: float | None = 300.0,
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    enterprise_root: str | None = None,
    repo_scope: RepoScope = "both",
) -> dict[str, Any]:
    roots = resolve_repo_roots(
        repo_scope=repo_scope,
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=enterprise_root,
    )
    return _start_watcher(roots, interval_s=interval_s, periodic_refresh_s=periodic_refresh_s)


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------

def register_watch_tools(mcp: FastMCP) -> None:
    """Register watcher lifecycle tools on *mcp*.

    Called by the standalone arch-mcp-watch server.  Not registered on the
    main arch-mcp-model server — that server auto-starts the watcher at
    startup without exposing lifecycle tools to agents.
    """
    from typing import Literal

    @mcp.tool(
        name="model_tools_watch",
        title="Model Tools: Watch Lifecycle",
        description=(
            "Control the file-system watcher that auto-refreshes model caches. "
            "action='start' — begin polling (interval_s default 2 s, periodic refresh default 300 s); "
            "action='stop' — stop the watcher; "
            "action='status' — return current watcher state."
            "\n\nThe main model server starts the watcher automatically at startup; "
            "use this tool only when you need explicit lifecycle control."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        structured_output=True,
    )
    def model_tools_watch(
        action: Literal["start", "stop", "status"],
        *,
        interval_s: float = 2.0,
        periodic_refresh_s: float | None = 300.0,
        repo_root: str | None = None,
        repo_preset: RepoPreset | None = None,
        enterprise_root: str | None = None,
        repo_scope: RepoScope = "both",
    ) -> dict[str, object]:
        roots = resolve_repo_roots(
            repo_scope=repo_scope,
            repo_root=repo_root,
            repo_preset=repo_preset,
            enterprise_root=enterprise_root,
        )
        repo_key = _roots_key(roots)
        if action == "start":
            return _start_watcher(roots, interval_s=interval_s, periodic_refresh_s=periodic_refresh_s)
        if action == "stop":
            with _watch_lock:
                stop = _watch_stop.get(repo_key)
                t = _watch_threads.get(repo_key)
            if stop is None or t is None:
                return {"repo_roots": [str(r) for r in roots], "stopped": False, "reason": "not_running"}
            stop.set()
            t.join(timeout=1.0)
            with _watch_lock:
                running = bool(t.is_alive())
                st = dict(_watch_state.get(repo_key, {}))
                st["running"] = running
                _watch_state[repo_key] = st
            return {"repo_roots": [str(r) for r in roots], "stopped": True, "running": running}
        # status
        with _watch_lock:
            thread = _watch_threads.get(repo_key)
            state = dict(_watch_state.get(repo_key, {}))
        return {
            "repo_roots": [str(r) for r in roots],
            "running": bool(thread and thread.is_alive()),
            "state": state,
        }

    @mcp.tool(
        name="model_tools_refresh",
        title="Model Tools: Refresh Index",
        description=(
            "Force a synchronous re-scan and cache refresh for the selected repository. "
            "Use this after writing entity/connection/diagram files outside the MCP tools, "
            "or when the auto-watcher has not yet picked up recent changes."
            "\n\nRepo selection: repo_scope defaults to both (engagement + enterprise)."
        ),
        structured_output=True,
    )
    def model_tools_refresh(
        *,
        repo_root: str | None = None,
        repo_preset: RepoPreset | None = None,
        enterprise_root: str | None = None,
        repo_scope: RepoScope = "both",
    ) -> dict[str, object]:
        roots = resolve_repo_roots(
            repo_scope=repo_scope,
            repo_root=repo_root,
            repo_preset=repo_preset,
            enterprise_root=enterprise_root,
        )
        sync_refresh(roots)
        return {"repo_roots": [str(p) for p in roots], "repo_scope": repo_scope, "refreshed": True}
