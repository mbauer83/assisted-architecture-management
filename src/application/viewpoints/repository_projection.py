"""Repository-context projection (companion plan §6.1): evaluate a definition's query
against the whole repo-scope-admitted population and produce a ``ViewpointProjection``
containing only matches, all visible, styled. Feeds the WU-E7 execution result and the
table/matrix/exploration/diagram representations.
"""

from __future__ import annotations

from src.application.viewpoints.ports import RepositoryReadAccess
from src.domain.concept_scope import ConceptScope
from src.domain.module_types import EntityTypeName
from src.domain.viewpoint_condition_validation import RegistrySnapshot
from src.domain.viewpoint_criteria_evaluation import evaluate_entity_criteria
from src.domain.viewpoint_population_evaluation import resolve_neighbor_inclusions, select_connections
from src.domain.viewpoint_projection import Membership, ProjectedOccurrence, ViewpointProjection, drift_warnings
from src.domain.viewpoint_style_evaluation import evaluate_item_style
from src.domain.viewpoints import RepoScope, ViewpointDefinition


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
) -> ViewpointProjection:
    query = definition.query
    if query is None:
        return ViewpointProjection(target="repository", items=())

    drift: set[str] = set()
    primary_ids: set[str] = set()
    for entity_id in _population_entity_ids(read_access, query.repo_scope):
        entity = read_access.get_entity(entity_id)
        if entity is None:
            continue
        if scope_filter is not None and not scope_filter.admits_entity_type(
            EntityTypeName(entity.artifact_type), registries.entity_type_infos.get(entity.artifact_type)
        ):
            continue
        outcome = evaluate_entity_criteria(
            query.entity_criteria, entity, read_access=read_access, registries=registries
        )
        drift |= outcome.schema_drift
        if outcome.matched:
            primary_ids.add(entity_id)

    inclusion_result = resolve_neighbor_inclusions(
        frozenset(primary_ids), query.include_connected, read_access=read_access, registries=registries
    )
    drift |= inclusion_result.schema_drift
    included_ids = frozenset(primary_ids) | inclusion_result.expanded_ids

    connections_result = select_connections(
        included_ids, query.connections, read_access=read_access, registries=registries
    )
    drift |= connections_result.schema_drift

    items: list[ProjectedOccurrence] = []
    for entity_id in sorted(included_ids):
        entity = read_access.get_entity(entity_id)
        if entity is None:
            continue
        style, style_drift = evaluate_item_style(
            entity, "entity", definition.presentation, read_access=read_access, registries=registries
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
            connection, "connection", definition.presentation, read_access=read_access, registries=registries
        )
        drift |= style_drift
        items.append(
            ProjectedOccurrence(item_id=connection.artifact_id, item_kind="connection", state="visible", style=style)
        )

    return ViewpointProjection(target="repository", items=tuple(items), warnings=drift_warnings(frozenset(drift)))
