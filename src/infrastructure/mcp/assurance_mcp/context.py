"""Shared context for assurance MCP tools.

Provides the ConfidentialAssuranceStore, AssuranceArchive, and
SQLiteSecurityConnector for tools. The store is resolved from the workspace
root (default) or ARCH_ASSURANCE_DB_PATH env.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive
from src.infrastructure.assurance._security_connector import SQLiteSecurityConnector
from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

_ENV_DB_PATH = "ARCH_ASSURANCE_DB_PATH"
_ENV_SIGNALS_DB_PATH = "ARCH_SECURITY_SIGNALS_DB_PATH"


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_db_path() -> Path:
    env = os.getenv(_ENV_DB_PATH)
    if env:
        return Path(env).expanduser()
    return _workspace_root() / ".arch-assurance" / "store.db"


def default_signals_db_path() -> Path:
    env = os.getenv(_ENV_SIGNALS_DB_PATH)
    if env:
        return Path(env).expanduser()
    return _workspace_root() / ".arch-assurance" / "security-signals.db"


@lru_cache(maxsize=1)
def _build_store() -> tuple[SQLCipherAssuranceStore, SQLCipherAssuranceArchive]:
    db_path = default_db_path()
    store = SQLCipherAssuranceStore(db_path)
    archive = SQLCipherAssuranceArchive(lambda: store._conn)  # noqa: SLF001
    return store, archive


@lru_cache(maxsize=1)
def _build_connector() -> SQLiteSecurityConnector:
    return SQLiteSecurityConnector(default_signals_db_path())


class AssuranceContext:
    """Accessor for the shared assurance store, archive, and security connector."""

    @property
    def store(self) -> SQLCipherAssuranceStore:
        return _build_store()[0]

    @property
    def archive(self) -> SQLCipherAssuranceArchive:
        return _build_store()[1]

    @property
    def connector(self) -> SQLiteSecurityConnector:
        return _build_connector()

    def is_available(self) -> bool:
        return self.store.is_unlocked()

    def locked_response(self) -> dict[str, object]:
        return {
            "error": "assurance_store_locked",
            "message": (
                "The confidential assurance store is not unlocked. "
                "Run `arch-assurance unlock` to enable assurance tools."
            ),
        }

    def not_found_response(self, node_id: str) -> dict[str, object]:
        return {"error": "not_found", "node_id": node_id}


_CTX = AssuranceContext()


def get_assurance_context() -> AssuranceContext:
    return _CTX


def clear_context_cache() -> None:
    _build_store.cache_clear()
    _build_connector.cache_clear()
