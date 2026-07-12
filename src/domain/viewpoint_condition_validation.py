"""Leaf-level validation for one ``AttributeCondition`` (companion plan §3.3, §3.4): value
shape per comparator, attribute resolution (reserved path vs. effective schema), and
comparator/type gating. Split out of ``viewpoint_criteria_validation.py`` to keep tree
recursion and leaf checks each independently readable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from src.domain.viewpoint_criteria import (
    NUMERIC_ATTRIBUTE_TYPES,
    NUMERIC_OPERATORS,
    RESERVED_CONNECTION_PATHS,
    RESERVED_ENTITY_PATHS,
    AttributeCondition,
)
from src.domain.viewpoint_validation_issue import ViewpointValidationIssue

CriteriaContext = Literal["entity", "connection"]


@dataclass(frozen=True)
class RegistrySnapshot:
    """Everything criteria-tree validation needs to resolve against the current
    repository/registries — bundled to keep recursive call signatures manageable."""

    known_entity_types: frozenset[str]
    known_connection_types: frozenset[str]
    known_specialization_slugs: frozenset[str]
    entity_attribute_types: Mapping[str, str]
    connection_attribute_types: Mapping[str, str]
    symmetric_connection_types: frozenset[str] = frozenset()
    depth_cap: int = 4


def issue(severity: Literal["error", "warning"], code: str, path: str, message: str) -> ViewpointValidationIssue:
    return ViewpointValidationIssue(severity=severity, code=code, path=path, message=message)


def resolve_attribute_path(
    attribute: str, *, context: CriteriaContext, registries: RegistrySnapshot
) -> str | Literal["reserved"] | None:
    """Resolve a dotted attribute path's declared type: ``"reserved"`` for a §3.3 reserved
    path, the declared schema type string for a known profile attribute, or ``None`` if
    unknown against both."""
    head = attribute.split(".", 1)[0]
    reserved = RESERVED_ENTITY_PATHS if context == "entity" else RESERVED_CONNECTION_PATHS
    if head in reserved:
        return "reserved"
    attribute_types = (
        registries.entity_attribute_types if context == "entity" else registries.connection_attribute_types
    )
    return attribute_types.get(attribute)


def _validate_value_shape(
    condition: AttributeCondition, *, path: str, context: CriteriaContext
) -> list[ViewpointValidationIssue]:
    issues: list[ViewpointValidationIssue] = []
    value = condition.value
    if condition.comparator in ("exists", "absent"):
        if value.kind != "literal" or value.literal is not None:
            issues.append(issue("error", "unexpected-value", f"{path}/value", f"{condition.comparator} takes no value"))
        return issues
    if value.kind == "attribute_of_endpoint":
        if value.endpoint is None:
            issues.append(
                issue("error", "value-ref-missing-endpoint", f"{path}/value", "attribute_of_endpoint requires endpoint")
            )
        if context != "connection":
            issues.append(
                issue(
                    "error",
                    "value-ref-endpoint-outside-connection",
                    f"{path}/value",
                    "attribute_of_endpoint is only valid within a connection condition",
                )
            )
    if value.kind in ("attribute_of_self", "attribute_of_endpoint") and not value.attribute:
        issues.append(
            issue("error", "value-ref-missing-attribute", f"{path}/value", f"{value.kind} requires attribute")
        )
    if condition.comparator == "in" and value.kind == "literal" and not isinstance(value.literal, (list, tuple)):
        issues.append(issue("error", "unsupported-value-shape", f"{path}/value", "'in' requires a list value"))
    return issues


def _validate_reserved_value(
    condition: AttributeCondition, *, path: str, context: CriteriaContext, registries: RegistrySnapshot
) -> list[ViewpointValidationIssue]:
    if condition.value.kind != "literal" or condition.comparator not in ("eq", "neq", "in"):
        return []
    head = condition.attribute.split(".", 1)[0]
    values = (
        condition.value.literal if isinstance(condition.value.literal, (list, tuple)) else [condition.value.literal]
    )
    known: frozenset[str] | None = None
    if head == "type":
        known = registries.known_entity_types if context == "entity" else registries.known_connection_types
    elif head == "specialization":
        known = registries.known_specialization_slugs
    if known is None:
        return []
    return [
        issue("error", "unknown-value", f"{path}/value", f"{head} value {value!r} is not a known slug")
        for value in values
        if isinstance(value, str) and value not in known
    ]


def validate_condition(
    condition: AttributeCondition, *, path: str, context: CriteriaContext, registries: RegistrySnapshot
) -> list[ViewpointValidationIssue]:
    issues = _validate_value_shape(condition, path=path, context=context)
    declared = resolve_attribute_path(condition.attribute, context=context, registries=registries)
    if declared is None:
        issues.append(
            issue("error", "unknown-attribute", f"{path}/attribute", f"unknown attribute {condition.attribute!r}")
        )
        return issues
    if declared == "reserved":
        if condition.comparator in NUMERIC_OPERATORS:
            message = (
                f"numeric comparator {condition.comparator!r} is not valid for reserved path {condition.attribute!r}"
            )
            issues.append(issue("error", "operator-type-mismatch", f"{path}/comparator", message))
        issues.extend(_validate_reserved_value(condition, path=path, context=context, registries=registries))
        return issues
    if condition.comparator in NUMERIC_OPERATORS and declared not in NUMERIC_ATTRIBUTE_TYPES:
        comparator, attribute = condition.comparator, condition.attribute
        message = f"comparator {comparator!r} invalid for attribute {attribute!r} of type {declared!r}"
        issues.append(issue("error", "operator-type-mismatch", f"{path}/comparator", message))
    return issues
