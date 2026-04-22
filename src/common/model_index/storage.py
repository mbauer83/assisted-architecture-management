from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.common.model_query_types import ConnectionRecord, DiagramRecord, EntityRecord

from .schema import init_db

if TYPE_CHECKING:
    from .service import ModelIndex


def rebuild_sqlite(index: "ModelIndex") -> None:
    with index._conn:
        index._conn.execute("DELETE FROM entities")
        index._conn.execute("DELETE FROM connections")
        index._conn.execute("DELETE FROM diagrams")
        index._conn.execute("DELETE FROM entity_context_edges")
        index._conn.execute("DELETE FROM entity_context_stats")
        if index._fts_enabled:
            index._conn.execute("DELETE FROM entities_fts")
            index._conn.execute("DELETE FROM connections_fts")
            index._conn.execute("DELETE FROM diagrams_fts")

        index._conn.executemany(
            """
            INSERT INTO entities (
                artifact_id, artifact_type, name, version, status, domain, subdomain,
                path, scope, keywords_json, extra_json, content_text,
                display_blocks_json, display_label, display_alias
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_entity_row(index, rec) for rec in index._entities.values()],
        )
        index._conn.executemany(
            """
            INSERT INTO connections (
                artifact_id, source, target, conn_type, version, status,
                path, scope, extra_json, content_text,
                associated_entities_json, src_cardinality, tgt_cardinality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_connection_row(index, rec) for rec in index._connections.values()],
        )
        index._conn.executemany(
            """
            INSERT INTO diagrams (
                artifact_id, artifact_type, name, diagram_type, version, status,
                path, scope, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    rec.artifact_id,
                    rec.artifact_type,
                    rec.name,
                    rec.diagram_type,
                    rec.version,
                    rec.status,
                    str(rec.path),
                    index.scope_for_path(rec.path),
                    json.dumps(rec.extra, sort_keys=True),
                )
                for rec in index._diagrams.values()
            ],
        )
        if index._fts_enabled:
            index._conn.executemany(
                """
                INSERT INTO entities_fts (
                    artifact_id, name, artifact_type, domain, subdomain, keywords, content_text, display_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        rec.artifact_id,
                        rec.name,
                        rec.artifact_type,
                        rec.domain,
                        rec.subdomain,
                        " ".join(rec.keywords),
                        rec.content_text,
                        rec.display_label,
                    )
                    for rec in index._entities.values()
                ],
            )
            index._conn.executemany(
                """
                INSERT INTO connections_fts (
                    artifact_id, source, target, conn_type, content_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (rec.artifact_id, rec.source, rec.target, rec.conn_type, rec.content_text)
                    for rec in index._connections.values()
                ],
            )
            index._conn.executemany(
                """
                INSERT INTO diagrams_fts (
                    artifact_id, name, diagram_type, artifact_type
                ) VALUES (?, ?, ?, ?)
                """,
                [(rec.artifact_id, rec.name, rec.diagram_type, rec.artifact_type) for rec in index._diagrams.values()],
            )
    index._rebuild_entity_context_projection()


def upsert_entity_record(index: "ModelIndex", rec: EntityRecord) -> None:
    index._entities[rec.artifact_id] = rec
    with index._conn:
        index._conn.execute("DELETE FROM entities WHERE artifact_id = ?", (rec.artifact_id,))
        index._conn.execute(
            """
            INSERT INTO entities (
                artifact_id, artifact_type, name, version, status, domain, subdomain,
                path, scope, keywords_json, extra_json, content_text,
                display_blocks_json, display_label, display_alias
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _entity_row(index, rec),
        )
        if index._fts_enabled:
            index._conn.execute("DELETE FROM entities_fts WHERE artifact_id = ?", (rec.artifact_id,))
            index._conn.execute(
                """
                INSERT INTO entities_fts (
                    artifact_id, name, artifact_type, domain, subdomain, keywords, content_text, display_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.artifact_id,
                    rec.name,
                    rec.artifact_type,
                    rec.domain,
                    rec.subdomain,
                    " ".join(rec.keywords),
                    rec.content_text,
                    rec.display_label,
                ),
            )


def delete_entity_record(index: "ModelIndex", artifact_id: str) -> None:
    index._entities.pop(artifact_id, None)
    with index._conn:
        index._conn.execute("DELETE FROM entities WHERE artifact_id = ?", (artifact_id,))
        index._conn.execute("DELETE FROM entity_context_edges WHERE entity_id = ?", (artifact_id,))
        index._conn.execute("DELETE FROM entity_context_stats WHERE entity_id = ?", (artifact_id,))
        if index._fts_enabled:
            index._conn.execute("DELETE FROM entities_fts WHERE artifact_id = ?", (artifact_id,))


def upsert_connection_record(index: "ModelIndex", rec: ConnectionRecord) -> None:
    index._connections[rec.artifact_id] = rec
    with index._conn:
        index._conn.execute("DELETE FROM connections WHERE artifact_id = ?", (rec.artifact_id,))
        index._conn.execute(
            """
            INSERT INTO connections (
                artifact_id, source, target, conn_type, version, status,
                path, scope, extra_json, content_text,
                associated_entities_json, src_cardinality, tgt_cardinality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _connection_row(index, rec),
        )
        if index._fts_enabled:
            index._conn.execute("DELETE FROM connections_fts WHERE artifact_id = ?", (rec.artifact_id,))
            index._conn.execute(
                """
                INSERT INTO connections_fts (
                    artifact_id, source, target, conn_type, content_text
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (rec.artifact_id, rec.source, rec.target, rec.conn_type, rec.content_text),
            )


def delete_connection_record(index: "ModelIndex", artifact_id: str) -> None:
    index._connections.pop(artifact_id, None)
    with index._conn:
        index._conn.execute("DELETE FROM connections WHERE artifact_id = ?", (artifact_id,))
        index._conn.execute("DELETE FROM entity_context_edges WHERE connection_id = ?", (artifact_id,))
        if index._fts_enabled:
            index._conn.execute("DELETE FROM connections_fts WHERE artifact_id = ?", (artifact_id,))


def upsert_diagram_record(index: "ModelIndex", rec: DiagramRecord) -> None:
    index._diagrams[rec.artifact_id] = rec
    with index._conn:
        index._conn.execute("DELETE FROM diagrams WHERE artifact_id = ?", (rec.artifact_id,))
        index._conn.execute(
            """
            INSERT INTO diagrams (
                artifact_id, artifact_type, name, diagram_type, version, status,
                path, scope, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rec.artifact_id,
                rec.artifact_type,
                rec.name,
                rec.diagram_type,
                rec.version,
                rec.status,
                str(rec.path),
                index.scope_for_path(rec.path),
                json.dumps(rec.extra, sort_keys=True),
            ),
        )
        if index._fts_enabled:
            index._conn.execute("DELETE FROM diagrams_fts WHERE artifact_id = ?", (rec.artifact_id,))
            index._conn.execute(
                """
                INSERT INTO diagrams_fts (
                    artifact_id, name, diagram_type, artifact_type
                ) VALUES (?, ?, ?, ?)
                """,
                (rec.artifact_id, rec.name, rec.diagram_type, rec.artifact_type),
            )


def delete_diagram_record(index: "ModelIndex", artifact_id: str) -> None:
    index._diagrams.pop(artifact_id, None)
    with index._conn:
        index._conn.execute("DELETE FROM diagrams WHERE artifact_id = ?", (artifact_id,))
        if index._fts_enabled:
            index._conn.execute("DELETE FROM diagrams_fts WHERE artifact_id = ?", (artifact_id,))


def _entity_row(index: "ModelIndex", rec: EntityRecord) -> tuple[str, ...]:
    return (
        rec.artifact_id,
        rec.artifact_type,
        rec.name,
        rec.version,
        rec.status,
        rec.domain,
        rec.subdomain,
        str(rec.path),
        index.scope_for_path(rec.path),
        json.dumps(list(rec.keywords)),
        json.dumps(rec.extra, sort_keys=True),
        rec.content_text,
        json.dumps(rec.display_blocks, sort_keys=True),
        rec.display_label,
        rec.display_alias,
    )


def _connection_row(index: "ModelIndex", rec: ConnectionRecord) -> tuple[str, ...]:
    return (
        rec.artifact_id,
        rec.source,
        rec.target,
        rec.conn_type,
        rec.version,
        rec.status,
        str(rec.path),
        index.scope_for_path(rec.path),
        json.dumps(rec.extra, sort_keys=True),
        rec.content_text,
        json.dumps(list(rec.associated_entities)),
        rec.src_cardinality,
        rec.tgt_cardinality,
    )
