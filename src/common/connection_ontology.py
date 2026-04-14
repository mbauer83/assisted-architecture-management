"""
connection_ontology.py — Authoritative ArchiMate relationship rules.

Single source of truth for:
  - Which connection types are symmetric vs directed
  - Which element categories each entity type belongs to
  - Which (source_category, target_category) pairs are valid per connection type
  - Derived queries: permissible targets, permissible connection types, classify

Used by ModelVerifier (rule enforcement), GUI (form generation), and MCP tools.
"""

from __future__ import annotations

from typing import Literal

from src.common.archimate_types import ALL_ENTITY_TYPES, CONNECTION_TYPES_BY_LANGUAGE

# ---------------------------------------------------------------------------
# Element categories (ArchiMate structural classification)
# ---------------------------------------------------------------------------

ElementCategory = Literal[
    "active", "behavioral", "passive",
    "motivation", "strategy", "implementation", "composite",
]

_CATEGORY_MAP: dict[str, ElementCategory] = {}

# Motivation
for _t in ("stakeholder", "driver", "assessment", "goal", "outcome",
           "principle", "requirement", "architecture-constraint",
           "meaning", "value"):
    _CATEGORY_MAP[_t] = "motivation"

# Strategy
for _t in ("capability", "value-stream", "resource", "course-of-action"):
    _CATEGORY_MAP[_t] = "strategy"

# Common behavioral (domain-neutral)
for _t in ("service", "process", "function", "interaction", "event"):
    _CATEGORY_MAP[_t] = "behavioral"
_CATEGORY_MAP["role"] = "active"

# Business
for _t in ("business-actor", "business-role", "business-collaboration",
           "business-interface"):
    _CATEGORY_MAP[_t] = "active"
for _t in ("business-process", "business-function", "business-interaction",
           "business-event", "business-service"):
    _CATEGORY_MAP[_t] = "behavioral"
for _t in ("business-object", "contract", "representation"):
    _CATEGORY_MAP[_t] = "passive"
_CATEGORY_MAP["product"] = "composite"

# Application
for _t in ("application-component", "application-collaboration",
           "application-interface"):
    _CATEGORY_MAP[_t] = "active"
for _t in ("application-function", "application-interaction",
           "application-process", "application-event", "application-service"):
    _CATEGORY_MAP[_t] = "behavioral"
_CATEGORY_MAP["data-object"] = "passive"

# Technology
for _t in ("technology-node", "device", "system-software",
           "technology-collaboration", "technology-interface",
           "path", "communication-network"):
    _CATEGORY_MAP[_t] = "active"
for _t in ("technology-function", "technology-process",
           "technology-interaction", "technology-event",
           "technology-service"):
    _CATEGORY_MAP[_t] = "behavioral"
_CATEGORY_MAP["artifact"] = "passive"

# Physical
for _t in ("equipment", "facility", "distribution-network"):
    _CATEGORY_MAP[_t] = "active"
_CATEGORY_MAP["material"] = "passive"

# Implementation
for _t in ("work-package", "deliverable", "implementation-event",
           "plateau", "gap"):
    _CATEGORY_MAP[_t] = "implementation"


def element_category(artifact_type: str) -> ElementCategory | None:
    return _CATEGORY_MAP.get(artifact_type)


# ---------------------------------------------------------------------------
# Symmetric connections
# ---------------------------------------------------------------------------

SYMMETRIC_CONNECTIONS: frozenset[str] = frozenset({
    "archimate-association",
})

#: ArchiMate connection types used for model-level entity connections.
#: Non-archimate types (ER, sequence, activity, use-case) are diagram-only.
ARCHIMATE_CONNECTION_TYPES: frozenset[str] = CONNECTION_TYPES_BY_LANGUAGE["archimate"]


def is_symmetric(conn_type: str) -> bool:
    return conn_type in SYMMETRIC_CONNECTIONS


# ---------------------------------------------------------------------------
# Relationship validity rules: conn_type → set of (src_cat, tgt_cat)
# ---------------------------------------------------------------------------

_CAT_ALL = ("active", "behavioral", "passive", "motivation",
            "strategy", "implementation", "composite")

