"""Tests for POST /api/viewpoints/execute (companion plan §7): read-only REST wrapper
around ``evaluate_viewpoint`` — endpoint shape stability, slug and ad-hoc execution,
and the "no write-queue access" boundary.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fastapi import FastAPI

from src.application.artifact_repository import ArtifactRepository
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

    from src.infrastructure.app_bootstrap import (
        build_runtime_catalogs,
        get_module_registry,
        runtime_catalogs_dependency,
    )

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
    app.dependency_overrides[runtime_catalogs_dependency] = lambda: catalogs
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


class TestExecuteProjection:
    """POST /api/viewpoints/execute-projection: the GUI-only styled sibling of
    ``execute`` (companion plan §6.1) — never called by MCP."""

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
    """POST /api/viewpoints/execute-diagram: the GUI-only ad-hoc ArchiMate-notation
    rendering behind the `diagram` execution representation (companion plan §5.1) —
    never persisted, no `ViewpointApplication`, no write-queue/artifact-file access."""

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
