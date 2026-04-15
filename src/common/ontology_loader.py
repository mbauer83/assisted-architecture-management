"""ontology_loader.py — Load entity & connection ontology from YAML config.

Reads config/entity_ontology.yaml and config/connection_ontology.yaml once at
import time and builds all registries consumed by archimate_types, connection_ontology,
and model_write_catalog.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

# Import dataclass definitions only (no circular dependency — model_write_catalog
# does NOT import from this module at class-definition time).
from src.common.model_write_catalog import ConnectionTypeInfo, EntityTypeInfo

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
        archimate_domain=_info["archimate_domain"],
        archimate_element_type=_info["archimate_element_type"],
        element_category=_info["element_category"],
        element_classes=tuple(_info.get("element_classes", ())),
    )

# ── CONNECTION_TYPES ─────────────────────────────────────────────────────
CONNECTION_TYPES: dict[str, ConnectionTypeInfo] = {}
for _lang, _types in _conn_data["connection_types"].items():
    for _name, _info in _types.items():
        CONNECTION_TYPES[_name] = ConnectionTypeInfo(
            artifact_type=_name,
            conn_lang=_lang,
            conn_dir=_info["directory"],
            archimate_relationship_type=_info.get("archimate_relationship_type"),
            symmetric=_info.get("symmetric", False),
        )

# ── Derived: stereotype → connection type ────────────────────────────────
ARCHIMATE_STEREOTYPE_TO_CONNECTION_TYPE: dict[str, str] = {
    ct.conn_dir: ct.artifact_type
    for ct in CONNECTION_TYPES.values()
    if ct.conn_lang == "archimate"
}

# ── Element-class membership (inverted from entity element_classes) ──────
CLASS_MEMBERS: dict[str, list[str]] = {}
for _etype, _einfo in ENTITY_TYPES.items():
    for _cls in _einfo.element_classes:
        CLASS_MEMBERS.setdefault(_cls, []).append(_etype)

ALL_ENTITY_TYPE_NAMES: list[str] = sorted(ENTITY_TYPES)

# ── Category map ─────────────────────────────────────────────────────────
CATEGORY_MAP: dict[str, str] = {
    n: info.element_category for n, info in ENTITY_TYPES.items()
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
