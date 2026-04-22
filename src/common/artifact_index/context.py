from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from src.common.artifact_parsing import parse_diagram, parse_document, parse_entity, parse_outgoing_file
from src.common.ontology_loader import SYMMETRIC_CONNECTIONS
from src.common.artifact_types import ConnectionRecord

from .types import EntityContextConnection, EntityContextCounts, EntityContextReadModel

if TYPE_CHECKING:
    from .service import ArtifactIndex


def rebuild_entity_context_projection(index: "ArtifactIndex") -> None:
    rows = [
        row
        for rec in index._connections.values()
        for row in entity_context_rows_for_connection(index, rec)
    ]
    if rows:
        index._conn.executemany(
            """
            INSERT INTO entity_context_edges (
                entity_id, connection_id, direction_bucket, other_entity_id, conn_type,
                connection_status, source_id, target_id, source_name, target_name,
                source_artifact_type, target_artifact_type, source_domain, target_domain,
                source_scope, target_scope, path, content_text, associated_entities_json,
                src_cardinality, tgt_cardinality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    index._conn.execute(
        """
        INSERT INTO entity_context_stats (entity_id, conn_in, conn_out, conn_sym)
        SELECT
            entity_id,
            SUM(CASE WHEN direction_bucket = 'inbound' THEN 1 ELSE 0 END) AS conn_in,
            SUM(CASE WHEN direction_bucket = 'outbound' THEN 1 ELSE 0 END) AS conn_out,
            SUM(CASE WHEN direction_bucket = 'symmetric' THEN 1 ELSE 0 END) AS conn_sym
        FROM entity_context_edges
        GROUP BY entity_id
        """
    )


def entity_context_rows_for_connection(index: "ArtifactIndex", rec: ConnectionRecord) -> list[tuple[str, ...]]:
    src = index._entities.get(rec.source)
    tgt = index._entities.get(rec.target)
    shared = (
        rec.conn_type,
        rec.status,
        rec.source,
        rec.target,
        src.name if src is not None and src.name else rec.source,
        tgt.name if tgt is not None and tgt.name else rec.target,
        src.artifact_type if src is not None else "unknown",
        tgt.artifact_type if tgt is not None else "unknown",
        src.domain if src is not None else "unknown",
        tgt.domain if tgt is not None else "unknown",
        index.scope_for_path(src.path) if src is not None else "unknown",
        index.scope_for_path(tgt.path) if tgt is not None else "unknown",
        str(rec.path),
        rec.content_text,
        json.dumps(list(rec.associated_entities)),
        rec.src_cardinality,
        rec.tgt_cardinality,
    )
    if rec.conn_type in SYMMETRIC_CONNECTIONS:
        rows = [(rec.source, rec.artifact_id, "symmetric", rec.target, *shared)]
        if rec.target != rec.source:
            rows.append((rec.target, rec.artifact_id, "symmetric", rec.source, *shared))
        return rows
    return [
        (rec.source, rec.artifact_id, "outbound", rec.target, *shared),
        (rec.target, rec.artifact_id, "inbound", rec.source, *shared),
    ]


def rebuild_entity_context_for(index: "ArtifactIndex", entity_id: str) -> None:
    index._ensure_loaded()
    with index._lock, index._conn:
        index._conn.execute("DELETE FROM entity_context_edges WHERE entity_id = ?", (entity_id,))
        for rec in index._connections.values():
            for row in entity_context_rows_for_connection(index, rec):
                if row[0] == entity_id:
                    index._conn.execute(
                        """
                        INSERT INTO entity_context_edges (
                            entity_id, connection_id, direction_bucket, other_entity_id, conn_type,
                            connection_status, source_id, target_id, source_name, target_name,
                            source_artifact_type, target_artifact_type, source_domain, target_domain,
                            source_scope, target_scope, path, content_text, associated_entities_json,
                            src_cardinality, tgt_cardinality
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        row,
                    )
        recompute_entity_context_stats(index, entity_id)


def recompute_entity_context_stats(index: "ArtifactIndex", entity_id: str) -> None:
    index._conn.execute("DELETE FROM entity_context_stats WHERE entity_id = ?", (entity_id,))
    index._conn.execute(
        """
        INSERT INTO entity_context_stats (entity_id, conn_in, conn_out, conn_sym)
        SELECT
            entity_id,
            SUM(CASE WHEN direction_bucket = 'inbound' THEN 1 ELSE 0 END) AS conn_in,
            SUM(CASE WHEN direction_bucket = 'outbound' THEN 1 ELSE 0 END) AS conn_out,
            SUM(CASE WHEN direction_bucket = 'symmetric' THEN 1 ELSE 0 END) AS conn_sym
        FROM entity_context_edges
        WHERE entity_id = ?
        GROUP BY entity_id
        """,
        (entity_id,),
    )


def apply_entity_file_change(index: "ArtifactIndex", path: Path, *, bump_generation: bool = True) -> None:
    index._ensure_loaded()
    with index._lock:
        old_record = next((rec for rec in index._entities.values() if rec.path == path), None)
        model_root = index._model_root_for_path(path)
        new_record = parse_entity(path, model_root) if path.exists() and model_root is not None else None
        impacted_ids: set[str] = set()
        if old_record is not None:
            impacted_ids.add(old_record.artifact_id)
            impacted_ids.update(
                rec.source if rec.source != old_record.artifact_id else rec.target
                for rec in index._connections.values()
                if old_record.artifact_id in (rec.source, rec.target)
            )
            if new_record is None or old_record.artifact_id != new_record.artifact_id:
                index._delete_entity_record(old_record.artifact_id)
        if new_record is not None:
            index._upsert_entity_record(new_record)
            impacted_ids.add(new_record.artifact_id)
            impacted_ids.update(
                rec.source if rec.source != new_record.artifact_id else rec.target
                for rec in index._connections.values()
                if new_record.artifact_id in (rec.source, rec.target)
            )
        for entity_id in sorted(impacted_ids):
            rebuild_entity_context_for(index, entity_id)
        if bump_generation:
            index._bump_generation()


def apply_outgoing_file_change(index: "ArtifactIndex", path: Path, *, bump_generation: bool = True) -> None:
    index._ensure_loaded()
    with index._lock:
        old_records = [rec for rec in index._connections.values() if rec.path == path]
        old_by_id = {rec.artifact_id: rec for rec in old_records}
        new_records = parse_outgoing_file(path) if path.exists() else []
        new_by_id = {rec.artifact_id: rec for rec in new_records}
        affected_entities = {
            entity_id
            for rec in old_records + new_records
            for entity_id in (rec.source, rec.target)
        }
        for artifact_id in sorted(set(old_by_id) - set(new_by_id)):
            index._delete_connection_record(artifact_id)
        for rec in new_records:
            index._upsert_connection_record(rec)
        for entity_id in sorted(affected_entities):
            rebuild_entity_context_for(index, entity_id)
        if bump_generation:
            index._bump_generation()


def apply_diagram_file_change(index: "ArtifactIndex", path: Path, *, bump_generation: bool = True) -> None:
    index._ensure_loaded()
    with index._lock:
        old_record = next((rec for rec in index._diagrams.values() if rec.path == path), None)
        new_record = parse_diagram(path) if path.exists() else None
        if old_record is not None and (new_record is None or old_record.artifact_id != new_record.artifact_id):
            index._delete_diagram_record(old_record.artifact_id)
        if new_record is not None:
            index._upsert_diagram_record(new_record)
        if bump_generation:
            index._bump_generation()


def apply_document_file_change(index: "ArtifactIndex", path: Path, *, bump_generation: bool = True) -> None:
    index._ensure_loaded()
    with index._lock:
        old_record = next((rec for rec in index._documents.values() if rec.path == path), None)
        new_record = parse_document(path) if path.exists() else None
        if old_record is not None and (new_record is None or old_record.artifact_id != new_record.artifact_id):
            index._delete_document_record(old_record.artifact_id)
        if new_record is not None:
            index._upsert_document_record(new_record)
        if bump_generation:
            index._bump_generation()


def read_entity_context(index: "ArtifactIndex", entity_id: str) -> EntityContextReadModel | None:
    index._ensure_loaded()
    entity = index._entities.get(entity_id)
    if entity is None:
        return None
    counts_row = index._conn.execute(
        "SELECT conn_in, conn_out, conn_sym FROM entity_context_stats WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    counts: EntityContextCounts = {
        "conn_in": int(counts_row["conn_in"]) if counts_row is not None else 0,
        "conn_out": int(counts_row["conn_out"]) if counts_row is not None else 0,
        "conn_sym": int(counts_row["conn_sym"]) if counts_row is not None else 0,
    }
    grouped: dict[str, list[EntityContextConnection]] = {"outbound": [], "inbound": [], "symmetric": []}
    rows = index._conn.execute(
        """
        SELECT *
        FROM entity_context_edges
        WHERE entity_id = ?
        ORDER BY direction_bucket, connection_id
        """,
        (entity_id,),
    ).fetchall()
    for row in rows:
        record = index._connections[str(row["connection_id"])]
        grouped[str(row["direction_bucket"])].append(
            {
                "artifact_id": str(row["connection_id"]),
                "source": str(row["source_id"]),
                "target": str(row["target_id"]),
                "conn_type": str(row["conn_type"]),
                "version": record.version,
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
        "entity": {
            "artifact_id": entity.artifact_id,
            "artifact_type": entity.artifact_type,
            "name": entity.name,
            "version": entity.version,
            "status": entity.status,
            "domain": entity.domain,
            "subdomain": entity.subdomain,
            "record_type": "entity",
            "path": str(entity.path),
            "content_snippet": entity.content_text[:240],
            "keywords": list(entity.keywords),
            "content_text": entity.content_text,
            "display_blocks": entity.display_blocks,
            "extra": entity.extra,
        },
        "connections": grouped,
        "counts": counts,
        "generation": index._generation,
        "etag": index.read_model_version().etag,
    }
