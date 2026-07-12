"""Leaf-level evaluation for one ``AttributeCondition`` (companion plan §3.4): resolves the
condition's attribute and comparison value against a live entity/connection record, then
applies the normative per-comparator × presence semantics table. No coercion — types are
compared as parsed (validation gates comparator/type mismatches at save time); a
TypeError-worthy mismatch that survives to evaluation time anyway (e.g. after schema drift)
is treated as no match for that candidate rather than crashing the whole viewpoint
execution.
"""

from __future__ import annotations

from collections.abc import Mapping

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.viewpoint_condition_validation import (
    CriteriaContext,
    RegistrySnapshot,
    resolve_attribute_path,
)
from src.domain.viewpoint_criteria import (
    RESERVED_CONNECTION_PATHS,
    RESERVED_ENTITY_PATHS,
    AttributeCondition,
    ValueRef,
)
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess, EvaluationOutcome

Record = EntityRecord | ConnectionRecord

_NUMERIC_COMPARATORS: frozenset[str] = frozenset({"lt", "lte", "gt", "gte"})


def _numeric_compare(comparator: str, candidate: object, expected: object) -> bool:
    try:
        if comparator == "lt":
            return candidate < expected  # type: ignore[operator]
        if comparator == "lte":
            return candidate <= expected  # type: ignore[operator]
        if comparator == "gt":
            return candidate > expected  # type: ignore[operator]
        return candidate >= expected  # type: ignore[operator]
    except TypeError:
        return False


def _reserved_entity_field(record: EntityRecord, head: str) -> tuple[object, bool]:
    if head == "id":
        return record.artifact_id, True
    if head == "name":
        return record.name, True
    if head == "type":
        return record.artifact_type, True
    if head == "specialization":
        return record.specialization, bool(record.specialization)
    if head == "group":
        return record.group, True
    if head == "domain":
        return record.domain, True
    if head == "subdomain":
        return record.subdomain, True
    if head == "status":
        return record.status, True
    if head == "version":
        return record.version, True
    raise AssertionError(f"unhandled reserved entity path {head!r}")


def _reserved_connection_field(record: ConnectionRecord, head: str) -> tuple[object, bool]:
    if head == "id":
        return record.artifact_id, True
    if head == "type":
        return record.conn_type, True
    if head == "specialization":
        return record.specialization, bool(record.specialization)
    raise AssertionError(f"unhandled reserved connection path {head!r}")


def read_attribute_value(record: Record, attribute: str, *, context: CriteriaContext) -> tuple[object, bool]:
    """Read a dotted attribute path off a record: reserved fields first, then ``extra``.
    Returns ``(value, present)`` — shared by condition evaluation and style-rule range
    lookups (``viewpoint_style_evaluation.py``), so both read attributes identically.
    """
    head, _, rest = attribute.partition(".")
    reserved = RESERVED_ENTITY_PATHS if context == "entity" else RESERVED_CONNECTION_PATHS
    if head in reserved:
        if context == "entity":
            assert isinstance(record, EntityRecord)
            return _reserved_entity_field(record, head)
        assert isinstance(record, ConnectionRecord)
        return _reserved_connection_field(record, head)
    extra: object = record.extra
    if not isinstance(extra, Mapping) or head not in extra:
        return None, False
    value = extra[head]
    for part in rest.split(".") if rest else ():
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        else:
            return None, False
    return value, True


def _resolve_attribute_ref(
    attribute: str, *, record: Record, context: CriteriaContext, registries: RegistrySnapshot
) -> tuple[object, frozenset[str], bool]:
    """Resolve a ``ValueRef``'s referenced attribute: ``(value, drift-warnings, resolved?)``."""
    if not attribute:
        return None, frozenset(), False
    declared = resolve_attribute_path(attribute, context=context, registries=registries)
    if declared is None:
        return None, frozenset({attribute}), False
    actual, present = read_attribute_value(record, attribute, context=context)
    return (actual, frozenset(), True) if present else (None, frozenset(), False)


def _resolve_value(
    value: ValueRef,
    *,
    record: Record,
    context: CriteriaContext,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    connection: ConnectionRecord | None,
) -> tuple[object, frozenset[str], bool]:
    if value.kind == "literal":
        return value.literal, frozenset(), True
    if value.kind == "attribute_of_self":
        return _resolve_attribute_ref(value.attribute or "", record=record, context=context, registries=registries)
    if value.kind == "attribute_of_endpoint":
        if context != "connection" or connection is None or value.endpoint is None:
            return None, frozenset(), False
        endpoint_id = connection.source if value.endpoint == "source" else connection.target
        endpoint_entity = read_access.get_entity(endpoint_id)
        if endpoint_entity is None:
            return None, frozenset(), False
        return _resolve_attribute_ref(
            value.attribute or "", record=endpoint_entity, context="entity", registries=registries
        )
    raise AssertionError(f"unhandled value ref kind {value.kind!r}")


def _compare(comparator: str, actual: object, expected: object) -> bool:
    if comparator == "eq":
        if isinstance(actual, (list, tuple)):
            return any(element == expected for element in actual)
        return actual == expected
    if comparator == "neq":
        if isinstance(actual, (list, tuple)):
            return not any(element == expected for element in actual)
        return actual != expected
    if comparator == "in":
        options = expected if isinstance(expected, (list, tuple)) else ()
        if isinstance(actual, (list, tuple)):
            return any(element in options for element in actual)
        return actual in options
    if comparator in _NUMERIC_COMPARATORS:
        candidates = actual if isinstance(actual, (list, tuple)) else (actual,)
        return any(_numeric_compare(comparator, candidate, expected) for candidate in candidates)
    raise AssertionError(f"unhandled comparator {comparator!r}")


def evaluate_attribute_condition(
    condition: AttributeCondition,
    *,
    record: Record,
    context: CriteriaContext,
    read_access: CriteriaReadAccess,
    registries: RegistrySnapshot,
    connection: ConnectionRecord | None,
) -> EvaluationOutcome:
    declared = resolve_attribute_path(condition.attribute, context=context, registries=registries)
    drift: frozenset[str] = frozenset()
    if declared is None:
        drift = frozenset({condition.attribute})
        actual, present = None, False
    else:
        actual, present = read_attribute_value(record, condition.attribute, context=context)

    if condition.comparator == "exists":
        matched = present
    elif condition.comparator == "absent":
        matched = not present
    elif not present:
        matched = False
    else:
        expected, ref_drift, resolved = _resolve_value(
            condition.value,
            record=record,
            context=context,
            read_access=read_access,
            registries=registries,
            connection=connection,
        )
        drift = drift | ref_drift
        matched = resolved and _compare(condition.comparator, actual, expected)

    if condition.negate:
        matched = not matched
    return EvaluationOutcome(matched, drift)
