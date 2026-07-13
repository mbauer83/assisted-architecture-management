"""Private loader: YAML → _ArchiMate4Module instance."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Literal, cast

import yaml  # type: ignore[import-untyped]

from src.domain.guidance import GuidanceKey, GuidanceOverlay
from src.domain.module_types import ConnectionTypeName, ElementClassName, EntityTypeName
from src.domain.ontology_types import ConnectionTypeInfo, ElementClassInfo, EntityTypeInfo
from src.domain.permitted_relationships import (
    PermittedRelationship,
    PermittedRelationshipSet,
)
from src.domain.specializations import (
    SpecializationCatalog,
    merge_specialization_catalogs,
    overlay_specialization_guidance,
    specialization_catalog_from_mapping,
)

_PACKAGE_DIR = Path(__file__).parent

META_ONTOLOGY_ALIAS = "archimate-4"
_GLYPHS_PATH = _PACKAGE_DIR.parent.parent.parent / "tools" / "gui" / "src" / "ui" / "lib" / "archimateGlyphs.json"

DISPLAY_SECTION_ID = "archimate"
DerivationRole = Literal["structural", "dependency", "dynamic", "specialization"]


def _sprite_key(artifact_type: str) -> str:
    return artifact_type.replace("-", "_")


def _load_glyphs() -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(_GLYPHS_PATH.read_text(encoding="utf-8")))
    except OSError:
        return {}


class _ArchiMate4Module:
    name = "archimate-4-0"
    display_section_id = DISPLAY_SECTION_ID
    module_class: Literal["architecture", "assurance"] = "architecture"
    enabled: bool = True
    requires: list[str] = []

    def __init__(
        self,
        entity_types: dict[EntityTypeName, EntityTypeInfo],
        connection_types: dict[ConnectionTypeName, ConnectionTypeInfo],
        permitted_relationships: PermittedRelationshipSet,
        matrix_abbreviations: dict[str, str],
        element_classes: dict[str, ElementClassInfo] | None = None,
        specialization_catalog: SpecializationCatalog | None = None,
        svg_converter: Callable[[str], str] | None = None,
    ) -> None:
        self._entity_types = entity_types
        self._connection_types = connection_types
        self._permitted_relationships = permitted_relationships
        self._matrix_abbreviations = matrix_abbreviations
        self._element_classes: dict[str, ElementClassInfo] = element_classes or {}
        self._specialization_catalog = specialization_catalog or SpecializationCatalog.empty()
        self._svg_converter = svg_converter

        self._class_index: dict[ElementClassName, frozenset[EntityTypeName]] = {}
        _class_build: dict[ElementClassName, set[EntityTypeName]] = {}
        for ename, info in entity_types.items():
            for cls in info.classes:
                _class_build.setdefault(ElementClassName(cls), set()).add(ename)
        self._class_index = {k: frozenset(v) for k, v in _class_build.items()}

        self._classification_index: dict[str, frozenset[ConnectionTypeName]] = {}
        _clf_build: dict[str, set[ConnectionTypeName]] = {}
        for cname, info in connection_types.items():
            for clf in info.classes:
                _clf_build.setdefault(clf, set()).add(cname)
        self._classification_index = {k: frozenset(v) for k, v in _clf_build.items()}

        self._glyphs: dict[str, Any] = {}
        self._glyphs_loaded = False

    def _ensure_glyphs(self) -> None:
        if not self._glyphs_loaded:
            self._glyphs = _load_glyphs()
            self._glyphs_loaded = True

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

    @property
    def element_classes(self) -> dict[str, ElementClassInfo]:
        return self._element_classes

    @property
    def specialization_catalog(self) -> SpecializationCatalog:
        return self._specialization_catalog

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

    def render_display_section(
        self,
        artifact_type: str,
        name: str,
        alias: str,
    ) -> str:
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
        self._ensure_glyphs()
        if not self._glyphs:
            return None
        kind = self._glyphs.get("types", {}).get(artifact_type)
        if not kind:
            return None
        markup = self._glyphs.get("kinds", {}).get(kind)
        if not markup:
            return None
        if self._svg_converter is None:
            return None
        key = _sprite_key(artifact_type)
        return f"sprite $archimate_{key} {self._svg_converter(markup)}"


def _entity_guidance(guidance: GuidanceOverlay, artifact_type: str, info: dict[str, Any]) -> tuple[str, str]:
    key = GuidanceKey(module_alias=META_ONTOLOGY_ALIAS, concept_kind="entity", type_name=artifact_type)
    overlaid = guidance.get(key)
    if overlaid is not None:
        return overlaid.create_when, overlaid.never_create_when
    return info.get("create_when", ""), info.get("never_create_when", "")


def _load_entity_types(
    data: dict[str, Any], guidance: GuidanceOverlay | None = None
) -> dict[EntityTypeName, EntityTypeInfo]:
    overlay = guidance if guidance is not None else GuidanceOverlay()
    out: dict[EntityTypeName, EntityTypeInfo] = {}
    for artifact_type, info in data["entity_types"].items():
        raw_hierarchy = info.get("hierarchy", [])
        hierarchy = tuple(raw_hierarchy) + (artifact_type,)
        create_when, never_create_when = _entity_guidance(overlay, artifact_type, info)
        out[EntityTypeName(artifact_type)] = EntityTypeInfo(
            artifact_type=artifact_type,
            prefix=info["prefix"],
            hierarchy=hierarchy,
            classes=tuple(info.get("classes", ())),
            create_when=create_when,
            never_create_when=never_create_when,
            internal=bool(info.get("internal", False)),
        )
    return out


def _load_connection_types(data: dict[str, Any]) -> dict[ConnectionTypeName, ConnectionTypeInfo]:
    out: dict[ConnectionTypeName, ConnectionTypeInfo] = {}
    derivation_strengths: dict[str, set[int]] = {}
    for lang, types in data["connection_types"].items():
        for name, info in cast(dict[str, Any | None], types or {}).items():
            raw: dict[str, Any] = info or {}
            hp_raw = raw.get("hierarchy_priority")
            derivation_role, derivation_strength = _parse_derivation(raw.get("derivation"), name)
            if derivation_strength is not None:
                assert derivation_role is not None
                strengths = derivation_strengths.setdefault(derivation_role, set())
                if derivation_strength in strengths:
                    raise ValueError(f"connection type {name!r}: duplicate derivation strength {derivation_strength}")
                strengths.add(derivation_strength)
            out[ConnectionTypeName(name)] = ConnectionTypeInfo(
                artifact_type=name,
                conn_lang=lang,
                archimate_relationship_type=raw.get("archimate_relationship_type"),
                symmetric=bool(raw.get("symmetric", False)),
                puml_arrow=raw.get("puml_arrow", "-->"),
                show_stereotype=bool(raw.get("show_stereotype", "puml_arrow" not in raw)),
                classes=tuple(raw.get("classes", ())),
                hierarchy_priority=int(hp_raw) if hp_raw is not None else None,
                hierarchy_label=str(raw["hierarchy_label"]) if raw.get("hierarchy_label") else None,
                bidirectional_sync=bool(raw.get("bidirectional_sync", False)),
                relationship_kind=str(raw["relationship_kind"]) if raw.get("relationship_kind") else None,
                derivation_role=derivation_role,
                derivation_strength=derivation_strength,
            )
    return out


def _parse_derivation(raw: object, name: str) -> tuple[DerivationRole | None, int | None]:
    if raw is None:
        return None, None
    if not isinstance(raw, Mapping):
        raise ValueError(f"connection type {name!r}: derivation must be a mapping")
    role = raw.get("role")
    valid_roles = {"structural", "dependency", "dynamic", "specialization"}
    if role not in valid_roles:
        raise ValueError(f"connection type {name!r}: unknown derivation role {role!r}")
    has_strength = "strength" in raw
    strength = raw.get("strength")
    if role in {"structural", "dependency"}:
        if not isinstance(strength, int) or isinstance(strength, bool):
            raise ValueError(f"connection type {name!r}: derivation role {role!r} requires an integer strength")
        return cast(DerivationRole, role), strength
    if has_strength:
        raise ValueError(f"connection type {name!r}: derivation role {role!r} forbids strength")
    return cast(DerivationRole, role), None


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
        raw_src, raw_tgt, raw_conn_shorts = rule
        conn_types = [ConnectionTypeName(f"archimate-{t}") for t in raw_conn_shorts]
        sources = _expand_ref(raw_src, all_types, class_members)

        for src in sources:
            targets = [src] if raw_tgt == "@same" else _expand_ref(raw_tgt, all_types, class_members)
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


def _load_element_classes(data: dict[str, Any]) -> dict[str, ElementClassInfo]:
    raw_classes: dict[str, Any] = data.get("element_classes") or {}
    out: dict[str, ElementClassInfo] = {}
    for ec_name, ec_info in raw_classes.items():
        raw: dict[str, Any] = ec_info or {}
        out[str(ec_name)] = ElementClassInfo(
            name=str(ec_name),
            description=str(raw.get("description") or ""),
        )
    return out


def _load_module_specializations(package_dir: Path) -> SpecializationCatalog:
    path = package_dir / "specializations.yaml"
    if not path.exists():
        return SpecializationCatalog.empty()
    with path.open(encoding="utf-8") as handle:
        loaded: Any = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Invalid specialization declarations in {path}: top-level YAML value must be a mapping")
    return specialization_catalog_from_mapping(loaded, module_alias=META_ONTOLOGY_ALIAS)


def _specialization_guidance_entries(
    guidance: GuidanceOverlay,
) -> dict[tuple[str, Literal["entity", "connection"], str, str], tuple[str, str]]:
    entries: dict[tuple[str, Literal["entity", "connection"], str, str], tuple[str, str]] = {}
    for key, value in guidance.entries.items():
        if key.module_alias == META_ONTOLOGY_ALIAS and key.specialization:
            entries[(key.module_alias, key.concept_kind, key.type_name, key.specialization)] = (
                value.create_when,
                value.never_create_when,
            )
    return entries


def _validate_specialization_parents(
    catalog: SpecializationCatalog,
    entity_types: dict[EntityTypeName, EntityTypeInfo],
    connection_types: dict[ConnectionTypeName, ConnectionTypeInfo],
) -> None:
    for entry in catalog.entries:
        if entry.concept_kind == "entity" and EntityTypeName(entry.parent_type) not in entity_types:
            raise ValueError(f"Unknown parent entity type {entry.parent_type!r} for specialization {entry.slug!r}")
        if entry.concept_kind == "connection" and ConnectionTypeName(entry.parent_type) not in connection_types:
            raise ValueError(f"Unknown parent connection type {entry.parent_type!r} for specialization {entry.slug!r}")


def load_archimate_4_module(
    package_dir: Path,
    *,
    svg_converter: Callable[[str], str] | None = None,
    guidance: GuidanceOverlay | None = None,
    specializations: SpecializationCatalog | None = None,
) -> _ArchiMate4Module:
    with open(package_dir / "entities.yaml") as fh:
        entity_data = yaml.safe_load(fh)
    with open(package_dir / "connections.yaml") as fh:
        conn_data = yaml.safe_load(fh)

    entity_types = _load_entity_types(entity_data, guidance)
    connection_types = _load_connection_types(conn_data)
    permitted = _build_permitted_relationships(conn_data, entity_types)
    matrix_abbreviations: dict[str, str] = dict(conn_data.get("matrix_abbreviations", {}))
    element_classes = _load_element_classes(entity_data)
    overlay = guidance if guidance is not None else GuidanceOverlay()
    module_specializations = overlay_specialization_guidance(
        _load_module_specializations(package_dir),
        _specialization_guidance_entries(overlay),
    )
    specialization_catalog = merge_specialization_catalogs(
        module_specializations,
        specializations or SpecializationCatalog.empty(),
    )
    _validate_specialization_parents(specialization_catalog, entity_types, connection_types)

    return _ArchiMate4Module(
        entity_types=entity_types,
        connection_types=connection_types,
        permitted_relationships=permitted,
        matrix_abbreviations=matrix_abbreviations,
        element_classes=element_classes,
        specialization_catalog=specialization_catalog,
        svg_converter=svg_converter,
    )
