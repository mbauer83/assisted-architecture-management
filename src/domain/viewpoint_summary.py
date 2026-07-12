"""Plain-language summary renderer (companion plan §9.1): one pure domain function turning
a query's criteria trees, neighbor inclusions, and connection selection into a single
human-readable sentence set — shared verbatim by GUI live preview, REST, and MCP
``list``/``execute`` so the three surfaces can never disagree.

Renders every node kind over the read-model attribute-path namespace (§3.3): conditions
(incl. the §3.4 negate rule — ``eq`` + ``negate`` reads as "is not X, or has no value", the
strict-complement wording the plan calls out explicitly), incident predicates, boolean
groups, neighbor-inclusion terms, and connection selection. No type-name humanization: it
renders the addressable attribute paths and values verbatim, which keeps the renderer
deterministic and testable without inventing a display-name lookup the plan does not
specify.
"""

from __future__ import annotations

from src.domain.viewpoint_criteria import (
    AttributeCondition,
    ConnectionCriteriaGroup,
    ConnectionCriteriaNode,
    ConnectionSelection,
    EntityCriteriaGroup,
    EntityCriteriaNode,
    IncidentConnectionCondition,
    IncidentDirection,
    ValueRef,
)
from src.domain.viewpoints import ExecutableViewpointQuery, NeighborInclusion

_COMPARATOR_WORDS: dict[str, str] = {"lt": "less than", "lte": "at most", "gt": "greater than", "gte": "at least"}
_INCIDENT_DIRECTION_WORDS: dict[IncidentDirection, str] = {
    "outgoing": "an outgoing",
    "incoming": "an incoming",
    "either": "an",
}


def render_query_summary(query: ExecutableViewpointQuery) -> str:
    sentences = [f"Entities where {render_entity_group(query.entity_criteria)}."]
    sentences.extend(f"{render_neighbor_inclusion(inclusion)}." for inclusion in query.include_connected)
    sentences.append(f"{render_connection_selection(query.connections)}.")
    return " ".join(sentences)


def render_value(value: ValueRef) -> str:
    if value.kind == "attribute_of_self":
        return f"its own {value.attribute}"
    if value.kind == "attribute_of_endpoint":
        return f"the {value.endpoint} entity's {value.attribute}"
    literal = value.literal
    if isinstance(literal, (list, tuple)):
        return ", ".join(str(item) for item in literal)
    return str(literal)


def _condition_phrase(condition: AttributeCondition) -> str:
    if condition.comparator == "exists":
        return f"{condition.attribute} is present"
    if condition.comparator == "absent":
        return f"{condition.attribute} has no value"
    value_text = render_value(condition.value)
    if condition.comparator == "eq":
        return f"{condition.attribute} is {value_text}"
    if condition.comparator == "neq":
        return f"{condition.attribute} is not {value_text}"
    if condition.comparator == "in":
        return f"{condition.attribute} is one of {value_text}"
    return f"{condition.attribute} is {_COMPARATOR_WORDS[condition.comparator]} {value_text}"


def render_condition(condition: AttributeCondition) -> str:
    """§3.4: ``negate`` is the strict logical complement. ``eq`` + ``negate`` is special-cased
    to the plan's own required wording ("is not X, or has no value") rather than a generic
    "NOT (...)" wrapper, since that is the case the plan calls out as easy to get wrong."""
    if not condition.negate:
        return _condition_phrase(condition)
    if condition.comparator == "eq":
        return f"{condition.attribute} is not {render_value(condition.value)}, or has no value"
    return f"NOT ({_condition_phrase(condition)})"


def render_incident(condition: IncidentConnectionCondition) -> str:
    if condition.negate:
        return "has no such connection"
    direction_word = _INCIDENT_DIRECTION_WORDS[condition.direction]
    connection_phrase = (
        render_connection_group(condition.connection_criteria) if condition.connection_criteria is not None else "any"
    )
    endpoint_phrase = (
        render_entity_group(condition.endpoint_criteria) if condition.endpoint_criteria is not None else "any entity"
    )
    return f"has {direction_word} connection ({connection_phrase}) to an entity where ({endpoint_phrase})"


def _render_entity_node(node: EntityCriteriaNode) -> str:
    if isinstance(node, EntityCriteriaGroup):
        return render_entity_group(node)
    if isinstance(node, IncidentConnectionCondition):
        return render_incident(node)
    return render_condition(node)


def _render_connection_node(node: ConnectionCriteriaNode) -> str:
    if isinstance(node, ConnectionCriteriaGroup):
        return render_connection_group(node)
    return render_condition(node)


def render_entity_group(group: EntityCriteriaGroup) -> str:
    if not group.children:
        return "no entity" if group.negate else "any entity"
    joiner = " and " if group.conjunction == "and" else " or "
    joined = joiner.join(_render_entity_node(child) for child in group.children)
    phrase = f"({joined})" if group.negate or len(group.children) > 1 else joined
    return f"NOT {phrase}" if group.negate else phrase


def render_connection_group(group: ConnectionCriteriaGroup) -> str:
    if not group.children:
        return "no connection" if group.negate else "any connection"
    joiner = " and " if group.conjunction == "and" else " or "
    joined = joiner.join(_render_connection_node(child) for child in group.children)
    phrase = f"({joined})" if group.negate or len(group.children) > 1 else joined
    return f"NOT {phrase}" if group.negate else phrase


def render_neighbor_inclusion(inclusion: NeighborInclusion) -> str:
    direction_word = _INCIDENT_DIRECTION_WORDS[inclusion.direction]
    neighbor_phrase = (
        render_entity_group(inclusion.neighbor_criteria) if inclusion.neighbor_criteria is not None else "any entity"
    )
    connection_phrase = (
        render_connection_group(inclusion.connection_criteria)
        if inclusion.connection_criteria is not None
        else "any connection"
    )
    return (
        f"Also include entities where ({neighbor_phrase}) connected via {direction_word} "
        f"connection ({connection_phrase}) to the primary selection"
    )


def render_connection_selection(selection: ConnectionSelection) -> str:
    if not selection.enabled:
        return "No connections are displayed"
    if not selection.criteria.children:
        return "All connections between included entities are displayed"
    return f"Connections are displayed where {render_connection_group(selection.criteria)}"
