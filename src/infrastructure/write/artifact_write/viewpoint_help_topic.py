"""Viewpoints help topic (companion plan §9.1): the Appendix-A schema pointer, comparator
semantics (§3.4), reserved attribute paths (§3.3), and representation capabilities, exposed
via ``artifact_help`` so the ``artifact_query_viewpoint``/``artifact_viewpoint`` tool
descriptions can stay short while the full grammar is one deliberate hop away.
"""

from __future__ import annotations

from src.domain.viewpoint_criteria import (
    RESERVED_CONNECTION_PATHS,
    RESERVED_ENTITY_PATHS,
    VALID_VALUE_REF_KINDS,
)
from src.domain.viewpoints import QUERY_SCHEMA_VERSION, REPRESENTATION_CAPABILITIES

_COMPARATOR_SEMANTICS: dict[str, str] = {
    "eq": "equal; a multi-valued attribute matches if any element equals the value",
    "neq": "not equal; a multi-valued attribute matches only if no element equals the value",
    "in": "value is one of a list; a multi-valued attribute matches if any element is in the list",
    "exists": "attribute is present (no value operand)",
    "absent": "attribute is missing (no value operand) — the only comparator matching a missing attribute",
    "lt": "less than (numeric/date attributes only)",
    "lte": "at most (numeric/date attributes only)",
    "gt": "greater than (numeric/date attributes only)",
    "gte": "at least (numeric/date attributes only)",
}

# Appendix A example 1 — the simplest worked example (flat AND, one condition), copied
# verbatim so this topic's example never drifts from the canonical form the parser accepts.
_CANONICAL_FORM_EXAMPLE: dict[str, object] = {
    "query_schema": QUERY_SCHEMA_VERSION,
    "entity_criteria": {
        "kind": "group",
        "conjunction": "and",
        "children": [
            {"kind": "condition", "attribute": "type", "comparator": "in", "value": ["application-component"]}
        ],
    },
}


def viewpoints_help_topic() -> dict[str, object]:
    """§3.3/§3.4 reference tables plus one canonical worked example — everything an agent
    needs to author or read a viewpoint query without re-deriving the grammar from source."""
    return {
        "query_schema": QUERY_SCHEMA_VERSION,
        "comparators": _COMPARATOR_SEMANTICS,
        "value_ref_kinds": sorted(VALID_VALUE_REF_KINDS),
        "reserved_entity_paths": sorted(RESERVED_ENTITY_PATHS),
        "reserved_connection_paths": sorted(RESERVED_CONNECTION_PATHS),
        "representation_capabilities": {
            representation: sorted(capabilities) for representation, capabilities in REPRESENTATION_CAPABILITIES.items()
        },
        "canonical_form_example": _CANONICAL_FORM_EXAMPLE,
        "notes": (
            "negate is the strict logical complement (§3.4): 'eq' + negate on a missing attribute "
            "matches — it reads as 'is not X, or has no value', not 'has X removed'. Connection "
            "endpoints are not addressable as left-hand condition paths; compare against an "
            "endpoint's attribute with a ValueRef(kind=attribute_of_endpoint) value instead."
        ),
    }
