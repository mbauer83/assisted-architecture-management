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
    MatrixAxisIds,
    Membership,
    ViewpointExecutionResult,
)
from src.application.viewpoints.ports import RepositoryReadAccess
from src.application.viewpoints.repository_projection import project_repository
from src.application.viewpoints.scope_query import definition_with_scope_query
from src.domain.artifact_types import EntityRecord
from src.domain.clock import utc_now_iso
from src.domain.viewpoint_binding_evaluation import (
    BindingEvaluationInput,
    evaluate_bindings,
    evaluate_derived_attributes,
)
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria_evaluation import evaluate_entity_criteria
from src.domain.viewpoint_projection import ViewpointProjection, drift_warnings
from src.domain.viewpoint_summary import render_query_summary
from src.domain.viewpoints import (
    ExecutableViewpointQuery,
    PresentationSpec,
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


class ViewpointParameterError(ValueError):
    """Raised when supplied query parameters do not match the declaration."""

    def __init__(self, code: str, parameter: str) -> None:
        super().__init__(f"{code}: {parameter}")
        self.code = code
        self.parameter = parameter


def _bind_parameters(
    query: ExecutableViewpointQuery, supplied: Mapping[str, object] | None, read_access: RepositoryReadAccess
) -> dict[str, object]:
    values = dict(supplied or {})
    declared = {parameter.name: parameter for parameter in query.parameters}
    for name in values:
        if name not in declared:
            raise ViewpointParameterError("unknown-parameter", name)
    resolved: dict[str, object] = {}
    for name, parameter in declared.items():
        if name not in values:
            if parameter.default is not None:
                resolved[name] = parameter.default
                continue
            if parameter.required:
                raise ViewpointParameterError("missing-parameter", name)
            continue
        value = values[name]
        if not _matches_parameter(value, parameter.value_type):
            raise ViewpointParameterError("parameter-type-mismatch", name)
        if parameter.value_type == "entity-id" and isinstance(value, str) and read_access.get_entity(value) is None:
            continue
        resolved[name] = value
    return resolved


def _matches_parameter(value: object, value_type: str) -> bool:
    if value_type in {"string", "slug", "date", "entity-id"}:
        return isinstance(value, str)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "boolean":
        return isinstance(value, bool)
    return False


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
) -> ViewpointProjection:
    """GUI-only repository-context ``ViewpointProjection`` carrying
    per-item style tokens — the styled sibling of ``evaluate_viewpoint``'s deliberately
    unstyled execution result. Never called by MCP: the boundary keeps
    style tokens out of the MCP/REST-shared execution-result contract, so this is a
    separate GUI-only entry point over the same ``project_repository`` service the
    execution result already uses internally.
    """
    definition, _, _ = resolve_viewpoint_definition(slug, query, catalog=catalog)
    executable_definition, scope_derived = definition_with_scope_query(definition)
    return project_repository(
        executable_definition,
        read_access=read_access,
        registries=registries,
        scope_filter=definition.scope if scope_derived else None,
    )


def _matrix_axis_ids(
    presentation: PresentationSpec | None,
    retained_entities: list[EntityRecord],
    *,
    read_access: RepositoryReadAccess,
    registries: RegistrySnapshot,
) -> tuple[MatrixAxisIds | None, frozenset[str]]:
    if presentation is None or presentation.representation != "matrix":
        return None, frozenset()
    if presentation.row_criteria is None or presentation.column_criteria is None:
        return None, frozenset()
    drift: set[str] = set()
    rows: list[str] = []
    columns: list[str] = []
    for record in retained_entities:
        row_outcome = evaluate_entity_criteria(
            presentation.row_criteria, record, read_access=read_access, registries=registries
        )
        drift |= row_outcome.schema_drift
        if row_outcome.matched:
            rows.append(record.artifact_id)
        column_outcome = evaluate_entity_criteria(
            presentation.column_criteria, record, read_access=read_access, registries=registries
        )
        drift |= column_outcome.schema_drift
        if column_outcome.matched:
            columns.append(record.artifact_id)
    return MatrixAxisIds(row_entity_ids=tuple(sorted(rows)), column_entity_ids=tuple(sorted(columns))), frozenset(drift)


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
) -> ViewpointExecutionResult:
    start = time.monotonic()

    definition, slug, version = resolve_viewpoint_definition(request.slug, request.query, catalog=catalog)
    executable_definition, scope_derived = definition_with_scope_query(definition)
    assert executable_definition.query is not None
    parameters = _bind_parameters(executable_definition.query, request.parameters, read_access)
    entity_candidates = _scoped_entity_ids(read_access, executable_definition.query.repo_scope)
    connection_candidates = _scoped_connection_ids(read_access, executable_definition.query.repo_scope)
    binding_input = BindingEvaluationInput(
        tuple(sorted(entity_candidates)), tuple(sorted(connection_candidates)), read_access, registries
    )
    binding_result = evaluate_bindings(
        executable_definition.query.bindings,
        parameters=parameters,
        input=binding_input,
    )
    environment = evaluate_derived_attributes(
        executable_definition.query.derived,
        tuple(sorted(entity_candidates)),
        input=binding_input,
        environment=binding_result.environment,
    )

    requested_limit = request.limit if request.limit is not None else default_limit
    limit = max(0, min(requested_limit, max_entities))

    projection = project_repository(
        executable_definition,
        read_access=read_access,
        registries=registries,
        scope_filter=definition.scope if scope_derived else None,
        environment=environment,
        candidate_entity_ids=frozenset(entity_candidates),
    )

    primary_ids = sorted(
        item.item_id for item in projection.items if item.item_kind == "entity" and item.membership == "primary"
    )
    expanded_ids = sorted(
        item.item_id for item in projection.items if item.item_kind == "entity" and item.membership == "expanded"
    )
    total_entity_count = len(primary_ids) + len(expanded_ids)
    # Primary-before-expanded retention order: context neighbors drop first.
    retained_id_set = frozenset((primary_ids + expanded_ids)[:limit])
    membership_by_id: dict[str, Membership] = {entity_id: "primary" for entity_id in primary_ids}
    membership_by_id.update({entity_id: "expanded" for entity_id in expanded_ids})

    connection_items = [item for item in projection.items if item.item_kind == "connection"]
    total_connection_count = len(connection_items)

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
            )
        )

    connection_summaries: list[ConnectionItemSummary] = []
    for item in connection_items:
        connection = read_access.get_connection(item.item_id)
        source = connection.source if connection is not None else item.source_id
        target = connection.target if connection is not None else item.target_id
        connection_type = connection.conn_type if connection is not None else item.connection_type
        if source is None or target is None or connection_type is None:
            continue
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
            )
        )
    connection_summaries.sort(key=lambda summary: summary.id)

    matrix_axes, matrix_drift = _matrix_axis_ids(
        executable_definition.presentation, retained_entities, read_access=read_access, registries=registries
    )
    warnings = tuple(projection.warnings) + drift_warnings(frozenset(matrix_drift))

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
        query_summary=(
            f"Selection derived from the viewpoint's concept scope: {render_query_summary(query)}"
            if scope_derived
            else render_query_summary(query)
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
