"""Tests for read-only viewpoint execution REST endpoints."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fastapi import FastAPI

from src.application.artifact_repository import ArtifactRepository
from src.application.viewpoints.evaluate_viewpoint import ViewpointExecutionTimeoutError
from src.domain.relationship_reachability import DerivationLimitError
from src.domain.viewpoint_binding_evaluation import BindingCardinalityError
from src.domain.viewpoint_criteria import EntityCriteriaGroup
from src.domain.viewpoints import (
    ExecutableViewpointQuery,
    PresentationSpec,
    StyleRule,
    ViewpointCatalog,
    ViewpointDefinition,
)
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.gui.routers import state as gui_state
from src.infrastructure.gui.routers.viewpoints import router as viewpoints_router

httpx = pytest.importorskip("httpx")

ENT_ID = "APC@1000000041.EntSch.viewpoint-exec-entity"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _entity_md(artifact_id: str, name: str) -> str:
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: application-component
name: "{name}"
version: 0.1.0
status: active
last-updated: '2026-01-01'
---

<!-- §content -->

## {name}

Test entity for viewpoint execution.

## Properties

| Attribute | Value |
|---|---|
| (none) | (none) |

<!-- §display -->

### archimate

```yaml
domain: Application
element-type: ApplicationComponent
label: "{name}"
alias: APC_test
```
"""


