"""Apply the versioned security-signals migrations to a live connection.

One explicit version table (``signals_schema_meta``), one ordered migration
list (``src.domain.signals_schema``), one transaction per migration. The
refresh-run aggregate is the sole signals model.
"""

from __future__ import annotations

from typing import Any

from src.domain.signals_schema import (
    SIGNALS_MIGRATIONS,
    SIGNALS_SCHEMA_VERSION,
    signals_migration_statements,
)

_BASELINE_VERSION = 1

__all__ = [
    "SIGNALS_MIGRATIONS",
    "SIGNALS_SCHEMA_VERSION",
    "apply_signals_migrations",
    "signals_schema_version",
]


def signals_schema_version(conn: Any) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS signals_schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    row = conn.execute(
        "SELECT value FROM signals_schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        return _BASELINE_VERSION
    return int(row["value"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])


def apply_signals_migrations(conn: Any) -> int:
    """Bring the signals schema to the current version; one transaction per
    migration (SQLite DDL is transactional). Returns the resulting version."""
    current = signals_schema_version(conn)
    for version, ddl in SIGNALS_MIGRATIONS:
        if version <= current:
            continue
        try:
            conn.execute("BEGIN IMMEDIATE")
        except Exception:  # noqa: BLE001 — already inside an implicit transaction
            pass
        try:
            for statement in signals_migration_statements(ddl):
                conn.execute(statement)
            conn.execute(
                "INSERT OR REPLACE INTO signals_schema_meta(key, value) VALUES ('schema_version', ?)",
                (str(version),),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        current = version
    return current
