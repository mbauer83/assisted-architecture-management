"""ERP v2.0 Model Query — indexed query API over entities, connections, and diagrams."""


import threading
from pathlib import Path
from typing import Literal, cast, overload

from src.common.model_query_parsing import parse_diagram, parse_entity, parse_outgoing_file
from src.common.model_query_scoring import score_connection, score_diagram, score_entity, tokenize
from src.common.model_query_types import (
    ArtifactSummary,
    ConnectionRecord,
    DiagramRecord,
    DuplicateArtifactIdError,
    EntityRecord,
    RepoMount,
    SearchHit,
    SearchResult,
    SemanticSearchProvider,
    infer_mount,
    summary_from_connection,
    summary_from_diagram,
    summary_from_entity,
)
from src.common._model_query_helpers import (
    matches_entity as _matches_entity,
    matches_connection as _matches_connection,
    matches_diagram as _matches_diagram,
    matches_entity_sets as _matches_entity_sets,
    matches_connection_sets as _matches_connection_sets,
    matches_diagram_sets as _matches_diagram_sets,
    next_frontier as _next_frontier,
    matches_direction as _matches_direction,
    to_set as _to_set,
    single_or_none as _single_or_none,
    summary_group_key as _summary_group_key,
    read_entity as _read_entity,
    read_connection as _read_connection,
    read_diagram as _read_diagram,
)

_NONE_LABEL = "(none)"


