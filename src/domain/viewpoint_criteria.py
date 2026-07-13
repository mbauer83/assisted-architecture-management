"""The criteria engine: reusable condition trees for viewpoint query filtering, neighbor
inclusion, and style-rule matching.

``EntityCriteriaGroup``/``ConnectionCriteriaGroup`` are the ONE condition-building concept
used everywhere a boolean tree of attribute predicates appears — query filters, style-rule
``mode="match"`` criteria, and matrix axis criteria all reuse these same types rather than
parallel structures. Pure shapes only: parsing lives in ``viewpoint_criteria_parsing.py``,
registry-aware validation in ``viewpoint_criteria_validation.py``, evaluation semantics are
implemented by the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Conjunction = Literal["and", "or"]
Comparator = Literal["eq", "neq", "in", "exists", "absent", "lt", "lte", "gt", "gte"]
ValueRefKind = Literal["literal", "attribute_of_self", "attribute_of_endpoint", "binding", "parameter"]
IncidentDirection = Literal["outgoing", "incoming", "either"]
RelationshipTraversal = Literal["direct", "derived"]

# Exactly today's operator vocabulary — the criteria-tree redesign restructures how
# conditions nest, it does not expand the comparator set. There is deliberately no
# `not_in`: per-condition `negate` already expresses it as `in` + negate, keeping one
# spelling per meaning.
NUMERIC_OPERATORS: frozenset[str] = frozenset({"lt", "lte", "gt", "gte"})
NUMERIC_ATTRIBUTE_TYPES: frozenset[str] = frozenset({"integer", "number", "date"})
VALID_COMPARATORS: frozenset[str] = frozenset({"eq", "neq", "in", "exists", "absent"}) | NUMERIC_OPERATORS
VALID_VALUE_REF_KINDS: frozenset[str] = frozenset(
    {"literal", "attribute_of_self", "attribute_of_endpoint", "binding", "parameter"}
)
VALID_INCIDENT_DIRECTIONS: frozenset[str] = frozenset({"outgoing", "incoming", "either"})
VALID_CONJUNCTIONS: frozenset[str] = frozenset({"and", "or"})

# Addressable properties: reserved read-model paths, resolved before
# the effective schema. None are numeric/date, so numeric comparators are always a save-mode
# error against a reserved path (`version` is explicitly "string comparators only").
RESERVED_ENTITY_PATHS: frozenset[str] = frozenset(
    {"id", "name", "type", "specialization", "group", "domain", "subdomain", "status", "version"}
)
RESERVED_CONNECTION_PATHS: frozenset[str] = frozenset({"id", "type", "specialization"})


@dataclass(frozen=True)
class ValueRef:
    """A condition's comparison value: a literal, or a reference to another attribute.

    ``attribute_of_self`` compares against another attribute on the SAME entity/connection
    being evaluated (e.g. ``end_date >= start_date``). ``attribute_of_endpoint`` is valid
    only within a connection condition, and reads an attribute off the source or target
    entity (e.g. ``strength >= target.threshold``).
    """

    kind: ValueRefKind = "literal"
    literal: object = None
    attribute: str | None = None  # required when kind != "literal"
    endpoint: Literal["source", "target"] | None = None  # required when kind == "attribute_of_endpoint"
    binding: str | None = None
    parameter: str | None = None
    project: str | None = None
    aggregate: Literal["count", "sum", "avg", "min", "max"] | None = None
    quantifier: Literal["any", "all"] | None = None


@dataclass(frozen=True)
class AttributeCondition:
    attribute: str  # dotted path
    comparator: Comparator
    value: ValueRef = ValueRef()
    negate: bool = False  # strict logical complement, including a missing attribute


@dataclass(frozen=True)
class EntityCriteriaGroup:
    conjunction: Conjunction = "and"
    children: "tuple[AttributeCondition | IncidentConnectionCondition | EntityCriteriaGroup, ...]" = ()
    negate: bool = False


@dataclass(frozen=True)
class ConnectionCriteriaGroup:
    conjunction: Conjunction = "and"
    children: "tuple[AttributeCondition | ConnectionCriteriaGroup, ...]" = ()
    negate: bool = False


@dataclass(frozen=True)
class IncidentConnectionCondition:
    """Entity-only predicate: "this entity has (or, negated, does not have) at least one
    incident connection matching ``connection_criteria``/``direction`` whose OTHER endpoint
    matches ``endpoint_criteria``." Fully criteria-based on both legs of the hop; recursive
    via ``endpoint_criteria``, bounded by save-time depth-cap validation.
    """

    connection_criteria: ConnectionCriteriaGroup | None = None  # None = any connection
    direction: IncidentDirection = "either"
    endpoint_criteria: EntityCriteriaGroup | None = None  # None = any entity
    negate: bool = False
    traversal: RelationshipTraversal = "direct"
    include_potential: bool = False
    max_hops: int | None = None


@dataclass(frozen=True)
class ConnectionSelection:
    """Which connections a query displays, within the structural invariant: a
    connection is included only if both its source and target entities are in the included
    entity set. ``criteria`` narrows within that set; it can never widen past it.
    """

    enabled: bool = True
    criteria: ConnectionCriteriaGroup = ConnectionCriteriaGroup()


@dataclass(frozen=True)
class NeighborInclusion:
    """Additive population term: include entities matching ``neighbor_criteria`` that
    are connected — by a connection matching ``connection_criteria``, in ``direction``
    relative to the anchor — to at least one entity of the query's PRIMARY result set.
    Anchors are always the primary set; inclusions never chain off other inclusions' results.
    """

    connection_criteria: ConnectionCriteriaGroup | None = None  # None = any connection
    direction: IncidentDirection = "either"  # relative to the anchor
    neighbor_criteria: EntityCriteriaGroup | None = None  # None = any entity
    traversal: RelationshipTraversal = "direct"
    include_potential: bool = False
    max_hops: int | None = None


EntityCriteriaNode = AttributeCondition | IncidentConnectionCondition | EntityCriteriaGroup
ConnectionCriteriaNode = AttributeCondition | ConnectionCriteriaGroup
