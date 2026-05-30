"""PlantUML renderer for C4-style diagram-owned diagram types."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.diagram_types._c4_resolve import _ResolvedItem, resolve_c4_state
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.ontology_protocol import DiagramRendererReferences
from src.infrastructure.rendering.puml_safety import (
    configured_puml_size_warning_threshold,
    warn_when_puml_exceeds_threshold,
)


class C4PumlRenderer:
    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        person_archimate_types: frozenset[str] = frozenset(),
    ) -> None:
        self._config = dict(config)
        self._person_archimate_types = person_archimate_types

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
        del entities, connections
        diagram_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-") or "c4-diagram"
        state = resolve_c4_state(
            self._config, diagram_type, repo_root,
            diagram_entities or {}, diagram_connections or [],
            self._person_archimate_types,
        )
        lines: list[str] = [
            f"@startuml {diagram_name}",
            "left to right direction",
            "skinparam shadowing false",
            "skinparam linetype ortho",
            "skinparam defaultTextAlignment center",
            "skinparam wrapWidth 240",
            "skinparam maxMessageSize 240",
            "skinparam rectangle {",
            "  RoundCorner 12",
            "  Padding 10",
            "}",
            "skinparam actor {",
            "  BackgroundColor #08427b",
            "  BorderColor #052e56",
            "  FontColor white",
            "}",
            "skinparam rectangle<<C4System>> {",
            "  BackgroundColor #1168bd",
            "  BorderColor #0b4884",
            "  FontColor white",
            "}",
            "skinparam rectangle<<C4Container>> {",
            "  BackgroundColor #438dd5",
            "  BorderColor #2f6da6",
            "  FontColor white",
            "}",
            "skinparam rectangle<<C4Component>> {",
            "  BackgroundColor #85bbf0",
            "  BorderColor #5e98c8",
            "  FontColor black",
            "}",
            "skinparam rectangle<<C4External>> {",
            "  BackgroundColor #dddddd",
            "  BorderColor #777777",
            "  FontColor black",
            "}",
            "",
            f"title {name}",
            "",
        ]

        if state.scope_render_mode == "node":
            lines.append(self._render_item(state.scope_item))
        else:
            lines.append(
                f'rectangle "{_escape_puml(state.scope_item.label)}" '
                f"<<C4System>> as {state.scope_item.alias} {{"
            )
            for item in state.internal_items:
                lines.append(f"  {self._render_item(item)}")
            self._append_hidden_chain(lines, [item.alias for item in state.internal_items], indent="  ")
            lines.append("}")

        self._append_hidden_chain(lines, [state.scope_item.alias], indent="")

        outside_items = state.outside_items
        if outside_items:
            for item in outside_items:
                lines.append(self._render_item(item))
            lines.append("")
            ordered_aliases = (
                [item.alias for item in outside_items if item.item_type == "person"]
                + [state.scope_item.alias]
                + [item.alias for item in outside_items if item.item_type != "person"]
            )
            self._append_hidden_chain(lines, ordered_aliases, indent="")

        lines.append("")
        for conn in state.connections:
            label = _escape_puml(conn.label) if conn.label else ""
            lines.append(f"{conn.src_alias} --> {conn.tgt_alias} : {label}")
        lines.append("@enduml")

        body = "\n".join(line for line in lines if line is not None)
        threshold = configured_puml_size_warning_threshold(self._config)
        warn_when_puml_exceeds_threshold(body, threshold=threshold)
        return body + "\n"

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
    ) -> DiagramRendererReferences:
        state = resolve_c4_state(
            self._config, diagram_type, repo_root,
            diagram_entities or {}, diagram_connections or [],
            self._person_archimate_types,
        )
        return DiagramRendererReferences(
            entity_ids=state.entity_ids,
            connection_ids=state.connection_artifact_ids,
        )

    def _render_item(self, item: _ResolvedItem) -> str:
        if item.item_type == "person":
            return f'actor "{_render_item_body(item)}" as {item.alias}'
        stereotype = {
            "software-system": "C4External" if item.external else "C4System",
            "container": "C4External" if item.external else "C4Container",
            "component": "C4External" if item.external else "C4Component",
        }.get(item.item_type, "C4External" if item.external else "C4Container")
        return f'rectangle "{_render_item_body(item)}" <<{stereotype}>> as {item.alias}'

    def _append_hidden_chain(self, lines: list[str], aliases: list[str], *, indent: str) -> None:
        if len(aliases) < 2:
            if aliases:
                lines.append("")
            return
        for index in range(len(aliases) - 1):
            lines.append(f"{indent}{aliases[index]} -[hidden]right- {aliases[index + 1]}")
        lines.append("")


def alias_for_c4_item(item_type: str, local_id: str, index: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", local_id)
    prefix = "".join(part[:1].upper() for part in item_type.replace("-", "_").split("_")) or "C"
    return f"{prefix}_{normalized}_{index}"


def _render_item_body(item: _ResolvedItem) -> str:
    parts = [_escape_puml(item.label)]
    if item.technology:
        parts.append(f"[{_escape_puml(item.technology)}]")
    if item.description:
        parts.append(_escape_puml(item.description))
    return "\\n".join(part for part in parts if part)


def _escape_puml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'")
