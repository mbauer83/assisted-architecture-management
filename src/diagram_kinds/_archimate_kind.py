"""Helpers for config-backed ArchiMate diagram kinds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.domain.module_types import ConnectionTypeName, DiagramKindName, EntityTypeName
from src.domain.ontology_protocol import DiagramKindBase, DiagramKindModule
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet
from src.ontologies.archimate_next import module as archimate_next

_EMPTY_ENTITY_TYPES: dict[EntityTypeName, EntityTypeInfo] = {}
_EMPTY_CONNECTION_TYPES: dict[ConnectionTypeName, ConnectionTypeInfo] = {}


class _ConfiguredArchimateDiagramKind(DiagramKindBase):
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._name = DiagramKindName(str(config["name"]))
        self._accepted_domains = frozenset(str(value) for value in config.get("accepted_domains", ()))

    @property
    def name(self) -> DiagramKindName:
        return self._name

    @property
    def primary_ontology(self):  # type: ignore[override]
        return archimate_next

    def accepts_entity_type(self, t: EntityTypeName) -> bool:
        info = archimate_next.entity_types.get(t)
        return info is not None and info.domain_dir in self._accepted_domains

    def accepts_connection_type(self, t: ConnectionTypeName) -> bool:
        return t in archimate_next.connection_types

    @property
    def own_entity_types(self) -> dict[EntityTypeName, EntityTypeInfo]:
        return _EMPTY_ENTITY_TYPES

    @property
    def own_connection_types(self) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
        return _EMPTY_CONNECTION_TYPES

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet:
        return PermittedRelationshipSet.empty()


def load_archimate_diagram_kind(package_dir: Path) -> DiagramKindModule:
    """Load one config-backed ArchiMate diagram kind module."""
    config_path = package_dir / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return _ConfiguredArchimateDiagramKind(config)
