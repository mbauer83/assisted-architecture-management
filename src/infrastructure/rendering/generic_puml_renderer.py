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
    format_multiplicity_label,
    format_specializations_guillemet,
)
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.module_types import ConnectionTypeName, ElementClassName
from src.domain.ontology_protocol import DiagramRendererReferences
from src.domain.ontology_types import ConnectionTypeInfo
from src.domain.relationship_reachability import is_derived_connection_id
from src.domain.specializations import SpecializationCatalog, merge_specialization_catalogs
from src.infrastructure.rendering._archimate_includes import (
    inject_archimate_includes,
)
from src.infrastructure.rendering._diagram_layout import (
    build_branch_direction_hints,
    build_nested_layout_lines,
)
from src.infrastructure.rendering._diagram_text import insert_arrow_direction, insert_arrow_line_style
from src.infrastructure.rendering.archimate_entity_declarations import (
    entity_declaration,
    entity_nest_declaration,
    grouping_key,
    grouping_stereotype,
    ordered_domains,
    ordered_entity_type_groups,
)
from src.infrastructure.rendering.archimate_occurrences import occurrence_entities
from src.infrastructure.rendering.generic_puml_layout import (
    build_generic_visual_nesting,
)
from src.infrastructure.rendering.puml_safety import (
    configured_puml_size_warning_threshold,
    warn_when_puml_exceeds_threshold,
)


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
        *,
        diagram_entities: Mapping[str, object] | None = None,
        diagram_connections: list[dict[str, object]] | None = None,
        edge_labels: dict[str, str] | None = None,
        label_attribute: str | None = None,
    ) -> str:
        del repo_root
        diagram_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-") or "diagram"
        lines: list[str] = [f"@startuml {diagram_name}"]
        for include in self._includes():
            lines.append(f"!include ../{include}")
        lines.extend(["", f"title {name}", ""])

        entity_by_id = {entity.artifact_id: entity for entity in entities}
        render_entities = list(entities)
        render_entities.extend(occurrence_entities(diagram_entities, entity_by_id))

        alias_by_id = {
            entity.artifact_id: normalize_puml_alias(entity.display_alias)
            for entity in entities
            if entity.display_alias
        }
        entity_by_alias = {
            normalize_puml_alias(entity.display_alias): entity for entity in render_entities if entity.display_alias
        }

        domain_entities: dict[str, list[EntityRecord]] = defaultdict(list)
        for entity in render_entities:
            alias = normalize_puml_alias(entity.display_alias)
            if alias:
                domain_entities[grouping_key(entity, _registry())].append(entity)

        ordered_domain_keys = ordered_domains(domain_entities, _registry())
        single_domain = len(ordered_domain_keys) == 1
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

        specialization_catalog = self._specialization_catalog()

        def render_entity(entity: EntityRecord, indent: str) -> list[str]:
            alias = normalize_puml_alias(entity.display_alias)
            if not alias:
                return []
            children = children_map.get(alias, [])
            decl_args = (entity, alias, _registry(), self._junction_types(), specialization_catalog)
            if not children:
                return [f"{indent}{entity_declaration(*decl_args, label_attribute=label_attribute)}"]
            inner = indent + "  "
            rendered = [f"{indent}{entity_nest_declaration(*decl_args, label_attribute=label_attribute)}"]
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
        if single_domain and ordered_domain_keys:
            lines.insert(len(self._includes()) + 2, "top to bottom direction")
            lines.insert(len(self._includes()) + 3, "")
            domain = ordered_domain_keys[0]
            grouping = grouping_stereotype(self._config, domain)
            prev_anchor_alias: str | None = None
            for index, (label, grouped_entities) in enumerate(
                ordered_entity_type_groups(domain_entities[domain], _registry())
            ):
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
            for domain in ordered_domain_keys:
                lines.append(f'rectangle "{domain.title()}" <<{grouping_stereotype(self._config, domain)}>> {{')
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
            resolved_specs = [
                specialization_catalog.get("connection", conn.conn_type, slug) for slug in conn.specializations
            ]
            # Primary specialization drives notation (arrow line style, marker); the label
            # below shows all of them (§15.2 comma-separated list).
            conn_spec = next((info for info in resolved_specs if info is not None), None)
            arrow = conn_info.puml_arrow if conn_info else "-->"
            if is_derived_connection_id(conn.artifact_id):
                certainty = conn.extra.get("certainty") if isinstance(conn.extra, Mapping) else None
                arrow = insert_arrow_line_style(arrow, "dashed" if certainty == "certain" else "dotted")
            elif conn_spec is not None and conn_spec.notation.line_style and not direction:
                arrow = insert_arrow_line_style(arrow, conn_spec.notation.line_style)
            if direction:
                arrow = insert_arrow_direction(arrow, direction)
            override = edge_labels.get(f"{src}:{tgt}") if edge_labels else None
            if override is not None:
                label = override
            else:
                visible_label = self.visible_connection_label(conn, diagram_connections)
                if conn_spec is not None and conn_spec.notation.label_marker:
                    visible_label = f"{conn_spec.notation.label_marker} {visible_label}".strip()
                show_stereo = conn_info.show_stereotype if conn_info is not None else True
                if show_stereo:
                    label = f"<<{display_connection_label(conn.conn_type)}>>"
                    if visible_label:
                        label = f"{label} {visible_label}"
                else:
                    label = visible_label
                guillemet = format_specializations_guillemet(
                    [info.name for info in resolved_specs if info is not None]
                )
                if guillemet:
                    label = f"{label} {guillemet}".strip() if label else guillemet
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
        bindings: list[dict[str, object]] | None = None,
    ) -> DiagramRendererReferences:
        del diagram_type, repo_root, diagram_entities, diagram_connections, bindings
        return DiagramRendererReferences()

    def visible_connection_label(
        self,
        conn: ConnectionRecord,
        diagram_connections: list[dict[str, object]] | None = None,
    ) -> str:
        del diagram_connections
        return format_multiplicity_label(conn.src_multiplicity, conn.tgt_multiplicity)

    def _includes(self) -> list[str]:
        return [str(value) for value in self._config.get("includes", ())]

    def _connection_info(self, conn_type: str) -> ConnectionTypeInfo | None:
        return _registry().find_connection_type(ConnectionTypeName(conn_type))

    def _specialization_catalog(self) -> SpecializationCatalog:
        """The merged specialization catalog across every registered ontology — same
        module-registry-singleton pattern already used by `_connection_info`/
        `_junction_types` above, not a new service-locator surface."""
        return merge_specialization_catalogs(
            *(module.specialization_catalog for module in _registry().all_ontologies().values())
        )

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
            result.update(_registry().connection_types_with_class(str(value)))
        return frozenset(result)

    def _nesting_conn_types(self) -> frozenset[str]:
        return self._classified_conn_types("nesting_connection_classes", "nesting")

    def _flow_conn_types(self) -> frozenset[str]:
        return self._classified_conn_types("flow_connection_classes", "dynamic")

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
