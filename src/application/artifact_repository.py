"""Query/search facade built on top of an ArtifactStorePort."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

from src.application._artifact_search import (
    count_artifacts_by as _count_artifacts_by,
)
from src.application._artifact_search import (
    search as _search,
)
from src.application._artifact_search import (
    search_artifacts as _search_artifacts,
)
from src.application.ports import ArtifactStorePort
from src.application.read_models import (
    EntityContextConnection,
    EntityContextReadModel,
    ReadModelVersion,  # noqa: F401
)
from src.domain.artifact_types import (
    ArtifactSummary,
    ConnectionRecord,
    DiagramRecord,
    DocumentRecord,
    EntityRecord,
    RepoMount,
    SearchResult,
    SemanticSearchProvider,
)

_RecordType = Literal["entity", "connection", "diagram", "document"]


class ArtifactRepository:
    """Query/search facade over an ArtifactStorePort."""

    def __init__(
        self,
        store: ArtifactStorePort,
        semantic_provider: SemanticSearchProvider | None = None,
    ) -> None:
        self._store = store
        self._semantic = semantic_provider

    @property
    def repo_mounts(self) -> list[RepoMount]:
        return self._store.repo_mounts

    @property
    def repo_roots(self) -> list[Path]:
        return self._store.repo_roots

    @property
    def repo_root(self) -> Path:
        return self._store.repo_root

    def refresh(self) -> None:
        self._store.refresh()

    def read_model_version(self) -> ReadModelVersion:
        return self._store.read_model_version()

    def apply_file_change(self, path: Path) -> None:
        self._store.apply_file_changes([path])

    def apply_file_changes(self, paths: Iterable[Path]) -> ReadModelVersion:
        return self._store.apply_file_changes(list(paths))

    def read_entity_context(self, artifact_id: str) -> EntityContextReadModel | None:
        return self._store.read_entity_context(artifact_id)

    def candidate_connections_for_entities(self, entity_ids: list[str]) -> list[EntityContextConnection]:
        return self._store.candidate_connections_for_entities(entity_ids)

    def get_entity(self, artifact_id: str) -> EntityRecord | None:
        return self._store.get_entity(artifact_id)

    def get_connection(self, artifact_id: str) -> ConnectionRecord | None:
        return self._store.get_connection(artifact_id)

    def get_diagram(self, artifact_id: str) -> DiagramRecord | None:
        return self._store.get_diagram(artifact_id)

    def get_document(self, artifact_id: str) -> DocumentRecord | None:
        return self._store.get_document(artifact_id)

    def list_documents(
        self, *, doc_type: str | None = None, status: str | None = None
    ) -> list[DocumentRecord]:
        return self._store.list_documents(doc_type=doc_type, status=status)

    def list_entities(
        self,
        *,
        artifact_type: str | None = None,
        domain: str | None = None,
        subdomain: str | None = None,
        status: str | None = None,
    ) -> list[EntityRecord]:
        return self._store.list_entities(
            artifact_type=artifact_type,
            domain=domain,
            subdomain=subdomain,
            status=status,
        )

    def list_connections(
        self,
        *,
        conn_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        status: str | None = None,
    ) -> list[ConnectionRecord]:
        return self._store.list_connections(
            conn_type=conn_type, source=source, target=target, status=status
        )

    def list_diagrams(
        self, *, diagram_type: str | None = None, status: str | None = None
    ) -> list[DiagramRecord]:
        return self._store.list_diagrams(diagram_type=diagram_type, status=status)

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
        return self._store.list_artifacts(
            artifact_type=artifact_type,
            domain=domain,
            status=status,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
        )

    def read_artifact(
        self,
        artifact_id: str,
        *,
        mode: Literal["summary", "full"] = "summary",
        section: str | None = None,
    ) -> dict[str, object] | None:
        return self._store.read_artifact(artifact_id, mode=mode, section=section)

    def summarize_artifact(self, artifact_id: str) -> ArtifactSummary | None:
        return self._store.summarize_artifact(artifact_id)

    def stats(self) -> dict[str, object]:
        return self._store.stats()

    def connection_counts(self) -> dict[str, tuple[int, int, int]]:
        return self._store.connection_counts()

    def connection_counts_for(self, entity_id: str) -> tuple[int, int, int]:
        return self._store.connection_counts_for(entity_id)

    def connection_counts_for_entities(
        self, entity_ids: list[str] | set[str] | frozenset[str]
    ) -> dict[str, tuple[int, int, int]]:
        return self._store.connection_counts_for_entities(entity_ids)

    def list_connections_by_types(self, types: frozenset[str]) -> list[ConnectionRecord]:
        return self._store.list_connections_by_types(types)

    def list_connections_by_types_for_entities(
        self,
        types: frozenset[str],
        entity_ids: list[str] | set[str] | frozenset[str],
    ) -> list[ConnectionRecord]:
        return self._store.list_connections_by_types_for_entities(types, entity_ids)

    def find_connections_for(
        self,
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]:
        return self._store.find_connections_for(entity_id, direction=direction, conn_type=conn_type)

    def find_neighbors(
        self,
        entity_id: str,
        *,
        max_hops: int = 1,
        conn_type: str | None = None,
    ) -> dict[str, set[str]]:
        return self._store.find_neighbors(entity_id, max_hops=max_hops, conn_type=conn_type)

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
        return _count_artifacts_by(
            self._store,
            group_by,
            artifact_type=artifact_type,
            domain=domain,
            status=status,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
        )

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
        prefer_record_type: _RecordType | None = None,
        strict_record_type: bool = False,
    ) -> SearchResult:
        return _search_artifacts(
            self._store,
            self._semantic,
            query,
            limit=limit,
            domain=domain,
            artifact_type=artifact_type,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
            prefer_record_type=prefer_record_type,
            strict_record_type=strict_record_type,
        )

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
        prefer_record_type: _RecordType | None = None,
        strict_record_type: bool = False,
    ) -> SearchResult:
        return _search(
            self._store,
            self._semantic,
            query,
            limit=limit,
            entity_types=entity_types,
            domains=domains,
            include_connections=include_connections,
            include_diagrams=include_diagrams,
            include_documents=include_documents,
            prefer_record_type=prefer_record_type,
            strict_record_type=strict_record_type,
        )
