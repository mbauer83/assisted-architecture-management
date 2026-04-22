from __future__ import annotations

from pathlib import Path
from typing import Literal

from src.common.artifact_index import shared_artifact_index


class ArtifactRegistry:
    """Verifier/write-oriented facade over the shared model index."""

    def __init__(self, repo_root: Path | list[Path]) -> None:
        self._index = shared_artifact_index(repo_root)
        self._index.refresh()

    @property
    def repo_roots(self) -> list[Path]:
        return self._index.repo_roots

    def refresh(self) -> None:
        self._index.refresh()

    def find_file_by_id(self, artifact_id: str) -> Path | None:
        return self._index.find_file_by_id(artifact_id)

    def entity_ids(self) -> set[str]:
        return self._index.entity_ids()

    def enterprise_entity_ids(self) -> set[str]:
        return self._index.enterprise_entity_ids()

    def engagement_entity_ids(self) -> set[str]:
        return self._index.engagement_entity_ids()

    def connection_ids(self) -> set[str]:
        return self._index.connection_ids()

    def enterprise_connection_ids(self) -> set[str]:
        return self._index.enterprise_connection_ids()

    def engagement_connection_ids(self) -> set[str]:
        return self._index.engagement_connection_ids()

    def entity_status(self, artifact_id: str) -> str | None:
        return self._index.entity_status(artifact_id)

    def entity_statuses(self) -> dict[str, str]:
        return self._index.entity_statuses()

    def connection_status(self, artifact_id: str) -> str | None:
        return self._index.connection_status(artifact_id)

    def scope_for_path(self, path: Path) -> Literal["enterprise", "engagement", "unknown"]:
        scope = self._index.scope_for_path(path)
        return "enterprise" if scope == "enterprise" else "engagement" if scope == "engagement" else "unknown"

    def scope_of_entity(self, artifact_id: str) -> Literal["enterprise", "engagement", "unknown"]:
        scope = self._index.scope_of_entity(artifact_id)
        return "enterprise" if scope == "enterprise" else "engagement" if scope == "engagement" else "unknown"

    def scope_of_connection(self, artifact_id: str) -> Literal["enterprise", "engagement", "unknown"]:
        scope = self._index.scope_of_connection(artifact_id)
        return "enterprise" if scope == "enterprise" else "engagement" if scope == "engagement" else "unknown"
