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


def _build_entity_filter(filter_cfg: dict[str, Any]):
    """Return a predicate that tests whether an EntityTypeInfo matches the filter config.

    Supported filter clauses (all present clauses are ANDed):
    - ``hierarchy_level``: ``{index: int, values: [str]}`` — hierarchy[index] must be in values
    - ``element_classes``: ``[str]`` — entity must have at least one listed class
    - ``entity_types``: ``[str]`` — entity artifact_type must be in the explicit list
    """
    hierarchy_cfg = filter_cfg.get("hierarchy_level")
    class_set = frozenset(str(c) for c in filter_cfg.get("element_classes", ()))
    type_set = frozenset(str(t) for t in filter_cfg.get("entity_types", ()))

    def _matches(info: EntityTypeInfo) -> bool:
        if hierarchy_cfg:
            idx = int(hierarchy_cfg["index"])
            values = frozenset(str(v) for v in hierarchy_cfg.get("values", ()))
            if idx >= len(info.hierarchy) or info.hierarchy[idx] not in values:
                return False
        if class_set and not class_set.intersection(info.element_classes):
            return False
        if type_set and info.artifact_type not in type_set:
            return False
        return True

    return _matches


class _ConfiguredArchimateDiagramKind(DiagramKindBase):
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._name = DiagramKindName(str(config["name"]))
        filter_cfg: dict[str, Any] = config.get("filter", {})
        self._entity_filter = _build_entity_filter(filter_cfg)

    @property
    def name(self) -> DiagramKindName:
        return self._name

    @property
    def primary_ontology(self):  # type: ignore[override]
        return archimate_next

    def accepts_entity_type(self, t: EntityTypeName) -> bool:
        info = archimate_next.entity_types.get(t)
        return info is not None and self._entity_filter(info)

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
        config: dict[str, Any] = yaml.safe_load(handle) or {}
    return _ConfiguredArchimateDiagramKind(config)
