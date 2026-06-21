from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
        ):
            getattr(self, attr).clear()

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
