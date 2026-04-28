"""FastAPI application construction for the arch backend."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import traceback
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, cast

from mcp.server.fastmcp.server import StreamableHTTPASGIApp

from src.infrastructure.artifact_index.coordination import get_write_queue_state_snapshot
from src.infrastructure.gui.routers import state as gui_state
from src.infrastructure.mcp.artifact_mcp import auto_start_default_watcher
from src.infrastructure.mcp.mcp_artifact_server import mcp_read, mcp_write

logger = logging.getLogger(__name__)
_REQUEST_SLOW_WARNING_S = 5.0
_REQUEST_THREAD_DUMP_S = 20.0

if TYPE_CHECKING:
    from src.infrastructure.git.git_sync import RepoSpec


def _find_git_repos() -> "list[RepoSpec]":
    """Return git-backed repos from arch-workspace.yaml, tagged with their role."""
    from src.config.workspace_paths import find_workspace_config, parse_workspace_config
    from src.infrastructure.git.git_sync import RepoSpec

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
            repos.append(
                RepoSpec(
                    path=(workspace_root / rel).resolve(),
                    role=key,  # type: ignore[arg-type]
                )
            )
    return repos


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


def _log_slow_request_warning(*, method: str, path: str, threshold_s: float) -> None:
    queue_state = get_write_queue_state_snapshot()
    logger.warning(
        "HTTP request still running method=%s path=%s threshold_s=%.1f "
        "active_jobs=%s pending_jobs=%s active_tool=%s active_operation_id=%s active_phase=%s",
        method,
        path,
        threshold_s,
        queue_state["active_jobs"],
        queue_state["pending_jobs"],
        queue_state["active_tool_name"],
        queue_state["active_operation_id"],
        queue_state["active_phase"],
    )


def _log_structured_output_tool_inventory() -> None:
    """Log structured-output tool counts at startup for observability."""
    read_tools = mcp_read._tool_manager.list_tools()  # type: ignore[attr-defined]
    write_tools = mcp_write._tool_manager.list_tools()  # type: ignore[attr-defined]
    read_structured = [t.name for t in read_tools if t.output_schema is not None]
    write_structured = [t.name for t in write_tools if t.output_schema is not None]
    if read_structured:
        logger.info(
            "Read server: %d structured-output tools: %s",
            len(read_structured),
            ", ".join(read_structured),
        )
    else:
        logger.warning("Read server has no structured-output tools — normalizer may not be installed")
    if write_structured:
        logger.info(
            "Write server: %d structured-output tools: %s",
            len(write_structured),
            ", ".join(write_structured),
        )


def _build_app(git_ssh_passphrase: str | None = None):  # type: ignore[no-untyped-def]
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles

    from src.infrastructure.gui.routers.admin import router as admin_router
    from src.infrastructure.gui.routers.connections import router as connections_router
    from src.infrastructure.gui.routers.diagrams import router as diagrams_router
    from src.infrastructure.gui.routers.documents import router as documents_router
    from src.infrastructure.gui.routers.entities import router as entities_router
    from src.infrastructure.gui.routers.events import router as events_router
    from src.infrastructure.gui.routers.promote import router as promote_router
    from src.infrastructure.gui.routers.sync import router as sync_router

    mcp_read.streamable_http_app()
    mcp_write.streamable_http_app()

    read_app = StreamableHTTPASGIApp(mcp_read.session_manager)
    write_app = StreamableHTTPASGIApp(mcp_write.session_manager)

    async def _on_repo_changed(repo_path: Path) -> None:
        """Refresh the artifact index and notify GUI clients after a git pull or merge."""
        repo = gui_state.maybe_get_repo()
        if repo is not None:
            await asyncio.to_thread(repo.refresh)
        from src.infrastructure.gui.routers.events import event_bus
        from src.infrastructure.gui.routers.sync_status_cache import invalidate_sync_status_cache

        invalidate_sync_status_cache(repo=repo_path)
        await event_bus.publish(
            {
                "type": "sync_repository_updated",
                "repo": str(repo_path),
                "label": "Repository updated — refreshing view…",
            }
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with AsyncExitStack() as stack:
            logger.info("Starting MCP session managers")
            await stack.enter_async_context(mcp_read.session_manager.run())
            await stack.enter_async_context(mcp_write.session_manager.run())
            from src.infrastructure.mcp.artifact_mcp.write_queue import attach_event_loop

            attach_event_loop(asyncio.get_running_loop())
            auto_start_default_watcher()
            logger.info("Default watcher auto-started")
            _log_structured_output_tool_inventory()

            git_repos = _find_git_repos()
            sync_mgr = None
            if git_repos:
                from src.infrastructure.git.git_sync import GitSyncManager

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
        slow_watchdog = threading.Timer(
            _REQUEST_SLOW_WARNING_S,
            _log_slow_request_warning,
            kwargs={
                "method": request.method,
                "path": request.url.path,
                "threshold_s": _REQUEST_SLOW_WARNING_S,
            },
        )
        dump_watchdog = threading.Timer(
            _REQUEST_THREAD_DUMP_S,
            _log_thread_dump,
            kwargs={
                "reason": (
                    f"request still running after {_REQUEST_THREAD_DUMP_S:.1f}s"
                    f" method={request.method} path={request.url.path}"
                )
            },
        )
        slow_watchdog.daemon = True
        dump_watchdog.daemon = True
        slow_watchdog.start()
        dump_watchdog.start()
        logger.info("HTTP request started method=%s path=%s", request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000.0
            logger.exception(
                "HTTP request failed method=%s path=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        finally:
            slow_watchdog.cancel()
            dump_watchdog.cancel()
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
    @app.get("/health", include_in_schema=False)
    async def health_check():  # type: ignore[no-untyped-def]
        from fastapi.responses import JSONResponse

        read_tools = mcp_read._tool_manager.list_tools()  # type: ignore[attr-defined]
        write_tools = mcp_write._tool_manager.list_tools()  # type: ignore[attr-defined]
        structured = [t.name for t in read_tools if t.output_schema is not None]
        return JSONResponse(
            {
                "status": "ok",
                "read_tools": len(read_tools),
                "write_tools": len(write_tools),
                "structured_output_tools": len(structured),
                "structured_output_tool_names": structured,
            }
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
    app.add_route("/mcp/read", cast(object, read_app), include_in_schema=False)  # type: ignore[arg-type]
    app.add_route("/mcp/read/", cast(object, read_app), include_in_schema=False)  # type: ignore[arg-type]
    app.add_route("/mcp/write", cast(object, write_app), include_in_schema=False)  # type: ignore[arg-type]
    app.add_route("/mcp/write/", cast(object, write_app), include_in_schema=False)  # type: ignore[arg-type]

    gui_dist = Path(__file__).resolve().parent.parent.parent / "tools" / "gui" / "dist"
    if gui_dist.exists():
        app.mount("/", StaticFiles(directory=str(gui_dist), html=True), name="static")
    return app
