from __future__ import annotations

import json
import sqlite3

from src.application.artifact_scoring import tokenize

from .types import EntityContextConnection, EntityContextCounts, EntityContextReadModel


def search_fts(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int,
    include_connections: bool,
    include_diagrams: bool,
    include_documents: bool,
    prefer_record_type: str | None,
    strict_record_type: bool,
    fts_enabled: bool,
) -> list[tuple[str, str, float]]:
    tokens = tokenize(query.lower())
    if not tokens or not fts_enabled:
        return []
    match_query = " OR ".join(f'"{token}"' for token in tokens)
    statements = [
        "SELECT artifact_id, 'entity' AS record_type, "
        "1.0 / (1.0 + bm25(entities_fts)) AS score "
        "FROM entities_fts WHERE entities_fts MATCH ?"
    ]
    params: list[str] = [match_query]
    if include_connections:
        statements.append(
            "SELECT artifact_id, 'connection' AS record_type, "
            "1.0 / (1.0 + bm25(connections_fts)) AS score "
            "FROM connections_fts WHERE connections_fts MATCH ?"
        )
        params.append(match_query)
    if include_diagrams:
        statements.append(
            "SELECT artifact_id, 'diagram' AS record_type, "
            "1.0 / (1.0 + bm25(diagrams_fts)) AS score "
            "FROM diagrams_fts WHERE diagrams_fts MATCH ?"
        )
        params.append(match_query)
    if include_documents:
        statements.append(
            "SELECT artifact_id, 'document' AS record_type, "
            "1.0 / (1.0 + bm25(documents_fts)) AS score "
            "FROM documents_fts WHERE documents_fts MATCH ?"
        )
        params.append(match_query)
    sql = "SELECT artifact_id, record_type, score FROM (" + " UNION ALL ".join(statements) + ")"
    if strict_record_type and prefer_record_type is not None:
        sql += " WHERE record_type = ?"
        params.append(prefer_record_type)
    sql += " ORDER BY "
    if prefer_record_type is not None and not strict_record_type:
        sql += "CASE WHEN record_type = ? THEN 1 ELSE 0 END DESC, "
        params.append(prefer_record_type)
    sql += "score DESC, artifact_id ASC LIMIT ?"
    params.append(str(max(limit, 0)))
    rows = conn.execute(sql, params).fetchall()
    return [(str(r["artifact_id"]), str(r["record_type"]), float(r["score"])) for r in rows]


def all_connection_stats(conn: sqlite3.Connection) -> dict[str, tuple[int, int, int]]:
    rows = conn.execute(
        "SELECT entity_id, conn_in, conn_sym, conn_out FROM entity_context_stats"
    ).fetchall()
    return {
        str(r["entity_id"]): (int(r["conn_in"]), int(r["conn_sym"]), int(r["conn_out"]))
        for r in rows
    }


