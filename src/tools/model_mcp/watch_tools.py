
import hashlib
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.model_mcp.context import RepoPreset, RepoScope, refresh_caches_for_repo, resolve_repo_roots


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------

def _repo_state_fingerprint(repo_path: Path) -> str:
    digest = hashlib.blake2b(digest_size=16)
    for sub in ("model", "diagram-catalog/diagrams"):
        root = repo_path / sub
        if not root.exists():
            continue
        for p in root.rglob("*"):
            try:
                if p.is_file():
                    st = p.stat()
                    rel = p.relative_to(repo_path).as_posix()
                    digest.update(rel.encode("utf-8"))
                    digest.update(str(int(st.st_mtime_ns)).encode("ascii"))
                    digest.update(str(int(st.st_size)).encode("ascii"))
            except OSError:
                continue
    return digest.hexdigest()


def _roots_state_fingerprint(roots: list[Path]) -> str:
    digest = hashlib.blake2b(digest_size=16)
    for root in roots:
        digest.update(str(root.resolve()).encode("utf-8"))
        digest.update(_repo_state_fingerprint(root).encode("ascii"))
    return digest.hexdigest()


def _roots_key(roots: list[Path]) -> str:
    return "|".join(str(p.resolve()) for p in roots)


# ---------------------------------------------------------------------------
# Refresh coordinator — deduplicates concurrent triggers (watcher, periodic, tool)
#
# Design: lock + pending Event per roots-key.
#   schedule_refresh()  — non-blocking; sets pending; starts bg thread if lock is free.
#   sync_refresh()      — blocking; waits for any in-progress refresh, then runs one more.
#
# Guarantee: at most one refresh worker runs at a time per roots-key.
# If a new trigger arrives while a refresh is in progress, the worker sees the
# pending flag after finishing and runs one additional pass — no pile-up.
# ---------------------------------------------------------------------------

@dataclass
class _RefreshCoord:
    lock: threading.Lock = field(default_factory=threading.Lock)
    pending: threading.Event = field(default_factory=threading.Event)


_refresh_coords: dict[str, _RefreshCoord] = {}
_refresh_mu = threading.Lock()


def _coord(roots: list[Path]) -> _RefreshCoord:
    key = _roots_key(roots)
    with _refresh_mu:
        if key not in _refresh_coords:
            _refresh_coords[key] = _RefreshCoord()
        return _refresh_coords[key]


def _do_refresh(roots: list[Path]) -> None:
    """Perform the actual cache clear + macro regeneration."""
    refresh_caches_for_repo(roots)
    try:
        from src.tools.generate_macros import generate_macros  # noqa: PLC0415
    except ImportError:
        return
    for root in roots:
        if (root / "model").is_dir():
            try:
                generate_macros(root)
            except Exception:  # noqa: BLE001
                pass


def _refresh_worker(roots: list[Path], coord: _RefreshCoord) -> None:
    """Background worker: drain pending refreshes; release lock when quiescent."""
    try:
        while True:
            coord.pending.clear()
            _do_refresh(roots)
            if not coord.pending.is_set():
                break
    except Exception:  # noqa: BLE001
        pass
    finally:
        coord.lock.release()


def schedule_refresh(roots: list[Path]) -> None:
    """Non-blocking: request one refresh. Deduplicates if one is already running."""
    c = _coord(roots)
    c.pending.set()
    if c.lock.acquire(blocking=False):
        t = threading.Thread(
            target=_refresh_worker,
            args=(roots, c),
            daemon=True,
            name=f"model-refresh:{_roots_key(roots)}",
        )
        t.start()
    # else: in-progress worker will see pending and do one more pass


def sync_refresh(roots: list[Path]) -> None:
    """Blocking: wait for any in-progress refresh, then run one synchronously."""
    c = _coord(roots)
    c.pending.set()
    c.lock.acquire()  # wait for any running worker
    try:
        c.pending.clear()
        _do_refresh(roots)
    finally:
        c.lock.release()


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
    last_fp = _roots_state_fingerprint(roots)
    last_periodic = time.monotonic()
    with _watch_lock:
        _watch_state[repo_key] = {
            "repo_roots": [str(r) for r in roots],
            "interval_s": interval_s,
            "periodic_refresh_s": periodic_refresh_s,
            "running": True,
            "last_fingerprint": last_fp,
            "last_refresh_time": None,
            "refresh_count": 0,
        }

    while not stop.is_set():
        time.sleep(interval_s)
        try:
            now = time.monotonic()
            fp = _roots_state_fingerprint(roots)
            force = (
                periodic_refresh_s is not None
                and (now - last_periodic) >= periodic_refresh_s
            )
            if fp != last_fp or force:
                schedule_refresh(roots)
                last_fp = fp
                if force:
                    last_periodic = now
                with _watch_lock:
                    st = _watch_state.get(repo_key, {})
                    st["last_fingerprint"] = fp
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
        fp = _roots_state_fingerprint(roots)
        _watch_state[repo_key] = {
            "repo_roots": [str(r) for r in roots],
            "interval_s": interval_s,
            "periodic_refresh_s": periodic_refresh_s,
            "running": True,
            "last_fingerprint": fp,
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
