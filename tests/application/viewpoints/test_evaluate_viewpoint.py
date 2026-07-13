"""Tests for ``EvaluateViewpoint``: sorted ids/summaries, entity-denominated truncation, four counts, matrix axis
complement property, timeout, repo_scope, index revision, duration.
"""

from __future__ import annotations

import pytest

from src.application.viewpoints.evaluate_viewpoint import (
    UnknownViewpointSlugError,
    ViewpointExecutionRequest,
    ViewpointExecutionTimeoutError,
    evaluate_viewpoint,
    project_viewpoint_repository,
    resolve_viewpoint_definition,
)
from src.application.viewpoints.parameter_binding import ViewpointParameterError
from src.domain.viewpoint_bindings import QueryParameter
from src.domain.viewpoint_criteria import AttributeCondition, EntityCriteriaGroup, NeighborInclusion, ValueRef
from src.domain.viewpoints import (
    ExecutableViewpointQuery,
    PresentationSpec,
    StyleRule,
    ViewpointCatalog,
    ViewpointDefinition,
)
from tests.application.viewpoints._fixtures import REGISTRIES, Store, connection, entity

_DEFAULTS: dict[str, object] = dict(max_entities=500, default_limit=500, timeout_seconds=10.0, index_generation=None)


def _run(request: ViewpointExecutionRequest, *, catalog: ViewpointCatalog, read_access: Store, **overrides: object):
    kwargs = {**_DEFAULTS, **overrides}
    return evaluate_viewpoint(request, catalog=catalog, read_access=read_access, registries=REGISTRIES, **kwargs)


def _type_condition(value: str) -> AttributeCondition:
    return AttributeCondition(attribute="type", comparator="eq", value=ValueRef(literal=value))


def _definition(**kw: object) -> ViewpointDefinition:
    defaults: dict[str, object] = dict(slug="test-viewpoint", version=3, name="Test")
    defaults.update(kw)
    return ViewpointDefinition(**defaults)  # type: ignore[arg-type]


class TestSlugResolution:
    def test_unknown_slug_raises(self) -> None:
        with pytest.raises(UnknownViewpointSlugError):
            _run(ViewpointExecutionRequest(slug="missing"), catalog=ViewpointCatalog.empty(), read_access=Store())

    def test_known_slug_carries_identity(self) -> None:
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=Store())
        assert result.slug == "test-viewpoint"
        assert result.version == 3

    def test_ad_hoc_query_has_no_identity(self) -> None:
        request = ViewpointExecutionRequest(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        result = _run(request, catalog=ViewpointCatalog.empty(), read_access=Store())
        assert result.slug is None
        assert result.version is None

    def test_request_without_slug_or_query_raises(self) -> None:
        with pytest.raises(ValueError):
            _run(ViewpointExecutionRequest(), catalog=ViewpointCatalog.empty(), read_access=Store())


class TestParameters:
    def test_missing_unknown_and_mistyped_parameters_raise_typed_errors(self) -> None:
        query = ExecutableViewpointQuery(parameters=(QueryParameter("limit", "integer"),))
        for supplied, code in (
            (None, "missing-parameter"),
            ({"other": 1}, "unknown-parameter"),
            ({"limit": "1"}, "parameter-type-mismatch"),
        ):
            with pytest.raises(ViewpointParameterError) as error:
                _run(
                    ViewpointExecutionRequest(query=query, parameters=supplied),
                    catalog=ViewpointCatalog.empty(),
                    read_access=Store(),
                )
            assert error.value.code == code


class TestSummaries:
    def test_entity_and_connection_summaries(self) -> None:
        store = Store(
            entities={
                "ENT@A": entity(artifact_id="ENT@A", name="Alpha", group="core", specialization="custom-spec"),
                "ENT@B": entity(artifact_id="ENT@B", name="Beta"),
            },
            connections=[connection(artifact_id="CON@ab", source="ENT@A", target="ENT@B")],
        )
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store)

        assert result.entity_ids == ("ENT@A", "ENT@B")
        alpha = next(e for e in result.entities if e.id == "ENT@A")
        assert alpha.name == "Alpha"
        assert alpha.type == "application-component"
        assert alpha.specialization_slugs == ("custom-spec",)
        assert alpha.group == "core"
        assert alpha.membership == "primary"

        assert result.connection_ids == ("CON@ab",)
        link = result.connections[0]
        assert (link.type, link.source, link.target) == ("archimate-serving", "ENT@A", "ENT@B")


