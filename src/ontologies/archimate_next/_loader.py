"""Private loader: YAML → _ArchiMateNextModule instance."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo
from src.domain.permitted_relationships import (
    PermittedRelationship,
    PermittedRelationshipSet,
)


class _ArchiMateNextModule:
    name = "archimate-next-snapshot1"

    def __init__(
        self,
        entity_types: dict[EntityTypeName, EntityTypeInfo],
        connection_types: dict[ConnectionTypeName, ConnectionTypeInfo],
        permitted_relationships: PermittedRelationshipSet,
        matrix_abbreviations: dict[str, str],
    ) -> None:
        self._entity_types = entity_types
        self._connection_types = connection_types
        self._permitted_relationships = permitted_relationships
        self._matrix_abbreviations = matrix_abbreviations

        self._class_index: dict[ElementClassName, frozenset[EntityTypeName]] = {}
        _class_build: dict[ElementClassName, set[EntityTypeName]] = {}
        for ename, info in entity_types.items():
            for cls in info.element_classes:
                _class_build.setdefault(ElementClassName(cls), set()).add(ename)
        self._class_index = {k: frozenset(v) for k, v in _class_build.items()}

        self._classification_index: dict[str, frozenset[ConnectionTypeName]] = {}
        _clf_build: dict[str, set[ConnectionTypeName]] = {}
        for cname, info in connection_types.items():
            for clf in info.classifications:
                _clf_build.setdefault(clf, set()).add(cname)
        self._classification_index = {k: frozenset(v) for k, v in _clf_build.items()}

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
    def matrix_abbreviations(self) -> dict[str, str]:
        return self._matrix_abbreviations

    def entity_types_with_class(self, cls: ElementClassName) -> frozenset[EntityTypeName]:
        return self._class_index.get(ElementClassName(cls), frozenset())

    def connection_types_with_classification(
        self, classification: str
    ) -> frozenset[ConnectionTypeName]:
        return self._classification_index.get(classification, frozenset())

    def permits_connection(
        self,
        src: EntityTypeName,
        tgt: EntityTypeName,
        conn: ConnectionTypeName,
    ) -> bool:
        return self._permitted_relationships.permits(src, tgt, conn)


def _load_entity_types(data: dict[str, Any]) -> dict[EntityTypeName, EntityTypeInfo]:
    out: dict[EntityTypeName, EntityTypeInfo] = {}
    for name, info in data["entity_types"].items():
        raw_et = info.get("archimate_element_type")
        archimate_element_type: str | None = raw_et if raw_et else None
        out[EntityTypeName(name)] = EntityTypeInfo(
            artifact_type=name,
            prefix=info["prefix"],
            domain_dir=info["domain"],
            subdir=info["subdir"],
            archimate_element_type=archimate_element_type,
            element_classes=tuple(info.get("element_classes", ())),
            create_when=info.get("create_when", ""),
            never_create_when=info.get("never_create_when", ""),
            has_sprite=bool(info.get("has_sprite", False)),
            internal=bool(info.get("internal", False)),
        )
    return out


def _load_connection_types(data: dict[str, Any]) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
    out: dict[ConnectionTypeName, ConnectionTypeInfo] = {}
    for lang, types in data["connection_types"].items():
        for name, info in (types or {}).items():
            raw = info or {}
            out[ConnectionTypeName(name)] = ConnectionTypeInfo(
                artifact_type=name,
                conn_lang=lang,
                archimate_relationship_type=raw.get("archimate_relationship_type"),
                symmetric=bool(raw.get("symmetric", False)),
                puml_arrow=raw.get("puml_arrow", "-->"),
                classifications=tuple(raw.get("classifications", ())),
            )
    return out


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
    all_types = list(entity_types.keys())

    class_members: dict[str, list[str]] = {}
    for ename, info in entity_types.items():
        for cls in info.element_classes:
            class_members.setdefault(cls, []).append(ename)

    rules: set[PermittedRelationship] = set()

    for rule in data.get("permitted_relationships", []):
        raw_src, raw_tgt, raw_conn_shorts = rule
        conn_types = [ConnectionTypeName(f"archimate-{t}") for t in raw_conn_shorts]
        sources = _expand_ref(raw_src, all_types, class_members)

        for src in sources:
            if raw_tgt == "@same":
                targets = [src]
            else:
                targets = _expand_ref(raw_tgt, all_types, class_members)
            for tgt in targets:
                for ct in conn_types:
                    rules.add(PermittedRelationship(
                        source_type=EntityTypeName(src),
                        target_type=EntityTypeName(tgt),
                        connection_type=ct,
                    ))

    return PermittedRelationshipSet(frozenset(rules))


def load_archimate_next_module(package_dir: Path) -> _ArchiMateNextModule:
    with open(package_dir / "entities.yaml") as fh:
        entity_data = yaml.safe_load(fh)
    with open(package_dir / "connections.yaml") as fh:
        conn_data = yaml.safe_load(fh)

    entity_types = _load_entity_types(entity_data)
    connection_types = _load_connection_types(conn_data)
    permitted = _build_permitted_relationships(conn_data, entity_types)
    matrix_abbreviations: dict[str, str] = dict(conn_data.get("matrix_abbreviations", {}))

    return _ArchiMateNextModule(
        entity_types=entity_types,
        connection_types=connection_types,
        permitted_relationships=permitted,
        matrix_abbreviations=matrix_abbreviations,
    )
