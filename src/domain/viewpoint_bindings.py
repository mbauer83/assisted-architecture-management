"""Immutable value objects for query bindings, parameters, and derived attributes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.domain.viewpoint_criteria import ConnectionCriteriaGroup, EntityCriteriaGroup, IncidentDirection
from src.domain.viewpoint_value_types import AggregateKind, BindingSelect, QueryResultType, ScalarKind

DerivedTraversal = Literal["direct", "derived"]


@dataclass(frozen=True)
class QueryBinding:
    name: str
    result_type: QueryResultType
    select: BindingSelect | None = None
    criteria: EntityCriteriaGroup | ConnectionCriteriaGroup | None = None
    project: str | None = None
    aggregate: AggregateKind | None = None
    tuple_of: tuple[str, ...] = ()
    include_in_result: bool = False


@dataclass(frozen=True)
class QueryParameter:
    name: str
    value_type: ScalarKind | Literal["entity-id"]
    required: bool = True
    default: object = None
    description: str = ""


@dataclass(frozen=True)
class DerivedAttribute:
    name: str
    direction: IncidentDirection = "either"
    traversal: DerivedTraversal = "direct"
    include_potential: bool = False
    max_hops: int | None = None
    connection_criteria: ConnectionCriteriaGroup | None = None
    endpoint_criteria: EntityCriteriaGroup | None = None
    reduce: AggregateKind = "count"
    of: str | None = None
