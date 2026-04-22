"""Unified FastAPI + MCP backend entry point."""

from __future__ import annotations

import argparse
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import uvicorn
from mcp.server.fastmcp.server import StreamableHTTPASGIApp

from src.common.artifact_query import ArtifactRepository
from src.tools import gui_server
from src.tools.backend_runtime import (
    backend_status,
    probe_backend,
    read_backend_state,
    remove_backend_state,
    stop_backend,
    write_backend_state,
)
from src.tools.gui_routers import state as gui_state
from src.tools.mcp_artifact_server import mcp
from src.tools.artifact_mcp import auto_start_default_watcher


def _build_app():  # type: ignore[no-untyped-def]
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from src.tools.gui_routers.admin import router as admin_router
    from src.tools.gui_routers.connections import router as connections_router
    from src.tools.gui_routers.diagrams import router as diagrams_router
    from src.tools.gui_routers.documents import router as documents_router
    from src.tools.gui_routers.entities import router as entities_router
    from src.tools.gui_routers.promote import router as promote_router

    mcp.streamable_http_app()
    mcp_app = StreamableHTTPASGIApp(mcp.session_manager)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            auto_start_default_watcher()
            yield

    app = FastAPI(title="Architecture Repository Backend", version="0.3.0", lifespan=lifespan)
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
    app.include_router(admin_router)
    # Starlette mounts only match `/mcp/…`, not the bare `/mcp` path.
    # Serve the MCP ASGI handler on both variants so IDE clients can POST to
    # `/mcp` without getting routed into the SPA/static handler.
    app.add_route("/mcp", mcp_app, include_in_schema=False)
    app.add_route("/mcp/", mcp_app, include_in_schema=False)

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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    if args.status:
        result = backend_status(port=args.port)
        reason = result.get("reason")
        if result.get("running"):
            print(f"backend is running on port {result.get('port')} (pid {result.get('pid')})")
        elif reason == "unmanaged_backend":
            print(f"backend is responding on port {result.get('port')} but is not managed by this workspace")
        elif reason == "port_in_use":
            print(f"port {result.get('port')} is in use by another process")
        elif reason == "not_running":
            print("backend is not running")
        elif reason == "invalid_state":
            print("backend state is invalid")
        else:
            print(f"backend is not healthy on port {result.get('port')} (pid {result.get('pid')})")
        return

    if args.stop:
        result = stop_backend()
        reason = result.get("reason")
        if result.get("stopped"):
            print(f"stopped backend pid {result.get('pid')}")
        elif reason == "not_running":
            print("backend is not running")
        elif reason == "stale_pid":
            print(f"removed stale backend pid {result.get('pid')}")
        elif reason == "invalid_state":
            print("removed invalid backend state")
        else:
            raise SystemExit(f"failed to stop backend pid {result.get('pid')}")
        return

    if args.restart:
        result = stop_backend()
        reason = result.get("reason")
        if result.get("stopped"):
            print(f"stopped backend pid {result.get('pid')}")
        elif reason not in {"not_running", "stale_pid", "invalid_state"}:
            raise SystemExit(f"failed to restart backend pid {result.get('pid')}")

    existing = read_backend_state()
    if existing is not None:
        existing_port = existing.get("port")
        if isinstance(existing_port, int) and probe_backend(existing_port):
            print(f"backend already running on port {existing_port}")
            return

    status = backend_status(port=args.port)
    if status.get("reason") == "unmanaged_backend":
        print(f"backend already responding on port {args.port} but is not managed by this workspace")
        return
    if status.get("reason") == "port_in_use":
        raise SystemExit(f"port {args.port} is already in use by another process")

    repo_root_path, enterprise_root_path = gui_server.resolve_server_roots(args.repo_root, args.enterprise_root)
    if repo_root_path is None:
        parser.error(
            "No --repo-root given, ARCH_REPO_ROOT not set, and no .arch/init-state.yaml found. "
            "Run arch-init first."
        )

    roots: list[Path] = [repo_root_path]
    if enterprise_root_path is not None:
        roots.append(enterprise_root_path)

    gui_state.init_state(
        ArtifactRepository(roots),
        repo_root_path,
        enterprise_root_path,
        admin_mode=args.admin_mode,
    )

    write_backend_state(port=args.port)
    app = _build_app()
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    finally:
        remove_backend_state()


if __name__ == "__main__":
    main()
