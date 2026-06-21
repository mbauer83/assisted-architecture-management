"""GSN (Goal Structuring Notation) diagram type for assurance cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.diagram_types._base import DiagramTypeBase
from src.diagram_types.gsn.renderer import GsnDiagramRenderer
from src.domain.module_types import ConnectionTypeName, DiagramTypeName, EntityTypeName, FreeOntology
from src.domain.ontology_protocol import (
    DiagramTypeModule,
    DiagramTypeWriteGuidance,
)
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

_EMPTY_ENTITY_TYPES: dict[EntityTypeName, EntityTypeInfo] = {}
_EMPTY_CONNECTION_TYPES: dict[ConnectionTypeName, ConnectionTypeInfo] = {}

class _GsnDiagramType(DiagramTypeBase):
    module_class = "assurance"
    requires: list[str] = ["confidential_store"]

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config

    @property
    def name(self) -> DiagramTypeName:
        return DiagramTypeName(str(self._config["name"]))

    @property
    def primary_ontology(self):  # type: ignore[override]
        return FreeOntology

    def accepts_entity_type(self, t: EntityTypeName) -> bool:
        del t
        return False

    def accepts_connection_type(self, t: ConnectionTypeName) -> bool:
        del t
        return False

    @property
    def own_entity_types(self) -> dict[EntityTypeName, EntityTypeInfo]:
        return _EMPTY_ENTITY_TYPES

    @property
    def own_connection_types(self) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
        return _EMPTY_CONNECTION_TYPES

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet:
        return PermittedRelationshipSet.empty()

    @property
    def renderer(self) -> GsnDiagramRenderer:
        return GsnDiagramRenderer()

    def write_guidance(self) -> DiagramTypeWriteGuidance:
        return DiagramTypeWriteGuidance(
            when_to_use=(
                "Use to render a Goal Structuring Notation (GSN) argument structure for an assurance case. "
                "Shows goals (G), strategies (S), solutions/evidence (Sn), contexts (C), "
                "assumptions (A), justifications (J), and undeveloped markers with supported-by "
                "and in-context-of edges, using GSN Community Standard notation. "
                "This diagram type is assurance-only and renders into the confidential store context."
            ),
            when_not_to_use=(
                "Do not use for bowtie threat models (use bowtie instead) or STPA control structures "
                "(use control-structure instead). GSN is for structured argumentation, not causal modelling."
            ),
        )


def _load_config(package_dir: Path) -> dict[str, Any]:
    config_path = package_dir / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


module: DiagramTypeModule = _GsnDiagramType(_load_config(Path(__file__).parent))