@pytest.fixture()
def populated_root(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-VPX" / "architecture-repository"
    _write(root / "model" / "application" / "application-component" / f"{ENT_ID}.md", _entity_md(ENT_ID, "Exec Entity"))
    (root / "diagram-catalog" / "diagrams").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def client(populated_root: Path):
    from starlette.testclient import TestClient

    from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry
    from src.infrastructure.gui.routers.viewpoints import fresh_viewpoints_runtime_catalogs_dependency

    repo = ArtifactRepository(shared_artifact_index([populated_root]))
    gui_state.init_state(repo, populated_root, None)
    catalogs = build_runtime_catalogs(get_module_registry())
    definition = ViewpointDefinition(
        slug="exec-test", version=1, name="Exec Test", query=ExecutableViewpointQuery(),
        presentation=PresentationSpec(
            representation="exploration",
            styling_rules=(StyleRule(capability="node_color", match_criteria=EntityCriteriaGroup(), value="positive"),),
        ),
    )
    catalogs = dataclasses.replace(catalogs, viewpoints=ViewpointCatalog(entries=(definition,)))

    app = FastAPI()
    app.dependency_overrides[fresh_viewpoints_runtime_catalogs_dependency] = lambda: catalogs
    app.include_router(viewpoints_router)
    return TestClient(app)


class TestSlugExecution:
    def test_executes_known_slug(self, client) -> None:
        resp = client.post("/api/viewpoints/execute", json={"slug": "exec-test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "exec-test"
        assert body["version"] == 1
        assert ENT_ID in body["entity_ids"]

    def test_unknown_slug_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute", json={"slug": "does-not-exist"})
        assert resp.status_code == 400


class TestAdHocExecution:
    def test_executes_inline_query(self, client) -> None:
        resp = client.post("/api/viewpoints/execute", json={"query": {}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] is None
        assert body["version"] is None
        assert ENT_ID in body["entity_ids"]

    def test_executes_parameterized_derived_traversal_query(self, client) -> None:
        response = client.post(
            "/api/viewpoints/execute",
            json={
                "parameters": {"entity_type": "application-component"},
                "query": {
                    "query_schema": 1,
                    "parameters": [{"name": "entity_type", "type": "string"}],
                    "entity_criteria": {
                        "kind": "group",
                        "conjunction": "and",
                        "children": [
                            {
                                "kind": "condition",
                                "attribute": "type",
                                "comparator": "eq",
                                "value": {"from": "parameter", "name": "entity_type"},
                            }
                        ],
                    },
                    "connections": {"enabled": True, "traversal": "derived", "max_hops": 2},
                },
            },
        )
        assert response.status_code == 200
        assert ENT_ID in response.json()["entity_ids"]


class TestRequestShape:
    def test_both_slug_and_query_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute", json={"slug": "exec-test", "query": {}})
        assert resp.status_code == 400

    def test_neither_slug_nor_query_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute", json={})
        assert resp.status_code == 400

    def test_response_shape_is_stable(self, client) -> None:
        resp = client.post("/api/viewpoints/execute", json={"slug": "exec-test"})
        body = resp.json()
        assert set(body.keys()) == {
            "slug", "version", "query_schema", "repo_scope", "executed_at", "index_generation",
            "entity_ids", "connection_ids", "entities", "connections",
            "total_entity_count", "returned_entity_count", "total_connection_count", "returned_connection_count",
            "truncated", "entity_limit", "matrix_axes", "warnings", "duration_ms", "query_summary",
        }
        # D15 boundary: the shared MCP/REST content stays unstyled — no style tokens leak in.
        assert all("style" not in entity for entity in body["entities"])


class TestParameters:
    def test_parameter_errors_have_one_payload_shape_on_every_execution_route(self, client) -> None:
        for endpoint in ("execute", "execute-projection", "execute-diagram"):
            response = client.post(f"/api/viewpoints/{endpoint}", json={"slug": "exec-test", "parameters": {"x": 1}})
            assert response.status_code == 400
            assert response.json()["detail"] == {
                "code": "unknown-parameter", "path": "parameters/x", "message": "unknown-parameter: x"
            }


class TestTypedExecutionErrors:
    @pytest.mark.parametrize(
        ("error", "status", "code"),
        [
            (BindingCardinalityError("binding 'one' requires one result, got 2"), 400, "binding-cardinality-violation"),
            (DerivationLimitError(1), 400, "derivation-limit"),
            (ViewpointExecutionTimeoutError(2, 1), 504, "execution-timeout"),
        ],
    )
    def test_returns_issue_payload_without_result(
        self, client, monkeypatch, error: Exception, status: int, code: str
    ) -> None:
        import src.infrastructure.gui.routers.viewpoints as viewpoints_module

        def _raise(*_args: object, **_kwargs: object) -> object:
            raise error

        monkeypatch.setattr(viewpoints_module, "evaluate_viewpoint", _raise)
        response = client.post("/api/viewpoints/execute", json={"slug": "exec-test"})
        assert response.status_code == status
        assert response.json()["detail"]["code"] == code
        assert response.json()["detail"]["path"] == "query"
        assert "entity_ids" not in response.json()


class TestExecuteProjection:
    """The GUI-only styled sibling of ``execute``."""

    def test_executes_known_slug_with_style(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-projection", json={"slug": "exec-test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] is True
        assert body["target"] == "repository"
        item = next(i for i in body["items"] if i["item_id"] == ENT_ID)
        assert item["style"] == {"node_color": "positive"}

    def test_executes_inline_query(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-projection", json={"query": {}})
        assert resp.status_code == 200
        body = resp.json()
        assert body["target"] == "repository"

    def test_unknown_slug_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-projection", json={"slug": "does-not-exist"})
        assert resp.status_code == 400

    def test_both_slug_and_query_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-projection", json={"slug": "exec-test", "query": {}})
        assert resp.status_code == 400

    def test_neither_slug_nor_query_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-projection", json={})
        assert resp.status_code == 400


class TestExecuteDiagram:
    """The GUI-only unpersisted ArchiMate diagram rendering route."""

    def test_renders_known_slug_to_svg(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-diagram", json={"slug": "exec-test"})
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"svg", "warnings"}
        assert body["svg"] is not None
        assert "<svg" in body["svg"]
        assert isinstance(body["warnings"], list)

    def test_renders_inline_query(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-diagram", json={"query": {}})
        assert resp.status_code == 200
        assert "<svg" in resp.json()["svg"]

    def test_unknown_slug_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-diagram", json={"slug": "does-not-exist"})
        assert resp.status_code == 400

    def test_both_slug_and_query_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-diagram", json={"slug": "exec-test", "query": {}})
        assert resp.status_code == 400

    def test_neither_slug_nor_query_is_400(self, client) -> None:
        resp = client.post("/api/viewpoints/execute-diagram", json={})
        assert resp.status_code == 400

    def test_no_write_queue_or_artifact_file_access(self, client, monkeypatch) -> None:
        """Regression: this endpoint must reach evaluation/rendering only, never the
        write-queue machinery real diagram creation uses."""
        import src.infrastructure.gui.routers.state as state_mod

        def _boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("write-queue must never be touched by execute-diagram")

        monkeypatch.setattr(state_mod, "get_write_deps", _boom, raising=True)
        resp = client.post("/api/viewpoints/execute-diagram", json={"slug": "exec-test"})
        assert resp.status_code == 200

    def test_derived_connections_reach_the_renderer(self, client, monkeypatch) -> None:
        """Regression: a derived connection's synthetic id must never be silently dropped
        by diagram-selection resolution — it should reach the renderer as a synthetic,
        renderer-only ConnectionRecord."""
        import src.infrastructure.gui.routers.viewpoints as viewpoints_mod
        from src.application.viewpoints.execution_result import (
            ConnectionItemSummary,
            EntityItemSummary,
            ViewpointExecutionResult,
        )

        other_id = "APC@1000000042.EntSch.viewpoint-exec-other"
        path_key = "SOME@1---OTHER@2@@archimate-serving@fwd"
        derived_id = f"derived::archimate-realization::{path_key}"
        result = ViewpointExecutionResult(
            slug=None, version=None, query_schema=1, repo_scope="both", executed_at="2026-01-01T00:00:00Z",
            index_generation=None, entity_ids=(ENT_ID, other_id), connection_ids=(derived_id,),
            entities=(
                EntityItemSummary(
                    id=ENT_ID, name="Exec Entity", type="application-component", specialization_slugs=(),
                    group="uncategorized", membership="primary",
                ),
                EntityItemSummary(
                    id=other_id, name="Other", type="application-component", specialization_slugs=(),
                    group="uncategorized", membership="expanded",
                ),
            ),
            connections=(
                ConnectionItemSummary(
                    id=derived_id, type="archimate-realization", source=ENT_ID, target=other_id, certainty="certain",
                    hops=2, via_connection_ids=("c1", "c2"),
                ),
            ),
            total_entity_count=2, returned_entity_count=2, total_connection_count=1, returned_connection_count=1,
            truncated=False, entity_limit=1000, matrix_axes=None, warnings=(), duration_ms=1.0, query_summary="t",
        )
        monkeypatch.setattr(viewpoints_mod, "evaluate_viewpoint", lambda *a, **kw: result)

        from src.domain.artifact_types import ConnectionRecord, EntityRecord

        captured: dict[str, list[ConnectionRecord]] = {}

        def _capture(
            name: str,
            entities: list[EntityRecord],
            connections: list[ConnectionRecord],
            *,
            diagram_type: str,
            repo_root: Path,
            label_attribute: str | None = None,
        ) -> str:
            captured["connections"] = connections
            return "@startuml\n@enduml\n"

        import src.infrastructure.rendering.diagram_builder as diagram_builder_mod

        monkeypatch.setattr(diagram_builder_mod, "generate_archimate_puml_body", _capture)
        monkeypatch.setattr(diagram_builder_mod, "render_puml_svg", lambda *a, **kw: ("<svg/>", []))

        resp = client.post("/api/viewpoints/execute-diagram", json={"query": {}})
        assert resp.status_code == 200
        connection_ids = {c.artifact_id for c in captured["connections"]}
        assert derived_id in connection_ids

    def test_slug_definitions_label_attribute_reaches_the_renderer(self, populated_root: Path, monkeypatch) -> None:
        """A definition's saved ``display_options.label_attribute`` must reach the
        renderer when executing by slug — an ad-hoc query has no saved presentation."""
        from starlette.testclient import TestClient

        from src.infrastructure.app_bootstrap import build_runtime_catalogs, get_module_registry

        repo = ArtifactRepository(shared_artifact_index([populated_root]))
        gui_state.init_state(repo, populated_root, None)
        catalogs = build_runtime_catalogs(get_module_registry())
        definition = ViewpointDefinition(
            slug="labelled", version=1, name="Labelled", query=ExecutableViewpointQuery(),
            presentation=PresentationSpec(representation="diagram", display_options={"label_attribute": "owner"}),
        )
        catalogs = dataclasses.replace(catalogs, viewpoints=ViewpointCatalog(entries=(definition,)))
        app = FastAPI()
        from src.infrastructure.gui.routers.viewpoints import fresh_viewpoints_runtime_catalogs_dependency

        app.dependency_overrides[fresh_viewpoints_runtime_catalogs_dependency] = lambda: catalogs
        app.include_router(viewpoints_router)
        labelled_client = TestClient(app)

        captured: dict[str, object] = {}
        import src.infrastructure.rendering.diagram_builder as diagram_builder_mod

        def _capture(*args: object, **kwargs: object) -> str:
            captured["label_attribute"] = kwargs.get("label_attribute")
            return "@startuml\n@enduml\n"

        monkeypatch.setattr(diagram_builder_mod, "generate_archimate_puml_body", _capture)
        monkeypatch.setattr(diagram_builder_mod, "render_puml_svg", lambda *a, **kw: ("<svg/>", []))

        resp = labelled_client.post("/api/viewpoints/execute-diagram", json={"slug": "labelled"})
        assert resp.status_code == 200
        assert captured["label_attribute"] == "owner"

    def test_ad_hoc_query_has_no_label_attribute(self, client, monkeypatch) -> None:
        captured: dict[str, object] = {}
        import src.infrastructure.rendering.diagram_builder as diagram_builder_mod

        def _capture(*args: object, **kwargs: object) -> str:
            captured["label_attribute"] = kwargs.get("label_attribute")
            return "@startuml\n@enduml\n"

        monkeypatch.setattr(diagram_builder_mod, "generate_archimate_puml_body", _capture)
        monkeypatch.setattr(diagram_builder_mod, "render_puml_svg", lambda *a, **kw: ("<svg/>", []))

        resp = client.post("/api/viewpoints/execute-diagram", json={"query": {}})
        assert resp.status_code == 200
        assert captured["label_attribute"] is None