class TestTruncation:
    def _store_with_expanded_neighbors(self) -> Store:
        primary = entity(artifact_id="ENT@A", artifact_type="application-component")
        neighbor1 = entity(artifact_id="ENT@N1", artifact_type="process")
        neighbor2 = entity(artifact_id="ENT@N2", artifact_type="process")
        link1 = connection(artifact_id="CON@1", source="ENT@A", target="ENT@N1")
        link2 = connection(artifact_id="CON@2", source="ENT@A", target="ENT@N2")
        return Store(entities={"ENT@A": primary, "ENT@N1": neighbor1, "ENT@N2": neighbor2}, connections=[link1, link2])

    def _definition_with_inclusion(self) -> ViewpointDefinition:
        return _definition(
            query=ExecutableViewpointQuery(
                entity_criteria=EntityCriteriaGroup(children=(_type_condition("application-component"),)),
                include_connected=(NeighborInclusion(),),
            )
        )

    def test_expanded_dropped_before_primary(self) -> None:
        store = self._store_with_expanded_neighbors()
        catalog = ViewpointCatalog(entries=(self._definition_with_inclusion(),))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint", limit=2), catalog=catalog, read_access=store)
        assert result.entity_ids == ("ENT@A", "ENT@N1")
        assert result.returned_entity_count == 2
        assert result.total_entity_count == 3
        assert result.truncated is True
        assert result.entity_limit == 2

    def test_connections_refiltered_to_retained_entities(self) -> None:
        store = self._store_with_expanded_neighbors()
        catalog = ViewpointCatalog(entries=(self._definition_with_inclusion(),))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint", limit=2), catalog=catalog, read_access=store)
        assert result.total_connection_count == 2
        assert result.returned_connection_count == 1
        assert result.connection_ids == ("CON@1",)

    def test_limit_clamped_to_max_entities(self) -> None:
        store = self._store_with_expanded_neighbors()
        catalog = ViewpointCatalog(entries=(self._definition_with_inclusion(),))
        result = _run(
            ViewpointExecutionRequest(slug="test-viewpoint", limit=1000),
            catalog=catalog,
            read_access=store,
            max_entities=1,
            default_limit=1,
        )
        assert result.entity_limit == 1
        assert result.returned_entity_count == 1

    def test_untruncated_result_reports_false(self) -> None:
        store = Store(entities={"ENT@A": entity(artifact_id="ENT@A")})
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store)
        assert result.truncated is False
        assert result.total_entity_count == result.returned_entity_count == 1


class TestMatrixAxes:
    def _store(self) -> Store:
        return Store(
            entities={
                "ENT@A": entity(artifact_id="ENT@A", artifact_type="application-component"),
                "ENT@B": entity(artifact_id="ENT@B", artifact_type="process"),
                "ENT@C": entity(artifact_id="ENT@C", artifact_type="process", name="Neither"),
            }
        )

    def _matrix_definition(self) -> ViewpointDefinition:
        return _definition(
            query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()),
            presentation=PresentationSpec(
                representation="matrix",
                row_criteria=EntityCriteriaGroup(children=(_type_condition("application-component"),)),
                column_criteria=EntityCriteriaGroup(
                    children=(AttributeCondition(attribute="name", comparator="eq", value=ValueRef(literal="Beta")),)
                ),
            ),
        )

    def test_present_for_criteria_axes_matrix(self) -> None:
        store = self._store()
        store.entities["ENT@B"] = entity(artifact_id="ENT@B", artifact_type="process", name="Beta")
        catalog = ViewpointCatalog(entries=(self._matrix_definition(),))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store)
        assert result.matrix_axes is not None
        assert result.matrix_axes.row_entity_ids == ("ENT@A",)
        assert result.matrix_axes.column_entity_ids == ("ENT@B",)

    def test_complement_is_unrendered_entities(self) -> None:
        store = self._store()
        store.entities["ENT@B"] = entity(artifact_id="ENT@B", artifact_type="process", name="Beta")
        catalog = ViewpointCatalog(entries=(self._matrix_definition(),))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store)
        axis_union = set(result.matrix_axes.row_entity_ids) | set(result.matrix_axes.column_entity_ids)
        unrendered = set(result.entity_ids) - axis_union
        assert unrendered == {"ENT@C"}

    def test_absent_without_matrix_presentation(self) -> None:
        store = Store(entities={"ENT@A": entity(artifact_id="ENT@A")})
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store)
        assert result.matrix_axes is None


