"""FastAPI REST server backing the GUI tool.

All endpoint logic lives in src/tools/gui_routers/.
This file only wires together the app, CORS, routers, static files, and CLI entrypoint.

Admin mode (``--admin-mode``) enables the ``/admin/api/*`` router, which allows
writes to the enterprise (global) repository in addition to the engagement repo.
It is a convention guard for local use — there is no authentication.
After an admin session, run ``git commit`` in the enterprise repo before
restarting in normal mode (arch-init rejects dirty clones).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def _make_app():  # type: ignore[no-untyped-def]
    """Build and return the FastAPI application (lazy to avoid import-time FastAPI requirement)."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from src.tools.gui_routers.admin import router as admin_router
    from src.tools.gui_routers.connections import router as connections_router
    from src.tools.gui_routers.diagrams import router as diagrams_router
    from src.tools.gui_routers.entities import router as entities_router
    from src.tools.gui_routers.promote import router as promote_router

    app = FastAPI(title="Architecture Repository GUI", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:4173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(entities_router)
    app.include_router(connections_router)
    app.include_router(diagrams_router)
    app.include_router(promote_router)
    app.include_router(admin_router)
    return app


def resolve_server_roots(
    arg_repo_root: str | None,
    arg_enterprise_root: str | None,
) -> tuple[Path | None, Path | None]:
    """Resolve engagement and enterprise roots.

    Priority: explicit CLI arg > environment variable > arch-init state file.
    Environment variables: ARCH_REPO_ROOT, ARCH_ENTERPRISE_ROOT.
    Returns (engagement_root, enterprise_root); either may be None.
    """
    from src.tools.workspace_init import load_init_state
    ws = load_init_state()

    eng = (
        Path(arg_repo_root) if arg_repo_root
        else Path(os.environ["ARCH_REPO_ROOT"]) if os.environ.get("ARCH_REPO_ROOT")
        else Path(ws["engagement_root"]) if ws and "engagement_root" in ws
        else None
    )
    ent = (
        Path(arg_enterprise_root) if arg_enterprise_root
        else Path(os.environ["ARCH_ENTERPRISE_ROOT"]) if os.environ.get("ARCH_ENTERPRISE_ROOT")
        else Path(ws["enterprise_root"]) if ws and "enterprise_root" in ws
        else None
    )
    return eng, ent


def main(argv: list[str] | None = None) -> None:
    from src.tools.arch_backend import main as backend_main

    backend_main(argv)


if __name__ == "__main__":
    main()
