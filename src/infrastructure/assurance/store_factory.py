"""Assurance store/archive/connector factory keyed by workspace (SC-1).

Reads `storage.assurance` config (store_backend, signals_backend) and returns
port-typed instances. Unknown backends fail closed at build time (ValueError at
startup rather than at first use).

Connection sharing:
  - sqlcipher: archive + colocated-signals share the store's SQLCipher connection
    via a conn_factory callable; no `_conn` reference escapes the factory.
  - private-git: archive is EncryptedGitArchive (chain.jsonl + Fernet .enc files);
    shares the store's Fernet key via a fernet_factory lambda.
  - pocketbase: archive uses a plain-SQLite file alongside the assurance dir.

Cache is keyed by resolved workspace path. Call `clear_factory_cache()` in tests.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from src.application.assurance_ports import AssuranceArchive, ConfidentialAssuranceStore, SecuritySignalConnector

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_instances: dict[str, "_AssuranceBundle"] = {}


class _AssuranceBundle:
    """Container for the three port-typed assurance adapters."""

    def __init__(
        self,
        store: ConfidentialAssuranceStore,
        archive: AssuranceArchive,
        connector: SecuritySignalConnector,
        store_backend: str,
        signals_backend: str,
    ) -> None:
        self.store = store
        self.archive = archive
        self.connector = connector
        self.store_backend = store_backend
        self.signals_backend = signals_backend


def get_assurance_bundle(
    workspace: Path,
    *,
    db_path: Path | None = None,
    signals_db_path: Path | None = None,
) -> _AssuranceBundle:
    """Return the workspace-keyed assurance bundle, building it on first call."""
    key = str(workspace.resolve())
    with _lock:
        bundle = _instances.get(key)
        if bundle is None:
            bundle = _build_bundle(workspace, db_path=db_path, signals_db_path=signals_db_path)
            _instances[key] = bundle
        return bundle


def clear_factory_cache() -> None:
    """Evict all cached bundles. Use in tests or after backend config changes."""
    with _lock:
        _instances.clear()


# ── Internal builders ─────────────────────────────────────────────────────────


def _build_bundle(
    workspace: Path,
    *,
    db_path: Path | None,
    signals_db_path: Path | None,
) -> _AssuranceBundle:
    from src.config.settings import storage_assurance_signals_backend, storage_assurance_store_backend

    store_backend = storage_assurance_store_backend()
    signals_backend = storage_assurance_signals_backend()
    assurance_dir = workspace / ".arch-assurance"

    store = _build_store(store_backend, workspace, db_path, assurance_dir)
    archive = _build_archive(store, store_backend, assurance_dir)
    connector = _build_connector(
        store, store_backend, signals_backend, assurance_dir, signals_db_path
    )

    logger.info("Assurance bundle: store=%s signals=%s", store_backend, signals_backend)
    return _AssuranceBundle(store, archive, connector, store_backend, signals_backend)


def _build_store(
    store_backend: str,
    workspace: Path,
    db_path: Path | None,
    assurance_dir: Path,
) -> ConfidentialAssuranceStore:
    if store_backend == "sqlcipher":
        from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

        return SQLCipherAssuranceStore(db_path or assurance_dir / "store.db")

    if store_backend == "pocketbase":
        return _build_pocketbase_store()

    if store_backend == "private-git":
        repo_path = db_path or workspace / ".arch-assurance-git"
        from src.infrastructure.assurance._encrypted_private_git_store import (
            EncryptedPrivateGitAssuranceStore,
        )

        return EncryptedPrivateGitAssuranceStore(repo_path)

    raise ValueError(  # fail-closed — checked by settings loader, but defensive repeat
        f"Unsupported store_backend: {store_backend!r}"
    )


def _build_archive(
    store: ConfidentialAssuranceStore,
    store_backend: str,
    assurance_dir: Path,
) -> AssuranceArchive:
    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive

    if store_backend == "sqlcipher":
        from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

        assert isinstance(store, SQLCipherAssuranceStore)
        sqlcipher_store = store
        return SQLCipherAssuranceArchive(lambda: sqlcipher_store._conn)  # noqa: SLF001

    if store_backend == "private-git":
        from src.infrastructure.assurance._encrypted_git_archive import EncryptedGitArchive
        from src.infrastructure.assurance._encrypted_private_git_store import (
            EncryptedPrivateGitAssuranceStore,
        )

        assert isinstance(store, EncryptedPrivateGitAssuranceStore)
        return EncryptedGitArchive(store._repo, fernet_factory=lambda: store._fernet)  # noqa: SLF001

    # Non-SQLCipher/non-private-git backends (pocketbase): plain-SQLite local archive.
    archive_filename = f"{store_backend.replace('-', '_')}_archive.db"
    archive_path = assurance_dir / archive_filename
    return _make_local_sqlite_archive(archive_path)


def _build_connector(
    store: ConfidentialAssuranceStore,
    store_backend: str,
    signals_backend: str,
    assurance_dir: Path,
    signals_db_path: Path | None,
) -> SecuritySignalConnector:
    if signals_backend == "sqlcipher-colocated":
        if store_backend != "sqlcipher":
            raise ValueError(
                "signals_backend 'sqlcipher-colocated' requires store_backend 'sqlcipher'. "
                f"Current store_backend: {store_backend!r}"
            )
        from src.infrastructure.assurance._collocated_signals_connector import (
            CollocatedSQLCipherSignalsConnector,
        )
        from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

        assert isinstance(store, SQLCipherAssuranceStore)
        sqlcipher_store = store
        return CollocatedSQLCipherSignalsConnector(lambda: sqlcipher_store._conn)  # noqa: SLF001

    if signals_backend == "sqlite":
        from src.infrastructure.assurance._security_connector import SQLiteSecurityConnector

        return SQLiteSecurityConnector(
            signals_db_path or assurance_dir / "security-signals.db"
        )

    # "encrypted" — for sqlcipher store, co-locate; otherwise plain sqlite
    if store_backend == "sqlcipher":
        from src.infrastructure.assurance._collocated_signals_connector import (
            CollocatedSQLCipherSignalsConnector,
        )
        from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

        assert isinstance(store, SQLCipherAssuranceStore)
        sqlcipher_store = store
        return CollocatedSQLCipherSignalsConnector(lambda: sqlcipher_store._conn)  # noqa: SLF001

    from src.infrastructure.assurance._security_connector import SQLiteSecurityConnector

    return SQLiteSecurityConnector(signals_db_path or assurance_dir / "security-signals.db")


def _build_pocketbase_store() -> ConfidentialAssuranceStore:
    import os

    from src.infrastructure.assurance._pocketbase_store import PocketBaseAssuranceStore

    base_url = os.getenv("ARCH_POCKETBASE_URL", "")
    admin_email = os.getenv("ARCH_POCKETBASE_ADMIN_EMAIL", "")
    admin_password = os.getenv("ARCH_POCKETBASE_ADMIN_PASSWORD", "")
    if not base_url:
        raise RuntimeError(
            "store_backend 'pocketbase' requires ARCH_POCKETBASE_URL env var. "
            "Set it to the PocketBase instance URL (e.g. http://localhost:8090)."
        )
    return PocketBaseAssuranceStore(base_url, admin_email, admin_password)


def _dict_row(cursor: Any, row: Any) -> dict[str, object]:
    return dict(zip([col[0] for col in cursor.description], row))


def _make_local_sqlite_archive(archive_path: Path) -> AssuranceArchive:
    """Lazy plain-SQLite archive for non-SQLCipher backends."""
    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive
    from src.infrastructure.assurance._schema import ARCHIVE_ONLY_SCHEMA_SQL

    init_lock = threading.Lock()
    conn_holder: list[sqlite3.Connection] = []

    def _get_conn() -> sqlite3.Connection:
        if not conn_holder:
            with init_lock:
                if not conn_holder:
                    archive_path.parent.mkdir(parents=True, exist_ok=True)
                    conn = sqlite3.connect(str(archive_path))
                    conn.row_factory = _dict_row  # type: ignore[assignment]
                    conn.executescript(ARCHIVE_ONLY_SCHEMA_SQL)
                    conn.commit()
                    conn_holder.append(conn)
        return conn_holder[0]

    return SQLCipherAssuranceArchive(_get_conn)