class TestRepoScope:
    def test_filters_entities_and_echoes_scope(self) -> None:
        store = Store(
            entities={
                "ENT@enterprise": entity(artifact_id="ENT@enterprise"),
                "ENT@engagement": entity(artifact_id="ENT@engagement"),
            },
            enterprise_ids=frozenset({"ENT@enterprise"}),
        )
        definition = _definition(
            query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup(), repo_scope="enterprise")
        )
        catalog = ViewpointCatalog(entries=(definition,))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store)
        assert result.entity_ids == ("ENT@enterprise",)
        assert result.repo_scope == "enterprise"


class TestIndexRevisionAndDuration:
    def test_index_generation_passthrough(self) -> None:
        store = Store(entities={"ENT@A": entity(artifact_id="ENT@A")})
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        result = _run(
            ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store, index_generation=42
        )
        assert result.index_generation == 42

    def test_duration_is_recorded(self) -> None:
        store = Store(entities={"ENT@A": entity(artifact_id="ENT@A")})
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        result = _run(ViewpointExecutionRequest(slug="test-viewpoint"), catalog=catalog, read_access=store)
        assert result.duration_ms >= 0.0


class TestTimeout:
    def test_negative_budget_always_raises_typed_error_no_partial_result(self) -> None:
        store = Store(entities={"ENT@A": entity(artifact_id="ENT@A")})
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        with pytest.raises(ViewpointExecutionTimeoutError) as excinfo:
            _run(
                ViewpointExecutionRequest(slug="test-viewpoint"),
                catalog=catalog,
                read_access=store,
                timeout_seconds=-1.0,
            )
        assert excinfo.value.timeout_seconds == -1.0


class TestResolveViewpointDefinition:
    """``resolve_viewpoint_definition`` — the resolver shared by ``evaluate_viewpoint`` and
    ``project_viewpoint_repository`` (a delegation regression: both must resolve slugs
    identically)."""

    def test_unknown_slug_raises(self) -> None:
        with pytest.raises(UnknownViewpointSlugError):
            resolve_viewpoint_definition("missing", None, catalog=ViewpointCatalog.empty())

    def test_known_slug_resolves_definition_and_identity(self) -> None:
        definition = _definition(query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()))
        catalog = ViewpointCatalog(entries=(definition,))
        resolved, slug, version = resolve_viewpoint_definition("test-viewpoint", None, catalog=catalog)
        assert resolved is definition
        assert (slug, version) == ("test-viewpoint", 3)

    def test_ad_hoc_query_has_no_identity(self) -> None:
        query = ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup())
        resolved, slug, version = resolve_viewpoint_definition(None, query, catalog=ViewpointCatalog.empty())
        assert resolved.query == query
        assert (slug, version) == (None, None)

    def test_neither_slug_nor_query_raises(self) -> None:
        with pytest.raises(ValueError):
            resolve_viewpoint_definition(None, None, catalog=ViewpointCatalog.empty())


class TestProjectViewpointRepository:
    """``project_viewpoint_repository`` — the styled, GUI-only sibling of the unstyled
    execution result (the data source for exploration/table/matrix/diagram
    representations)."""

    def test_delegates_to_project_repository_with_resolved_definition(self) -> None:
        store = Store(entities={"ENT@A": entity(artifact_id="ENT@A", group="core")})
        definition = _definition(
            query=ExecutableViewpointQuery(entity_criteria=EntityCriteriaGroup()),
            presentation=PresentationSpec(
                representation="exploration",
                styling_rules=(
                    StyleRule(capability="node_color", match_criteria=EntityCriteriaGroup(), value="positive"),
                ),
            ),
        )
        catalog = ViewpointCatalog(entries=(definition,))
        projection = project_viewpoint_repository(
            "test-viewpoint", None, catalog=catalog, read_access=store, registries=REGISTRIES
        )
        assert projection.target == "repository"
        item = next(i for i in projection.items if i.item_id == "ENT@A")
        assert item.style == {"node_color": "positive"}

    def test_unknown_slug_raises(self) -> None:
        with pytest.raises(UnknownViewpointSlugError):
            project_viewpoint_repository(
                "missing", None, catalog=ViewpointCatalog.empty(), read_access=Store(), registries=REGISTRIES
            )
