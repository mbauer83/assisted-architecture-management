"""Config-backed PlantUML renderer for diagram types."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from src.application.artifact_parsing import normalize_puml_alias
from src.domain.archimate_relation_rendering import (
    display_connection_label,
    format_cardinality_label,
    render_archimate_relation,
)
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_protocol import DiagramRendererReferences
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.infrastructure.rendering._archimate_includes import (
    inject_archimate_includes,
    parse_archimate_display_block,
)
from src.infrastructure.rendering._diagram_layout import (
    build_branch_direction_hints,
    build_nested_layout_lines,
)
from src.infrastructure.rendering._diagram_text import insert_arrow_direction, pluralize_label
from src.infrastructure.rendering.generic_puml_layout import (
    build_generic_visual_nesting,
    ordered_type_groups,
)
from src.infrastructure.rendering.puml_safety import (
    configured_puml_size_warning_threshold,
    warn_when_puml_exceeds_threshold,
)


def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def _stereotype_key(artifact_type: str) -> str:
    return artifact_type.replace("-", "_")


class GenericPumlRenderer:
    """Renderer for config-backed ArchiMate-style PlantUML diagrams."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self._config: dict[str, Any] = dict(config)

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
        del repo_root, diagram_entities
        diagram_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-") or "diagram"
        lines: list[str] = [f"@startuml {diagram_name}"]
        for include in self._includes():
            lines.append(f"!include ../{include}")
        lines.extend(["", f"title {name}", ""])

        alias_by_id = {
            entity.artifact_id: normalize_puml_alias(entity.display_alias)
            for entity in entities
            if entity.display_alias
        }
        entity_by_alias = {
            normalize_puml_alias(entity.display_alias): entity for entity in entities if entity.display_alias
        }

        domain_entities: dict[str, list[EntityRecord]] = defaultdict(list)
        for entity in entities:
            alias = normalize_puml_alias(entity.display_alias)
            if alias:
                domain_entities[self._grouping_key(entity)].append(entity)

        ordered_domains = self._ordered_domains(domain_entities)
        single_domain = len(ordered_domains) == 1
        nested_main_axis = "down" if single_domain else "right"
        nested_branch_axis = "right" if single_domain else "down"
        flow_edges = [
            (src_alias, tgt_alias)
            for conn in connections
            if conn.conn_type in self._flow_conn_types()
            and (src_alias := alias_by_id.get(conn.source))
            and (tgt_alias := alias_by_id.get(conn.target))
        ]
        junction_aliases = {
            alias for alias, entity in entity_by_alias.items() if entity.artifact_type in self._junction_types()
        }
        layout_direction_hints: dict[tuple[str, str], str] = {}

        children_map, nested_aliases = self._build_visual_nesting(
            entities,
            connections,
            alias_by_id,
            entity_by_alias,
        )
        for domain in list(domain_entities):
            domain_entities[domain] = [
                entity
                for entity in domain_entities[domain]
                if normalize_puml_alias(entity.display_alias) not in nested_aliases
            ]

        def render_entity(entity: EntityRecord, indent: str) -> list[str]:
            alias = normalize_puml_alias(entity.display_alias)
            if not alias:
                return []
            children = children_map.get(alias, [])
            if not children:
                return [f"{indent}{self._entity_declaration(entity, alias)}"]
            inner = indent + "  "
            rendered = [f"{indent}{self._entity_nest_declaration(entity, alias)}"]
            for child in children:
                rendered.extend(render_entity(child, inner))
            child_als = [normalize_puml_alias(child.display_alias) for child in children if child.display_alias]
            layout_direction_hints.update(
                build_branch_direction_hints(
                    child_aliases=child_als,
                    flow_edges=flow_edges,
                    junction_aliases=junction_aliases,
                    branch_axis=nested_branch_axis,
                )
            )
            rendered.extend(
                build_nested_layout_lines(
                    child_aliases=child_als,
                    flow_edges=flow_edges,
                    junction_aliases=junction_aliases,
                    main_axis=nested_main_axis,
                    branch_axis=nested_branch_axis,
                    indent=inner,
                )
            )
            rendered.append(f"{indent}}}")
            return rendered

        group_index_by_alias: dict[str, int] = {}
        if single_domain and ordered_domains:
            lines.insert(len(self._includes()) + 2, "top to bottom direction")
            lines.insert(len(self._includes()) + 3, "")
            domain = ordered_domains[0]
            grouping = self._grouping_stereotype(domain)
            prev_anchor_alias: str | None = None
            for index, (label, grouped_entities) in enumerate(self._ordered_type_groups(domain_entities[domain])):
                lines.append(f'rectangle "{label}" <<{grouping}>> {{')
                for entity in grouped_entities:
                    lines.extend(render_entity(entity, "  "))
                    alias = normalize_puml_alias(entity.display_alias)
                    if alias:
                        group_index_by_alias[alias] = index
                lines.append("}")
                top_aliases = [
                    normalize_puml_alias(entity.display_alias) for entity in grouped_entities if entity.display_alias
                ]
                hidden_dir = "right" if index % 2 == 0 else "down"
                for idx in range(len(top_aliases) - 1):
                    lines.append(f"{top_aliases[idx]} -[hidden]{hidden_dir}- {top_aliases[idx + 1]}")
                if prev_anchor_alias and top_aliases:
                    lines.append(f"{prev_anchor_alias} -[hidden]down- {top_aliases[0]}")
                if top_aliases:
                    prev_anchor_alias = top_aliases[-1]
                lines.append("")
        else:
            for domain in ordered_domains:
                lines.append(f'rectangle "{domain.title()}" <<{self._grouping_stereotype(domain)}>> {{')
                for entity in domain_entities[domain]:
                    lines.extend(render_entity(entity, "  "))
                lines.append("}")
                lines.append("")

        conn_lines: list[str] = []
        for conn in connections:
            conn_info = self._connection_info(conn.conn_type)
            if conn_info and conn.conn_type in self._nesting_conn_types():
                continue
            src = alias_by_id.get(conn.source)
            tgt = alias_by_id.get(conn.target)
            if not src or not tgt:
                continue
            direction: str | None = layout_direction_hints.get((src, tgt))
            if single_domain:
                src_group = group_index_by_alias.get(src)
                tgt_group = group_index_by_alias.get(tgt)
                if direction is None and src_group is not None and tgt_group is not None and src_group != tgt_group:
                    direction = "down" if src_group < tgt_group else "up"
            visible_label = self.visible_connection_label(conn, diagram_connections)
            macro_line = render_archimate_relation(
                src,
                tgt,
                conn.conn_type,
                direction=direction,
                label_text=visible_label,
            )
            if macro_line is not None:
                conn_lines.append(macro_line)
                continue
            arrow = conn_info.puml_arrow if conn_info else "-->"
            if direction:
                arrow = insert_arrow_direction(arrow, direction)
            show_stereo = conn_info.show_stereotype if conn_info is not None else True
            if show_stereo:
                label = f"<<{display_connection_label(conn.conn_type)}>>"
                if visible_label:
                    label = f"{label} {visible_label}"
            else:
                label = visible_label
            if label:
                conn_lines.append(f"{src} {arrow} {tgt} : {label}")
            else:
                conn_lines.append(f"{src} {arrow} {tgt}")
        if conn_lines:
            lines.append("' Connections")
            lines.extend(conn_lines)
            lines.append("")

        lines.append("@enduml")
        body = "\n".join(lines)
        threshold = configured_puml_size_warning_threshold(self._config)
        warn_when_puml_exceeds_threshold(body, threshold=threshold)
        return body

    def inject_includes(self, body: str, repo_root: Path) -> str:
        _STEREO = "!include ../_archimate-stereotypes.puml"
        _GLYPH = "!include ../_archimate-glyphs.puml"
        for marker in (_STEREO, _GLYPH):
            if marker not in body:
                body = re.sub(r"(@startuml(?:\s+\S+)?)\n", rf"\1\n{marker}\n", body, count=1)
        return inject_archimate_includes(body, repo_root)

    def collect_references(
        self,
        diagram_type: str,
        repo_root: Path,
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
    ) -> DiagramRendererReferences:
        del diagram_type, repo_root, diagram_entities, diagram_connections
        return DiagramRendererReferences()

    def visible_connection_label(
        self,
        conn: ConnectionRecord,
        diagram_connections: list[dict[str, object]] | None = None,
    ) -> str:
        del diagram_connections
        return format_cardinality_label(conn.src_cardinality, conn.tgt_cardinality)

    def _includes(self) -> list[str]:
        return [str(value) for value in self._config.get("includes", ())]

    def _entity_info(self, artifact_type: str) -> EntityTypeInfo | None:
        return _registry().find_entity_type(EntityTypeName(artifact_type))

    def _connection_info(self, conn_type: str) -> ConnectionTypeInfo | None:
        return _registry().find_connection_type(ConnectionTypeName(conn_type))

    def _junction_types(self) -> frozenset[str]:
        return frozenset(_registry().entity_types_with_class(ElementClassName("junction")))

    def _classified_conn_types(self, config_key: str, default: str) -> frozenset[str]:
        layout = self._config.get("layout", {})
        if not isinstance(layout, dict):
            return frozenset()
        values = layout.get(config_key, [default])
        if not isinstance(values, list):
            return frozenset()
        result: set[str] = set()
        for value in values:
            result.update(_registry().connection_types_with_classification(str(value)))
        return frozenset(result)

    def _nesting_conn_types(self) -> frozenset[str]:
        return self._classified_conn_types("nesting_connection_classes", "nesting")

    def _flow_conn_types(self) -> frozenset[str]:
        return self._classified_conn_types("flow_connection_classes", "dynamic")

    def _grouping_key(self, entity: EntityRecord) -> str:
        info = self._entity_info(entity.artifact_type)
        if info is not None and info.hierarchy:
            return info.hierarchy[0]
        return (entity.domain or "common").lower()

    def _ordered_domains(self, domain_entities: Mapping[str, list[EntityRecord]]) -> list[str]:
        ordered: list[str] = []
        for domain in _registry().domain_order():
            if domain in domain_entities:
                ordered.append(domain)
        for domain in sorted(domain_entities):
            if domain not in ordered:
                ordered.append(domain)
        return ordered

    def _grouping_stereotype(self, grouping_key: str) -> str:
        grouping = self._config.get("grouping", {})
        if not isinstance(grouping, dict):
            return grouping_key.capitalize() + "Grouping"
        pattern = str(grouping.get("stereotype_pattern", "{hierarchy_0|capitalize}Grouping"))
        return (
            pattern.replace("{hierarchy_0|capitalize}", grouping_key.capitalize())
            .replace("{hierarchy_0}", grouping_key)
            # legacy pattern names kept for any hand-authored configs
            .replace("{domain_dir|capitalize}", grouping_key.capitalize())
            .replace("{domain_dir}", grouping_key)
        )

    def _display_section_id(self, entity: EntityRecord) -> str:
        ontology = _registry().ontology_for_entity_type(EntityTypeName(entity.artifact_type))
        if ontology is not None:
            return ontology.display_section_id
        return "archimate"

    def _entity_label_and_stereotype(
        self,
        entity: EntityRecord,
    ) -> tuple[str, str | None]:
        section_id = self._display_section_id(entity)
        raw_block = entity.display_blocks.get(section_id, "")
        archimate_block = parse_archimate_display_block(raw_block)
        label = str(archimate_block.get("label") or entity.display_label or entity.name).replace('"', "'")
        info = self._entity_info(entity.artifact_type)
        stereotype = _stereotype_key(info.artifact_type) if info else None
        return label, stereotype

    def _entity_has_sprite(self, entity: EntityRecord) -> bool:
        ontology = _registry().ontology_for_entity_type(EntityTypeName(entity.artifact_type))
        return ontology is not None and ontology.sprite_for(entity.artifact_type) is not None

    def _entity_declaration(self, entity: EntityRecord, alias: str) -> str:
        if entity.artifact_type in self._junction_types():
            return f'circle " " as {alias}'
        label, stereotype = self._entity_label_and_stereotype(entity)
        if stereotype and self._entity_has_sprite(entity):
            return f'rectangle "<$archimate_{stereotype}{{scale=1.5}}> {label}" <<{stereotype}>> as {alias}'
        if stereotype:
            return f'rectangle "{label}" <<{stereotype}>> as {alias}'
        return f'rectangle "{label}" as {alias}'

    def _entity_nest_declaration(self, entity: EntityRecord, alias: str) -> str:
        if entity.artifact_type in self._junction_types():
            return f'circle " " as {alias}'
        label, stereotype = self._entity_label_and_stereotype(entity)
        if stereotype and self._entity_has_sprite(entity):
            return f'rectangle "<$archimate_{stereotype}{{scale=1.5}}> {label}" <<{stereotype}>> as {alias} {{'
        if stereotype:
            return f'rectangle "{label}" <<{stereotype}>> as {alias} {{'
        return f'rectangle "{label}" as {alias} {{'

    def _ordered_type_groups(self, entities: list[EntityRecord]) -> list[tuple[str, list[EntityRecord]]]:
        return ordered_type_groups(
            entities,
            type_order=[str(k) for k in _registry().all_entity_types()],
            label_by_type={
                entity.artifact_type: pluralize_label(
                    (self._entity_info(entity.artifact_type) or entity).artifact_type.replace("-", " ").title()
                )
                for entity in entities
            },
        )

    def _build_visual_nesting(
        self,
        entities: Sequence[EntityRecord],
        connections: Sequence[ConnectionRecord],
        alias_by_id: Mapping[str, str],
        entity_by_alias: Mapping[str, EntityRecord],
    ) -> tuple[dict[str, list[EntityRecord]], set[str]]:
        return build_generic_visual_nesting(
            entities=entities,
            connections=connections,
            alias_by_id=alias_by_id,
            entity_by_alias=entity_by_alias,
            nesting_connection_types=self._nesting_conn_types(),
            junction_entity_types=self._junction_types(),
        )
