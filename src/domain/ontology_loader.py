"""ontology_loader.py — Load entity & connection ontology from YAML config.

Reads config/entity_ontology.yaml and config/connection_ontology.yaml once at
import time and builds all registries consumed by archimate_types, connection_ontology,
and model_write_catalog.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.domain.ontology_types import ConnectionTypeInfo, EntityTypeInfo

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _load(name: str) -> dict:
    with open(_CONFIG_DIR / name) as fh:
        return yaml.safe_load(fh)


# ── Raw YAML data ────────────────────────────────────────────────────────
_entity_data = _load("entity_ontology.yaml")
_conn_data = _load("connection_ontology.yaml")

# ── ENTITY_TYPES ─────────────────────────────────────────────────────────
ENTITY_TYPES: dict[str, EntityTypeInfo] = {}
for _name, _info in _entity_data["entity_types"].items():
    ENTITY_TYPES[_name] = EntityTypeInfo(
        artifact_type=_name,
        prefix=_info["prefix"],
        domain_dir=_info["domain"],
        subdir=_info["subdir"],
        archimate_element_type=_info["archimate_element_type"],
        element_classes=tuple(_info.get("element_classes", ())),
        create_when=_info.get("create_when", ""),
        never_create_when=_info.get("never_create_when", ""),
        has_sprite=bool(_info.get("has_sprite", False)),
        internal=bool(_info.get("internal", False)),
    )

# ── CONNECTION_TYPES ─────────────────────────────────────────────────────
CONNECTION_TYPES: dict[str, ConnectionTypeInfo] = {}
for _lang, _types in _conn_data["connection_types"].items():
    for _name, _info in _types.items():
        CONNECTION_TYPES[_name] = ConnectionTypeInfo(
            artifact_type=_name,
            conn_lang=_lang,
            archimate_relationship_type=_info.get("archimate_relationship_type"),
            symmetric=_info.get("symmetric", False),
            puml_arrow=_info.get("puml_arrow", "-->"),
        )

# ── Derived: stereotype → connection type ────────────────────────────────
ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE: dict[str, str] = {
    ct.archimate_relationship_type.lower(): ct.artifact_type
    for ct in CONNECTION_TYPES.values()
    if ct.conn_lang == "archimate" and ct.archimate_relationship_type
}

# ── Element-class membership (inverted from entity element_classes) ──────
CLASS_MEMBERS: dict[str, list[str]] = {}
for _etype, _einfo in ENTITY_TYPES.items():
    for _cls in _einfo.element_classes:
        CLASS_MEMBERS.setdefault(_cls, []).append(_etype)

ALL_ENTITY_TYPE_NAMES: list[str] = sorted(ENTITY_TYPES)

# ── Domain ordering & display (derived from entity_ontology.yaml insertion order) ──
#: Unique domain_dir values in the order they first appear in the YAML.
#: Internal types (e.g. global-entity-reference) are excluded.
DOMAIN_ORDER: list[str] = list(
    dict.fromkeys(et.domain_dir for et in ENTITY_TYPES.values() if not et.internal)
)

#: domain_dir → grouping stereotype name (e.g. "motivation" → "MotivationGrouping")
DOMAIN_GROUPING: dict[str, str] = {
    et.domain_dir: et.domain_dir.capitalize() + "Grouping"
    for et in ENTITY_TYPES.values()
    if not et.internal
}

#: domain_dir → display name (capitalized) as it appears in diagrams
DOMAIN_DISPLAY: dict[str, str] = {
    et.domain_dir: et.domain_dir.capitalize() for et in ENTITY_TYPES.values() if not et.internal
}

#: archimate_element_type → has_sprite bool
ELEMENT_TYPE_HAS_SPRITE: dict[str, bool] = {
    et.archimate_element_type: et.has_sprite
    for et in ENTITY_TYPES.values()
    if et.archimate_element_type
}

# ── Symmetric connections ────────────────────────────────────────────────
SYMMETRIC_CONNECTIONS: frozenset[str] = frozenset(
    n for n, ct in CONNECTION_TYPES.items() if ct.symmetric
)


# ── Expand rule references ───────────────────────────────────────────────


def _expand_ref(ref: str | list, all_types: list[str]) -> list[str]:
    """Expand a source/target reference to concrete entity-type names."""
    if isinstance(ref, list):
        out: list[str] = []
        for item in ref:
            out.extend(_expand_ref(item, all_types))
        return out
    if ref == "@all":
        return list(all_types)
    if ref.startswith("@"):
        return list(CLASS_MEMBERS.get(ref[1:], []))
    return [ref]


def expand_entity_type_term(term: str) -> list[str]:
    """Expand a concrete entity type, @all, or @element-class term."""
    return _expand_ref(term, ALL_ENTITY_TYPE_NAMES)


def format_entity_type_term(term: str) -> str:
    """Return a readable label for a concrete entity type, @all, or @element-class term."""
    if term == "@all":
        return "entity"
    normalized = term[1:] if term.startswith("@") else term
    return normalized.replace("-", " ").replace("_", " ")


def entity_type_term_matches(term: str, linked_types: set[str]) -> bool:
    """Return whether linked entity types satisfy a document type requirement term."""
    return bool(set(expand_entity_type_term(term)) & linked_types)


def _build_rules() -> dict[tuple[str, str], set[str]]:
    rules: dict[tuple[str, str], set[str]] = {}
    all_types = ALL_ENTITY_TYPE_NAMES

    for rule in _conn_data.get("permitted_relationships", []):
        raw_src, raw_tgt, raw_types = rule
        sources = _expand_ref(raw_src, all_types)
        conn_types = [f"archimate-{t}" for t in raw_types]

        for src in sources:
            if raw_tgt == "@same":
                targets = [src]
            else:
                targets = _expand_ref(raw_tgt, all_types)
            for tgt in targets:
                rules.setdefault((src, tgt), set()).update(conn_types)

    return rules


# ── PERMITTED_RELATIONSHIPS ──────────────────────────────────────────────
#: (source_type, target_type) → frozenset of permitted archimate connection types
PERMITTED_RELATIONSHIPS: dict[tuple[str, str], frozenset[str]] = {
    k: frozenset(v) for k, v in _build_rules().items()
}

# ── Indexed lookups ──────────────────────────────────────────────────────
#: source_type → [(target_type, frozenset[conn_types])]
RULES_BY_SOURCE: dict[str, list[tuple[str, frozenset[str]]]] = {}
#: target_type → [(source_type, frozenset[conn_types])]
RULES_BY_TARGET: dict[str, list[tuple[str, frozenset[str]]]] = {}

for (_src, _tgt), _ctypes in PERMITTED_RELATIONSHIPS.items():
    RULES_BY_SOURCE.setdefault(_src, []).append((_tgt, _ctypes))
    RULES_BY_TARGET.setdefault(_tgt, []).append((_src, _ctypes))
