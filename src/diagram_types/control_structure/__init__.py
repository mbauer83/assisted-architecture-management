"""Control-structure diagram type for STPA/STAMP analysis.

Renders a PlantUML component diagram from diagram_entities JSON, showing
control-structure-nodes (CSN) and control-actions (CTA) with their
issues/acts-on/feedback edges.  Binding status is visualised via
background colour and a name marker.

module_class = "assurance"; requires the confidential store.
"""

from __future__ import annotations

import json as _json
import re as _re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.diagram_types._base import DiagramTypeBase
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.module_types import ConnectionTypeName, DiagramTypeName, EntityTypeName, FreeOntology
from src.domain.ontology_protocol import (
    DiagramRenderer,
    DiagramRendererReferences,
    DiagramTypeModule,
    DiagramTypeWriteGuidance,
)
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import PermittedRelationshipSet

_EMPTY_ENTITY_TYPES: dict[EntityTypeName, EntityTypeInfo] = {}
_EMPTY_CONNECTION_TYPES: dict[ConnectionTypeName, ConnectionTypeInfo] = {}

# binding_status → (PlantUML background colour, label suffix)
_BINDING_STYLE: dict[str, tuple[str, str]] = {
    "bound":            ("#White",       ""),
    "unbound-pending":  ("#LightYellow", " [?]"),
    "out-of-scope":     ("#LightGray",   " [~]"),
}
_DEFAULT_BINDING_STYLE: tuple[str, str] = ("#White", "")

# node_role → PlantUML stereotype label
_ROLE_STEREOTYPE: dict[str, str] = {
    "controller":         "<<controller>>",
    "controlled-process": "<<controlled-process>>",
    "actuator":           "<<actuator>>",
    "sensor":             "<<sensor>>",
}

# connection type → (arrow glyph, label)
_EDGE_ARROW: dict[str, str] = {
    "issues":   "-->",
    "acts-on":  "-->",
    "feedback": "..>",
}
_EDGE_LABEL: dict[str, str] = {
    "issues":   "issues",
    "acts-on":  "acts-on",
    "feedback": "feedback",
}


def _safe_alias(node_id: str) -> str:
    safe = _re.sub(r"[^A-Za-z0-9_]", "_", node_id)
    safe = _re.sub(r"_+", "_", safe).strip("_")
    return safe or "node"


class _ControlStructureRenderer:
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

        lines: list[str] = [f"@startuml {_safe_alias(name)}", "left to right direction", ""]

        for node in nodes:
            node_id = str(node.get("node_id", ""))
            node_name = str(node.get("name", node_id))
            node_type = str(node.get("node_type", ""))
            binding = str(node.get("binding_status") or "bound")
            role = str(node.get("node_role") or "")
            colour, suffix = _BINDING_STYLE.get(binding, _DEFAULT_BINDING_STYLE)
            stereotype = _ROLE_STEREOTYPE.get(role, "")
            alias = _safe_alias(node_id)
            keyword = "control" if node_type == "control-action" else "component"
            label = f'"{node_name}{suffix}"'
            if stereotype:
                lines.append(f"{keyword} {label} {stereotype} as {alias} {colour}")
            else:
                lines.append(f"{keyword} {label} as {alias} {colour}")

        if nodes:
            lines.append("")

        for edge in edges:
            src = _safe_alias(str(edge.get("source_id", "")))
            tgt = _safe_alias(str(edge.get("target_id", "")))
            conn = str(edge.get("conn_type", ""))
            arrow = _EDGE_ARROW.get(conn, "-->")
            label = _EDGE_LABEL.get(conn, conn)
            lines.append(f"{src} {arrow} {tgt} : {label}")

        lines.extend(["", "@enduml"])
        return "\n".join(lines)

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


class _ControlStructureDiagramType(DiagramTypeBase):
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
        return _ControlStructureRenderer()

    def write_guidance(self) -> DiagramTypeWriteGuidance:
        return DiagramTypeWriteGuidance(
            when_to_use=(
                "Use to visualise the STAMP control structure for an STPA analysis. "
                "Shows controllers, controlled processes, and control actions with their "
                "binding status relative to the architecture model."
            ),
            when_not_to_use=(
                "Do not use for general component architecture or deployment topology. "
                "This diagram type is assurance-only and renders into the confidential store context."
            ),
        )


def _load_config(package_dir: Path) -> dict[str, Any]:
    config_path = package_dir / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


module: DiagramTypeModule = _ControlStructureDiagramType(_load_config(Path(__file__).parent))
