"""Private loader: YAML → _SysmlV2MinModule instance."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

import yaml  # type: ignore[import-untyped]

from src.domain.guidance import GuidanceOverlay
from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, ElementClassInfo, EntityTypeInfo
from src.domain.permitted_relationships import (
    PermittedRelationship,
    PermittedRelationshipSet,
)

DISPLAY_SECTION_ID = "sysml"


class _SysmlV2MinModule:
    name = "sysml_v2_min"
    display_section_id = DISPLAY_SECTION_ID
    module_class: Literal["architecture", "assurance"] = "architecture"
    enabled: bool = True
    requires: list[str] = []
    attribute_profiles: Mapping[str, dict[str, object]] = {}

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

        _class_build: dict[ElementClassName, set[EntityTypeName]] = {}
        for ename, info in entity_types.items():
            for cls in info.classes:
                _class_build.setdefault(ElementClassName(cls), set()).add(ename)
        self._class_index: dict[ElementClassName, frozenset[EntityTypeName]] = {
            k: frozenset(v) for k, v in _class_build.items()
        }

        _clf_build: dict[str, set[ConnectionTypeName]] = {}
        for cname, info in connection_types.items():
            for clf in info.classes:
                _clf_build.setdefault(clf, set()).add(cname)
        self._classification_index: dict[str, frozenset[ConnectionTypeName]] = {
            k: frozenset(v) for k, v in _clf_build.items()
        }

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
        return self._classification_index.get(cls, frozenset())

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
    for artifact_type, info in data["entity_types"].items():
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
    for lang, types in data["connection_types"].items():
        for name, info in cast(dict[str, Any | None], types or {}).items():
            raw: dict[str, Any] = info or {}
            out[ConnectionTypeName(name)] = ConnectionTypeInfo(
                artifact_type=name,
                conn_lang=lang,
                archimate_relationship_type=None,
                symmetric=bool(raw.get("symmetric", False)),
                puml_arrow=raw.get("puml_arrow", "-->"),
                show_stereotype=bool(raw.get("show_stereotype", "puml_arrow" not in raw)),
                classes=tuple(raw.get("classes", ())),
            )
    return out


def _load_element_classes(data: dict[str, Any]) -> dict[str, ElementClassInfo]:
    raw_classes: dict[str, Any] = data.get("element_classes") or {}
    return {
        str(name): ElementClassInfo(
            name=str(name),
            description=str((raw or {}).get("description", "")),
        )
        for name, raw in raw_classes.items()
    }


def _expand_ref(
    ref: str | list[Any],
    all_types: list[str],
    class_members: dict[str, list[str]],
) -> list[str]:
    if isinstance(ref, list):
        out: list[str] = []
        for item in ref:
            out.extend(_expand_ref(item, all_types, class_members))
        return out
    if ref == "@all":
        return list(all_types)
    if ref.startswith("@"):
        return list(class_members.get(ref[1:], []))
    return [ref]


def _build_permitted_relationships(
    data: dict[str, Any],
    entity_types: dict[EntityTypeName, EntityTypeInfo],
) -> PermittedRelationshipSet:
    all_types: list[str] = [str(k) for k in entity_types.keys()]

    class_members: dict[str, list[str]] = {}
    for ename, info in entity_types.items():
        for cls in info.classes:
            class_members.setdefault(cls, []).append(str(ename))

    rules: set[PermittedRelationship] = set()
    for rule in data.get("permitted_relationships", []):
        raw_src, raw_tgt, raw_conns = rule
        conn_types = [ConnectionTypeName(c) for c in raw_conns]
        sources = _expand_ref(raw_src, all_types, class_members)
        for src in sources:
            targets = _expand_ref(raw_tgt, all_types, class_members)
            for tgt in targets:
                for ct in conn_types:
                    rules.add(
                        PermittedRelationship(
                            source_type=EntityTypeName(src),
                            target_type=EntityTypeName(tgt),
                            connection_type=ct,
                        )
                    )
    return PermittedRelationshipSet(frozenset(rules))


def load_sysml_module(package_dir: Path, *, guidance: GuidanceOverlay | None = None) -> _SysmlV2MinModule:
    """``guidance`` is accepted for interface parity with the archimate_4 loader; sysml_v2_min
    guidance is inline (not spec-derived text, see PLAN §4.3), so it is unused here.
    """
    with open(package_dir / "entities.yaml") as fh:
        entity_data = yaml.safe_load(fh)
    with open(package_dir / "connections.yaml") as fh:
        conn_data = yaml.safe_load(fh)

    entity_types = _load_entity_types(entity_data)
    connection_types = _load_connection_types(conn_data)
    permitted = _build_permitted_relationships(conn_data, entity_types)
    element_classes = _load_element_classes(entity_data)

    return _SysmlV2MinModule(
        entity_types=entity_types,
        connection_types=connection_types,
        permitted_relationships=permitted,
        element_classes=element_classes,
    )
