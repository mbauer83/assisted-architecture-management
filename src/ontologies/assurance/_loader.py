"""Assurance ontology module loader: YAML → _AssuranceModule instance."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]

from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, ElementClassInfo, EntityTypeInfo
from src.domain.permitted_relationships import (
    PermittedRelationship,
    PermittedRelationshipSet,
)

DISPLAY_SECTION_ID = "assurance"

_ATTRIBUTE_PROFILES: Mapping[str, dict[str, object]] = {
    "hazard": {
        "type": "object",
        "properties": {
            "concern_class": {
                "type": "string",
                "enum": ["safety", "security", "operational", "financial", "privacy"],
            },
            "tlp": {
                "type": "string",
                "enum": ["TLP:WHITE", "TLP:GREEN", "TLP:AMBER", "TLP:RED"],
                "default": "TLP:WHITE",
            },
            "classification_scheme": {"type": "string"},
            "classification_code": {"type": "string"},
        },
    },
    "assurance-constraint": {
        "type": "object",
        "properties": {
            "concern_class": {
                "type": "string",
                "enum": ["safety", "security", "operational", "financial", "privacy"],
            },
            "disposition": {
                "type": "string",
                "enum": [
                    "eliminated",
                    "prevented-by-design",
                    "controlled-with-evidence",
                    "alarp-justified",
                    "accepted",
                    "mitigate",
                    "transfer",
                    "avoid",
                ],
            },
            "level": {"type": "string", "enum": ["system", "controller", "technical"]},
            "tlp": {
                "type": "string",
                "enum": ["TLP:WHITE", "TLP:GREEN", "TLP:AMBER", "TLP:RED"],
            },
            "enforcement_status": {"type": "string"},
        },
    },
    "unsafe-control-action": {
        "type": "object",
        "properties": {
            "uca_type": {
                "type": "string",
                "enum": ["not-provided", "provided", "wrong-timing", "stopped-too-soon"],
            },
            "mode": {"type": "string", "enum": ["hypothesized", "observed"]},
            "context": {"type": "string"},
            "concern_class": {
                "type": "string",
                "enum": ["safety", "security", "operational", "financial", "privacy"],
            },
        },
    },
    "control-structure-node": {
        "type": "object",
        "properties": {
            "node_role": {
                "type": "string",
                "enum": ["controller", "controlled-process", "actuator", "sensor"],
            },
            "binding_status": {
                "type": "string",
                "enum": ["bound", "unbound-pending", "out-of-scope"],
                "default": "unbound-pending",
            },
            "granularity_note": {"type": "string"},
        },
    },
    "risk": {
        "type": "object",
        "properties": {
            "likelihood": {"type": "string", "enum": ["rare", "unlikely", "possible", "likely", "almost-certain"]},
            "impact": {"type": "string", "enum": ["negligible", "minor", "moderate", "major", "catastrophic"]},
            "treatment": {"type": "string", "enum": ["mitigate", "transfer", "avoid", "accept"]},
            "residual_likelihood": {"type": "string"},
            "residual_impact": {"type": "string"},
            "review_date": {"type": "string", "format": "date"},
        },
    },
}


class _AssuranceModule:
    name = "assurance"
    display_section_id = DISPLAY_SECTION_ID
    module_class: Literal["architecture", "assurance"] = "assurance"
    enabled: bool = True
    requires: list[str] = ["confidential_store"]
    attribute_profiles: Mapping[str, dict[str, object]] = _ATTRIBUTE_PROFILES

    def __init__(
        self,
        entity_types: dict[EntityTypeName, EntityTypeInfo],
        connection_types: dict[ConnectionTypeName, ConnectionTypeInfo],
        permitted_relationships: PermittedRelationshipSet,
        element_classes: dict[str, ElementClassInfo],
    ) -> None:
        self._entity_types = entity_types
        self._connection_types = connection_types
        self._permitted_relationships = permitted_relationships
        self._element_classes = element_classes

        self._class_index: dict[ElementClassName, frozenset[EntityTypeName]] = {}
        _cb: dict[ElementClassName, set[EntityTypeName]] = {}
        for ename, info in entity_types.items():
            for cls in info.classes:
                _cb.setdefault(ElementClassName(cls), set()).add(ename)
        self._class_index = {k: frozenset(v) for k, v in _cb.items()}

        self._clf_index: dict[str, frozenset[ConnectionTypeName]] = {}
        _cfb: dict[str, set[ConnectionTypeName]] = {}
        for cname, info in connection_types.items():
            for clf in info.classes:
                _cfb.setdefault(clf, set()).add(cname)
        self._clf_index = {k: frozenset(v) for k, v in _cfb.items()}

    @property
    def entity_types(self) -> dict[EntityTypeName, EntityTypeInfo]:
        return self._entity_types

    @property
    def connection_types(self) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
        return self._connection_types

    @property
    def permitted_relationships(self) -> PermittedRelationshipSet:
        return self._permitted_relationships

    @property
    def element_classes(self) -> dict[str, ElementClassInfo]:
        return self._element_classes

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]:
        return self._class_index.get(ElementClassName(cls), frozenset())

    def connection_types_with_class(self, cls: str) -> frozenset[ConnectionTypeName]:
        return self._clf_index.get(cls, frozenset())

    def permits_connection(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
        conn: ConnectionTypeName,
    ) -> bool:
        return self._permitted_relationships.permits(src, tgt, conn)

    def render_display_section(self, artifact_type: str, name: str, alias: str) -> str:
        label = name.replace('"', "'")
        return f"label: {label}\nalias: {alias}"

    def extract_display_section(self, section_content: str) -> dict | None:
        import re

        text = re.sub(r"^```(?:yaml)?\n", "", section_content.strip(), count=1)
        text = re.sub(r"\n```$", "", text, count=1)
        try:
            loaded: Any = yaml.safe_load(text) or {}
        except Exception:  # noqa: BLE001
            return None
        return loaded if isinstance(loaded, dict) else None

    def sprite_for(self, artifact_type: str) -> str | None:
        return None


def _load_entity_types(data: dict[str, Any]) -> dict[EntityTypeName, EntityTypeInfo]:
    out: dict[EntityTypeName, EntityTypeInfo] = {}
    for artifact_type, info in data.get("entity_types", {}).items():
        raw_hierarchy = info.get("hierarchy", [])
        hierarchy = tuple(raw_hierarchy) + (artifact_type,)
        out[EntityTypeName(artifact_type)] = EntityTypeInfo(
            artifact_type=artifact_type,
            prefix=info["prefix"],
            hierarchy=hierarchy,
            classes=tuple(info.get("classes", ())),
            create_when=info.get("create_when", ""),
            never_create_when=info.get("never_create_when", ""),
            internal=bool(info.get("internal", False)),
        )
    return out


def _load_connection_types(data: dict[str, Any]) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
    out: dict[ConnectionTypeName, ConnectionTypeInfo] = {}
    conn_name: str
    conn_entry: dict[str, Any]
    for _lang, types in data.get("connection_types", {}).items():
        for conn_name, conn_entry in ((types or {}).items()):
            raw: dict[str, Any] = conn_entry or {}
            hp_raw = raw.get("hierarchy_priority")
            out[ConnectionTypeName(conn_name)] = ConnectionTypeInfo(
                artifact_type=conn_name,
                conn_lang="assurance",
                archimate_relationship_type=None,
                symmetric=bool(raw.get("symmetric", False)),
                puml_arrow=raw.get("puml_arrow", "-->"),
                show_stereotype=bool(raw.get("show_stereotype", "puml_arrow" not in raw)),
                classes=tuple(raw.get("classes", ())),
                hierarchy_priority=int(hp_raw) if hp_raw is not None else None,
                hierarchy_label=str(raw["hierarchy_label"]) if raw.get("hierarchy_label") else None,
                bidirectional_sync=bool(raw.get("bidirectional_sync", False)),
            )
    return out


def _load_element_classes(data: dict[str, Any]) -> dict[str, ElementClassInfo]:
    out: dict[str, ElementClassInfo] = {}
    class_name: str
    class_entry: Any
    for class_name, class_entry in (data.get("element_classes") or {}).items():
        raw: dict[str, Any] = class_entry or {}
        out[str(class_name)] = ElementClassInfo(
            name=str(class_name),
            description=str(raw.get("description") or ""),
        )
    return out


def _build_permitted_relationships(
    data: dict[str, Any],
    entity_types: dict[EntityTypeName, EntityTypeInfo],
) -> PermittedRelationshipSet:
    all_types = [str(k) for k in entity_types]
    class_members: dict[str, list[str]] = {}
    for ename, info in entity_types.items():
        for cls in info.classes:
            class_members.setdefault(cls, []).append(str(ename))

    rules: set[PermittedRelationship] = set()
    for rule in data.get("permitted_relationships", []):
        raw_src, raw_tgt, raw_conns = rule
        conn_types = [ConnectionTypeName(c) for c in raw_conns]

        def _expand(ref: object) -> list[str]:
            if isinstance(ref, list):
                result: list[str] = []
                for item in ref:
                    result.extend(_expand(item))
                return result
            ref_str = str(ref)
            if ref_str == "@all":
                return list(all_types)
            if ref_str.startswith("@"):
                return list(class_members.get(ref_str[1:], []))
            return [ref_str]

        for src in _expand(raw_src):
            for tgt in _expand(raw_tgt):
                for ct in conn_types:
                    rules.add(PermittedRelationship(
                        source_type=EntityTypeName(src),
                        target_type=EntityTypeName(tgt),
                        connection_type=ct,
                    ))
    return PermittedRelationshipSet(frozenset(rules))


def load_assurance_module(package_dir: Path) -> _AssuranceModule:
    with open(package_dir / "entities.yaml") as fh:
        entity_data = yaml.safe_load(fh)
    with open(package_dir / "connections.yaml") as fh:
        conn_data = yaml.safe_load(fh)

    entity_types = _load_entity_types(entity_data)
    connection_types = _load_connection_types(conn_data)
    permitted = _build_permitted_relationships(conn_data, entity_types)
    element_classes = _load_element_classes(entity_data)

    return _AssuranceModule(
        entity_types=entity_types,
        connection_types=connection_types,
        permitted_relationships=permitted,
        element_classes=element_classes,
    )
