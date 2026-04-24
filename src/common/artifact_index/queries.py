from __future__ import annotations

from typing import TYPE_CHECKING

from src.common.artifact_scoring import tokenize

if TYPE_CHECKING:
    from .service import ArtifactIndex


def find_connection_ids_for(index: "ArtifactIndex", entity_id: str, *, direction: str = "any", conn_type: str | None = None) -> list[str]:
    index._ensure_loaded()
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
    sql = "SELECT DISTINCT connection_id AS artifact_id FROM entity_context_edges WHERE " + " AND ".join(where) + " ORDER BY artifact_id"
    with index._lock:
        rows = index._conn.execute(sql, params).fetchall()
    return [str(row["artifact_id"]) for row in rows]


def search_artifacts(
    index: "ArtifactIndex",
    query: str,
    *,
    limit: int = 10,
    include_connections: bool = True,
    include_diagrams: bool = True,
    include_documents: bool = True,
    prefer_record_type: str | None = None,
    strict_record_type: bool = False,
) -> list[tuple[str, str, float]]:
    index._ensure_loaded()
    tokens = tokenize(query.lower())
    if not tokens or not index._fts_enabled:
        return []
    match_query = " OR ".join(f'"{token}"' for token in tokens)
    statements = ["SELECT artifact_id, 'entity' AS record_type, 1.0 / (1.0 + bm25(entities_fts)) AS score FROM entities_fts WHERE entities_fts MATCH ?"]
    params: list[str] = [match_query]
    if include_connections:
        statements.append("SELECT artifact_id, 'connection' AS record_type, 1.0 / (1.0 + bm25(connections_fts)) AS score FROM connections_fts WHERE connections_fts MATCH ?")
        params.append(match_query)
    if include_diagrams:
        statements.append("SELECT artifact_id, 'diagram' AS record_type, 1.0 / (1.0 + bm25(diagrams_fts)) AS score FROM diagrams_fts WHERE diagrams_fts MATCH ?")
        params.append(match_query)
    if include_documents:
        statements.append("SELECT artifact_id, 'document' AS record_type, 1.0 / (1.0 + bm25(documents_fts)) AS score FROM documents_fts WHERE documents_fts MATCH ?")
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
    with index._lock:
        rows = index._conn.execute(sql, params).fetchall()
    return [(str(r["artifact_id"]), str(r["record_type"]), float(r["score"])) for r in rows]


def find_neighbors(index: "ArtifactIndex", entity_id: str, *, max_hops: int = 1, conn_type: str | None = None) -> dict[str, set[str]]:
    index._ensure_loaded()
    if max_hops < 1:
        return {}
    with index._lock:
        rows = index._conn.execute(
            """
            WITH RECURSIVE walk(depth, entity_id, visited) AS (
                SELECT 0, ?, ',' || ? || ','
                UNION ALL
                SELECT
                    walk.depth + 1,
                    CASE WHEN connections.source = walk.entity_id THEN connections.target ELSE connections.source END,
                    walk.visited || CASE WHEN connections.source = walk.entity_id THEN connections.target ELSE connections.source END || ','
                FROM walk
                JOIN connections ON (connections.source = walk.entity_id OR connections.target = walk.entity_id)
                WHERE walk.depth < ?
                  AND (? IS NULL OR connections.conn_type = ?)
                  AND instr(walk.visited, ',' || CASE WHEN connections.source = walk.entity_id THEN connections.target ELSE connections.source END || ',') = 0
            )
            SELECT depth, entity_id FROM walk WHERE depth > 0
            """,
            (entity_id, entity_id, max_hops, conn_type, conn_type),
        ).fetchall()
    result: dict[str, set[str]] = {}
    for row in rows:
        result.setdefault(str(int(row["depth"])), set()).add(str(row["entity_id"]))
    return result
