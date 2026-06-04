"""UCA matrix diagram type — bespoke frontend grid renderer.

The frontend renders UCA matrices as an interactive markdown-style grid
(control-action × guideword). PlantUML rendering is explicitly unsupported;
render_body raises ValueError to prevent the PUML pipeline from being invoked.

module_class = "assurance"; requires the confidential store.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.module_types import ConnectionTypeName, DiagramTypeName, EntityTypeName, FreeOntology
from src.domain.ontology_protocol import (
    DiagramRenderer,
    DiagramRendererReferences,
    DiagramTypeBase,
    DiagramTypeModule,
    DiagramTypeWriteGuidance,
)
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

_EMPTY_ENTITY_TYPES: dict[EntityTypeName, EntityTypeInfo] = {}
_EMPTY_CONNECTION_TYPES: dict[ConnectionTypeName, ConnectionTypeInfo] = {}


class _UcaMatrixRenderer:
    def render_body(
        self,
        name: str,
        entities: Sequence[EntityRecord],
        connections: Sequence[ConnectionRecord],
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
    ) -> str:
        del name, entities, connections, diagram_type, repo_root, diagram_entities, diagram_connections
        raise ValueError("UCA matrix diagrams use the markdown UCA grid renderer")

    def inject_includes(self, body: str, repo_root: Path) -> str:
        del repo_root
        return body

    def collect_references(
        self,
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
        bindings: list[dict[str, object]] | None = None,
    ) -> DiagramRendererReferences:
        del diagram_type, repo_root, diagram_entities, diagram_connections, bindings
        return DiagramRendererReferences()


class _UcaMatrixDiagramType(DiagramTypeBase):
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
    def renderer(self) -> DiagramRenderer:
        return _UcaMatrixRenderer()

    def write_guidance(self) -> DiagramTypeWriteGuidance:
        return DiagramTypeWriteGuidance(
            when_to_use=(
                "Use to display the UCA grid: rows=control-actions, columns=uca-types "
                "(not-provided, provided-when-unsafe, wrong-timing, stopped-too-soon). "
                "The frontend renders this as an interactive markdown grid."
            ),
            when_not_to_use=(
                "Do not use for PlantUML rendering pipelines. This diagram type has no PUML "
                "body; any attempt to call render_body raises ValueError by design."
            ),
        )


def _load_config(package_dir: Path) -> dict[str, Any]:
    config_path = package_dir / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


module: DiagramTypeModule = _UcaMatrixDiagramType(_load_config(Path(__file__).parent))
