"""SQLCipher-backed confidential assurance store adapter.

Key management: the encryption key is retrieved from the secure credential store
(_credential_store). The DB file is stored at the path given at construction
time (typically .arch-assurance/store.db, gitignored).

Thread-safety: the store is a process singleton served by the backend from a pool
of OS threads (the FastAPI/anyio threadpool for sync REST handlers and FastMCP
tool execution). SQLite/SQLCipher connection objects are bound to the thread that
created them, so each accessing thread gets its **own** connection, opened lazily
and cached thread-locally. Connections run in **WAL** mode with a busy timeout, so
concurrent readers do not block one another or the writer. Application-level write
*serialisation* (single-writer discipline) is provided separately by the assurance
write queue at the MCP/REST boundary; this adapter only guarantees that any thread
can safely talk to the store. ``lock()`` disposes every open connection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.infrastructure.assurance import _credential_store as creds
from src.infrastructure.assurance import _sqlcipher_analysis as _analysis
from src.infrastructure.assurance._id_utils import make_edge_id, make_node_id
from src.infrastructure.assurance._schema import ASSURANCE_SCHEMA_MIGRATIONS, ASSURANCE_SCHEMA_SQL, SCHEMA_VERSION
from src.infrastructure.assurance._sqlcipher_connection import ThreadLocalConnectionManager
from src.infrastructure.assurance._sqlcipher_util import now_iso as _now_iso
from src.infrastructure.assurance._sqlcipher_util import suppress_c_stderr as _suppress_c_stderr
from src.infrastructure.assurance._sqlcipher_util import where as _where

logger = logging.getLogger(__name__)

_KEY_ACCOUNT = "db-encryption-key"


class SQLCipherAssuranceStore:
    """Adapter implementing ConfidentialAssuranceStore using SQLCipher.

    Connection lifecycle (per-thread WAL connections, generation-based
    invalidation, disposal on lock) is delegated to ThreadLocalConnectionManager.
    The encryption key is held in process memory only between unlock and lock
    (never written to disk).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conns = ThreadLocalConnectionManager(db_path, bootstrap=self._bootstrap_schema)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def is_unlocked(self) -> bool:
        return self._conns.is_open()

    def unlock(self) -> None:
        key = creds.get(_KEY_ACCOUNT)
        if key is None:
            raise RuntimeError(
                "Assurance store key not found in credential store. "
                "Run `arch-assurance init` to initialise the store."
            )
        self._conns.open(key)
        logger.info("Assurance store unlocked at %s", self._db_path)

    def lock(self) -> None:
        self._conns.close()
        logger.info("Assurance store locked")

    @staticmethod
    def _bootstrap_schema(conn: Any) -> None:
        """Apply schema + migrations on the first connection; key mismatch → RuntimeError."""
        # Suppress C-library 'ERROR CORE ...' output on key mismatch; the
        # RuntimeError below carries the actionable message instead.
        try:
            with _suppress_c_stderr():
                conn.executescript(ASSURANCE_SCHEMA_SQL)
        except Exception as exc:
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

    def _thread_conn_or_none(self) -> Any:
        """Calling thread's connection, or None if locked (archive/signals factory)."""
        return self._conns.get_or_none()

    def _require_unlocked(self) -> Any:
        return self._conns.require()

    def unlocked_connection(self) -> Any:
        """Public handle to the unlocked DB connection for bulk portability operations."""
        return self._require_unlocked()

    # ── Analysis aggregate ──────────────────────────────────────────────────────

    def create_analysis(
        self,
        name: str,
        method: str,
        architecture_anchor_id: str = "",
        *,
        tlp: str = "TLP:WHITE",
        status: str = "draft",
    ) -> str:
        return _analysis.create(
            self._require_unlocked(), name, method, architecture_anchor_id, tlp=tlp, status=status
        )

    def get_analysis(self, analysis_id: str) -> dict[str, object] | None:
        return _analysis.get(self._require_unlocked(), analysis_id)

    def list_analyses(
        self,
        *,
        method: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        return _analysis.list_analyses(self._require_unlocked(), method=method, status=status)

    def update_analysis(self, analysis_id: str, **attrs: object) -> None:
        _analysis.update(self._require_unlocked(), analysis_id, attrs)

    def delete_analysis(self, analysis_id: str) -> None:
        _analysis.delete(self._require_unlocked(), analysis_id)

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
        analysis_id: str | None = None,
    ) -> list[dict[str, object]]:
        conn = self._require_unlocked()
        where, params = _where(
            {
                "node_type": node_type, "status": status, "concern_class": concern_class,
                "tlp": tlp, "analysis_id": analysis_id,
            }
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
        analysis_id: str | None = None,
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
                 uca_type, binding_status, node_role, analysis_id, attributes_json,
                 content_text, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id, node_type, name, status, tlp, concern_class, disposition,
                uca_type, binding_status, node_role, analysis_id,
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

    def search_nodes(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        conn = self._require_unlocked()
        pattern = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM assurance_nodes
               WHERE name LIKE ? OR content_text LIKE ?
               ORDER BY
                   CASE WHEN name LIKE ? THEN 0 ELSE 1 END,
                   created_at
               LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
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
