"""Unified FastAPI + MCP backend entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import uvicorn
from mcp.server.fastmcp.server import StreamableHTTPASGIApp

from src.common.artifact_query import ArtifactRepository
from src.common.settings import backend_min_log_level
from src.tools import gui_server
from src.tools.backend_runtime import (
    backend_log_path,
    backend_status,
    probe_backend,
    read_backend_state,
    remove_backend_state,
    resolve_backend_port,
    stop_backend,
    write_backend_state,
)
from src.tools.gui_routers import state as gui_state
from src.tools.mcp_artifact_server import mcp_read, mcp_write
from src.tools.artifact_mcp import auto_start_default_watcher

logger = logging.getLogger(__name__)
_REQUEST_WATCHDOG_S = 5.0


def _print_stopped(result: dict) -> None:
    pids = result.get("pids")
    if isinstance(pids, list) and len(pids) > 1:
        print(f"stopped backend pids {', '.join(str(p) for p in pids)}")
    else:
        print(f"stopped backend pid {result.get('pid')}")


def _confirm_stop_other_instance(*, expected_port: int, pid: int, actual_port: object) -> bool:
    prompt = (
        f"Configured backend port is {expected_port}, but found one arch-backend instance "
        f"on port {actual_port} (pid {pid}). Stop it? [y/N] "
    )
    if not sys.stdin.isatty():
        print(
            f"found one arch-backend instance on port {actual_port} (pid {pid}), "
            f"but the configured port is {expected_port}; rerun interactively or pass --port {actual_port}"
        )
        return False
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _is_background_tty_job() -> bool:
    try:
        return sys.stderr.isatty() and os.tcgetpgrp(sys.stderr.fileno()) != os.getpgrp()
    except OSError:
        return False


def _redirect_stdio_to_backend_log(*, start: Path | None = None) -> Path:
    log_path = backend_log_path(start)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    null_fd = os.open(os.devnull, os.O_RDONLY)
    try:
        os.dup2(null_fd, sys.stdin.fileno())
        os.dup2(log_fd, sys.stdout.fileno())
        os.dup2(log_fd, sys.stderr.fileno())
    finally:
        if log_fd > 2:
            os.close(log_fd)
        if null_fd > 2:
            os.close(null_fd)
    return log_path


def _log_thread_dump(*, reason: str) -> None:
    frames = sys._current_frames()
    threads = {thread.ident: thread for thread in threading.enumerate()}
    lines = [f"=== thread dump: {reason} ==="]
    for ident, frame in frames.items():
        thread = threads.get(ident)
        name = thread.name if thread is not None else "unknown"
        lines.append(f"--- thread ident={ident} name={name} ---")
        lines.extend(line.rstrip("\n") for line in traceback.format_stack(frame))
    logger.warning("\n".join(lines))


def _status_detail_lines(result: dict[str, object]) -> list[str]:
    lines: list[str] = []
    if result.get("process_state"):
        lines.append(f"process state: {result.get('process_state')}")
    stdio = [
        f"stdin={result.get('stdin')}" if result.get("stdin") is not None else None,
        f"stdout={result.get('stdout')}" if result.get("stdout") is not None else None,
        f"stderr={result.get('stderr')}" if result.get("stderr") is not None else None,
    ]
    stdio_text = " ".join(part for part in stdio if part)
    if stdio_text:
        lines.append(f"stdio: {stdio_text}")
    if result.get("log_path"):
        lines.append(f"log: {result.get('log_path')}")
    return lines


def _print_status_details(result: dict[str, object]) -> None:
    for line in _status_detail_lines(result):
        print(f"  {line}")


def _daemon_argv(argv: list[str] | None) -> list[str]:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    # Strip lifecycle control flags — the daemon should just start, not stop-then-start again.
    return [arg for arg in raw_args if arg not in ("--daemon", "--restart", "--stop")]


def _start_daemon(*, argv: list[str] | None, log_path: Path) -> int:
    command = [sys.argv[0], *_daemon_argv(argv)]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=str(Path.cwd()),
        )
    return int(proc.pid)


def _find_git_repos() -> "list[RepoSpec]":
    """Return git-backed repos from arch-workspace.yaml, tagged with their role."""
    from src.common.workspace_paths import find_workspace_config, parse_workspace_config
    from src.tools.git_sync import RepoSpec

    cfg = find_workspace_config(Path.cwd())
    if cfg is None:
        return []
    workspace_root = cfg.parent
    config = parse_workspace_config(cfg)
    repos = []
    for key in ("engagement", "enterprise"):
        spec = config.get(key, {})
        if "git" in spec:
            git_spec = spec["git"]
            rel = git_spec.get("path", f"./{key}-repository")
            repos.append(RepoSpec(
                path=(workspace_root / rel).resolve(),
                role=key,  # type: ignore[arg-type]
            ))
    return repos


def _build_app(git_ssh_passphrase: str | None = None):  # type: ignore[no-untyped-def]
    from fastapi import FastAPI
    from fastapi import Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from src.tools.gui_routers.admin import router as admin_router
    from src.tools.gui_routers.connections import router as connections_router
    from src.tools.gui_routers.diagrams import router as diagrams_router
    from src.tools.gui_routers.documents import router as documents_router
    from src.tools.gui_routers.entities import router as entities_router
    from src.tools.gui_routers.events import router as events_router
    from src.tools.gui_routers.promote import router as promote_router
    from src.tools.gui_routers.sync import router as sync_router

    mcp_read.streamable_http_app()
    mcp_write.streamable_http_app()

    read_app = StreamableHTTPASGIApp(mcp_read.session_manager)
    write_app = StreamableHTTPASGIApp(mcp_write.session_manager)

    async def _on_repo_changed(repo_path: Path) -> None:
        """Refresh the artifact index and notify GUI clients after a git pull or merge."""
        repo = gui_state.maybe_get_repo()
        if repo is not None:
            await asyncio.to_thread(repo.refresh)
        from src.tools.gui_routers.events import event_bus
        await event_bus.publish({
            "type": "sync_repository_updated",
            "repo": str(repo_path),
            "label": "Repository updated — refreshing view…",
        })

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with AsyncExitStack() as stack:
            logger.info("Starting MCP session managers")
            await stack.enter_async_context(mcp_read.session_manager.run())
            await stack.enter_async_context(mcp_write.session_manager.run())
            auto_start_default_watcher()
            logger.info("Default watcher auto-started")

            git_repos = _find_git_repos()
            sync_mgr = None
            if git_repos:
                from src.tools.git_sync import GitSyncManager
                logger.info(
                    "Starting git-sync for repos: %s",
                    ", ".join(f"{r.path}({r.role})" for r in git_repos),
                )
                sync_mgr = GitSyncManager(
                    git_repos,
                    ssh_passphrase=git_ssh_passphrase,
                    on_repo_changed=_on_repo_changed,
                )
                await sync_mgr.start()
            else:
                logger.info("No git-backed repositories configured for sync")

            yield

            if sync_mgr is not None:
                logger.info("Stopping git-sync manager")
                await sync_mgr.stop()
            logger.info("Backend lifespan shutdown complete")

    app = FastAPI(title="Architecture Repository Backend", version="0.3.0", lifespan=lifespan)
    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        watchdog = threading.Timer(
            _REQUEST_WATCHDOG_S,
            _log_thread_dump,
            kwargs={"reason": f"request still running after {_REQUEST_WATCHDOG_S:.1f}s method={request.method} path={request.url.path}"},
        )
        watchdog.daemon = True
        watchdog.start()
        logger.info("HTTP request started method=%s path=%s", request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000.0
            logger.exception("HTTP request failed method=%s path=%s duration_ms=%.1f", request.method, request.url.path, duration_ms)
            raise
        finally:
            watchdog.cancel()
        duration_ms = (time.perf_counter() - started) * 1000.0
        logger.info(
            "HTTP request completed method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:4173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(entities_router)
    app.include_router(connections_router)
    app.include_router(diagrams_router)
    app.include_router(documents_router)
    app.include_router(promote_router)
    app.include_router(sync_router)
    app.include_router(admin_router)
    app.include_router(events_router)
    # Starlette mounts only match `/mcp/…`, not the bare `/mcp` path.
    # Serve the MCP ASGI handlers on both variants so IDE clients can POST to
    # `/mcp` without getting routed into the SPA/static handler.
    app.add_route("/mcp/read", read_app, include_in_schema=False)
    app.add_route("/mcp/read/", read_app, include_in_schema=False)
    app.add_route("/mcp/write", write_app, include_in_schema=False)
    app.add_route("/mcp/write/", write_app, include_in_schema=False)

    gui_dist = Path(__file__).resolve().parent.parent.parent / "tools" / "gui" / "dist"
    if gui_dist.exists():
        app.mount("/", StaticFiles(directory=str(gui_dist), html=True), name="static")
    return app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Unified architecture backend")
    parser.add_argument(
        "--repo-root", default=None,
        help="Engagement repository root (default: ARCH_REPO_ROOT env var or arch-init state)",
    )
    parser.add_argument(
        "--enterprise-root", default=None,
        help="Enterprise repository root (default: ARCH_ENTERPRISE_ROOT env var or arch-init state)",
    )
    parser.add_argument(
        "--admin-mode", action="store_true", default=False,
        help="Enable enterprise-repo writes through /admin/api/*",
    )
    parser.add_argument(
        "--read-only", action="store_true", default=False,
        help="Block all engagement-repo writes (use for shared/review deployments)",
    )
    parser.add_argument(
        "--stop", action="store_true", default=False,
        help="Stop the currently running arch-backend for this workspace",
    )
    parser.add_argument(
        "--status", action="store_true", default=False,
        help="Show whether arch-backend is running for this workspace",
    )
    parser.add_argument(
        "--restart", action="store_true", default=False,
        help="Restart the currently running backend before starting a new one",
    )
    parser.add_argument(
        "--daemon", action="store_true", default=False,
        help="Start arch-backend detached with stdin from /dev/null and output in .arch/backend.log",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--git-ssh-password", default=None, metavar="PASSPHRASE",
        help="SSH key passphrase for git operations (overrides ARCH_GIT_SSH_PASSWORD env var)",
    )
    args = parser.parse_args(argv)

    if not (args.status or args.stop) and _is_background_tty_job():
        log_path = _redirect_stdio_to_backend_log(start=Path.cwd())
        print(f"arch-backend detected a background TTY job; redirecting output to {log_path}")

    log_level_name = backend_min_log_level()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=logging.CRITICAL if args.status else log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    resolved_port = resolve_backend_port(start=Path.cwd(), explicit_port=args.port)

    if args.status:
        result = backend_status(port=resolved_port)
        reason = result.get("reason")
        if result.get("running"):
            print(f"backend is running on port {result.get('port')} (pid {result.get('pid')})")
            _print_status_details(result)
        elif reason == "unmanaged_backend":
            print(f"backend is responding on port {result.get('port')} but is not managed by this workspace")
            _print_status_details(result)
        elif reason == "port_in_use":
            print(f"port {result.get('port')} is in use by another process")
            _print_status_details(result)
        elif reason == "not_running":
            print("backend is not running")
        elif reason == "stopped_backend":
            print(f"backend process pid {result.get('pid')} is stopped on port {result.get('port')}")
            _print_status_details(result)
        elif reason == "unhealthy_backend":
            print(f"backend process pid {result.get('pid')} is not responding on port {result.get('port')}")
            _print_status_details(result)
        elif reason == "stale_pid":
            print(f"removed stale backend pid {result.get('pid')}")
        elif reason == "invalid_state":
            print("backend state is invalid")
        else:
            print(f"backend is not healthy on port {result.get('port')} (pid {result.get('pid')})")
            _print_status_details(result)
        return

    if args.stop:
        result = stop_backend(port=resolved_port)
        reason = result.get("reason")
        if result.get("stopped"):
            _print_stopped(result)
        elif reason == "not_running":
            print("backend is not running")
        elif reason == "stale_pid":
            print(f"removed stale backend pid {result.get('pid')}")
        elif reason == "single_other_port":
            pid = int(result["pid"])
            other_port = result.get("port")
            if _confirm_stop_other_instance(expected_port=resolved_port, pid=pid, actual_port=other_port):
                follow_up = stop_backend(port=int(other_port) if isinstance(other_port, int) else None)
                if follow_up.get("stopped"):
                    _print_stopped(follow_up)
                else:
                    raise SystemExit(f"failed to stop backend pid {follow_up.get('pid')}")
            else:
                raise SystemExit(1)
        elif reason == "invalid_state":
            print("removed invalid backend state")
        else:
            raise SystemExit(f"failed to stop backend pid {result.get('pid')}")
        return

    if args.restart:
        result = stop_backend(port=resolved_port)
        reason = result.get("reason")
        if result.get("stopped"):
            _print_stopped(result)
        elif reason not in {"not_running", "stale_pid", "invalid_state"}:
            raise SystemExit(f"failed to restart backend pid {result.get('pid')}")

    if args.daemon:
        existing = read_backend_state()
        if existing is not None:
            existing_port = existing.get("port")
            if isinstance(existing_port, int) and probe_backend(existing_port):
                print(f"backend already running on port {existing_port}")
                return

        status = backend_status(port=resolved_port)
        if status.get("running"):
            print(f"backend already running on port {status.get('port')} (pid {status.get('pid')})")
            return
        if status.get("reason") in {"stopped_backend", "unhealthy_backend"}:
            if args.restart:
                # A declarant survived the restart stop; attempt cleanup and continue.
                cleanup = stop_backend(port=resolved_port)
                if not cleanup.get("stopped") and cleanup.get("reason") not in {"not_running", "stale_pid"}:
                    raise SystemExit(
                        f"arch-backend pid {status.get('pid')} is not healthy and could not be stopped; "
                        f"run 'arch-backend --stop' manually"
                    )
            else:
                raise SystemExit(
                    f"arch-backend pid {status.get('pid')} is on port {resolved_port} but is not healthy; "
                    f"run 'arch-backend --stop' or 'arch-backend --restart --daemon'"
                )
        if status.get("reason") == "unmanaged_backend":
            print(f"backend already responding on port {resolved_port} but is not managed by this workspace")
            return
        if status.get("reason") == "port_in_use":
            raise SystemExit(f"port {resolved_port} is already in use by another process")

        log_path = backend_log_path(Path.cwd())
        pid = _start_daemon(argv=argv, log_path=log_path)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if probe_backend(resolved_port):
                print(f"backend started on port {resolved_port} (pid {pid}); log: {log_path}")
                return
            time.sleep(0.25)
        raise SystemExit(f"timed out waiting for backend on port {resolved_port}; see {log_path}")

    existing = read_backend_state()
    if existing is not None:
        existing_port = existing.get("port")
        if isinstance(existing_port, int) and probe_backend(existing_port):
            print(f"backend already running on port {existing_port}")
            return

    status = backend_status(port=resolved_port)
    if status.get("running"):
        print(f"backend already running on port {status.get('port')} (pid {status.get('pid')})")
        return
    if status.get("reason") in {"stopped_backend", "unhealthy_backend"}:
        raise SystemExit(
            f"arch-backend pid {status.get('pid')} is on port {resolved_port} but is not healthy; "
            f"run 'arch-backend --stop' or 'arch-backend --restart'"
        )
    if status.get("reason") == "unmanaged_backend":
        print(f"backend already responding on port {resolved_port} but is not managed by this workspace")
        return
    if status.get("reason") == "port_in_use":
        raise SystemExit(f"port {resolved_port} is already in use by another process")

    repo_root_path, enterprise_root_path = gui_server.resolve_server_roots(args.repo_root, args.enterprise_root)
    if repo_root_path is None:
        parser.error(
            "No --repo-root given, ARCH_REPO_ROOT not set, and no .arch/init-state.yaml found. "
            "Run arch-init first."
        )

    roots: list[Path] = [repo_root_path]
    if enterprise_root_path is not None:
        roots.append(enterprise_root_path)

    logger.info(
        "Initializing backend for repo_root=%s enterprise_root=%s admin_mode=%s read_only=%s host=%s port=%s",
        repo_root_path,
        enterprise_root_path,
        args.admin_mode,
        args.read_only,
        args.host,
        resolved_port,
    )
    repo = ArtifactRepository(roots)
    repo.refresh()  # eager-load index at startup so first request is fast
    gui_state.init_state(
        repo,
        repo_root_path,
        enterprise_root_path,
        admin_mode=args.admin_mode,
        read_only=args.read_only,
    )

    from src.common.artifact_document_schema import load_document_schemata
    load_document_schemata(repo_root_path)  # pre-warm schema cache so first navigation is fast

    # Pre-block engagement repo if read-only mode is active
    if args.read_only:
        from src.tools.write_block_manager import block_repo
        block_repo(repo_root_path)

    git_ssh_passphrase = args.git_ssh_password or os.environ.get("ARCH_GIT_SSH_PASSWORD") or None
    app = _build_app(git_ssh_passphrase=git_ssh_passphrase)
    write_backend_state(port=resolved_port)
    logger.info("Backend state file written for pid=%s port=%s", os.getpid(), resolved_port)
    try:
        uvicorn.run(app, host=args.host, port=resolved_port, log_level=log_level_name.lower())
    except Exception:
        logger.exception("arch-backend terminated during startup")
        raise
    finally:
        logger.info("Removing backend state file")
        remove_backend_state()


if __name__ == "__main__":
    main()