class ModelRepository:
    def __init__(
        self,
        repo_root: Path | list[Path] | list[RepoMount],
        semantic_provider: SemanticSearchProvider | None = None,
    ) -> None:
        if isinstance(repo_root, Path):
            mounts: list[RepoMount] = [infer_mount(repo_root)]
        else:
            mounts = [m if isinstance(m, RepoMount) else infer_mount(m) for m in repo_root]

        roots = [m.root for m in mounts]
        if len(set(map(str, roots))) != len(roots):
            raise ValueError("Duplicate repo root in ModelRepository mounts")

        self.repo_mounts = mounts
        self.repo_root = mounts[0].root
        self._semantic = semantic_provider
        self._entities: dict[str, EntityRecord] = {}
        self._connections: dict[str, ConnectionRecord] = {}
        self._diagrams: dict[str, DiagramRecord] = {}
        self._loaded = False
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if not self._loaded:
                self._load_all()

    def refresh(self) -> None:
        with self._lock:
            self._entities = {}
            self._connections = {}
            self._diagrams = {}
            self._loaded = False

    def _load_all(self) -> None:
        self._entities = {}
        self._connections = {}
        self._diagrams = {}
        for mount in self.repo_mounts:
            self._load_entities(mount)
            self._load_connections(mount)
            self._load_diagrams(mount)
        self._loaded = True

    def _load_entities(self, mount: RepoMount) -> None:
        model_root = mount.root / "model"
        if not model_root.exists():
            return
        for path in sorted(model_root.rglob("*.md")):
            if path.name.endswith(".outgoing.md"):
                continue
            rec = parse_entity(path, model_root)
            if rec is not None:
                self._insert_unique(self._entities, rec.artifact_id, rec, "entity")

    def _load_connections(self, mount: RepoMount) -> None:
        model_root = mount.root / "model"
        if not model_root.exists():
            return
        for path in sorted(model_root.rglob("*.outgoing.md")):
            for rec in parse_outgoing_file(path):
                self._insert_unique(self._connections, rec.artifact_id, rec, "connection")

    def _load_diagrams(self, mount: RepoMount) -> None:
        diagrams_root = mount.root / "diagram-catalog" / "diagrams"
        if not diagrams_root.exists():
            return
        for suffix in ("*.puml", "*.md"):
            for path in sorted(diagrams_root.rglob(suffix)):
                if path.parent.name == "rendered":
                    continue
                rec = parse_diagram(path)
                if rec is not None:
                    self._insert_unique(self._diagrams, rec.artifact_id, rec, "diagram")

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

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        self._ensure_loaded()
        return self._entities.get(artifact_id)

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        self._ensure_loaded()
        return self._connections.get(artifact_id)

    def get_diagram(self, artifact_id: str) -> DiagramRecord | None:
        self._ensure_loaded()
        return self._diagrams.get(artifact_id)

    def list_entities(
        self,
        *,
        artifact_type: str | None = None,
        domain: str | None = None,
        subdomain: str | None = None,
        status: str | None = None,
    ) -> list[EntityRecord]:
        self._ensure_loaded()
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
        self._ensure_loaded()
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
        self._ensure_loaded()
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
    ) -> list[ArtifactSummary]:
        self._ensure_loaded()
        types = _to_set(artifact_type)
        domains = _to_set(domain)
        statuses = _to_set(status)

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
        return sorted(results, key=lambda s: s.artifact_id)

    def read_artifact(
        self,
        artifact_id: str,
        *,
        mode: Literal["summary", "full"] = "summary",
    ) -> dict[str, object] | None:
        self._ensure_loaded()
        entity = self._entities.get(artifact_id)
        if entity is not None:
            return _read_entity(entity, mode=mode)
        connection = self._connections.get(artifact_id)
        if connection is not None:
            return _read_connection(connection, mode=mode)
        diagram = self._diagrams.get(artifact_id)
        if diagram is not None:
            return _read_diagram(diagram, mode=mode)
        return None

    def summarize_artifact(self, artifact_id: str) -> ArtifactSummary | None:
        self._ensure_loaded()
        entity = self._entities.get(artifact_id)
        if entity is not None:
            return summary_from_entity(entity)
        connection = self._connections.get(artifact_id)
        if connection is not None:
            return summary_from_connection(connection)
        diagram = self._diagrams.get(artifact_id)
        if diagram is not None:
            return summary_from_diagram(diagram)
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
        prefer_record_type: Literal["entity", "connection", "diagram"] | None = None,
        strict_record_type: bool = False,
    ) -> SearchResult:
        domains = _to_set(domain)
        types = _to_set(artifact_type)
        return self.search(
            query,
            limit=limit,
            domains=list(domains) if domains else None,
            entity_types=list(types) if types else None,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
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
        self._ensure_loaded()
        counts: dict[str, int] = {}

        if group_by == "diagram_type":
            diagrams = self.list_diagrams(
                status=_single_or_none(status),
            )
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
        self._ensure_loaded()
        entities = list(self._entities.values())
        connections = list(self._connections.values())
        diagrams = list(self._diagrams.values())

        entities_by_domain: dict[str, int] = {}
        for entity in entities:
            entities_by_domain[entity.domain] = entities_by_domain.get(entity.domain, 0) + 1

        connections_by_type: dict[str, int] = {}
        for connection in connections:
            connections_by_type[connection.conn_type] = connections_by_type.get(connection.conn_type, 0) + 1

        return {
            "entities": len(entities),
            "connections": len(connections),
            "diagrams": len(diagrams),
            "entities_by_domain": entities_by_domain,
            "connections_by_type": connections_by_type,
        }

    def find_connections_for(
        self,
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]:
        self._ensure_loaded()
        results: list[ConnectionRecord] = []
        for rec in self._connections.values():
            if conn_type is not None and rec.conn_type != conn_type:
                continue
            if not _matches_direction(rec, entity_id=entity_id, direction=direction):
                continue
            results.append(rec)
        return sorted(results, key=lambda r: r.artifact_id)

    def find_neighbors(
        self,
        entity_id: str,
        *,
        max_hops: int = 1,
        conn_type: str | None = None,
    ) -> dict[str, set[str]]:
        self._ensure_loaded()
        visited: set[str] = {entity_id}
        frontier: set[str] = {entity_id}
        result: dict[str, set[str]] = {}

        for hop in range(1, max_hops + 1):
            next_frontier = _next_frontier(frontier, visited, self, conn_type)
            if not next_frontier:
                break
            result[str(hop)] = next_frontier
            visited |= next_frontier
            frontier = next_frontier
        return result

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        entity_types: list[str] | None = None,
        domains: list[str] | None = None,
        include_connections: bool = True,
        include_diagrams: bool = True,
        prefer_record_type: Literal["entity", "connection", "diagram"] | None = None,
        strict_record_type: bool = False,
    ) -> SearchResult:
        self._ensure_loaded()
        query_lc = query.lower()
        tokens = tokenize(query_lc)
        hits: list[SearchHit] = []

        entity_type_set = set(entity_types) if entity_types else set()
        domain_set = set(domains) if domains else set()

        hits.extend(self._search_entities(query_lc, tokens, entity_type_set, domain_set))
        if include_connections:
            hits.extend(self._search_connections(query_lc, tokens))
        if include_diagrams:
            hits.extend(self._search_diagrams(query_lc, tokens))
        self._apply_semantic_supplement(query, hits)

        if strict_record_type and prefer_record_type is not None:
            hits = [hit for hit in hits if hit.record_type == prefer_record_type]

        if prefer_record_type is not None:
            hits.sort(
                key=lambda h: (h.record_type == prefer_record_type, h.score),
                reverse=True,
            )
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

    def _apply_semantic_supplement(self, query: str, hits: list[SearchHit]) -> None:
        if self._semantic is None:
            return
        if not isinstance(self._semantic, SemanticSearchProvider):
            return
        if len(self._entities) < 50:
            return

        seen_ids = {
            hit.record.artifact_id
            for hit in hits
            if hasattr(hit.record, "artifact_id")
        }
        for sem_score, artifact_id in self._semantic.top_k(query, k=1, threshold=0.75):
            if artifact_id in seen_ids:
                continue
            rec = self._entities.get(artifact_id)
            if rec is not None:
                hits.append(SearchHit(score=sem_score * 3.0, record_type="entity", record=rec))

# All private helpers (_matches_*, _next_frontier, _to_set, etc.) live in
# src/common/_model_query_helpers.py and are imported at the top of this file.

