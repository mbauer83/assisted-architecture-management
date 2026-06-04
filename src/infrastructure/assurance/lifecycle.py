"""Assurance store lifecycle operations: init, unlock, backup, export, rotate-key.

These are called by the `arch-assurance` CLI. They are pure functions that
operate on a store path and the OS keychain.
"""

from __future__ import annotations

import json
import logging
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

from src.infrastructure.assurance._schema import ASSURANCE_SCHEMA_MIGRATIONS, ASSURANCE_SCHEMA_SQL, SCHEMA_VERSION
from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

logger = logging.getLogger(__name__)

_SERVICE_NAME = "arch-assurance"
_KEY_ACCOUNT = "db-encryption-key"
_RECOVERY_KEY_ACCOUNT = "db-recovery-key"


def _keyring() -> Any:
    import keyring  # type: ignore[import-untyped]

    return keyring


def default_store_path(workspace_root: Path) -> Path:
    return workspace_root / ".arch-assurance" / "store.db"


# ── init ──────────────────────────────────────────────────────────────────────


def init_store(db_path: Path, *, force: bool = False) -> dict[str, object]:
    """Initialise a new confidential assurance store.

    - Generates a 256-bit random key and stores it in the OS keychain.
    - Creates the SQLCipher DB at db_path with the full schema.
    - Saves a recovery key (hex-encoded) in the keychain under a separate account.
    - Adds db_path to .gitignore if possible.

    Returns a dict with status info. Raises if the store already exists and
    force=False.
    """
    import sqlcipher3  # type: ignore[import-untyped]

    kr = _keyring()

    if db_path.exists() and not force:
        raise FileExistsError(
            f"Assurance store already exists at {db_path}. "
            "Use --force to reinitialise (this DESTROYS all existing data)."
        )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    key = secrets.token_hex(32)
    recovery_key = secrets.token_hex(32)

    kr.set_password(_SERVICE_NAME, _KEY_ACCOUNT, key)
    kr.set_password(_SERVICE_NAME, _RECOVERY_KEY_ACCOUNT, recovery_key)

    conn = sqlcipher3.connect(str(db_path))
    conn.execute(f"PRAGMA key = '{key}'")
    conn.executescript(ASSURANCE_SCHEMA_SQL)
    for migration_sql in ASSURANCE_SCHEMA_MIGRATIONS:
        try:
            conn.execute(migration_sql)
        except Exception as _exc:  # noqa: BLE001
            if "duplicate column" not in str(_exc):
                raise
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("schema_version", SCHEMA_VERSION),
    )
    conn.commit()
    conn.close()

    _add_to_gitignore(db_path.parent)

    logger.info("Assurance store initialised at %s", db_path)
    return {
        "status": "initialised",
        "db_path": str(db_path),
        "schema_version": SCHEMA_VERSION,
        "recovery_key_in_keychain": _RECOVERY_KEY_ACCOUNT,
        "note": "Recovery key stored in OS keychain. Export it with `arch-assurance export-key`.",
    }


def _add_to_gitignore(directory: Path) -> None:
    gitignore = directory / ".gitignore"
    entry = "*.db\n*.db-wal\n*.db-shm\n"
    if gitignore.exists():
        existing = gitignore.read_text()
        if "*.db" not in existing:
            gitignore.write_text(existing + entry)
    else:
        gitignore.write_text(entry)


# ── backup ────────────────────────────────────────────────────────────────────


def backup_store(db_path: Path, *, backup_path: Path | None = None) -> dict[str, object]:
    """Copy the encrypted DB file to a backup location."""
    if not db_path.exists():
        raise FileNotFoundError(f"No store at {db_path}. Run `arch-assurance init` first.")
    if backup_path is None:
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        backup_path = db_path.parent / f"store.backup.{ts}.db"
    shutil.copy2(db_path, backup_path)
    logger.info("Assurance store backed up to %s", backup_path)
    return {"status": "backed_up", "backup_path": str(backup_path)}


# ── export ────────────────────────────────────────────────────────────────────


def export_store(store: SQLCipherAssuranceStore, output_path: Path) -> dict[str, object]:
    """Export all assurance nodes and edges to a JSON file (for data portability)."""
    if not store.is_unlocked():
        raise RuntimeError("Store must be unlocked before export.")
    data = {
        "export_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": store.list_nodes(),
        "edges": store.list_edges(),
        "arch_refs": store.list_arch_refs(),
    }
    output_path.write_text(json.dumps(data, indent=2))
    logger.info("Assurance store exported to %s", output_path)
    return {"status": "exported", "output_path": str(output_path), "node_count": len(data["nodes"])}


# ── rotate-key ────────────────────────────────────────────────────────────────


def rotate_key(db_path: Path) -> dict[str, object]:
    """Generate a new encryption key and re-encrypt the DB in place (REKEY)."""
    import sqlcipher3  # type: ignore[import-untyped]

    kr = _keyring()
    old_key = kr.get_password(_SERVICE_NAME, _KEY_ACCOUNT)
    if old_key is None:
        raise RuntimeError("Current key not found in keychain.")
    new_key = secrets.token_hex(32)
    conn = sqlcipher3.connect(str(db_path))
    conn.execute(f"PRAGMA key = '{old_key}'")
    conn.execute(f"PRAGMA rekey = '{new_key}'")
    conn.close()
    kr.set_password(_SERVICE_NAME, _KEY_ACCOUNT, new_key)
    logger.info("Assurance store key rotated successfully")
    return {"status": "key_rotated"}


# ── export-key ────────────────────────────────────────────────────────────────


def export_recovery_key() -> dict[str, object]:
    """Return the recovery key from the keychain (for safe offline storage)."""
    kr = _keyring()
    recovery_key = kr.get_password(_SERVICE_NAME, _RECOVERY_KEY_ACCOUNT)
    if recovery_key is None:
        raise RuntimeError("Recovery key not found in keychain.")
    return {
        "recovery_key": recovery_key,
        "warning": "Store this key securely offline. It can restore access if the OS keychain is lost.",
    }
