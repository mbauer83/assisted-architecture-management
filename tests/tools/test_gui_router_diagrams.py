"""Tests for the GUI diagrams router.

Covers: GET /api/diagrams, /api/diagram (404 + found), /api/entity-display-search,
/api/diagram-entity-types, /api/diagram-connection-types,
/api/diagram-context, /api/candidate-connections; helper _rendered_name.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from src.application.artifact_query import ArtifactRepository
from src.infrastructure.artifact_index import shared_artifact_index
from src.infrastructure.gui.routers import state as gui_state
from src.infrastructure.gui.routers.diagrams import router as diagrams_router

httpx = pytest.importorskip("httpx")


# ── helpers ───────────────────────────────────────────────────────────────────

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _entity_md(artifact_id: str, name: str) -> str:
    slug = artifact_id.split(".")[-1].replace("-", "_")
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: requirement
name: "{name}"
version: 0.1.0
status: active
last-updated: '2026-01-01'
---

<!-- §content -->

## {name}

Test entity for diagrams router.

## Properties

| Attribute | Value |
|---|---|
| (none) | (none) |

<!-- §display -->

### archimate

```yaml
domain: Motivation
element-type: Requirement
label: "{name}"
alias: REQ_{slug}
```
"""


def _diagram_md(artifact_id: str, name: str, diagram_type: str = "archimate-application") -> str:
    return f"""\
---
artifact-id: {artifact_id}
artifact-type: diagram
diagram-type: {diagram_type}
name: "{name}"
version: 0.1.0
status: draft
last-updated: '2026-01-01'
---
@startuml
component "Comp A" as compA
@enduml
"""


# ── IDs used across tests ─────────────────────────────────────────────────────

ENT_ID = "REQ@1000000020.EntDia.entity-for-diag"
DIAG_ID = "DIAG@1000000020.DiagTst.test-diagram"


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def populated_root(tmp_path: Path) -> Path:
    root = tmp_path / "engagements" / "ENG-DIAG" / "architecture-repository"
    model_dir = root / "model" / "motivation" / "requirement"
    diag_dir = root / "diagram-catalog" / "diagrams"
    _write(model_dir / f"{ENT_ID}.md", _entity_md(ENT_ID, "Entity For Diag"))
    _write(diag_dir / f"{DIAG_ID}.md", _diagram_md(DIAG_ID, "Test Diagram"))
    return root


@pytest.fixture()
def sync_client(populated_root: Path):
    from starlette.testclient import TestClient

    from src.infrastructure.app_bootstrap import (
        build_runtime_catalogs,
        get_module_registry,
        runtime_catalogs_dependency,
    )

    repo = ArtifactRepository(shared_artifact_index([populated_root]))
    gui_state.init_state(repo, populated_root, None)
    app = FastAPI()
    catalogs = build_runtime_catalogs(get_module_registry())
    app.dependency_overrides[runtime_catalogs_dependency] = lambda: catalogs
    app.include_router(diagrams_router)
    return TestClient(app)


# ── GET /api/diagrams ─────────────────────────────────────────────────────────


class TestListDiagrams:
    def test_returns_total_and_items(self, sync_client) -> None:
        r = sync_client.get("/api/diagrams")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "items" in data

    def test_lists_created_diagram(self, sync_client) -> None:
        r = sync_client.get("/api/diagrams")
        assert r.status_code == 200
        ids = [d["artifact_id"] for d in r.json()["items"]]
        assert DIAG_ID in ids

    def test_filter_by_type(self, sync_client) -> None:
        r = sync_client.get("/api/diagrams?diagram_type=archimate-application")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_filter_by_type_no_match(self, sync_client) -> None:
        r = sync_client.get("/api/diagrams?diagram_type=no-such-type")
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_filter_by_status(self, sync_client) -> None:
        r = sync_client.get("/api/diagrams?status=draft")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


# ── GET /api/diagram ──────────────────────────────────────────────────────────


class TestReadDiagram:
    def test_found(self, sync_client) -> None:
        r = sync_client.get(f"/api/diagram?id={DIAG_ID}")
        assert r.status_code == 200
        data = r.json()
        assert data["artifact_id"] == DIAG_ID

    def test_not_found_returns_404(self, sync_client) -> None:
        r = sync_client.get("/api/diagram?id=DIAG@9.ZZZ.no-such")
        assert r.status_code == 404

    def test_result_includes_diagram_fields(self, sync_client) -> None:
        r = sync_client.get(f"/api/diagram?id={DIAG_ID}")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "diagram_type" in data


# ── GET /api/entity-display-search ───────────────────────────────────────────


class TestEntityDisplaySearch:
    def test_empty_query_returns_items(self, sync_client) -> None:
        r = sync_client.get("/api/entity-display-search?q=")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_query_returns_matches(self, sync_client) -> None:
        r = sync_client.get("/api/entity-display-search?q=Entity")
        assert r.status_code == 200
        hits = r.json()
        assert isinstance(hits, list)

    def test_with_diagram_type_filter(self, sync_client) -> None:
        r = sync_client.get("/api/entity-display-search?q=&diagram_type=archimate-application")
        assert r.status_code == 200


# ── GET /api/diagram-types/{name}/entity-types ───────────────────────────────


class TestDiagramEntityTypes:
    def test_returns_items(self, sync_client) -> None:
        r = sync_client.get("/api/diagram-types/archimate-application/entity-types")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_unknown_type_returns_404(self, sync_client) -> None:
        r = sync_client.get("/api/diagram-types/no-such-type/entity-types")
        assert r.status_code == 404


# ── GET /api/diagram-types/{name}/connection-types ───────────────────────────


class TestDiagramConnectionTypes:
    def test_returns_items(self, sync_client) -> None:
        r = sync_client.get("/api/diagram-types/archimate-application/connection-types")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── GET /api/diagram-context ─────────────────────────────────────────────────


class TestDiagramContext:
    def test_not_found_returns_404(self, sync_client) -> None:
        r = sync_client.get("/api/diagram-context?id=DIAG@9.ZZZ.no-such")
        assert r.status_code == 404

    def test_found(self, sync_client) -> None:
        r = sync_client.get(f"/api/diagram-context?id={DIAG_ID}")
        assert r.status_code == 200


# ── GET /api/diagram-entity-discovery ────────────────────────────────────────


class TestDiagramEntityDiscovery:
    def test_returns_structure(self, sync_client) -> None:
        r = sync_client.get("/api/diagram-entity-discovery")
        assert r.status_code == 200
        data = r.json()
        assert "search_results" in data
        assert "candidate_connections" in data
        assert "suggested_entities" in data

    def test_with_query(self, sync_client) -> None:
        r = sync_client.get("/api/diagram-entity-discovery?q=Entity")
        assert r.status_code == 200

    def test_with_included_entity(self, sync_client) -> None:
        r = sync_client.get(
            f"/api/diagram-entity-discovery?included_entity_ids={ENT_ID}"
        )
        assert r.status_code == 200


# ── GET /api/diagram-refs ─────────────────────────────────────────────────────


class TestDiagramRefs:
    def test_no_shared_alias_returns_empty(self, sync_client) -> None:
        r = sync_client.get(f"/api/diagram-refs?source_id={ENT_ID}&target_id={ENT_ID}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_unknown_entities_returns_empty(self, sync_client) -> None:
        r = sync_client.get("/api/diagram-refs?source_id=REQ@9.ZZZ.x&target_id=REQ@9.ZZZ.y")
        assert r.status_code == 200
        assert r.json() == []
