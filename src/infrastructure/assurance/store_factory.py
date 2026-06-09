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
        archive_backend: str,
    ) -> None:
        self.store = store
        self.archive = archive
        self.connector = connector
        self.store_backend = store_backend
        self.signals_backend = signals_backend
        self.archive_backend = archive_backend


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
    from src.config.settings import (
        storage_assurance_archive_backend,
        storage_assurance_signals_backend,
        storage_assurance_store_backend,
    )

    store_backend = storage_assurance_store_backend()
    signals_backend = storage_assurance_signals_backend()
    archive_backend = storage_assurance_archive_backend()
    assurance_dir = workspace / ".arch-assurance"

    store = _build_store(store_backend, workspace, db_path, assurance_dir)
    archive = _build_archive(store, store_backend, assurance_dir, archive_backend)
    connector = _build_connector(
        store, store_backend, signals_backend, assurance_dir, signals_db_path
    )

    # Auto-unlock for key-backed backends. PocketBase omitted — its auth is
    # session-based (env-var HTTP credentials, not an OS-keychain key).
    if store_backend in ("sqlcipher", "private-git"):
        _try_auto_unlock(store, store_backend)

    logger.info(
        "Assurance bundle: store=%s signals=%s archive=%s",
        store_backend, signals_backend, archive_backend,
    )
    return _AssuranceBundle(store, archive, connector, store_backend, signals_backend, archive_backend)


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
    archive_backend: str,
) -> AssuranceArchive:
    # Cloud-native WORM archives are independent of the store backend.
    if archive_backend == "s3-worm":
        from src.infrastructure.assurance._s3_worm_archive import S3WORMAssuranceArchive

        return S3WORMAssuranceArchive.from_env()

    if archive_backend == "azure-blob-worm":
        from src.infrastructure.assurance._azure_blob_worm_archive import (
            AzureBlobWORMAssuranceArchive,
        )

        return AzureBlobWORMAssuranceArchive.from_env()

    if archive_backend == "worm" and store_backend != "sqlcipher":
        raise ValueError(
            "archive_backend 'worm' requires store_backend 'sqlcipher'. "
            f"Current store_backend: {store_backend!r}"
        )

    from src.infrastructure.assurance._archive import SQLCipherAssuranceArchive

    if store_backend == "sqlcipher":
        from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

        assert isinstance(store, SQLCipherAssuranceStore)
        sqlcipher_store = store
        conn_factory = lambda: sqlcipher_store._conn  # noqa: E731, SLF001
        if archive_backend == "worm":
            from src.infrastructure.assurance._worm_archive import WORMSQLCipherAssuranceArchive
            return WORMSQLCipherAssuranceArchive(conn_factory)
        return SQLCipherAssuranceArchive(conn_factory)

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


def _try_auto_unlock(store: ConfidentialAssuranceStore, store_backend: str) -> None:
    """Auto-unlock when the OS keychain confirms the store has been explicitly activated.

    The "setup-confirmed" keychain entry is written by `arch-assurance unlock` on first
    successful verification.  This gate preserves the required explicit activation step
    (recovery-key export prompt, conscious enablement) while eliminating the per-restart
    ceremony once confirmed.  Fail-closed: absent confirmation, absent key, or any unlock
    error leaves the store locked.
    """
    try:
        from src.infrastructure.assurance import _credential_store as creds  # noqa: PLC0415

        if not creds.get("setup-confirmed"):
            logger.debug(
                "Assurance store (%s) not auto-unlocked: "
                "run `arch-assurance unlock` once to activate.",
                store_backend,
            )
            return
        store.unlock()
        logger.info("Assurance store (%s) auto-unlocked from OS keychain.", store_backend)
    except RuntimeError:
        # Expected when not yet initialised (key absent) — stays locked.
        logger.debug(
            "Assurance store (%s) not auto-unlocked: key absent or store not initialised.",
            store_backend,
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Assurance store (%s) auto-unlock failed; store remains locked.",
            store_backend,
            exc_info=True,
        )


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
