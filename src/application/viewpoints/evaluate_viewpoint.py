"""``EvaluateViewpoint`` (companion plan §7): the one use case that resolves a viewpoint
(by slug, or an ad-hoc query) and executes it against the live model, wrapping the WU-E15
repository projection in the §7.1 execution result. REST and both MCP tools (WU-E7a) call
this — none re-implement evaluation.
"""

from __future__ import annotations

import logging
import time
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
from src.domain.artifact_types import EntityRecord
from src.domain.clock import utc_now_iso
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

_NO_QUERY_SUMMARY = "This viewpoint defines a scope only — it has no executable query."

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
    with no identity/provenance. ``limit`` is entity-denominated (§7.1); ``None`` defers to
    the caller-supplied default."""

    slug: str | None = None
    query: ExecutableViewpointQuery | None = None
    limit: int | None = None


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
    """GUI-only repository-context ``ViewpointProjection`` (companion plan §6.1) carrying
    per-item style tokens — the styled sibling of ``evaluate_viewpoint``'s deliberately
    unstyled §7.1 execution result. Never called by MCP: the D15 boundary (§2) keeps
    style tokens out of the MCP/REST-shared execution-result contract, so this is a
    separate GUI-only entry point over the same ``project_repository`` service the
    execution result already uses internally.
    """
    definition, _, _ = resolve_viewpoint_definition(slug, query, catalog=catalog)
    return project_repository(definition, read_access=read_access, registries=registries)


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

    requested_limit = request.limit if request.limit is not None else default_limit
    limit = max(0, min(requested_limit, max_entities))

    projection = project_repository(definition, read_access=read_access, registries=registries)

    primary_ids = sorted(
        item.item_id for item in projection.items if item.item_kind == "entity" and item.membership == "primary"
    )
    expanded_ids = sorted(
        item.item_id for item in projection.items if item.item_kind == "entity" and item.membership == "expanded"
    )
    total_entity_count = len(primary_ids) + len(expanded_ids)
    # Primary-before-expanded retention order (§7.1): context neighbors drop first.
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
        if connection is None or connection.source not in retained_id_set or connection.target not in retained_id_set:
            continue
        connection_summaries.append(
            ConnectionItemSummary(
                id=connection.artifact_id, type=connection.conn_type, source=connection.source, target=connection.target
            )
        )
    connection_summaries.sort(key=lambda summary: summary.id)

    matrix_axes, matrix_drift = _matrix_axis_ids(
        definition.presentation, retained_entities, read_access=read_access, registries=registries
    )
    warnings = tuple(projection.warnings) + drift_warnings(frozenset(matrix_drift))

    query = definition.query
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
        query_summary=render_query_summary(query) if query is not None else _NO_QUERY_SUMMARY,
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
