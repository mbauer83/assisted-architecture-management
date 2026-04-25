from __future__ import annotations

from pathlib import Path
from typing import Literal

from src.application.ports import ArtifactStorePort


class ArtifactRegistry:
    """Verifier/write-oriented facade over the shared model index."""

    def __init__(self, store: ArtifactStorePort) -> None:
        self._store = store

    @property
    def repo_roots(self) -> list[Path]:
        return self._store.repo_roots

    def refresh(self) -> None:
        self._store.refresh()

    def find_file_by_id(self, artifact_id: str) -> Path | None:
        return self._store.find_file_by_id(artifact_id)

    def entity_ids(self) -> set[str]:
        return self._store.entity_ids()

    def enterprise_entity_ids(self) -> set[str]:
        return self._store.enterprise_entity_ids()

    def enterprise_document_ids(self) -> set[str]:
        return self._store.enterprise_document_ids()

    def enterprise_diagram_ids(self) -> set[str]:
        return self._store.enterprise_diagram_ids()

    def engagement_entity_ids(self) -> set[str]:
        return self._store.engagement_entity_ids()

    def connection_ids(self) -> set[str]:
        return self._store.connection_ids()

    def enterprise_connection_ids(self) -> set[str]:
        return self._store.enterprise_connection_ids()

    def engagement_connection_ids(self) -> set[str]:
        return self._store.engagement_connection_ids()

    def entity_status(self, artifact_id: str) -> str | None:
        return self._store.entity_status(artifact_id)

    def entity_statuses(self) -> dict[str, str]:
        return self._store.entity_statuses()

    def connection_status(self, artifact_id: str) -> str | None:
        return self._store.connection_status(artifact_id)

    def scope_for_path(self, path: Path) -> Literal["enterprise", "engagement", "unknown"]:
        return self._store.scope_for_path(path)

    def scope_of_entity(self, artifact_id: str) -> Literal["enterprise", "engagement", "unknown"]:
        return self._store.scope_of_entity(artifact_id)

    def scope_of_connection(
        self, artifact_id: str
    ) -> Literal["enterprise", "engagement", "unknown"]:
        return self._store.scope_of_connection(artifact_id)
