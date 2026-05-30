"""Shared loader for diagram-owned C4 diagram types."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.diagram_types.c4_renderer import C4PumlRenderer
from src.domain.bridges import BridgeDeclaration
from src.domain.diagram_entities_schema import derive_diagram_entities_schema
from src.domain.diagram_ontology_loader import DiagramOntology, load_diagram_ontology
from src.domain.module_types import ConnectionTypeName, DiagramTypeName, EntityTypeName, FreeOntology
from src.domain.ontology_protocol import (
    DiagramRenderer,
    DiagramTypeBase,
    DiagramTypeModule,
    DiagramTypeWriteGuidance,
    diagram_type_ui_config_from_mapping,
)
from src.domain.ontology_types import ConnectionTypeInfo, ElementClassInfo, EntityTypeInfo
from src.domain.permitted_mappings import resolve_model_entity_types_for_diagram_only_types
from src.domain.permitted_relationships import PermittedRelationshipSet

_EMPTY_ENTITY_TYPES: dict[EntityTypeName, EntityTypeInfo] = {}

_C4_OWN_CONNECTION_TYPES: dict[ConnectionTypeName, ConnectionTypeInfo] = {
    ConnectionTypeName("c4-uses"): ConnectionTypeInfo(
        artifact_type="c4-uses",
        conn_lang="c4",
        symmetric=False,
        puml_arrow="-->",
        classes=(),
        hierarchy_priority=None,
        hierarchy_label="uses",
    ),
}


def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def _load_config(package_dir: Path) -> dict[str, Any]:
    config_path = package_dir / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _parse_element_classes(config: dict[str, Any]) -> dict[str, ElementClassInfo]:
    raw: object = config.get("element_classes") or {}
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(name): ElementClassInfo(
            name=str(name),
            description=str((info or {}).get("description") or "") if isinstance(info, Mapping) else "",
        )
        for name, info in raw.items()
    }


def _apply_ontology_fields(
    entry: dict[str, Any],
    ont_et: EntityTypeInfo,
    ontology: DiagramOntology,
) -> None:
    entry["classes"] = list(ont_et.classes)
    entry["create_when"] = ont_et.create_when
    entry["never_create_when"] = ont_et.never_create_when
    entry["min"] = ont_et.min
    entry["max"] = ont_et.max
    entry["mapping_required"] = ont_et.mapping_required
    pm = ont_et.permitted_mappings
    if pm.has_any():
        mapping_entry: dict[str, Any] = {
            "entity_types": list(pm.entity_types),
            "entity_classes": list(pm.entity_classes),
        }
        if pm.sources:
            mapping_entry["sources"] = [
                {
                    "ontology": source.ontology,
                    "entity_type": source.entity_type,
                    "entity_class": source.entity_class,
                    "transparent": source.transparent,
                }
                for source in pm.sources
            ]
        entry["permitted_mappings"] = mapping_entry
    raw_props = ontology.entity_type_properties.get(str(ont_et.artifact_type))
    if raw_props:
        entry["properties"] = raw_props
    raw_mf = ontology.entity_type_managed_fields.get(str(ont_et.artifact_type))
    if raw_mf:
        entry["managed_fields"] = raw_mf


def _merge_ontology_into_config(
    config: dict[str, Any],
    ontology: DiagramOntology,
) -> dict[str, Any]:
    ui: dict[str, Any] = dict(config.get("ui") or {})
    dot: list[Any] = list(ui.get("diagram_only_types") or [])
    updated: list[dict[str, Any]] = []
    seen_types: set[str] = set()

    for entry in dot:
        if not isinstance(entry, Mapping):
            updated.append(entry)
            continue
        etype = str(entry.get("entity_type") or "")
        seen_types.add(etype)
        merged: dict[str, Any] = dict(entry)
        ont_et = ontology.entity_types.get(EntityTypeName(etype))
        if ont_et is not None:
            _apply_ontology_fields(merged, ont_et, ontology)
        updated.append(merged)

    for etype_name, ont_et in ontology.entity_types.items():
        if str(etype_name) in seen_types:
            continue
        stub: dict[str, Any] = {
            "entity_type": str(etype_name),
            "label": str(etype_name).replace("-", " ").title(),
        }
        _apply_ontology_fields(stub, ont_et, ontology)
        updated.append(stub)

    merged_ui = {**ui, "diagram_only_types": updated}
    return {**config, "ui": merged_ui}


class _C4DiagramType(DiagramTypeBase):
    def __init__(self, config: dict[str, Any], ontology: DiagramOntology) -> None:
        self._ontology = ontology
        self._config = _merge_ontology_into_config(config, ontology)
        self._name = DiagramTypeName(str(config["name"]))
        self._element_classes = _parse_element_classes(config)
        self._ui_config = diagram_type_ui_config_from_mapping(
            self._config,
            default_label=str(config.get("ui", {}).get("label") or self._name).replace("-", " ").title(),
        )
        self._renderer = C4PumlRenderer(self._config, person_archimate_types=_person_archimate_types(ontology))
        self._mapped_model_entity_types: frozenset[EntityTypeName] | None = None

    @property
    def element_classes(self) -> dict[str, ElementClassInfo]:
        return self._element_classes

    @property
    def name(self) -> DiagramTypeName:
        return self._name

    @property
    def primary_ontology(self):  # type: ignore[override]
        return FreeOntology

    def accepts_entity_type(self, t: EntityTypeName) -> bool:
        return t in self._resolved_mapped_model_entity_types()

    def accepts_connection_type(self, t: ConnectionTypeName) -> bool:
        return _registry().find_connection_type(t) is not None

    def effective_entity_types(self) -> dict[EntityTypeName, EntityTypeInfo]:
        registry = _registry()
        return {
            entity_type: registry.get_entity_type(entity_type)
            for entity_type in sorted(self._resolved_mapped_model_entity_types())
            if registry.find_entity_type(entity_type) is not None
        }

    def effective_connection_types(self) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
        return dict(_registry().all_connection_types())

    @property
    def own_entity_types(self) -> dict[EntityTypeName, EntityTypeInfo]:
        return _EMPTY_ENTITY_TYPES

    @property
    def own_connection_types(self) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
        return _C4_OWN_CONNECTION_TYPES

    @property
    def own_permitted_relationships(self) -> PermittedRelationshipSet:
        return self._ontology.permitted_relationships

    @property
    def bridges(self) -> tuple[BridgeDeclaration, ...]:
        return self._ontology.bridges

    @property
    def renderer(self) -> DiagramRenderer:
        return self._renderer

    def write_guidance(self) -> DiagramTypeWriteGuidance:
        g: dict[str, Any] = self._config.get("guidance") or {}
        own_types = self._ui_config.diagram_only_types
        schema = self._augment_schema(derive_diagram_entities_schema(own_types))
        ab = self._ontology.allowed_bindings
        return DiagramTypeWriteGuidance(
            when_to_use=str(g.get("when_to_use") or ""),
            when_not_to_use=str(g.get("when_not_to_use") or ""),
            diagram_entities_schema=schema,
            own_entity_types=own_types,
            allowed_bindings=ab if not ab.is_empty() else None,
        )

    def _augment_schema(self, schema: dict[str, Any] | None) -> dict[str, Any]:
        base: dict[str, Any] = dict(schema) if schema else {"type": "object", "properties": {}}
        props: dict[str, Any] = dict(base.get("properties") or {})
        c4_cfg: dict[str, Any] = self._config.get("c4") or {}
        scope_type = str(c4_cfg.get("scope_entity_type") or "entity")
        props["_scope_entity_id"] = {
            "type": "string",
            "description": (
                f"entity_id of the {scope_type} model entity this diagram is scoped to. "
                "Set to enable model-backed mode (entities and connections auto-derived from ArchiMate graph). "
                "Omit for standalone mode (explicit diagram entities and c4-uses connections)."
            ),
        }
        props["_included_entity_ids"] = {
            "type": "array", "items": {"type": "string"},
            "description": (
                "entity_ids to include from the ArchiMate graph (model-backed only). "
                "Omit to include all connected entities. Use the smaller of included or excluded."
            ),
        }
        props["_excluded_entity_ids"] = {
            "type": "array", "items": {"type": "string"},
            "description": (
                "entity_ids to exclude from auto-derived neighbours (model-backed only). "
                "Mutually exclusive with _included_entity_ids. Use the smaller set."
            ),
        }
        return {**base, "properties": props}

    def _resolved_mapped_model_entity_types(self) -> frozenset[EntityTypeName]:
        if self._mapped_model_entity_types is None:
            self._mapped_model_entity_types = resolve_model_entity_types_for_diagram_only_types(
                self._ui_config.diagram_only_types,
                _registry(),
            )
        return self._mapped_model_entity_types


    def build_context_extras(
        self,
        repo: Any,
        diagram_id: str,
        diagram_entities: dict[str, Any],
    ) -> dict[str, Any]:
        from src.diagram_types._c4_navigation import build_c4_navigation  # noqa: PLC0415

        nav = build_c4_navigation(repo, diagram_id, str(self._name), diagram_entities)
        return {"c4_navigation": nav} if nav is not None else {}

def _person_archimate_types(ontology: DiagramOntology) -> frozenset[str]:
    person_et = ontology.entity_types.get(EntityTypeName("person"))
    if person_et is None:
        return frozenset()
    return frozenset(person_et.permitted_mappings.entity_types)


def load_c4_diagram_type(package_dir: Path) -> DiagramTypeModule:
    config = _load_config(package_dir)
    ontology = load_diagram_ontology(package_dir / "ontology.yaml")
    return _C4DiagramType(config, ontology)
