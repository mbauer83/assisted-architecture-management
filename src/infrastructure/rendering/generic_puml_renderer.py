"""Config-backed PlantUML renderer for diagram kinds."""

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
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.infrastructure.rendering._archimate_includes import (
    inject_archimate_includes,
    parse_archimate_display_block,
)
from src.infrastructure.rendering._diagram_layout import (
    build_branch_direction_hints,
    build_nested_layout_lines,
    build_visual_nesting,
)
from src.infrastructure.rendering._diagram_text import insert_arrow_direction, pluralize_label


def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


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
    ) -> str:
        del repo_root
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
            normalize_puml_alias(entity.display_alias): entity
            for entity in entities
            if entity.display_alias
        }

        domain_entities: dict[str, list[EntityRecord]] = defaultdict(list)
        for entity in entities:
            alias = normalize_puml_alias(entity.display_alias)
            if alias:
                domain_entities[self._domain_dir(entity)] .append(entity)

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
            alias for alias, entity in entity_by_alias.items()
            if entity.artifact_type in self._junction_types()
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
            decl = self._entity_declaration(entity, alias)
            children = children_map.get(alias, [])
            if not children:
                return [f"{indent}{decl}"]
            inner = indent + "  "
            rendered = [f"{indent}{decl} {{"]
            for child in children:
                rendered.extend(render_entity(child, inner))
            child_als = [
                normalize_puml_alias(child.display_alias)
                for child in children
                if child.display_alias
            ]
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
            card_label = format_cardinality_label(conn.src_cardinality, conn.tgt_cardinality)
            macro_line = render_archimate_relation(src, tgt, conn.conn_type, direction=direction, label_text=card_label)
            if macro_line is not None:
                conn_lines.append(macro_line)
                continue
            arrow = conn_info.puml_arrow if conn_info else "-->"
            if direction:
                arrow = insert_arrow_direction(arrow, direction)
            label = f"<<{display_connection_label(conn.conn_type)}>>"
            if card_label:
                label = f"{label} {card_label}"
            conn_lines.append(f"{src} {arrow} {tgt} : {label}")
        if conn_lines:
            lines.append("' Connections")
            lines.extend(conn_lines)
            lines.append("")

        lines.append("@enduml")
        return "\n".join(lines)

    def inject_includes(self, body: str, repo_root: Path) -> str:
        if "_archimate-stereotypes.puml" not in "\n".join(self._includes()):
            return body
        return inject_archimate_includes(body, repo_root)

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
        return self._classified_conn_types("flow_connection_classes", "flow")

    def _domain_dir(self, entity: EntityRecord) -> str:
        info = self._entity_info(entity.artifact_type)
        if info is not None:
            return info.domain_dir
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

    def _grouping_stereotype(self, domain_dir: str) -> str:
        grouping = self._config.get("grouping", {})
        if not isinstance(grouping, dict):
            return domain_dir.capitalize() + "Grouping"
        pattern = str(grouping.get("stereotype_pattern", "{domain_dir|capitalize}Grouping"))
        return pattern.replace("{domain_dir|capitalize}", domain_dir.capitalize()).replace("{domain_dir}", domain_dir)

    def _entity_label_and_type(
        self,
        entity: EntityRecord,
        *,
        fallback_to_ontology: bool,
    ) -> tuple[str, str | None]:
        archimate_block = parse_archimate_display_block(entity.display_blocks.get("archimate", ""))
        label = str(archimate_block.get("label") or entity.display_label or entity.name).replace('"', "'")
        element_type = str(archimate_block.get("element-type") or "").strip() or None
        info = self._entity_info(entity.artifact_type)
        if fallback_to_ontology and element_type is None and info is not None:
            element_type = info.archimate_element_type
        return label, element_type

    def _entity_declaration(self, entity: EntityRecord, alias: str) -> str:
        if entity.artifact_type in self._junction_types():
            return f'circle " " as {alias}'
        label, element_type = self._entity_label_and_type(entity, fallback_to_ontology=False)
        info = self._entity_info(entity.artifact_type)
        if element_type and info is not None and info.has_sprite:
            return f'rectangle "<$archimate_{element_type}{{scale=1.5}}> {label}" <<{element_type}>> as {alias}'
        if element_type:
            return f'rectangle "{label}" <<{element_type}>> as {alias}'
        return f'rectangle "{label}" as {alias}'

    def _type_group_label(self, entity: EntityRecord) -> str:
        _label, element_type = self._entity_label_and_type(entity, fallback_to_ontology=True)
        if element_type:
            return pluralize_label(element_type)
        return pluralize_label(entity.artifact_type.replace("-", " ").title())

    def _ordered_type_groups(self, entities: list[EntityRecord]) -> list[tuple[str, list[EntityRecord]]]:
        grouped: dict[str, list[EntityRecord]] = defaultdict(list)
        labels: dict[str, str] = {}
        for entity in entities:
            grouped[entity.artifact_type].append(entity)
            labels.setdefault(entity.artifact_type, self._type_group_label(entity))
        type_order: list[str] = [str(k) for k in _registry().all_entity_types()]
        ordered_types: list[str] = [artifact_type for artifact_type in type_order if artifact_type in grouped]
        for artifact_type in grouped:
            if artifact_type not in ordered_types:
                ordered_types.append(artifact_type)
        return [(labels[artifact_type], grouped[artifact_type]) for artifact_type in ordered_types]

    def _build_visual_nesting(
        self,
        entities: Sequence[EntityRecord],
        connections: Sequence[ConnectionRecord],
        alias_by_id: Mapping[str, str],
        entity_by_alias: Mapping[str, EntityRecord],
    ) -> tuple[dict[str, list[EntityRecord]], set[str]]:
        entity_order = {
            normalize_puml_alias(entity.display_alias): index
            for index, entity in enumerate(entities)
            if entity.display_alias
        }
        structural_edges: list[tuple[str, str]] = []
        neighbor_edges: list[tuple[str, str]] = []
        for conn in connections:
            src_alias = alias_by_id.get(conn.source)
            tgt_alias = alias_by_id.get(conn.target)
            if not src_alias or not tgt_alias:
                continue
            if conn.conn_type in self._nesting_conn_types() and tgt_alias in entity_by_alias:
                structural_edges.append((src_alias, tgt_alias))
                continue
            neighbor_edges.append((src_alias, tgt_alias))
        children_map, nested_aliases = build_visual_nesting(
            item_by_alias=dict(entity_by_alias),
            structural_edges=structural_edges,
            neighbor_edges=neighbor_edges,
            junction_aliases={
                alias for alias, entity in entity_by_alias.items()
                if entity.artifact_type in self._junction_types()
            },
        )
        for parent_alias, children in children_map.items():
            children.sort(
                key=lambda entity: entity_order.get(normalize_puml_alias(entity.display_alias), len(entity_order))
            )
        return children_map, nested_aliases
