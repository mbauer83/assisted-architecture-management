"""Shared runtime SQLite-backed index for entities, connections, and diagrams."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import cast, overload

from src.common.model_query_parsing import parse_diagram, parse_entity, parse_outgoing_file
from src.common.model_query_scoring import tokenize
from src.common.model_query_types import (
    ConnectionRecord,
    DiagramRecord,
    DuplicateArtifactIdError,
    EntityRecord,
    RepoMount,
    infer_mount,
)


def _normalize_mounts(repo_root: Path | list[Path] | list[RepoMount]) -> list[RepoMount]:
    if isinstance(repo_root, Path):
        mounts: list[RepoMount] = [infer_mount(repo_root)]
    else:
        mounts = [m if isinstance(m, RepoMount) else infer_mount(m) for m in repo_root]

    roots = [m.root for m in mounts]
    if len(set(map(str, roots))) != len(roots):
        raise ValueError("Duplicate repo root in ModelIndex mounts")
    return mounts


def _service_key(mounts: list[RepoMount]) -> str:
    return "|".join(str(m.root.resolve()) for m in mounts)


_services: dict[str, ModelIndex] = {}
_services_mu = threading.Lock()


def shared_model_index(repo_root: Path | list[Path] | list[RepoMount]) -> ModelIndex:
    mounts = _normalize_mounts(repo_root)
    key = _service_key(mounts)
    with _services_mu:
        service = _services.get(key)
        if service is None:
            service = ModelIndex(mounts)
            _services[key] = service
        return service


class ModelIndex:
    def __init__(self, repo_root: Path | list[Path] | list[RepoMount]) -> None:
        mounts = _normalize_mounts(repo_root)
        self.repo_mounts = mounts
        self.repo_roots = [m.root for m in mounts]
        self.repo_root = mounts[0].root
        self._entities: dict[str, EntityRecord] = {}
        self._connections: dict[str, ConnectionRecord] = {}
        self._diagrams: dict[str, DiagramRecord] = {}
        self._loaded = False
        self._last_fingerprint = ""
        self._lock = threading.RLock()
        self._fts_enabled = True
        name_hash = hashlib.blake2b(_service_key(mounts).encode("utf-8"), digest_size=10).hexdigest()
        self._conn = sqlite3.connect(
            f"file:arch-model-index-{name_hash}?mode=memory&cache=shared",
            uri=True,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                PRAGMA journal_mode = MEMORY;
                PRAGMA synchronous = OFF;
                PRAGMA temp_store = MEMORY;
                PRAGMA foreign_keys = OFF;

                CREATE TABLE IF NOT EXISTS entities (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    subdomain TEXT NOT NULL,
                    path TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    extra_json TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    display_blocks_json TEXT NOT NULL,
                    display_label TEXT NOT NULL,
                    display_alias TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS connections (
                    artifact_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    conn_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    path TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    extra_json TEXT NOT NULL,
                    content_text TEXT NOT NULL,
                    associated_entities_json TEXT NOT NULL,
                    src_cardinality TEXT NOT NULL,
                    tgt_cardinality TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagrams (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    diagram_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    path TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    extra_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(artifact_type);
                CREATE INDEX IF NOT EXISTS idx_entities_domain ON entities(domain);
                CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(status);
                CREATE INDEX IF NOT EXISTS idx_connections_source ON connections(source);
                CREATE INDEX IF NOT EXISTS idx_connections_target ON connections(target);
                CREATE INDEX IF NOT EXISTS idx_connections_type ON connections(conn_type);
                CREATE INDEX IF NOT EXISTS idx_connections_status ON connections(status);
                CREATE INDEX IF NOT EXISTS idx_diagrams_type ON diagrams(diagram_type);
                CREATE INDEX IF NOT EXISTS idx_diagrams_status ON diagrams(status);
                """
            )
        try:
            with self._conn:
                self._conn.executescript(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
                        artifact_id UNINDEXED,
                        name,
                        artifact_type,
                        domain,
                        subdomain,
                        keywords,
                        content_text,
                        display_label
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS connections_fts USING fts5(
                        artifact_id UNINDEXED,
                        source,
                        target,
                        conn_type,
                        content_text
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS diagrams_fts USING fts5(
                        artifact_id UNINDEXED,
                        name,
                        diagram_type,
                        artifact_type
                    );
                    """
                )
        except sqlite3.OperationalError:
            self._fts_enabled = False

    def _ensure_loaded(self) -> None:
        if self._loaded and self._current_fingerprint() == self._last_fingerprint:
            return
        with self._lock:
            if not self._loaded or self._current_fingerprint() != self._last_fingerprint:
                self.refresh()

    def refresh(self) -> None:
        with self._lock:
            entities: dict[str, EntityRecord] = {}
            connections: dict[str, ConnectionRecord] = {}
            diagrams: dict[str, DiagramRecord] = {}

            for mount in self.repo_mounts:
                self._scan_mount(mount, entities, connections, diagrams)

            self._entities = entities
            self._connections = connections
            self._diagrams = diagrams
            self._rebuild_sqlite()
            self._last_fingerprint = self._current_fingerprint()
            self._loaded = True

    def _current_fingerprint(self) -> str:
        digest = hashlib.blake2b(digest_size=16)
        for root in self.repo_roots:
            digest.update(str(root.resolve()).encode("utf-8"))
            for sub in ("model", "diagram-catalog/diagrams"):
                scan_root = root / sub
                if not scan_root.exists():
                    continue
                for path in scan_root.rglob("*"):
                    try:
                        if not path.is_file():
                            continue
                        st = path.stat()
                        rel = path.relative_to(root).as_posix()
                        digest.update(rel.encode("utf-8"))
                        digest.update(str(int(st.st_mtime_ns)).encode("ascii"))
                        digest.update(str(int(st.st_size)).encode("ascii"))
                    except OSError:
                        continue
        return digest.hexdigest()

    def _scan_mount(
        self,
        mount: RepoMount,
        entities: dict[str, EntityRecord],
        connections: dict[str, ConnectionRecord],
        diagrams: dict[str, DiagramRecord],
    ) -> None:
        model_root = mount.root / "model"
        if model_root.exists():
            for path in sorted(model_root.rglob("*.md")):
                if path.name.endswith(".outgoing.md"):
                    continue
                rec = parse_entity(path, model_root)
                if rec is not None:
                    self._insert_mounted(entities, rec.artifact_id, rec, "entity", mount.root)
            for path in sorted(model_root.rglob("*.outgoing.md")):
                for rec in parse_outgoing_file(path):
                    self._insert_mounted(connections, rec.artifact_id, rec, "connection", mount.root)

        diagrams_root = mount.root / "diagram-catalog" / "diagrams"
        if diagrams_root.exists():
            for suffix in ("*.puml", "*.md"):
                for path in sorted(diagrams_root.rglob(suffix)):
                    if path.parent.name == "rendered":
                        continue
                    rec = parse_diagram(path)
                    if rec is not None:
                        self._insert_mounted(diagrams, rec.artifact_id, rec, "diagram", mount.root)

    def _rebuild_sqlite(self) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM entities")
            self._conn.execute("DELETE FROM connections")
            self._conn.execute("DELETE FROM diagrams")
            if self._fts_enabled:
                self._conn.execute("DELETE FROM entities_fts")
                self._conn.execute("DELETE FROM connections_fts")
                self._conn.execute("DELETE FROM diagrams_fts")

            self._conn.executemany(
                """
                INSERT INTO entities (
                    artifact_id, artifact_type, name, version, status, domain, subdomain,
                    path, scope, keywords_json, extra_json, content_text,
                    display_blocks_json, display_label, display_alias
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        rec.artifact_id,
                        rec.artifact_type,
                        rec.name,
                        rec.version,
                        rec.status,
                        rec.domain,
                        rec.subdomain,
                        str(rec.path),
                        self.scope_for_path(rec.path),
                        json.dumps(list(rec.keywords)),
                        json.dumps(rec.extra, sort_keys=True),
                        rec.content_text,
                        json.dumps(rec.display_blocks, sort_keys=True),
                        rec.display_label,
                        rec.display_alias,
                    )
                    for rec in self._entities.values()
                ],
            )
            self._conn.executemany(
                """
                INSERT INTO connections (
                    artifact_id, source, target, conn_type, version, status,
                    path, scope, extra_json, content_text,
                    associated_entities_json, src_cardinality, tgt_cardinality
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        rec.artifact_id,
                        rec.source,
                        rec.target,
                        rec.conn_type,
                        rec.version,
                        rec.status,
                        str(rec.path),
                        self.scope_for_path(rec.path),
                        json.dumps(rec.extra, sort_keys=True),
                        rec.content_text,
                        json.dumps(list(rec.associated_entities)),
                        rec.src_cardinality,
                        rec.tgt_cardinality,
                    )
                    for rec in self._connections.values()
                ],
            )
            self._conn.executemany(
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
                        self.scope_for_path(rec.path),
                        json.dumps(rec.extra, sort_keys=True),
                    )
                    for rec in self._diagrams.values()
                ],
            )

            if self._fts_enabled:
                self._conn.executemany(
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
                        for rec in self._entities.values()
                    ],
                )
                self._conn.executemany(
                    """
                    INSERT INTO connections_fts (
                        artifact_id, source, target, conn_type, content_text
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            rec.artifact_id,
                            rec.source,
                            rec.target,
                            rec.conn_type,
                            rec.content_text,
                        )
                        for rec in self._connections.values()
                    ],
                )
                self._conn.executemany(
                    """
                    INSERT INTO diagrams_fts (
                        artifact_id, name, diagram_type, artifact_type
                    ) VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            rec.artifact_id,
                            rec.name,
                            rec.diagram_type,
                            rec.artifact_type,
                        )
                        for rec in self._diagrams.values()
                    ],
                )

    @staticmethod
    def _insert_mounted(
        store: dict[str, EntityRecord] | dict[str, ConnectionRecord] | dict[str, DiagramRecord],
        artifact_id: str,
        rec: EntityRecord | ConnectionRecord | DiagramRecord,
        label: str,
        mount_root: Path,
    ) -> None:
        existing = store.get(artifact_id)
        if existing is None:
            ModelIndex._insert_unique(store, artifact_id, rec, label)
            return
        try:
            existing.path.resolve().relative_to(mount_root.resolve())
        except ValueError:
            # Duplicate across mounted roots: preserve the first mount's record.
            return
        raise DuplicateArtifactIdError(
            f"Duplicate {label} artifact-id '{artifact_id}' in {rec.path} and {existing.path}"
        )

    @staticmethod
    @overload
    def _insert_unique(
        store: dict[str, EntityRecord],
        artifact_id: str,
        rec: EntityRecord,
        label: str,
    ) -> None: ...

    @staticmethod
    @overload
    def _insert_unique(
        store: dict[str, ConnectionRecord],
        artifact_id: str,
        rec: ConnectionRecord,
        label: str,
    ) -> None: ...

    @staticmethod
    @overload
    def _insert_unique(
        store: dict[str, DiagramRecord],
        artifact_id: str,
        rec: DiagramRecord,
        label: str,
    ) -> None: ...

    @staticmethod
    def _insert_unique(
        store: dict[str, EntityRecord] | dict[str, ConnectionRecord] | dict[str, DiagramRecord],
        artifact_id: str,
        rec: EntityRecord | ConnectionRecord | DiagramRecord,
        label: str,
    ) -> None:
        existing = store.get(artifact_id)
        if existing is not None:
            raise DuplicateArtifactIdError(
                f"Duplicate {label} artifact-id '{artifact_id}' in {rec.path} and {existing.path}"
            )
        if isinstance(rec, EntityRecord):
            cast("dict[str, EntityRecord]", store)[artifact_id] = rec
            return
        if isinstance(rec, ConnectionRecord):
            cast("dict[str, ConnectionRecord]", store)[artifact_id] = rec
            return
        cast("dict[str, DiagramRecord]", store)[artifact_id] = rec

    @staticmethod
    def _scope_for_root(root: Path) -> str:
        return "enterprise" if root.name == "enterprise-repository" else "engagement"

    def scope_for_path(self, path: Path) -> str:
        resolved = path.resolve()
        for root in self.repo_roots:
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            return self._scope_for_root(root)
        return "unknown"

    def entity_records(self) -> dict[str, EntityRecord]:
        self._ensure_loaded()
        return self._entities

    def connection_records(self) -> dict[str, ConnectionRecord]:
        self._ensure_loaded()
        return self._connections

    def diagram_records(self) -> dict[str, DiagramRecord]:
        self._ensure_loaded()
        return self._diagrams

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        self._ensure_loaded()
        return self._entities.get(artifact_id)

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        self._ensure_loaded()
        return self._connections.get(artifact_id)

    def get_diagram(self, artifact_id: str) -> DiagramRecord | None:
        self._ensure_loaded()
        return self._diagrams.get(artifact_id)

    def find_file_by_id(self, artifact_id: str) -> Path | None:
        rec = self.get_entity(artifact_id)
        return rec.path if rec is not None else None

    def entity_ids(self) -> set[str]:
        self._ensure_loaded()
        return set(self._entities.keys())

    def connection_ids(self) -> set[str]:
        self._ensure_loaded()
        return set(self._connections.keys())

    def enterprise_entity_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._entities.items() if self.scope_for_path(rec.path) == "enterprise"}

    def engagement_entity_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._entities.items() if self.scope_for_path(rec.path) == "engagement"}

    def enterprise_connection_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._connections.items() if self.scope_for_path(rec.path) == "enterprise"}

    def engagement_connection_ids(self) -> set[str]:
        self._ensure_loaded()
        return {aid for aid, rec in self._connections.items() if self.scope_for_path(rec.path) == "engagement"}

    def scope_of_entity(self, artifact_id: str) -> str:
        rec = self.get_entity(artifact_id)
        return self.scope_for_path(rec.path) if rec is not None else "unknown"

    def scope_of_connection(self, artifact_id: str) -> str:
        rec = self.get_connection(artifact_id)
        return self.scope_for_path(rec.path) if rec is not None else "unknown"

    def entity_status(self, artifact_id: str) -> str | None:
        rec = self.get_entity(artifact_id)
        return rec.status if rec is not None else None

    def entity_statuses(self) -> dict[str, str]:
        self._ensure_loaded()
        return {aid: rec.status for aid, rec in self._entities.items()}

    def connection_status(self, artifact_id: str) -> str | None:
        rec = self.get_connection(artifact_id)
        return rec.status if rec is not None else None

    def find_connection_ids_for(
        self,
        entity_id: str,
        *,
        direction: str = "any",
        conn_type: str | None = None,
    ) -> list[str]:
        self._ensure_loaded()
        where: list[str] = []
        params: list[str] = []
        if direction == "outbound":
            where.append("source = ?")
            params.append(entity_id)
        elif direction == "inbound":
            where.append("target = ?")
            params.append(entity_id)
        else:
            where.append("(source = ? OR target = ?)")
            params.extend([entity_id, entity_id])
        if conn_type is not None:
            where.append("conn_type = ?")
            params.append(conn_type)
        sql = "SELECT artifact_id FROM connections WHERE " + " AND ".join(where) + " ORDER BY artifact_id"
        rows = self._conn.execute(sql, params).fetchall()
        return [str(row["artifact_id"]) for row in rows]

    def search_artifacts(
        self,
        query: str,
        *,
        limit: int = 10,
        include_connections: bool = True,
        include_diagrams: bool = True,
        prefer_record_type: str | None = None,
        strict_record_type: bool = False,
    ) -> list[tuple[str, str, float]]:
        self._ensure_loaded()
        tokens = tokenize(query.lower())
        if not tokens:
            return []
        if not self._fts_enabled:
            return []
        match_query = " OR ".join(f'"{token}"' for token in tokens)
        statements: list[str] = [
            """
            SELECT artifact_id, 'entity' AS record_type, 1.0 / (1.0 + bm25(entities_fts)) AS score
            FROM entities_fts
            WHERE entities_fts MATCH ?
            """
        ]
        params: list[str] = [match_query]
        if include_connections:
            statements.append(
                """
                SELECT artifact_id, 'connection' AS record_type, 1.0 / (1.0 + bm25(connections_fts)) AS score
                FROM connections_fts
                WHERE connections_fts MATCH ?
                """
            )
            params.append(match_query)
        if include_diagrams:
            statements.append(
                """
                SELECT artifact_id, 'diagram' AS record_type, 1.0 / (1.0 + bm25(diagrams_fts)) AS score
                FROM diagrams_fts
                WHERE diagrams_fts MATCH ?
                """
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
        rows = self._conn.execute(sql, params).fetchall()
        return [(str(r["artifact_id"]), str(r["record_type"]), float(r["score"])) for r in rows]

    def find_neighbors(
        self,
        entity_id: str,
        *,
        max_hops: int = 1,
        conn_type: str | None = None,
    ) -> dict[str, set[str]]:
        self._ensure_loaded()
        if max_hops < 1:
            return {}
        sql = """
        WITH RECURSIVE walk(depth, entity_id, visited) AS (
            SELECT 0, ?, ',' || ? || ','
            UNION ALL
            SELECT
                walk.depth + 1,
                CASE
                    WHEN connections.source = walk.entity_id THEN connections.target
                    ELSE connections.source
                END,
                walk.visited ||
                CASE
                    WHEN connections.source = walk.entity_id THEN connections.target
                    ELSE connections.source
                END || ','
            FROM walk
            JOIN connections
              ON (connections.source = walk.entity_id OR connections.target = walk.entity_id)
            WHERE walk.depth < ?
              AND (? IS NULL OR connections.conn_type = ?)
              AND instr(
                    walk.visited,
                    ',' ||
                    CASE
                        WHEN connections.source = walk.entity_id THEN connections.target
                        ELSE connections.source
                    END || ','
                  ) = 0
        )
        SELECT depth, entity_id
        FROM walk
        WHERE depth > 0
        """
        rows = self._conn.execute(sql, (entity_id, entity_id, max_hops, conn_type, conn_type)).fetchall()
        result: dict[str, set[str]] = {}
        for row in rows:
            depth = str(int(row["depth"]))
            result.setdefault(depth, set()).add(str(row["entity_id"]))
        return result
