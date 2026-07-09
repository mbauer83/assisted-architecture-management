"""Bowtie diagram type for threat/hazard barrier analysis.

Renders a PlantUML component diagram showing the bowtie structure:
  threat → [barrier_left] → top_event → [barrier_right] → consequence

diagram_entities JSON format:
  nodes: list of {node_id, name, node_type, role}
    role values: "threat", "top_event", "consequence", "barrier_left", "barrier_right"
  edges: list of {source_id, target_id, label}

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

# role → (PlantUML keyword, background colour, stereotype)
_ROLE_STYLE: dict[str, tuple[str, str, str]] = {
    "threat":        ("component", "#FFD0D0", "<<threat>>"),
    "top_event":     ("component", "#FFB060", "<<top-event>>"),
    "consequence":   ("component", "#FFD0D0", "<<consequence>>"),
    "barrier_left":  ("card",      "#D0FFD0", "<<barrier>>"),
    "barrier_right": ("card",      "#D0FFD0", "<<barrier>>"),
}
_DEFAULT_ROLE_STYLE: tuple[str, str, str] = ("component", "#White", "")


def _safe_alias(node_id: str) -> str:
    safe = _re.sub(r"[^A-Za-z0-9_]", "_", node_id)
    safe = _re.sub(r"_+", "_", safe).strip("_")
    return safe or "node"


def _render_bowtie(name: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    lines: list[str] = [f"@startuml {_safe_alias(name)}", "left to right direction", ""]

    threats = [n for n in nodes if n.get("role") == "threat"]
    barriers_left = [n for n in nodes if n.get("role") == "barrier_left"]
    top_events = [n for n in nodes if n.get("role") == "top_event"]
    barriers_right = [n for n in nodes if n.get("role") == "barrier_right"]
    consequences = [n for n in nodes if n.get("role") == "consequence"]
    others = [
        n for n in nodes
        if n.get("role") not in {"threat", "barrier_left", "top_event", "barrier_right", "consequence"}
    ]

    ordered = threats + barriers_left + top_events + barriers_right + consequences + others

    for node in ordered:
        node_id = str(node.get("node_id", ""))
        node_name = str(node.get("name", node_id))
        role = str(node.get("role") or "")
        keyword, colour, stereotype = _ROLE_STYLE.get(role, _DEFAULT_ROLE_STYLE)
        alias = _safe_alias(node_id)
        label = f'"{node_name}"'
        if stereotype:
            lines.append(f"{keyword} {label} {stereotype} as {alias} {colour}")
        else:
            lines.append(f"{keyword} {label} as {alias} {colour}")

    if ordered:
        lines.append("")

    for edge in edges:
        src = _safe_alias(str(edge.get("source_id", "")))
        tgt = _safe_alias(str(edge.get("target_id", "")))
        label = str(edge.get("label") or "")
        if label:
            lines.append(f"{src} --> {tgt} : {label}")
        else:
            lines.append(f"{src} --> {tgt}")

    lines.extend(["", "@enduml"])
    return "\n".join(lines)


class _BowtieDiagramRenderer:
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

        return _render_bowtie(name, nodes, edges)

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


class _BowtieDiagramType(DiagramTypeBase):
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
        return _BowtieDiagramRenderer()

    def write_guidance(self) -> DiagramTypeWriteGuidance:
        return DiagramTypeWriteGuidance(
            when_to_use=(
                "Use to visualise a bowtie risk model: threats on the left, a top event in the "
                "centre, consequences on the right, with barrier controls on each side. "
                "Suitable for safety, security, and operational risk communication."
            ),
            when_not_to_use=(
                "Do not use for STPA control-structure diagrams (use control-structure instead) "
                "or for GSN argument structures (use gsn instead). "
                "This diagram type is assurance-only and renders into the confidential store context."
            ),
        )


def _load_config(package_dir: Path) -> dict[str, Any]:
    config_path = package_dir / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


module: DiagramTypeModule = _BowtieDiagramType(_load_config(Path(__file__).parent))
