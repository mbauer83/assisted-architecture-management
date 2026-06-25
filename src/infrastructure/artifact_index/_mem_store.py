from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.application.ports import Candidate
from src.domain.artifact_id import stable_id
from src.domain.artifact_types import ConnectionRecord, DiagramRecord, DocumentRecord, EntityRecord


@dataclass
class _MemStore:
    entities: dict[str, EntityRecord] = field(default_factory=dict)
    connections: dict[str, ConnectionRecord] = field(default_factory=dict)
    diagrams: dict[str, DiagramRecord] = field(default_factory=dict)
    documents: dict[str, DocumentRecord] = field(default_factory=dict)
    entity_by_path: dict[Path, str] = field(default_factory=dict)
    connections_by_path: dict[Path, set[str]] = field(default_factory=dict)
    connections_by_entity: dict[str, set[str]] = field(default_factory=dict)
    diagram_by_path: dict[Path, str] = field(default_factory=dict)
    document_by_path: dict[Path, str] = field(default_factory=dict)
    entities_by_diagram: dict[str, set[str]] = field(default_factory=dict)
    """diagram_id → set of diagram-only entity artifact_ids owned by that diagram."""
    connections_by_diagram: dict[str, set[str]] = field(default_factory=dict)
    """diagram_id → set of diagram-owned connection artifact_ids (artifact_id contains '#conn/')."""
    attribute_type_refs: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)
    """diagram_id → [(classifier_local_id, attr_name, type_id)] for classifier-typed attributes."""
    identity_candidates: dict[str, list[Candidate]] = field(default_factory=dict)
    """stable_id → all Candidate files ever indexed under that stable key (cross-mount multimap)."""

    def canonical_id(self, artifact_id: str) -> str:
        """Resolve a short or stale-slug id to the stored full id (any artifact kind).

        Lets readers pass either form: an exact hit wins; otherwise the unique
        record whose stable id matches is returned. Falls back to *artifact_id*
        unchanged when it is absent or ambiguous across mounts (so the caller's
        own lookup then misses safely). Must be called under the index read lock.
        """
        stores = (self.entities, self.connections, self.diagrams, self.documents)
        if any(artifact_id in store for store in stores):
            return artifact_id
        short = stable_id(artifact_id)
        for store in stores:
            matches = [key for key in store if stable_id(key) == short]
            if len(matches) == 1:
                return matches[0]
        return artifact_id

    def clear(self) -> None:
        for attr in (
            "entities",
            "connections",
            "diagrams",
            "documents",
            "entity_by_path",
            "connections_by_path",
            "connections_by_entity",
            "diagram_by_path",
            "document_by_path",
            "entities_by_diagram",
            "connections_by_diagram",
            "attribute_type_refs",
            "identity_candidates",
        ):
            getattr(self, attr).clear()

    def replace_from(self, other: _MemStore) -> None:
        for attr in ("entities", "connections", "diagrams", "documents", "identity_candidates", "attribute_type_refs"):
            getattr(self, attr).clear()
            getattr(self, attr).update(getattr(other, attr))

    def rebuild_path_indexes(self) -> None:
        self.entity_by_path = {
            r.path.resolve(): r.artifact_id for r in self.entities.values() if r.host_diagram_id is None
        }
        self.entities_by_diagram = {}
        for r in self.entities.values():
            if r.host_diagram_id is not None:
                self.entities_by_diagram.setdefault(r.host_diagram_id, set()).add(r.artifact_id)
        self.diagram_by_path = {r.path.resolve(): r.artifact_id for r in self.diagrams.values()}
        self.document_by_path = {r.path.resolve(): r.artifact_id for r in self.documents.values()}
        by_path: dict[Path, set[str]] = {}
        by_entity: dict[str, set[str]] = {}
        by_diagram: dict[str, set[str]] = {}
        for r in self.connections.values():
            by_path.setdefault(r.path.resolve(), set()).add(r.artifact_id)
            by_entity.setdefault(r.source, set()).add(r.artifact_id)
            by_entity.setdefault(r.target, set()).add(r.artifact_id)
            if "#conn/" in r.artifact_id:
                diagram_id = r.artifact_id.split("#conn/")[0]
                by_diagram.setdefault(diagram_id, set()).add(r.artifact_id)
        self.connections_by_path = by_path
        self.connections_by_entity = by_entity
        self.connections_by_diagram = by_diagram
