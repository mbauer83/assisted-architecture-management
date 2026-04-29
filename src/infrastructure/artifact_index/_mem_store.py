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
        ):
            getattr(self, attr).clear()

    def rebuild_path_indexes(self) -> None:
        self.entity_by_path = {r.path.resolve(): r.artifact_id for r in self.entities.values()}
        self.diagram_by_path = {r.path.resolve(): r.artifact_id for r in self.diagrams.values()}
        self.document_by_path = {r.path.resolve(): r.artifact_id for r in self.documents.values()}
        by_path: dict[Path, set[str]] = {}
        by_entity: dict[str, set[str]] = {}
        for r in self.connections.values():
            by_path.setdefault(r.path.resolve(), set()).add(r.artifact_id)
            by_entity.setdefault(r.source, set()).add(r.artifact_id)
            by_entity.setdefault(r.target, set()).add(r.artifact_id)
        self.connections_by_path = by_path
        self.connections_by_entity = by_entity
