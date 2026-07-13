"""Narrow read port for the repository-context projection: the pure
criteria-evaluator's ``CriteriaReadAccess`` plus repo-scope-partitioned entity enumeration
and connection point-lookup (the execution result needs full ``ConnectionRecord``s
for its per-item summaries, not just ids).

Structurally identical to the matching slice of ``ArtifactIndexLifecycle``/``ArtifactLookup``
(``src/application/ports.py``) — the real artifact index and the verifier's
``ArtifactRegistry`` already satisfy this, so no new adapter is needed, per the standing
"use existing read ports" rule.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.artifact_types import ConnectionRecord
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess


class RepositoryReadAccess(CriteriaReadAccess, Protocol):
    def entity_ids(self) -> set[str]: ...
    def enterprise_entity_ids(self) -> set[str]: ...
    def engagement_entity_ids(self) -> set[str]: ...
    def connection_ids(self) -> set[str]: ...
    def enterprise_connection_ids(self) -> set[str]: ...
    def engagement_connection_ids(self) -> set[str]: ...
    def get_connection(self, artifact_id: str) -> ConnectionRecord | None: ...
