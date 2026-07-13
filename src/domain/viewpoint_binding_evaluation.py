"""Pure execution of query bindings and direct derived attributes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.viewpoint_bindings import DerivedAttribute, QueryBinding
from src.domain.viewpoint_condition_evaluation import read_attribute_value
from src.domain.viewpoint_condition_validation import CriteriaContext, RegistrySnapshot
from src.domain.viewpoint_criteria import ConnectionCriteriaGroup, EntityCriteriaGroup
from src.domain.viewpoint_criteria_evaluation import (
    direction_matches,
    evaluate_connection_criteria,
    evaluate_entity_criteria,
)
from src.domain.viewpoint_evaluation_context import CriteriaReadAccess, EvaluationEnvironment
from src.domain.viewpoint_value_types import (
    ConnectionInstanceType,
    EntityInstanceType,
    OptionalType,
)


class BindingCardinalityError(ValueError):
    code = "binding-cardinality-violation"


@dataclass(frozen=True)
class BindingEvaluationInput:
    entity_ids: tuple[str, ...]
    connection_ids: tuple[str, ...]
    read_access: CriteriaReadAccess
    registries: RegistrySnapshot


@dataclass(frozen=True)
class BindingEvaluationResult:
    environment: EvaluationEnvironment


def evaluate_bindings(
    bindings: tuple[QueryBinding, ...], *, parameters: dict[str, object], input: BindingEvaluationInput
) -> BindingEvaluationResult:
    values: dict[str, object] = {}
    for binding in bindings:
        environment = EvaluationEnvironment(bindings=values, parameters=parameters)
        selected = _select(binding, input, environment)
        values[binding.name] = _materialize(binding, selected, input, environment)
    return BindingEvaluationResult(EvaluationEnvironment(bindings=values, parameters=parameters))


def evaluate_derived_attributes(
    attributes: tuple[DerivedAttribute, ...],
    entity_ids: tuple[str, ...],
    *,
    input: BindingEvaluationInput,
    environment: EvaluationEnvironment,
) -> EvaluationEnvironment:
    values: dict[tuple[str, str], object] = dict(environment.derived_values)
    for entity_id in entity_ids:
        entity = input.read_access.get_entity(entity_id)
        if entity is None:
            continue
        for attribute in attributes:
            values[(entity_id, attribute.name)] = _evaluate_derived(attribute, entity, input, environment)
    return EvaluationEnvironment(
        bindings=environment.bindings, parameters=environment.parameters, derived_values=values
    )


def _select(
    binding: QueryBinding, input: BindingEvaluationInput, environment: EvaluationEnvironment
) -> tuple[EntityRecord | ConnectionRecord, ...]:
    if binding.select == "entities":
        if binding.criteria is not None and not isinstance(binding.criteria, EntityCriteriaGroup):
            raise AssertionError("entity binding requires entity criteria")
        selected = (
            item
            for item_id in sorted(input.entity_ids)
            if (item := input.read_access.get_entity(item_id)) is not None
            and (
                binding.criteria is None
                or evaluate_entity_criteria(
                    binding.criteria,
                    item,
                    read_access=input.read_access,
                    registries=input.registries,
                    environment=environment,
                ).matched
            )
        )
        return tuple(selected)
    if binding.select == "connections":
        if binding.criteria is not None and not isinstance(binding.criteria, ConnectionCriteriaGroup):
            raise AssertionError("connection binding requires connection criteria")
        selected_connections: list[ConnectionRecord] = []
        for item_id in sorted(input.connection_ids):
            item = input.read_access.get_connection(item_id)
            if item is None:
                continue
            if (
                binding.criteria is not None
                and not evaluate_connection_criteria(
                    binding.criteria,
                    item,
                    read_access=input.read_access,
                    registries=input.registries,
                    environment=environment,
                ).matched
            ):
                continue
            selected_connections.append(item)
        return tuple(selected_connections)
    return ()


def _materialize(
    binding: QueryBinding,
    selected: tuple[EntityRecord | ConnectionRecord, ...],
    input: BindingEvaluationInput,
    environment: EvaluationEnvironment,
) -> object:
    if binding.tuple_of:
        return tuple(environment.bindings[name] for name in binding.tuple_of)
    value: object = selected
    if isinstance(binding.result_type, (EntityInstanceType, ConnectionInstanceType)):
        value = _single(binding.name, selected, required=True)
    elif isinstance(binding.result_type, OptionalType):
        value = _single(binding.name, selected, required=False)
    if binding.project is not None:
        context = cast(CriteriaContext, "entity" if binding.select == "entities" else "connection")
        records = value if isinstance(value, tuple) else (value,)
        values = tuple(
            item
            for record in records
            if isinstance(record, (EntityRecord, ConnectionRecord))
            for item, present in (
                read_attribute_value(record, binding.project, context=context, environment=environment),
            )
            if present
        )
        value = values if isinstance(value, tuple) else (values[0] if values else None)
    if binding.aggregate is not None:
        value = _reduce(value, binding.aggregate)
    return value


def _single(name: str, values: tuple[EntityRecord | ConnectionRecord, ...], *, required: bool) -> object:
    if len(values) == 1:
        return values[0]
    if not required and not values:
        return None
    expectation = "exactly one" if required else "zero or one"
    raise BindingCardinalityError(f"binding {name!r} requires {expectation} result, got {len(values)}")


def _reduce(value: object, reduce: str) -> object:
    values = value if isinstance(value, tuple) else (value,)
    present = tuple(item for item in values if item is not None)
    if reduce == "count":
        return len(present)
    if reduce == "sum":
        return sum(cast(tuple[int | float, ...], present)) if present else 0
    if reduce == "avg":
        return sum(cast(tuple[int | float, ...], present)) / len(present) if present else None
    if reduce == "min":
        return min(cast(tuple[str | int | float, ...], present)) if present else None
    if reduce == "max":
        return max(cast(tuple[str | int | float, ...], present)) if present else None
    raise AssertionError(f"unhandled reduction {reduce!r}")


def _evaluate_derived(
    attribute: DerivedAttribute,
    entity: EntityRecord,
    input: BindingEvaluationInput,
    environment: EvaluationEnvironment,
) -> object:
    if attribute.traversal != "direct":
        return None
    values: list[object] = []
    count = 0
    for connection in input.read_access.find_connections_for(entity.artifact_id, direction="any"):
        if not direction_matches(connection, entity.artifact_id, attribute.direction, input.registries):
            continue
        if (
            attribute.connection_criteria is not None
            and not evaluate_connection_criteria(
                attribute.connection_criteria,
                connection,
                read_access=input.read_access,
                registries=input.registries,
                environment=environment,
            ).matched
        ):
            continue
        other_id = connection.target if connection.source == entity.artifact_id else connection.source
        endpoint = input.read_access.get_entity(other_id)
        if endpoint is None:
            continue
        if (
            attribute.endpoint_criteria is not None
            and not evaluate_entity_criteria(
                attribute.endpoint_criteria,
                endpoint,
                read_access=input.read_access,
                registries=input.registries,
                environment=environment,
            ).matched
        ):
            continue
        count += 1
        if attribute.of is not None:
            head, _, path = attribute.of.partition(".")
            record = connection if head == "connection" else endpoint
            context = cast(CriteriaContext, "connection" if head == "connection" else "entity")
            value, present = read_attribute_value(record, path, context=context, environment=environment)
            if present:
                values.append(value)
    return count if attribute.reduce == "count" else _reduce(tuple(values), attribute.reduce)
