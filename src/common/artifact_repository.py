"""ERP v2.0 Model Query — indexed query API over entities, connections, and diagrams."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal, cast

from src.common._artifact_query_helpers import (
    matches_connection as _matches_connection,
    matches_connection_sets as _matches_connection_sets,
    matches_diagram as _matches_diagram,
    matches_diagram_sets as _matches_diagram_sets,
    matches_direction as _matches_direction,
    matches_entity as _matches_entity,
    matches_entity_sets as _matches_entity_sets,
    next_frontier as _next_frontier,
    read_connection as _read_connection,
    read_diagram as _read_diagram,
    read_document as _read_document,
    read_entity as _read_entity,
    single_or_none as _single_or_none,
    summary_group_key as _summary_group_key,
    to_set as _to_set,
)
from src.common.artifact_index import ReadModelVersion
from src.common.artifact_index import shared_artifact_index
from src.common.artifact_scoring import score_connection, score_diagram, score_document, score_entity, tokenize
from src.common.artifact_types import (
    ArtifactSummary,
    ConnectionRecord,
    DiagramRecord,
    DocumentRecord,
    EntityRecord,
    RepoMount,
    SearchHit,
    SearchResult,
    SemanticSearchProvider,
    summary_from_connection,
    summary_from_diagram,
    summary_from_document,
    summary_from_entity,
)

_NONE_LABEL = "(none)"


class ArtifactRepository:
    """Query/search facade built on top of the shared ArtifactIndex."""

    def __init__(
        self,
        repo_root: Path | list[Path] | list[RepoMount],
        semantic_provider: SemanticSearchProvider | None = None,
    ) -> None:
        self._index = shared_artifact_index(repo_root)
        self._semantic = semantic_provider
        self._index.refresh()

    @property
    def repo_mounts(self) -> list[RepoMount]:
        return self._index.repo_mounts

    @property
    def repo_roots(self) -> list[Path]:
        return self._index.repo_roots

    @property
    def repo_root(self) -> Path:
        return self._index.repo_root

    @property
    def _entities(self) -> dict[str, EntityRecord]:
        return self._index.entity_records()

    @property
    def _connections(self) -> dict[str, ConnectionRecord]:
        return self._index.connection_records()

    @property
    def _diagrams(self) -> dict[str, DiagramRecord]:
        return self._index.diagram_records()

    @property
    def _documents(self) -> dict[str, DocumentRecord]:
        return self._index.document_records()

    def refresh(self) -> None:
        self._index.refresh()

    def read_model_version(self) -> ReadModelVersion:
        return self._index.read_model_version()

    def apply_file_change(self, path: Path) -> None:
        if path.name.endswith(".outgoing.md"):
            self._index.apply_outgoing_file_change(path)
            return
        if self._index._is_diagram_source_path(path):
            self._index.apply_diagram_file_change(path)
            return
        if self._index._is_document_path(path):
            self._index.apply_document_file_change(path)
            return
        if path.suffix == ".md":
            self._index.apply_entity_file_change(path)
            return
        self.refresh()

    def apply_file_changes(self, paths: Iterable[Path]) -> ReadModelVersion:
        return self._index.apply_file_changes(list(paths))

    def read_entity_context(self, artifact_id: str) -> dict[str, object] | None:
        return self._index.read_entity_context(artifact_id)

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        return self._index.get_entity(artifact_id)

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        return self._index.get_connection(artifact_id)

    def get_diagram(self, artifact_id: str) -> DiagramRecord | None:
        return self._index.get_diagram(artifact_id)

    def get_document(self, artifact_id: str) -> DocumentRecord | None:
        return self._index.get_document(artifact_id)

    def list_documents(
        self,
        *,
        doc_type: str | None = None,
        status: str | None = None,
    ) -> list[DocumentRecord]:
        with self._index._lock:
            results = [
                rec
                for rec in self._documents.values()
                if (doc_type is None or rec.doc_type == doc_type)
                and (status is None or rec.status == status)
            ]
            return sorted(results, key=lambda r: r.artifact_id)

    def list_entities(
        self,
        *,
        artifact_type: str | None = None,
        domain: str | None = None,
        subdomain: str | None = None,
        status: str | None = None,
    ) -> list[EntityRecord]:
        with self._index._lock:
            results = [
                rec
                for rec in self._entities.values()
                if _matches_entity(
                    rec,
                    artifact_type=artifact_type,
                    domain=domain,
                    subdomain=subdomain,
                    status=status,
                )
            ]
            return sorted(results, key=lambda r: r.artifact_id)

    def list_connections(
        self,
        *,
        conn_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        status: str | None = None,
    ) -> list[ConnectionRecord]:
        with self._index._lock:
            results = [
                rec
                for rec in self._connections.values()
                if _matches_connection(
                    rec,
                    conn_type=conn_type,
                    source=source,
                    target=target,
                    status=status,
                )
            ]
            return sorted(results, key=lambda r: r.artifact_id)

    def list_diagrams(
        self,
        *,
        diagram_type: str | None = None,
        status: str | None = None,
    ) -> list[DiagramRecord]:
        with self._index._lock:
            results = [
                rec
                for rec in self._diagrams.values()
                if _matches_diagram(
                    rec,
                    diagram_type=diagram_type,
                    status=status,
                )
            ]
            return sorted(results, key=lambda r: r.artifact_id)

    def list_artifacts(
        self,
        *,
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_connections: bool = False,
        include_diagrams: bool = False,
        include_documents: bool = False,
    ) -> list[ArtifactSummary]:
        types = _to_set(artifact_type)
        domains = {d.lower() for d in _to_set(domain)}
        statuses = _to_set(status)

        with self._index._lock:
            results: list[ArtifactSummary] = []
            results.extend(
                summary_from_entity(rec)
                for rec in self._entities.values()
                if _matches_entity_sets(rec, types, domains, statuses)
            )
            if include_connections:
                results.extend(
                    summary_from_connection(rec)
                    for rec in self._connections.values()
                    if _matches_connection_sets(rec, statuses)
                )
            if include_diagrams:
                results.extend(
                    summary_from_diagram(rec)
                    for rec in self._diagrams.values()
                    if _matches_diagram_sets(rec, types, statuses)
                )
            if include_documents:
                results.extend(
                    summary_from_document(rec)
                    for rec in self._documents.values()
                    if (not statuses or rec.status in statuses)
                )
            return sorted(results, key=lambda s: s.artifact_id)

    def read_artifact(
        self,
        artifact_id: str,
        *,
        mode: Literal["summary", "full"] = "summary",
        section: str | None = None,
    ) -> dict[str, object] | None:
        with self._index._lock:
            entity = self._entities.get(artifact_id)
            if entity is not None:
                return _read_entity(entity, mode=mode)
            connection = self._connections.get(artifact_id)
            if connection is not None:
                return _read_connection(connection, mode=mode)
            diagram = self._diagrams.get(artifact_id)
            if diagram is not None:
                return _read_diagram(diagram, mode=mode)
            document = self._documents.get(artifact_id)
            if document is not None:
                return _read_document(document, mode=mode, section=section)
            return None

    def summarize_artifact(self, artifact_id: str) -> ArtifactSummary | None:
        with self._index._lock:
            entity = self._entities.get(artifact_id)
            if entity is not None:
                return summary_from_entity(entity)
            connection = self._connections.get(artifact_id)
            if connection is not None:
                return summary_from_connection(connection)
            diagram = self._diagrams.get(artifact_id)
            if diagram is not None:
                return summary_from_diagram(diagram)
            document = self._documents.get(artifact_id)
            if document is not None:
                return summary_from_document(document)
            return None

    def search_artifacts(
        self,
        query: str,
        *,
        limit: int = 10,
        domain: str | list[str] | None = None,
        artifact_type: str | list[str] | None = None,
        include_connections: bool = True,
        include_diagrams: bool = True,
        include_documents: bool = True,
        prefer_record_type: Literal["entity", "connection", "diagram", "document"] | None = None,
        strict_record_type: bool = False,
    ) -> SearchResult:
        domains = {d.lower() for d in _to_set(domain)}
        types = _to_set(artifact_type)
        return self.search(
            query,
            limit=limit,
            domains=list(domains) if domains else None,
            entity_types=list(types) if types else None,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
            prefer_record_type=prefer_record_type,
            strict_record_type=strict_record_type,
        )

    def count_artifacts_by(
        self,
        group_by: Literal["artifact_type", "diagram_type", "domain"],
        *,
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_connections: bool = True,
        include_diagrams: bool = True,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}

        if group_by == "diagram_type":
            diagrams = self.list_diagrams(status=_single_or_none(status))
            for rec in diagrams:
                key = rec.diagram_type or _NONE_LABEL
                counts[key] = counts.get(key, 0) + 1
            return dict(sorted(counts.items(), key=lambda item: item[0]))

        summaries = self.list_artifacts(
            artifact_type=artifact_type,
            domain=domain,
            status=status,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
        )
        for rec in summaries:
            key = _summary_group_key(rec, group_by)
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: item[0]))

    def stats(self) -> dict[str, object]:
        with self._index._lock:
            entities = list(self._entities.values())
            connections = list(self._connections.values())
            diagrams = list(self._diagrams.values())
            documents = list(self._documents.values())

            entities_by_domain: dict[str, int] = {}
            for entity in entities:
                entities_by_domain[entity.domain] = entities_by_domain.get(entity.domain, 0) + 1

            connections_by_type: dict[str, int] = {}
            for connection in connections:
                connections_by_type[connection.conn_type] = connections_by_type.get(connection.conn_type, 0) + 1

            documents_by_type: dict[str, int] = {}
            for doc in documents:
                documents_by_type[doc.doc_type] = documents_by_type.get(doc.doc_type, 0) + 1

            return {
                "entities": len(entities),
                "connections": len(connections),
                "diagrams": len(diagrams),
                "documents": len(documents),
                "entities_by_domain": entities_by_domain,
                "connections_by_type": connections_by_type,
                "documents_by_type": documents_by_type,
            }

    def find_connections_for(
        self,
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]:
        ids = self._index.find_connection_ids_for(entity_id, direction=direction, conn_type=conn_type)
        return [rec for cid in ids if (rec := self._connections.get(cid)) is not None]

    def find_neighbors(
        self,
        entity_id: str,
        *,
        max_hops: int = 1,
        conn_type: str | None = None,
    ) -> dict[str, set[str]]:
        return self._index.find_neighbors(entity_id, max_hops=max_hops, conn_type=conn_type)

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        entity_types: list[str] | None = None,
        domains: list[str] | None = None,
        include_connections: bool = True,
        include_diagrams: bool = True,
        include_documents: bool = True,
        prefer_record_type: Literal["entity", "connection", "diagram", "document"] | None = None,
        strict_record_type: bool = False,
    ) -> SearchResult:
        query_lc = query.lower()
        tokens = tokenize(query_lc)
        hits: list[SearchHit] = []

        entity_type_set = set(entity_types) if entity_types else set()
        domain_set = set(domains) if domains else set()

        indexed_hits = self._index.search_artifacts(
            query,
            limit=max(limit * 4, 20),
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
            prefer_record_type=prefer_record_type,
            strict_record_type=strict_record_type,
        )
        seen: set[tuple[str, str]] = set()
        for artifact_id, record_type, score in indexed_hits:
            rec = (
                self._entities.get(artifact_id)
                if record_type == "entity"
                else self._connections.get(artifact_id)
                if record_type == "connection"
                else self._documents.get(artifact_id)
                if record_type == "document"
                else self._diagrams.get(artifact_id)
            )
            if rec is None:
                continue
            if record_type == "entity":
                entity_rec = cast(EntityRecord, rec)
                if entity_type_set and entity_rec.artifact_type not in entity_type_set:
                    continue
                if domain_set and entity_rec.domain not in domain_set:
                    continue
            key = (record_type, artifact_id)
            if key in seen:
                continue
            seen.add(key)
            hits.append(SearchHit(score=score, record_type=cast(Literal["entity", "connection", "diagram", "document"], record_type), record=rec))

        if not hits:
            hits.extend(self._search_entities(query_lc, tokens, entity_type_set, domain_set))
            if include_connections:
                hits.extend(self._search_connections(query_lc, tokens))
            if include_diagrams:
                hits.extend(self._search_diagrams(query_lc, tokens))
            if include_documents:
                hits.extend(self._search_documents(query_lc, tokens))

        self._apply_semantic_supplement(query, hits)

        if strict_record_type and prefer_record_type is not None:
            hits = [hit for hit in hits if hit.record_type == prefer_record_type]

        if prefer_record_type is not None:
            hits.sort(key=lambda h: (h.record_type == prefer_record_type, h.score), reverse=True)
        else:
            hits.sort(key=lambda h: h.score, reverse=True)
        return SearchResult(query=query, hits=hits[:limit])

    def _search_entities(
        self,
        query_lc: str,
        tokens: list[str],
        entity_type_set: set[str],
        domain_set: set[str],
    ) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for rec in self._entities.values():
            if entity_type_set and rec.artifact_type not in entity_type_set:
                continue
            if domain_set and rec.domain not in domain_set:
                continue
            score = score_entity(rec, query_lc, tokens)
            if score > 0:
                hits.append(SearchHit(score=score, record_type="entity", record=rec))
        return hits

    def _search_connections(self, query_lc: str, tokens: list[str]) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for rec in self._connections.values():
            score = score_connection(rec, query_lc, tokens)
            if score > 0:
                hits.append(SearchHit(score=score, record_type="connection", record=rec))
        return hits

    def _search_diagrams(self, query_lc: str, tokens: list[str]) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for rec in self._diagrams.values():
            score = score_diagram(rec, query_lc, tokens)
            if score > 0:
                hits.append(SearchHit(score=score, record_type="diagram", record=rec))
        return hits

    def _search_documents(self, query_lc: str, tokens: list[str]) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for rec in self._documents.values():
            score = score_document(rec, query_lc, tokens)
            if score > 0:
                hits.append(SearchHit(score=score, record_type="document", record=rec))
        return hits

    def _apply_semantic_supplement(self, query: str, hits: list[SearchHit]) -> None:
        if self._semantic is None:
            return
        if not isinstance(self._semantic, SemanticSearchProvider):
            return
        if len(self._entities) < 50:
            return

        seen_ids = {hit.record.artifact_id for hit in hits if hasattr(hit.record, "artifact_id")}
        for sem_score, artifact_id in self._semantic.top_k(query, k=1, threshold=0.75):
            if artifact_id in seen_ids:
                continue
            rec = self._entities.get(artifact_id)
            if rec is not None:
                hits.append(SearchHit(score=sem_score * 3.0, record_type="entity", record=rec))
