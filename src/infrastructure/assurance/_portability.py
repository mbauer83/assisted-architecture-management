"""Bulk export/import of the confidential assurance graph (portability + seeding).

`export_bundle` collects analyses, nodes, edges, and arch-refs; `import_bundle` restores
them into whatever store the environment provisions. Ids are preserved verbatim so edges
and arch-refs keep resolving — the round-trip reconstructs an identical graph, re-encrypted
under the target store's own key. Column allowlists keep the dynamic SQL injection-safe;
parents are inserted before children so the foreign-key constraints hold.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.assurance._sqlcipher_store import SQLCipherAssuranceStore

# Column allowlists per table — the only names interpolated into SQL.
_ANALYSIS_COLS = (
    "analysis_id", "name", "method", "architecture_anchor_id", "status", "tlp",
    "created_at", "updated_at",
)
_NODE_COLS = (
    "node_id", "node_type", "name", "status", "tlp", "concern_class", "disposition",
    "uca_type", "binding_status", "node_role", "analysis_id", "attributes_json",
    "content_text", "created_at", "updated_at", "created_by",
)
_EDGE_COLS = ("edge_id", "source_id", "target_id", "conn_type", "attributes_json", "created_at")
_REF_COLS = ("assurance_node_id", "arch_artifact_id", "ref_type", "resolved_at")

# Children before parents on delete; parents before children on insert (FK-safe ordering).
_DELETE_ORDER = ("assurance_edges", "arch_refs", "assurance_nodes", "assurance_analyses")


def export_bundle(store: SQLCipherAssuranceStore) -> dict[str, list[dict[str, object]]]:
    """Collect the full assurance graph as plain dict rows. Requires an unlocked store."""
    if not store.is_unlocked():
        raise RuntimeError("Store must be unlocked before export.")
    return {
        "analyses": store.list_analyses(),
        "nodes": store.list_nodes(),
        "edges": store.list_edges(),
        "arch_refs": store.list_arch_refs(),
    }


def _insert_rows(conn: object, table: str, cols: tuple[str, ...], rows: list[dict[str, object]]) -> int:
    written = 0
    for row in rows:
        present = [c for c in cols if c in row]
        if not present:
            continue
        placeholders = ", ".join(["?"] * len(present))
        conn.execute(  # type: ignore[attr-defined]
            f"INSERT OR REPLACE INTO {table} ({', '.join(present)}) VALUES ({placeholders})",
            [row[c] for c in present],
        )
        written += 1
    return written


def import_bundle(
    store: SQLCipherAssuranceStore,
    bundle: dict[str, list[dict[str, object]]],
    *,
    replace: bool = False,
) -> dict[str, int]:
    """Insert an exported bundle into *store*, preserving ids. Requires an unlocked store.

    With ``replace=True`` the existing graph is cleared first (children before parents) so
    a re-seed is idempotent rather than additive.
    """
    if not store.is_unlocked():
        raise RuntimeError("Store must be unlocked before import.")
    conn = store.unlocked_connection()
    if replace:
        for table in _DELETE_ORDER:
            conn.execute(f"DELETE FROM {table}")
    counts = {
        "analyses": _insert_rows(conn, "assurance_analyses", _ANALYSIS_COLS, bundle.get("analyses", [])),
        "nodes": _insert_rows(conn, "assurance_nodes", _NODE_COLS, bundle.get("nodes", [])),
        "edges": _insert_rows(conn, "assurance_edges", _EDGE_COLS, bundle.get("edges", [])),
        "arch_refs": _insert_rows(conn, "arch_refs", _REF_COLS, bundle.get("arch_refs", [])),
    }
    conn.commit()  # type: ignore[attr-defined]
    return counts