def connection_stats_for(conn: sqlite3.Connection, entity_id: str) -> tuple[int, int, int]:
    row = conn.execute(
        "SELECT conn_in, conn_sym, conn_out FROM entity_context_stats WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if row is None:
        return (0, 0, 0)
    return (int(row["conn_in"]), int(row["conn_sym"]), int(row["conn_out"]))


def connection_ids_by_types(conn: sqlite3.Connection, types: frozenset[str]) -> list[str]:
    if not types:
        return []
    placeholders = ",".join("?" * len(types))
    sql = (
        f"SELECT artifact_id FROM connections WHERE conn_type IN ({placeholders})"
        " ORDER BY artifact_id"
    )
    rows = conn.execute(sql, tuple(types)).fetchall()
    return [str(row["artifact_id"]) for row in rows]


def connection_ids_for(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    direction: str = "any",
    conn_type: str | None = None,
) -> list[str]:
    where = ["entity_id = ?"]
    params: list[str] = [entity_id]
    if direction == "outbound":
        where.append("direction_bucket = 'outbound'")
    elif direction == "inbound":
        where.append("direction_bucket = 'inbound'")
    elif direction != "any":
        raise ValueError(f"Unsupported direction: {direction!r}")
    if conn_type is not None:
        where.append("conn_type = ?")
        params.append(conn_type)
    sql = (
        "SELECT DISTINCT connection_id AS artifact_id FROM entity_context_edges WHERE "
        + " AND ".join(where)
        + " ORDER BY artifact_id"
    )
    rows = conn.execute(sql, params).fetchall()
    return [str(row["artifact_id"]) for row in rows]


def connections_for_entity_set(
    conn: sqlite3.Connection,
    entity_ids: frozenset[str],
) -> list[dict]:
    """Single query returning all entity_context_edges rows touching any entity in the set."""
    if not entity_ids:
        return []
    phs = ",".join("?" * len(entity_ids))
    rows = conn.execute(
        f"SELECT * FROM entity_context_edges WHERE entity_id IN ({phs})",
        tuple(entity_ids),
    ).fetchall()
    # Deduplicate by connection_id; prefer outbound perspective when multiple rows exist
    seen: dict[str, dict] = {}
    for row in rows:
        cid = str(row["connection_id"])
        existing = seen.get(cid)
        if existing is None or str(row["direction_bucket"]) == "outbound":
            seen[cid] = dict(row)
    return list(seen.values())


def find_neighbors(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    max_hops: int,
    conn_type: str | None,
) -> dict[str, set[str]]:
    if max_hops < 1:
        return {}
    rows = conn.execute(
        """
        WITH RECURSIVE walk(depth, entity_id, visited) AS (
            SELECT 0, ?, ',' || ? || ','
            UNION ALL
            SELECT
                walk.depth + 1,
                CASE WHEN connections.source = walk.entity_id
                     THEN connections.target ELSE connections.source END,
                walk.visited
                    || CASE WHEN connections.source = walk.entity_id
                            THEN connections.target ELSE connections.source END
                    || ','
            FROM walk
            JOIN connections ON (
                connections.source = walk.entity_id
                OR connections.target = walk.entity_id
            )
            WHERE walk.depth < ?
              AND (? IS NULL OR connections.conn_type = ?)
              AND instr(walk.visited,
                  ',' || CASE WHEN connections.source = walk.entity_id
                              THEN connections.target ELSE connections.source END
                  || ',') = 0
        )
        SELECT depth, entity_id FROM walk WHERE depth > 0
        """,
        (entity_id, entity_id, max_hops, conn_type, conn_type),
    ).fetchall()
    result: dict[str, set[str]] = {}
    for row in rows:
        result.setdefault(str(int(row["depth"])), set()).add(str(row["entity_id"]))
    return result


def entity_context(
    conn: sqlite3.Connection,
    entity_id: str,
    entity_data: dict[str, object],
    generation: int,
    etag: str,
) -> EntityContextReadModel | None:
    counts_row = conn.execute(
        "SELECT conn_in, conn_out, conn_sym FROM entity_context_stats WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    counts: EntityContextCounts = {
        "conn_in": int(counts_row["conn_in"]) if counts_row is not None else 0,
        "conn_out": int(counts_row["conn_out"]) if counts_row is not None else 0,
        "conn_sym": int(counts_row["conn_sym"]) if counts_row is not None else 0,
    }
    grouped: dict[str, list[EntityContextConnection]] = {
        "outbound": [],
        "inbound": [],
        "symmetric": [],
    }
    rows = conn.execute(
        """
        SELECT *
        FROM entity_context_edges
        WHERE entity_id = ?
        ORDER BY direction_bucket, connection_id
        """,
        (entity_id,),
    ).fetchall()
    for row in rows:
        grouped[str(row["direction_bucket"])].append(
            {
                "artifact_id": str(row["connection_id"]),
                "source": str(row["source_id"]),
                "target": str(row["target_id"]),
                "conn_type": str(row["conn_type"]),
                "version": str(row["connection_version"]),
                "status": str(row["connection_status"]),
                "path": str(row["path"]),
                "content_text": str(row["content_text"]),
                "associated_entities": json.loads(str(row["associated_entities_json"])),
                "src_cardinality": str(row["src_cardinality"]),
                "tgt_cardinality": str(row["tgt_cardinality"]),
                "source_name": str(row["source_name"]),
                "target_name": str(row["target_name"]),
                "source_artifact_type": str(row["source_artifact_type"]),
                "target_artifact_type": str(row["target_artifact_type"]),
                "source_domain": str(row["source_domain"]),
                "target_domain": str(row["target_domain"]),
                "source_scope": str(row["source_scope"]),
                "target_scope": str(row["target_scope"]),
                "other_entity_id": str(row["other_entity_id"]),
                "direction": str(row["direction_bucket"]),
            }
        )
    return {
        "entity": entity_data,
        "connections": grouped,
        "counts": counts,
        "generation": generation,
        "etag": etag,
    }