RELATIONSHIP_RULES: dict[str, set[tuple[str, str]]] = {
    "archimate-composition": {(s, s) for s in _CAT_ALL},
    "archimate-aggregation": {(s, s) for s in _CAT_ALL},
    "archimate-assignment": {
        ("active", "behavioral"), ("active", "active"),
        ("active", "passive"), ("behavioral", "active"),
    },
    "archimate-realization": {(s, t) for s in _CAT_ALL for t in _CAT_ALL},
    "archimate-serving": {
        ("behavioral", "behavioral"), ("behavioral", "active"),
        ("active", "behavioral"), ("active", "active"),
        ("behavioral", "composite"), ("active", "composite"),
    },
    "archimate-access": {("behavioral", "passive"), ("active", "passive")},
    "archimate-influence": {(s, "motivation") for s in _CAT_ALL},
    "archimate-association": {(s, t) for s in _CAT_ALL for t in _CAT_ALL},
    "archimate-specialization": {(s, s) for s in _CAT_ALL},
    "archimate-flow": {("behavioral", "behavioral")},
    "archimate-triggering": {("behavioral", "behavioral")},
}


def _matches(src_cat: str, tgt_cat: str, valid: set[tuple[str, str]]) -> bool:
    return (src_cat, tgt_cat) in valid


# ---------------------------------------------------------------------------
# Public query API
# ---------------------------------------------------------------------------


def permissible_connection_types(
    source_type: str, target_type: str,
) -> list[str]:
    """Return ArchiMate connection types valid between source and target type."""
    src_cat = element_category(source_type)
    tgt_cat = element_category(target_type)
    if src_cat is None or tgt_cat is None:
        return []
    result: list[str] = []
    for ct, valid_pairs in RELATIONSHIP_RULES.items():
        if _matches(src_cat, tgt_cat, valid_pairs):
            result.append(ct)
        elif is_symmetric(ct) and _matches(tgt_cat, src_cat, valid_pairs):
            result.append(ct)
    if source_type != target_type and "archimate-specialization" in result:
        result.remove("archimate-specialization")
    return sorted(result)


def permissible_target_types(source_type: str) -> dict[str, list[str]]:
    """For a source type, return {conn_type: [valid_target_types]}.

    Only includes ArchiMate connection types with at least one valid target.
    """
    src_cat = element_category(source_type)
    if src_cat is None:
        return {}
    out: dict[str, list[str]] = {}
    for ct, valid_pairs in RELATIONSHIP_RULES.items():
        valid_tgt_cats = {pair[1] for pair in valid_pairs if pair[0] == src_cat}
        if is_symmetric(ct):
            valid_tgt_cats |= {pair[0] for pair in valid_pairs if pair[1] == src_cat}
        targets = [
            etype for etype in sorted(ALL_ENTITY_TYPES)
            if element_category(etype) in valid_tgt_cats
            and not (ct == "archimate-specialization" and etype != source_type)
        ]
        if targets:
            out[ct] = targets
    return out


def classify_connections(
    source_type: str,
) -> dict[str, dict[str, list[str]]]:
    """Classify permissible connections into outgoing/incoming/symmetric.

    Returns ``{"outgoing": {tgt_type: [conn_types]}, "incoming": ...,
    "symmetric": ...}``.  Only ArchiMate connection types are included.
    """
    src_cat = element_category(source_type)
    if src_cat is None:
        return {"outgoing": {}, "incoming": {}, "symmetric": {}}

    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    symmetric: dict[str, list[str]] = {}

    for ct, valid_pairs in RELATIONSHIP_RULES.items():
        sym = is_symmetric(ct)
        for etype in sorted(ALL_ENTITY_TYPES):
            ecat = element_category(etype)
            if ecat is None:
                continue
            if ct == "archimate-specialization" and etype != source_type:
                continue
            if sym:
                if _matches(src_cat, ecat, valid_pairs) or _matches(ecat, src_cat, valid_pairs):
                    symmetric.setdefault(etype, []).append(ct)
            else:
                if _matches(src_cat, ecat, valid_pairs):
                    outgoing.setdefault(etype, []).append(ct)
                if _matches(ecat, src_cat, valid_pairs):
                    incoming.setdefault(etype, []).append(ct)

    return {"outgoing": outgoing, "incoming": incoming, "symmetric": symmetric}
