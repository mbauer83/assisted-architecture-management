"""ontology_loader.py — shim during migration to the module system.

All data now lives in src/ontologies/archimate_next/.  This shim re-exports the
same public names for backward compatibility while the migration is in progress.
Delete this file (Phase 4) once all consumers have been migrated to the registry.
"""

from __future__ import annotations

from src.ontologies.archimate_next import module as _m
from src.ontologies.archimate_next._loader import _ArchiMateNextModule

assert isinstance(_m, _ArchiMateNextModule)

# ── Core dicts ────────────────────────────────────────────────────────────────
ENTITY_TYPES: dict = dict(_m.entity_types)
CONNECTION_TYPES: dict = dict(_m.connection_types)

# ── Derived: stereotype → connection type ─────────────────────────────────────
ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE: dict[str, str] = {
    ct.archimate_relationship_type.lower(): ct.artifact_type
    for ct in CONNECTION_TYPES.values()
    if ct.conn_lang == "archimate" and ct.archimate_relationship_type
}

# ── Element-class membership (inverted from entity element_classes) ───────────
CLASS_MEMBERS: dict[str, list[str]] = {}
for _etype, _einfo in ENTITY_TYPES.items():
    for _cls in _einfo.element_classes:
        CLASS_MEMBERS.setdefault(_cls, []).append(_etype)

ALL_ENTITY_TYPE_NAMES: list[str] = sorted(ENTITY_TYPES)

# ── Domain ordering & display ─────────────────────────────────────────────────
DOMAIN_ORDER: list[str] = list(dict.fromkeys(
    et.domain_dir for et in ENTITY_TYPES.values() if not et.internal
))
DOMAIN_GROUPING: dict[str, str] = {
    et.domain_dir: et.domain_dir.capitalize() + "Grouping"
    for et in ENTITY_TYPES.values() if not et.internal
}
DOMAIN_DISPLAY: dict[str, str] = {
    et.domain_dir: et.domain_dir.capitalize()
    for et in ENTITY_TYPES.values() if not et.internal
}

# ── Element type → has_sprite ─────────────────────────────────────────────────
ELEMENT_TYPE_HAS_SPRITE: dict[str, bool] = {
    et.archimate_element_type: et.has_sprite
    for et in ENTITY_TYPES.values()
    if et.archimate_element_type
}

# ── Symmetric connections ─────────────────────────────────────────────────────
SYMMETRIC_CONNECTIONS: frozenset[str] = frozenset(
    n for n, ct in CONNECTION_TYPES.items() if ct.symmetric
)

# ── Matrix abbreviations ──────────────────────────────────────────────────────
MATRIX_ABBREVIATIONS_BY_ABBREV: dict[str, str] = dict(_m.matrix_abbreviations)
CONN_TYPE_ABBREVIATIONS: dict[str, str] = {v: k for k, v in MATRIX_ABBREVIATIONS_BY_ABBREV.items()}

# ── Permitted relationships (old dict format) ─────────────────────────────────
_rules = _m.permitted_relationships._rules
PERMITTED_RELATIONSHIPS: dict[tuple[str, str], frozenset[str]] = {}
for _r in _rules:
    _key = (_r.source_type, _r.target_type)
    _existing = PERMITTED_RELATIONSHIPS.get(_key, frozenset())
    PERMITTED_RELATIONSHIPS[_key] = _existing | {_r.connection_type}

RULES_BY_SOURCE: dict[str, list[tuple[str, frozenset[str]]]] = {}
RULES_BY_TARGET: dict[str, list[tuple[str, frozenset[str]]]] = {}
for (_src, _tgt), _ctypes in PERMITTED_RELATIONSHIPS.items():
    RULES_BY_SOURCE.setdefault(_src, []).append((_tgt, _ctypes))
    RULES_BY_TARGET.setdefault(_tgt, []).append((_src, _ctypes))


# ── Expansion helpers (preserved for consumers that call them directly) ───────

def _expand_ref(ref: str | list, all_types: list[str]) -> list[str]:
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
    return _expand_ref(term, ALL_ENTITY_TYPE_NAMES)


def format_entity_type_term(term: str) -> str:
    if term == "@all":
        return "entity"
    normalized = term[1:] if term.startswith("@") else term
    return normalized.replace("-", " ").replace("_", " ")


def entity_type_term_matches(term: str, linked_types: set[str]) -> bool:
    return bool(set(expand_entity_type_term(term)) & linked_types)
