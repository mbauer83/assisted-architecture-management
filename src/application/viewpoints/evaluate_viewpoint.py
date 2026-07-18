"""``EvaluateViewpoint``: the one use case that resolves a viewpoint
(by slug, or an ad-hoc query) and executes it against the live model, wrapping repository
projection in the execution result. REST and both MCP tools call
this — none re-implement evaluation.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass

from src.application.viewpoints.execution_result import (
    ConnectionItemSummary,
    EntityItemSummary,
    Membership,
    ViewpointExecutionResult,
)
from src.application.viewpoints.parameter_binding import anchor_entity_ids, bind_parameters
from src.application.viewpoints.ports import RepositoryReadAccess
from src.application.viewpoints.repository_projection import project_repository
from src.application.viewpoints.result_aggregation import aggregation_for_result
from src.application.viewpoints.result_summaries import matrix_axis_ids, ordered_witness_steps_for
from src.domain.artifact_types import EntityRecord
from src.domain.clock import utc_now_iso
from src.domain.viewpoint_aggregation import AggregateConnection
from src.domain.viewpoint_anchor_distance import anchor_modeled_distances
from src.domain.viewpoint_binding_evaluation import (
    BindingEvaluationInput,
    evaluate_bindings,
    evaluate_derived_attributes,
)
from src.domain.viewpoint_bindings import DerivedAttribute
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_derived_attribute_deferral import split_eager_and_deferred_derived_attributes
from src.domain.viewpoint_evaluation_context import EvaluationEnvironment
from src.domain.viewpoint_projection import ViewpointProjection, drift_warnings
from src.domain.viewpoint_scope_query import definition_with_scope_query
from src.domain.viewpoint_summary import render_query_summary
from src.domain.viewpoint_target_population import declared_target_types, summarize_target_population
from src.domain.viewpoints import (
    ExecutableViewpointQuery,
    ViewpointCatalog,
    ViewpointDefinition,
)

logger = logging.getLogger(__name__)


class UnknownViewpointSlugError(ValueError):
    """Raised when a requested slug is absent from the effective merged catalog."""


class ViewpointExecutionTimeoutError(RuntimeError):
    """Raised instead of returning a result once evaluation exceeds
    ``execution_timeout_seconds`` — never a partial result silently presented as complete.

    A pure, synchronous, in-process evaluation over an in-memory read model has no I/O to
    preempt, so this measures elapsed wall-clock time around the evaluation rather than
    attempting true mid-flight cancellation; the observable contract (no partial result
    ever reaches a caller) is the same either way.
    """

    def __init__(self, elapsed_seconds: float, timeout_seconds: float) -> None:
        super().__init__(f"viewpoint execution exceeded {timeout_seconds}s (took {elapsed_seconds:.2f}s)")
        self.elapsed_seconds = elapsed_seconds
        self.timeout_seconds = timeout_seconds


@dataclass(frozen=True)
class ViewpointExecutionRequest:
    """Exactly one of ``slug``/``query`` is set: a catalog definition, or an ad-hoc query
    with no identity/provenance. ``limit`` is entity-denominated; ``None`` defers to
    the caller-supplied default."""

    slug: str | None = None
    query: ExecutableViewpointQuery | None = None
    limit: int | None = None
    parameters: Mapping[str, object] | None = None


def _ad_hoc_definition(query: ExecutableViewpointQuery) -> ViewpointDefinition:
    return ViewpointDefinition(slug="", version=0, name="", query=query, presentation=None)


def resolve_viewpoint_definition(
    slug: str | None,
    query: ExecutableViewpointQuery | None,
    *,
    catalog: ViewpointCatalog,
) -> tuple[ViewpointDefinition, str | None, int | None]:
    """Resolve exactly one of ``slug``/``query`` to a ``ViewpointDefinition`` plus its
    identity (``None``/``None`` for an ad-hoc query) — shared by ``evaluate_viewpoint``
    and ``project_viewpoint_repository`` so slug/ad-hoc resolution has one implementation.
    """
    if slug is not None:
        resolved = catalog.get(slug)
        if resolved is None:
            raise UnknownViewpointSlugError(f"unknown viewpoint slug '{slug}'")
        return resolved, resolved.slug, resolved.version
    if query is None:
        raise ValueError("requires exactly one of slug/query")
    return _ad_hoc_definition(query), None, None


def project_viewpoint_repository(
    slug: str | None,
    query: ExecutableViewpointQuery | None,
    *,
    catalog: ViewpointCatalog,
    read_access: RepositoryReadAccess,
    registries: RegistrySnapshot,
    parameters: Mapping[str, object] | None = None,
) -> ViewpointProjection:
    """GUI-only repository-context ``ViewpointProjection`` carrying
    per-item style tokens — the styled sibling of ``evaluate_viewpoint``'s deliberately
    unstyled execution result. Never called by MCP: the boundary keeps
    style tokens out of the MCP/REST-shared execution-result contract, so this is a
    separate GUI-only entry point over the same ``project_repository`` service the
    execution result already uses internally.
    """
    definition, _, _ = resolve_viewpoint_definition(slug, query, catalog=catalog)
    prepared = _prepare_query_environment(definition, parameters, read_access, registries)
    return project_repository(
        prepared.executable_definition,
        read_access=read_access,
        registries=registries,
        scope_filter=definition.scope if prepared.scope_derived else None,
        environment=prepared.environment,
        candidate_entity_ids=prepared.entity_candidates,
        deferred_derived=prepared.deferred_derived,
    )


def evaluate_viewpoint(
    request: ViewpointExecutionRequest,
    *,
    catalog: ViewpointCatalog,
    read_access: RepositoryReadAccess,
    registries: RegistrySnapshot,
    index_generation: int | None,
    max_entities: int,
    default_limit: int,
    timeout_seconds: float,
    default_legibility_budget: int = 100,
) -> ViewpointExecutionResult:
    start = time.monotonic()

    definition, slug, version = resolve_viewpoint_definition(request.slug, request.query, catalog=catalog)
    prepared = _prepare_query_environment(definition, request.parameters, read_access, registries)
    executable_definition, scope_derived = prepared.executable_definition, prepared.scope_derived

    requested_limit = request.limit if request.limit is not None else default_limit
    limit = max(0, min(requested_limit, max_entities))

    projection = project_repository(
        executable_definition,
        read_access=read_access,
        registries=registries,
        scope_filter=definition.scope if scope_derived else None,
        environment=prepared.environment,
        candidate_entity_ids=prepared.entity_candidates,
        deferred_derived=prepared.deferred_derived,
    )

    primary_ids = sorted(
        item.item_id for item in projection.items if item.item_kind == "entity" and item.membership == "primary"
    )
    expanded_ids = sorted(
        item.item_id for item in projection.items if item.item_kind == "entity" and item.membership == "expanded"
    )
    derived_match_hops_by_id = {
        item.item_id: item.derived_match_hops
        for item in projection.items
        if item.item_kind == "entity" and item.derived_match_hops is not None
    }
    column_values_by_id = {
        item.item_id: item.column_values
        for item in projection.items
        if item.item_kind == "entity" and item.column_values is not None
    }
    total_entity_count = len(primary_ids) + len(expanded_ids)
    # Primary-before-expanded retention order: context neighbors drop first.
    retained_id_set = frozenset((primary_ids + expanded_ids)[:limit])
    membership_by_id: dict[str, Membership] = {entity_id: "primary" for entity_id in primary_ids}
    membership_by_id.update({entity_id: "expanded" for entity_id in expanded_ids})

    connection_items = [item for item in projection.items if item.item_kind == "connection"]
    total_connection_count = len(connection_items)

    aggregate_connections: list[AggregateConnection] = []
    connection_summaries: list[ConnectionItemSummary] = []
    for item in connection_items:
        connection = read_access.get_connection(item.item_id)
        source = connection.source if connection is not None else item.source_id
        target = connection.target if connection is not None else item.target_id
        connection_type = connection.conn_type if connection is not None else item.connection_type
        if source is None or target is None or connection_type is None:
            continue
        # Aggregation reads the COMPLETE population — collected before the retained-set
        # cut, or a truncated-then-aggregated result would masquerade as an overview.
        aggregate_connections.append(
            AggregateConnection(
                connection_id=item.item_id,
                source=source,
                target=target,
                connection_type=connection_type,
                certainty=item.certainty,
            )
        )
        if source not in retained_id_set or target not in retained_id_set:
            continue
        connection_summaries.append(
            ConnectionItemSummary(
                id=item.item_id,
                type=connection_type,
                source=source,
                target=target,
                certainty=item.certainty,
                hops=item.hops,
                via_connection_ids=item.via_connection_ids,
                witness_steps=ordered_witness_steps_for(item, source, target, read_access),
            )
        )
    connection_summaries.sort(key=lambda summary: summary.id)

    distances = anchor_modeled_distances(prepared.anchor_ids, connection_summaries)

    retained_entities: list[EntityRecord] = []
    entity_summaries: list[EntityItemSummary] = []
    for entity_id in sorted(retained_id_set):
        record = read_access.get_entity(entity_id)
        if record is None:
            continue
        retained_entities.append(record)
        entity_summaries.append(
            EntityItemSummary(
                id=record.artifact_id,
                name=record.name,
                type=record.artifact_type,
                specialization_slugs=(record.specialization,) if record.specialization else (),
                group=record.group,
                membership=membership_by_id[entity_id],
                status=record.status,
                version=record.version,
                column_values=column_values_by_id.get(entity_id),
                anchor_modeled_distance=distances.get(entity_id),
                matched_via_derived_hops=derived_match_hops_by_id.get(entity_id),
            )
        )

    matrix_axes, matrix_drift = matrix_axis_ids(
        executable_definition.presentation, retained_entities, read_access=read_access, registries=registries
    )
    warnings = tuple(projection.warnings) + drift_warnings(frozenset(matrix_drift))

    aggregation = aggregation_for_result(
        executable_definition.presentation,
        total_entity_count=total_entity_count,
        population_entity_ids=tuple(primary_ids + expanded_ids),
        aggregate_connections=tuple(aggregate_connections),
        read_access=read_access,
        default_legibility_budget=default_legibility_budget,
    )

    target_types = declared_target_types(definition, registries.entity_type_infos)
    target_population = (
        summarize_target_population(
            target_types,
            (
                record.artifact_type
                for item in projection.items
                if item.item_kind == "entity" and (record := read_access.get_entity(item.item_id)) is not None
            ),
            registries.entity_type_infos,
        )
        if target_types is not None
        else None
    )

    query = executable_definition.query
    assert query is not None
    result = ViewpointExecutionResult(
        slug=slug,
        version=version,
        query_schema=query.query_schema if query is not None else ExecutableViewpointQuery().query_schema,
        repo_scope=query.repo_scope if query is not None else "both",
        executed_at=utc_now_iso(),
        index_generation=index_generation,
        entity_ids=tuple(sorted(retained_id_set)),
        connection_ids=tuple(summary.id for summary in connection_summaries),
        entities=tuple(entity_summaries),
        connections=tuple(connection_summaries),
        total_entity_count=total_entity_count,
        returned_entity_count=len(retained_id_set),
        total_connection_count=total_connection_count,
        returned_connection_count=len(connection_summaries),
        truncated=len(retained_id_set) < total_entity_count,
        entity_limit=limit,
        matrix_axes=matrix_axes,
        warnings=warnings,
        duration_ms=(time.monotonic() - start) * 1000,
        anchor_ids=prepared.anchor_ids,
        target_population=target_population,
        aggregation=aggregation,
        query_summary=(
            f"Selection derived from the viewpoint's concept scope: "
            f"{render_query_summary(query, default_derivation_max_hops=registries.derivation_max_hops)}"
            if scope_derived
            else render_query_summary(query, default_derivation_max_hops=registries.derivation_max_hops)
        ),
    )

    elapsed = time.monotonic() - start
    if elapsed > timeout_seconds:
        raise ViewpointExecutionTimeoutError(elapsed, timeout_seconds)

    logger.info(
        "viewpoint execution slug=%s entities=%d/%d connections=%d/%d duration_ms=%.1f",
        slug or "<ad-hoc>",
        result.returned_entity_count,
        result.total_entity_count,
        result.returned_connection_count,
        result.total_connection_count,
        result.duration_ms,
    )
    return result


@dataclass(frozen=True)
class _PreparedQueryEnvironment:
    executable_definition: ViewpointDefinition
    scope_derived: bool
    entity_candidates: frozenset[str]
    environment: EvaluationEnvironment
    deferred_derived: tuple[DerivedAttribute, ...]
    anchor_ids: tuple[str, ...]


def _prepare_query_environment(
    definition: ViewpointDefinition,
    parameters: Mapping[str, object] | None,
    read_access: RepositoryReadAccess,
    registries: RegistrySnapshot,
) -> _PreparedQueryEnvironment:
    executable_definition, scope_derived = definition_with_scope_query(definition)
    assert executable_definition.query is not None
    query = executable_definition.query
    entity_ids = _scoped_entity_ids(read_access, query.repo_scope)
    connection_ids = _scoped_connection_ids(read_access, query.repo_scope)
    binding_input = BindingEvaluationInput(
        tuple(sorted(entity_ids)), tuple(sorted(connection_ids)), read_access, registries
    )
    resolved_parameters = bind_parameters(query, parameters, read_access)
    bindings = evaluate_bindings(query.bindings, parameters=resolved_parameters, input=binding_input)
    eager_derived, deferred_derived = split_eager_and_deferred_derived_attributes(query)
    environment = evaluate_derived_attributes(
        eager_derived, tuple(sorted(entity_ids)), input=binding_input, environment=bindings.environment
    )
    return _PreparedQueryEnvironment(
        executable_definition=executable_definition,
        scope_derived=scope_derived,
        entity_candidates=frozenset(entity_ids),
        environment=environment,
        deferred_derived=deferred_derived,
        anchor_ids=anchor_entity_ids(query, resolved_parameters),
    )


def _scoped_entity_ids(read_access: RepositoryReadAccess, scope: str) -> set[str]:
    if scope == "enterprise":
        return read_access.enterprise_entity_ids()
    if scope == "engagement":
        return read_access.engagement_entity_ids()
    return read_access.entity_ids()


def _scoped_connection_ids(read_access: RepositoryReadAccess, scope: str) -> set[str]:
    if scope == "enterprise":
        return read_access.enterprise_connection_ids()
    if scope == "engagement":
        return read_access.engagement_connection_ids()
    return read_access.connection_ids()
