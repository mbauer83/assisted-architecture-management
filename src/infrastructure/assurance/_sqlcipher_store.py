"""SQLCipher-backed confidential assurance store adapter.

Key management: the encryption key is retrieved from the secure credential store
(_credential_store). The DB file is stored at the path given at construction
time (typically .arch-assurance/store.db, gitignored).

Thread-safety: this adapter is single-threaded and synchronous. The backend
uses it from within a write-queue serialised context.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from src.infrastructure.assurance import _credential_store as creds
from src.infrastructure.assurance._id_utils import make_edge_id, make_node_id
from src.infrastructure.assurance._schema import ASSURANCE_SCHEMA_MIGRATIONS, ASSURANCE_SCHEMA_SQL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

_KEY_ACCOUNT = "db-encryption-key"


def _dict_row_factory(cursor: Any, row: Any) -> dict[str, object]:
    """Convert a sqlcipher3 row to a plain dict using cursor.description."""
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _where(filters: dict[str, object | None]) -> tuple[str, list[object]]:
    """Build a parameterised ``WHERE`` clause from the truthy entries of ``filters``.

    Keys are trusted column names; values become positional ``?`` parameters.
    Returns ``("", [])`` when no filter is active.
    """
    active = [(col, val) for col, val in filters.items() if val]
    clauses = " AND ".join(f"{col} = ?" for col, _ in active)
    where = f"WHERE {clauses}" if active else ""
    return where, [val for _, val in active]


@contextlib.contextmanager  # type: ignore[misc]
def _suppress_c_stderr():  # type: ignore[return]
    """Redirect fd 2 to /dev/null for C-library calls that emit diagnostic noise.

    SQLCipher writes 'ERROR CORE ...' messages directly to fd 2 before raising a
    Python exception on key mismatch. Suppress them here; the RuntimeError raised
    by the caller carries the actionable message.
    """
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    os.dup2(devnull_fd, 2)
    try:
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull_fd)


class SQLCipherAssuranceStore:
    """Adapter implementing ConfidentialAssuranceStore using SQLCipher."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: Any = None  # sqlcipher3.Connection

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def is_unlocked(self) -> bool:
        return self._conn is not None

    def unlock(self) -> None:
        import sqlcipher3  # type: ignore[import-untyped]

        key = creds.get(_KEY_ACCOUNT)
        if key is None:
            raise RuntimeError(
                "Assurance store key not found in credential store. "
                "Run `arch-assurance init` to initialise the store."
            )
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlcipher3.connect(str(self._db_path))
        conn.execute(f"PRAGMA key = '{key}'")
        # Suppress C-library 'ERROR CORE ...' output on key mismatch; the
        # RuntimeError below carries the actionable message instead.
        try:
            with _suppress_c_stderr():
                conn.executescript(ASSURANCE_SCHEMA_SQL)
        except Exception as exc:
            conn.close()
            raise RuntimeError(
                "Failed to unlock the assurance store — the keychain key does not match "
                "this database. This usually means the store was re-initialised after the "
                "key was last saved. Run `arch-assurance init --force` to create a fresh "
                "store (existing data will be lost)."
            ) from exc
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
        conn.row_factory = _dict_row_factory
        self._conn = conn
        logger.info("Assurance store unlocked at %s", self._db_path)

    def lock(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        logger.info("Assurance store locked")

    def _require_unlocked(self) -> Any:
        if self._conn is None:
            raise RuntimeError("Assurance store is locked. Run `arch-assurance unlock`.")
        return self._conn

    # ── Node CRUD ─────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> dict[str, object] | None:
        conn = self._require_unlocked()
        row = conn.execute(
            "SELECT * FROM assurance_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        return row if row else None

    def list_nodes(
        self,
        *,
        node_type: str | None = None,
        status: str | None = None,
        concern_class: str | None = None,
        tlp: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._require_unlocked()
        where, params = _where(
            {"node_type": node_type, "status": status, "concern_class": concern_class, "tlp": tlp}
        )
        rows = conn.execute(
            f"SELECT * FROM assurance_nodes {where} ORDER BY created_at", params
        ).fetchall()
        return list(rows)

    def create_node(
        self,
        node_type: str,
        name: str,
        *,
        status: str = "draft",
        tlp: str = "TLP:WHITE",
        concern_class: str | None = None,
        disposition: str | None = None,
        uca_type: str | None = None,
        binding_status: str | None = None,
        node_role: str | None = None,
        attributes: dict[str, object] | None = None,
        content: str = "",
    ) -> str:
        conn = self._require_unlocked()
        node_id = make_node_id(node_type, name)
        now = _now_iso()
        conn.execute(
            """
            INSERT INTO assurance_nodes
                (node_id, node_type, name, status, tlp, concern_class, disposition,
                 uca_type, binding_status, node_role, attributes_json, content_text,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id, node_type, name, status, tlp, concern_class, disposition,
                uca_type, binding_status, node_role,
                json.dumps(attributes or {}), content, now, now,
            ),
        )
        conn.commit()
        return node_id

    def update_node(self, node_id: str, **attrs: object) -> None:
        conn = self._require_unlocked()
        allowed = {
            "name", "status", "tlp", "concern_class", "disposition",
            "uca_type", "binding_status", "node_role", "content_text",
        }
        sets: list[str] = ["updated_at = ?"]
        params: list[object] = [_now_iso()]
        for k, v in attrs.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                params.append(v)
            elif k == "attributes":
                sets.append("attributes_json = ?")
                params.append(json.dumps(v))
        params.append(node_id)
        conn.execute(
            f"UPDATE assurance_nodes SET {', '.join(sets)} WHERE node_id = ?", params
        )
        conn.commit()

    def delete_node(self, node_id: str) -> None:
        conn = self._require_unlocked()
        conn.execute("DELETE FROM assurance_nodes WHERE node_id = ?", (node_id,))
        conn.commit()

    # ── Edge CRUD ─────────────────────────────────────────────────────────────

    def list_edges(
        self,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        conn_type: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._require_unlocked()
        where, params = _where({"source_id": source_id, "target_id": target_id, "conn_type": conn_type})
        rows = conn.execute(
            f"SELECT * FROM assurance_edges {where} ORDER BY created_at", params
        ).fetchall()
        return list(rows)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        conn_type: str,
        *,
        attributes: dict[str, object] | None = None,
    ) -> str:
        conn = self._require_unlocked()
        edge_id = make_edge_id(source_id, target_id, conn_type)
        now = _now_iso()
        conn.execute(
            "INSERT INTO assurance_edges (edge_id, source_id, target_id, conn_type, attributes_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (edge_id, source_id, target_id, conn_type, json.dumps(attributes or {}), now),
        )
        conn.commit()
        return edge_id

    def remove_edge(self, edge_id: str) -> None:
        conn = self._require_unlocked()
        conn.execute("DELETE FROM assurance_edges WHERE edge_id = ?", (edge_id,))
        conn.commit()

    # ── Architecture cross-references ──────────────────────────────────────────

    def register_arch_ref(
        self,
        assurance_node_id: str,
        arch_artifact_id: str,
        ref_type: str,
    ) -> None:
        conn = self._require_unlocked()
        conn.execute(
            "INSERT OR REPLACE INTO arch_refs (assurance_node_id, arch_artifact_id, ref_type) "
            "VALUES (?, ?, ?)",
            (assurance_node_id, arch_artifact_id, ref_type),
        )
        conn.commit()

    def mark_arch_ref_resolved(
        self,
        assurance_node_id: str,
        arch_artifact_id: str,
        ref_type: str,
    ) -> None:
        """Set resolved_at timestamp on an existing arch_ref row."""
        conn = self._require_unlocked()
        conn.execute(
            "UPDATE arch_refs SET resolved_at = ? "
            "WHERE assurance_node_id = ? AND arch_artifact_id = ? AND ref_type = ?",
            (_now_iso(), assurance_node_id, arch_artifact_id, ref_type),
        )
        conn.commit()

    def list_arch_refs(
        self,
        *,
        assurance_node_id: str | None = None,
        arch_artifact_id: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._require_unlocked()
        where, params = _where(
            {"assurance_node_id": assurance_node_id, "arch_artifact_id": arch_artifact_id}
        )
        rows = conn.execute(f"SELECT * FROM arch_refs {where}", params).fetchall()
        return list(rows)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, object]:
        conn = self._require_unlocked()
        node_row: dict[str, object] = conn.execute("SELECT COUNT(*) as cnt FROM assurance_nodes").fetchone()
        edge_row: dict[str, object] = conn.execute("SELECT COUNT(*) as cnt FROM assurance_edges").fetchone()
        type_rows = conn.execute(
            "SELECT node_type, COUNT(*) as cnt FROM assurance_nodes GROUP BY node_type"
        ).fetchall()
        return {
            "node_count": node_row["cnt"],
            "edge_count": edge_row["cnt"],
            "by_type": {r["node_type"]: r["cnt"] for r in type_rows},
        }
