"""Repository-context projection: evaluate a definition's query
against the whole repo-scope-admitted population and produce a ``ViewpointProjection``
containing only matches, all visible, styled. Feeds the execution result and the
table/matrix/exploration/diagram representations.
"""

from __future__ import annotations

from typing import Literal

from src.application.viewpoints.ports import RepositoryReadAccess
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.concept_scope import ConceptScope
from src.domain.module_types import EntityTypeName
from src.domain.viewpoint_binding_evaluation import evaluate_derived_attributes
from src.domain.viewpoint_bindings import DerivedAttribute
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria_evaluation import evaluate_entity_criteria
from src.domain.viewpoint_evaluation_context import BindingEvaluationInput, EvaluationEnvironment
from src.domain.viewpoint_population_evaluation import resolve_neighbor_inclusions, select_connections
from src.domain.viewpoint_projection import (
    Membership,
    ProjectedOccurrence,
    ScaleLegendData,
    ViewpointProjection,
    derivation_truncation_warnings,
    drift_warnings,
)
from src.domain.viewpoint_style_evaluation import calculate_scale_bounds, evaluate_item_style
from src.domain.viewpoints import ExecutableViewpointQuery, RepoScope, ViewpointDefinition


def _population_entity_ids(read_access: RepositoryReadAccess, repo_scope: RepoScope) -> set[str]:
    if repo_scope == "enterprise":
        return read_access.enterprise_entity_ids()
    if repo_scope == "engagement":
        return read_access.engagement_entity_ids()
    return read_access.entity_ids()


def project_repository(
    definition: ViewpointDefinition,
    *,
    read_access: RepositoryReadAccess,
    registries: RegistrySnapshot,
    scope_filter: ConceptScope | None = None,
    environment: EvaluationEnvironment = EvaluationEnvironment(),
    candidate_entity_ids: frozenset[str] | None = None,
    deferred_derived: tuple[DerivedAttribute, ...] = (),
) -> ViewpointProjection:
    query = definition.query
    if query is None:
        return ViewpointProjection(target="repository", items=())

    drift: set[str] = set()
    primary_ids: set[str] = set()
    for entity_id in candidate_entity_ids or _population_entity_ids(read_access, query.repo_scope):
        entity = read_access.get_entity(entity_id)
        if entity is None:
            continue
        if scope_filter is not None and not scope_filter.admits_entity_type(
            EntityTypeName(entity.artifact_type), registries.entity_type_infos.get(entity.artifact_type)
        ):
            continue
        outcome = evaluate_entity_criteria(
            query.entity_criteria, entity, read_access=read_access, registries=registries, environment=environment
        )
        drift |= outcome.schema_drift
        if outcome.matched:
            primary_ids.add(entity_id)

    inclusion_result = resolve_neighbor_inclusions(
        frozenset(primary_ids),
        query.include_connected,
        read_access=read_access,
        registries=registries,
        environment=environment,
    )
    drift |= inclusion_result.schema_drift
    binding_ids = _result_included_binding_ids(query, environment)
    included_ids = frozenset(primary_ids) | inclusion_result.expanded_ids | binding_ids

    connections_result = select_connections(
        included_ids, query.connections, read_access=read_access, registries=registries, environment=environment
    )
    drift |= connections_result.schema_drift
    derivation_truncated = inclusion_result.derivation_truncated or connections_result.derivation_truncated

    entity_records = tuple(
        entity for entity_id in sorted(included_ids) if (entity := read_access.get_entity(entity_id)) is not None
    )
    if deferred_derived:
        # Presentation-only derived attributes (never referenced by a criteria tree, so
        # they had no bearing on which entities matched) are evaluated here, for the
        # retained population only — never for the full scoped candidate set, which
        # `_prepare_query_environment` already established these are exempt from.
        deferred_input = BindingEvaluationInput(
            tuple(entity.artifact_id for entity in entity_records), (), read_access, registries
        )
        environment = evaluate_derived_attributes(
            deferred_derived,
            tuple(entity.artifact_id for entity in entity_records),
            input=deferred_input,
            environment=environment,
        )
    styled_items_list: list[tuple[EntityRecord | ConnectionRecord, Literal["entity", "connection"]]] = []
    for entity in entity_records:
        styled_items_list.append((entity, "entity"))
    for connection in connections_result.connections:
        styled_items_list.append((connection, "connection"))
    styled_items = tuple(styled_items_list)
    scale_bounds, scale_legends, scale_drift = calculate_scale_bounds(
        definition.presentation,
        styled_items,
        registries=registries,
        environment=environment,
    )
    drift |= scale_drift

    items: list[ProjectedOccurrence] = []
    for entity in entity_records:
        entity_id = entity.artifact_id
        style, style_drift = evaluate_item_style(
            entity,
            "entity",
            definition.presentation,
            read_access=read_access,
            registries=registries,
            environment=environment,
            scale_bounds=scale_bounds,
        )
        drift |= style_drift
        membership: Membership = "primary" if entity_id in primary_ids else "expanded"
        items.append(
            ProjectedOccurrence(
                item_id=entity_id, item_kind="entity", state="visible", membership=membership, style=style
            )
        )
    for connection in connections_result.connections:
        style, style_drift = evaluate_item_style(
            connection,
            "connection",
            definition.presentation,
            read_access=read_access,
            registries=registries,
            environment=environment,
            scale_bounds=scale_bounds,
        )
        drift |= style_drift
        items.append(
            ProjectedOccurrence(
                item_id=connection.artifact_id,
                item_kind="connection",
                state="visible",
                style=style,
                connection_type=connection.conn_type,
                source_id=connection.source,
                target_id=connection.target,
            )
        )
    for connection in connections_result.derived_connections:
        items.append(
            ProjectedOccurrence(
                item_id=connection.artifact_id,
                item_kind="connection",
                state="visible",
                connection_type=connection.connection_type,
                source_id=connection.source_id,
                target_id=connection.target_id,
                certainty=connection.certainty,
                hops=connection.hops,
                via_connection_ids=connection.via_connection_ids,
            )
        )

    return ViewpointProjection(
        target="repository",
        items=tuple(items),
        warnings=drift_warnings(frozenset(drift)) + derivation_truncation_warnings(derivation_truncated),
        scale_legends=tuple(
            ScaleLegendData(
                capability=legend.capability,
                attribute=legend.attribute,
                minimum=legend.minimum,
                maximum=legend.maximum,
                tokens=legend.tokens,
            )
            for legend in scale_legends
        ),
    )


def _result_included_binding_ids(query: ExecutableViewpointQuery, environment: EvaluationEnvironment) -> frozenset[str]:
    ids: set[str] = set()
    for binding in query.bindings:
        if not binding.include_in_result:
            continue
        value = environment.bindings.get(binding.name)
        values = value if isinstance(value, tuple) else (value,)
        ids |= {item.artifact_id for item in values if isinstance(item, EntityRecord)}
    return frozenset(ids)
