"""GSN (Goal Structuring Notation) diagram type for assurance cases.

Renders a PlantUML diagram from GSN nodes and edges, following GSN notation:
  G  = Goal (rectangle)
  S  = Strategy (parallelogram — rendered as card)
  Sn = Solution/Evidence (database shape)
  C  = Context (rounded rectangle — rendered as usecase)
  A  = Assumption (rounded rectangle with A label)
  J  = Justification (rounded rectangle with J label)

Connections:
  "supported-by"   — downward decomposition (solid arrow)
  "in-context-of"  — context linkage (dashed arrow)

diagram_entities JSON format:
  nodes: list of {node_id, name, gsn_type}
    gsn_type values: "goal", "strategy", "solution", "context", "assumption", "justification"
  edges: list of {source_id, target_id, conn_type}
    conn_type values: "supported-by", "in-context-of"

module_class = "assurance"; requires the confidential store.
"""

from __future__ import annotations

import json as _json
import re as _re
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

# gsn_type → (PlantUML shape keyword, colour, label prefix)
_GSN_STYLE: dict[str, tuple[str, str, str]] = {
    "goal":          ("rectangle",  "#D0E8FF", "G: "),
    "strategy":      ("card",       "#E8E0FF", "S: "),
    "solution":      ("database",   "#D0FFD8", "Sn: "),
    "context":       ("usecase",    "#FFFFD0", "C: "),
    "assumption":    ("usecase",    "#FFE8D0", "A: "),
    "justification": ("usecase",    "#FFD0E8", "J: "),
}
_DEFAULT_GSN_STYLE: tuple[str, str, str] = ("rectangle", "#White", "")

# conn_type → arrow glyph
_CONN_ARROW: dict[str, str] = {
    "supported-by":  "-->",
    "in-context-of": "..>",
}


def _safe_alias(node_id: str) -> str:
    safe = _re.sub(r"[^A-Za-z0-9_]", "_", node_id)
    safe = _re.sub(r"_+", "_", safe).strip("_")
    return safe or "node"


def _render_gsn(name: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    lines: list[str] = [f"@startuml {_safe_alias(name)}", "top to bottom direction", ""]

    for node in nodes:
        node_id = str(node.get("node_id", ""))
        node_name = str(node.get("name", node_id))
        gsn_type = str(node.get("gsn_type") or "goal")
        keyword, colour, prefix = _GSN_STYLE.get(gsn_type, _DEFAULT_GSN_STYLE)
        alias = _safe_alias(node_id)
        display = f"{prefix}{node_name}"
        lines.append(f'{keyword} "{display}" as {alias} {colour}')

    if nodes:
        lines.append("")

    for edge in edges:
        src = _safe_alias(str(edge.get("source_id", "")))
        tgt = _safe_alias(str(edge.get("target_id", "")))
        conn = str(edge.get("conn_type") or "supported-by")
        arrow = _CONN_ARROW.get(conn, "-->")
        lines.append(f"{src} {arrow} {tgt} : {conn}")

    lines.extend(["", "@enduml"])
    return "\n".join(lines)


class _GsnDiagramRenderer:
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
        del entities, connections, diagram_type, repo_root
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        if diagram_entities:
            raw_nodes = diagram_entities.get("nodes")
            raw_edges = diagram_entities.get("edges")
            if isinstance(raw_nodes, str):
                raw_nodes = _json.loads(raw_nodes)
            if isinstance(raw_edges, str):
                raw_edges = _json.loads(raw_edges)
            if isinstance(raw_nodes, list):
                nodes = [n for n in raw_nodes if isinstance(n, dict)]
            if isinstance(raw_edges, list):
                edges = [e for e in raw_edges if isinstance(e, dict)]

        if diagram_connections:
            edges = edges + [e for e in diagram_connections if isinstance(e, dict)]

        return _render_gsn(name, nodes, edges)

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
    def renderer(self) -> DiagramRenderer:
        return _GsnDiagramRenderer()

    def write_guidance(self) -> DiagramTypeWriteGuidance:
        return DiagramTypeWriteGuidance(
            when_to_use=(
                "Use to render a Goal Structuring Notation (GSN) argument structure for an assurance case. "
                "Shows goals (G), strategies (S), solutions/evidence (Sn), contexts (C), "
                "assumptions (A), and justifications (J) with supported-by and in-context-of edges. "
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
