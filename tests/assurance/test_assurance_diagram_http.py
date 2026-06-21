"""HTTP tests for WU-G6 derived diagram and baselines endpoints.

Covers:
  - GET /api/assurance/diagrams → list of available diagram IDs
  - GET /api/assurance/diagrams/{id}/rendered → PUML + (optional) SVG
  - GET /api/assurance/diagrams/unknown/rendered → 404
  - GET /api/assurance/baselines → list (empty or populated)
  - 423 on all three when store is locked
  - Cache-Control: no-store on all responses
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI

httpx = pytest.importorskip("httpx")
from starlette.testclient import TestClient  # noqa: E402

# ── Minimal fakes ─────────────────────────────────────────────────────────────

class _FakeStore:
    def __init__(self, *, unlocked: bool = True) -> None:
        self._unlocked = unlocked
        self._nodes: list[dict[str, Any]] = []
        self._edges: list[dict[str, Any]] = []

    def is_unlocked(self) -> bool:
        return self._unlocked

    def list_nodes(self, **_kw: object) -> list[dict[str, Any]]:
        return list(self._nodes)

    def list_edges(self, **_kw: object) -> list[dict[str, Any]]:
        return list(self._edges)

    def search_nodes(self, q: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return []

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return None

    def list_arch_refs(self, **_kw: object) -> list[dict[str, Any]]:
        return []

    def stats(self) -> dict[str, Any]:
        return {}


class _FakeArchive:
    def __init__(self, baselines: list[dict[str, Any]] | None = None) -> None:
        self._baselines = baselines or []

    def list_baselines(self) -> list[dict[str, Any]]:
        return list(self._baselines)


class _FakeConnector:
    def list_bom_components(self, **_kw: object) -> list[Any]:
        return []

    def list_vulnerabilities(self, **_kw: object) -> list[Any]:
        return []

    def get_stats(self) -> dict[str, Any]:
        return {}


class _FakeContext:
    def __init__(self, store: _FakeStore, archive: _FakeArchive | None = None) -> None:
        self._store = store
        self._archive = archive or _FakeArchive()
        self._connector = _FakeConnector()
        self.max_classification = "TLP:RED"

    @property
    def store(self) -> _FakeStore:
        return self._store

    @property
    def archive(self) -> _FakeArchive:
        return self._archive

    @property
    def connector(self) -> _FakeConnector:
        return self._connector

    def is_available(self) -> bool:
        return self._store.is_unlocked()

    def signals_available(self) -> bool:
        return self._store.is_unlocked()

    def locked_response(self) -> dict[str, Any]:
        return {"error": "assurance_store_locked"}

    def signals_locked_response(self) -> dict[str, Any]:
        return {"error": "signals_store_locked"}

    def not_found_response(self, node_id: str) -> dict[str, Any]:
        return {"error": "not_found", "node_id": node_id}


_CTX = "src.infrastructure.gui.routers._assurance_read.get_assurance_context"


def _make_client(ctx: _FakeContext) -> TestClient:
    from src.infrastructure.gui.routers.assurance import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    patch(_CTX, return_value=ctx).start()
    return client


# ── GET /api/assurance/diagrams ────────────────────────────────────────────────

def test_list_diagrams_returns_available_ids() -> None:
    ctx = _FakeContext(_FakeStore())
    client = _make_client(ctx)
    r = client.get("/api/assurance/diagrams")
    assert r.status_code == 200
    ids = {d["diagram_id"] for d in r.json()["diagrams"]}
    assert "control-structure" in ids
    assert "uca-matrix" in ids
    assert r.headers.get("cache-control") == "no-store"


def test_list_diagrams_locked_returns_423() -> None:
    ctx = _FakeContext(_FakeStore(unlocked=False))
    client = _make_client(ctx)
    r = client.get("/api/assurance/diagrams")
    assert r.status_code == 423
    assert r.headers.get("cache-control") == "no-store"


# ── GET /api/assurance/diagrams/{id}/rendered ─────────────────────────────────

def test_rendered_control_structure_returns_puml() -> None:
    ctx = _FakeContext(_FakeStore())
    client = _make_client(ctx)
    r = client.get("/api/assurance/diagrams/control-structure/rendered")
    assert r.status_code == 200
    body = r.json()
    assert body["diagram_id"] == "control-structure"
    assert "@startuml" in body["puml"]
    assert "@enduml" in body["puml"]
    assert r.headers.get("cache-control") == "no-store"


def test_rendered_uca_matrix_returns_puml() -> None:
    ctx = _FakeContext(_FakeStore())
    client = _make_client(ctx)
    r = client.get("/api/assurance/diagrams/uca-matrix/rendered")
    assert r.status_code == 200
    assert "@startuml" in r.json()["puml"]


def test_rendered_unknown_id_returns_404() -> None:
    ctx = _FakeContext(_FakeStore())
    client = _make_client(ctx)
    r = client.get("/api/assurance/diagrams/no-such-diagram/rendered")
    assert r.status_code == 404
    assert "unknown_diagram_id" in r.json()["error"]


def test_rendered_locked_returns_423() -> None:
    ctx = _FakeContext(_FakeStore(unlocked=False))
    client = _make_client(ctx)
    r = client.get("/api/assurance/diagrams/control-structure/rendered")
    assert r.status_code == 423


def test_rendered_control_structure_svg_null_when_no_plantuml(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeContext(_FakeStore())
    client = _make_client(ctx)
    monkeypatch.setattr(
        "src.infrastructure.gui.routers._assurance_read.render_puml_svg",
        lambda *a, **kw: (None, ["plantuml unavailable"]),
        raising=False,
    )
    r = client.get("/api/assurance/diagrams/control-structure/rendered")
    assert r.status_code == 200
    assert r.json()["svg"] is None


# ── GET /api/assurance/baselines ──────────────────────────────────────────────

def test_baselines_empty_store() -> None:
    ctx = _FakeContext(_FakeStore())
    client = _make_client(ctx)
    r = client.get("/api/assurance/baselines")
    assert r.status_code == 200
    assert r.json()["baselines"] == []
    assert r.json()["count"] == 0
    assert r.headers.get("cache-control") == "no-store"


def test_baselines_populated() -> None:
    baseline = {"sealed_at": "2026-06-20T12:00:00Z", "notes": "Before CAST-001", "head_hash": "abc123"}
    ctx = _FakeContext(_FakeStore(), archive=_FakeArchive(baselines=[baseline]))
    client = _make_client(ctx)
    r = client.get("/api/assurance/baselines")
    assert r.status_code == 200
    assert r.json()["count"] == 1
    assert r.json()["baselines"][0]["head_hash"] == "abc123"


def test_baselines_locked_returns_423() -> None:
    ctx = _FakeContext(_FakeStore(unlocked=False))
    client = _make_client(ctx)
    r = client.get("/api/assurance/baselines")
    assert r.status_code == 423
