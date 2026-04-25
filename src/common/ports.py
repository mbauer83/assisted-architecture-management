from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Protocol

from src.common.artifact_types import (
    ArtifactSummary,
    ConnectionRecord,
    DiagramRecord,
    DocumentRecord,
    EntityRecord,
    RepoMount,
)
from src.infrastructure.artifact_index.types import EntityContextReadModel
from src.infrastructure.artifact_index.versioning import ReadModelVersion


class ArtifactStorePort(Protocol):
    # Lifecycle
    def refresh(self) -> None: ...
    def read_model_version(self) -> ReadModelVersion: ...
    def apply_file_changes(self, paths: list[Path]) -> ReadModelVersion: ...

    # Point lookups
    def get_entity(self, artifact_id: str) -> EntityRecord | None: ...
    def get_connection(self, artifact_id: str) -> ConnectionRecord | None: ...
    def get_diagram(self, artifact_id: str) -> DiagramRecord | None: ...
    def get_document(self, artifact_id: str) -> DocumentRecord | None: ...

    # Filtered list queries (return sorted copies — callers never hold the live dict)
    def list_entities(
        self,
        *,
        artifact_type: str | None = None,
        domain: str | None = None,
        subdomain: str | None = None,
        status: str | None = None,
    ) -> list[EntityRecord]: ...

    def list_connections(
        self,
        *,
        conn_type: str | None = None,
        source: str | None = None,
        target: str | None = None,
        status: str | None = None,
    ) -> list[ConnectionRecord]: ...

    def list_diagrams(
        self,
        *,
        diagram_type: str | None = None,
        status: str | None = None,
    ) -> list[DiagramRecord]: ...

    def list_documents(
        self,
        *,
        doc_type: str | None = None,
        status: str | None = None,
    ) -> list[DocumentRecord]: ...

    def list_artifacts(
        self,
        *,
        artifact_type: str | list[str] | None = None,
        domain: str | list[str] | None = None,
        status: str | list[str] | None = None,
        include_connections: bool = False,
        include_diagrams: bool = False,
        include_documents: bool = False,
    ) -> list[ArtifactSummary]: ...

    # Richer reads
    def read_artifact(
        self,
        artifact_id: str,
        *,
        mode: Literal["summary", "full"] = "summary",
        section: str | None = None,
    ) -> dict[str, object] | None: ...

    def summarize_artifact(self, artifact_id: str) -> ArtifactSummary | None: ...
    def read_entity_context(self, artifact_id: str) -> EntityContextReadModel | None: ...
    def stats(self) -> dict[str, object]: ...

    # Connection-specific queries
    def connection_counts(self) -> dict[str, tuple[int, int, int]]: ...
    def connection_counts_for(self, entity_id: str) -> tuple[int, int, int]: ...
    def list_connections_by_types(self, types: frozenset[str]) -> list[ConnectionRecord]: ...
    def find_connections_for(
        self,
        entity_id: str,
        *,
        direction: Literal["any", "outbound", "inbound"] = "any",
        conn_type: str | None = None,
    ) -> list[ConnectionRecord]: ...
    def find_neighbors(
        self,
        entity_id: str,
        *,
        max_hops: int = 1,
        conn_type: str | None = None,
    ) -> dict[str, set[str]]: ...

    # FTS search
    def search_fts(
        self,
        query: str,
        *,
        limit: int,
        include_connections: bool,
        include_diagrams: bool,
        include_documents: bool,
        prefer_record_type: str | None,
        strict_record_type: bool,
    ) -> list[tuple[str, str, float]]: ...

    # Scope
    def scope_for_path(self, path: Path) -> Literal["enterprise", "engagement", "unknown"]: ...
    def scope_of_entity(
        self, artifact_id: str
    ) -> Literal["enterprise", "engagement", "unknown"]: ...
    def scope_of_connection(
        self, artifact_id: str
    ) -> Literal["enterprise", "engagement", "unknown"]: ...

    # Registry-style queries
    def entity_ids(self) -> set[str]: ...
    def connection_ids(self) -> set[str]: ...
    def enterprise_entity_ids(self) -> set[str]: ...
    def engagement_entity_ids(self) -> set[str]: ...
    def enterprise_connection_ids(self) -> set[str]: ...
    def engagement_connection_ids(self) -> set[str]: ...
    def enterprise_document_ids(self) -> set[str]: ...
    def enterprise_diagram_ids(self) -> set[str]: ...
    def entity_status(self, artifact_id: str) -> str | None: ...
    def entity_statuses(self) -> dict[str, str]: ...
    def connection_status(self, artifact_id: str) -> str | None: ...
    def find_file_by_id(self, artifact_id: str) -> Path | None: ...

    # Mount introspection
    @property
    def repo_mounts(self) -> list[RepoMount]: ...
    @property
    def repo_roots(self) -> list[Path]: ...
    @property
    def repo_root(self) -> Path: ...


@dataclass(frozen=True)
class ArtifactParsers:
    """Injectable parser callables — swap out for lightweight fakes in tests."""

    parse_entity: Callable[[Path, Path], EntityRecord | None]
    parse_outgoing: Callable[[Path], list[ConnectionRecord]]
    parse_diagram: Callable[[Path], DiagramRecord | None]
    parse_document: Callable[[Path], DocumentRecord | None]

    @staticmethod
    def default() -> "ArtifactParsers":
        from src.common.artifact_parsing import (
            parse_diagram,
            parse_document,
            parse_entity,
            parse_outgoing_file,
        )

        return ArtifactParsers(
            parse_entity=parse_entity,
            parse_outgoing=parse_outgoing_file,
            parse_diagram=parse_diagram,
            parse_document=parse_document,
        )
