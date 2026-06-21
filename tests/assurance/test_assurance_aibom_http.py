"""Tests for the AI-BOM HTTP read endpoints (coverage / scan / export).

  - coverage: signals-gated (423 locked), exposure-filtered, reports unanchored
    components and anchored entity ids.
  - scan: un-gated; ranks public architecture model entities, excludes diagram-only
    nodes, honours the limit.
  - export: un-gated pure transform; emits CycloneDX 1.6 from caller-confirmed
    AI components; tolerates a malformed body.
  - Cache-Control: no-store on every response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI

pytest.importorskip("httpx")
from starlette.testclient import TestClient  # noqa: E402

_HTTP_CTX = "src.infrastructure.gui.routers._assurance_http.get_assurance_context"
_REPO = "src.infrastructure.gui.routers.state.maybe_get_repo"


class _FakeConnector:
    def __init__(self, components: list[dict], anchors: list[dict]) -> None:
        self._components = components
        self._anchors = anchors

    def list_bom_components(self, **_kwargs: Any) -> list[dict]:
        return self._components

    def list_anchors(self, **_kwargs: Any) -> list[dict]:
        return self._anchors


class _FakeContext:
    def __init__(self, *, unlocked: bool, components: list[dict], anchors: list[dict],
                 ceiling: str = "TLP:RED") -> None:
        self._unlocked = unlocked
        self.max_classification = ceiling
        self._connector = _FakeConnector(components, anchors)

    @property
    def connector(self) -> _FakeConnector:
        return self._connector

    def is_available(self) -> bool:
        return self._unlocked

    def signals_available(self) -> bool:
        return self._unlocked


@dataclass
class _FakeEntity:
    artifact_id: str
    name: str
    artifact_type: str
    content_text: str = ""
    host_diagram_id: str | None = None


class _FakeRepo:
    def __init__(self, entities: list[_FakeEntity]) -> None:
        self._entities = entities

    def list_entities(self, *, domain: str | None = None, **_kwargs: Any) -> list[_FakeEntity]:
        return self._entities


def _client(ctx: _FakeContext, monkeypatch: pytest.MonkeyPatch,
            repo: _FakeRepo | None = None) -> TestClient:
    from src.infrastructure.gui.routers.assurance import router

    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(_HTTP_CTX, lambda: ctx)
    if repo is not None:
        monkeypatch.setattr(_REPO, lambda: repo)
    return TestClient(app, raise_server_exceptions=False)


# ── Coverage ──────────────────────────────────────────────────────────────────

def test_coverage_locked_returns_423(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeContext(unlocked=False, components=[], anchors=[])
    r = _client(ctx, monkeypatch).get("/api/assurance/aibom/coverage")
    assert r.status_code == 423
    assert r.headers.get("cache-control") == "no-store"


def test_coverage_reports_unanchored_and_anchored(monkeypatch: pytest.MonkeyPatch) -> None:
    components = [
        {"name": "torch", "arch_entity_id": "APP@1"},
        {"name": "orphan-lib", "arch_entity_id": ""},
    ]
    anchors = [{"arch_entity_id": "APP@1"}]
    ctx = _FakeContext(unlocked=True, components=components, anchors=anchors)
    r = _client(ctx, monkeypatch).get("/api/assurance/aibom/coverage")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"
    body = r.json()
    assert body["total_bom_components"] == 2
    assert body["unanchored_components"] == 1
    assert body["anchor_mappings"] == 1
    assert body["anchored_entity_ids"] == ["APP@1"]
    assert body["unanchored"][0]["name"] == "orphan-lib"


# ── Scan ────────────────────────────────────────────────────────────────────

def test_scan_ranks_ai_entities_and_excludes_diagram_only(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRepo([
        _FakeEntity("APP@1", "Claude Inference Service", "application-component"),
        _FakeEntity("APP@2", "Billing Ledger", "application-component"),
        _FakeEntity("GSN@n", "LLM gateway node", "application-component", host_diagram_id="DGM@1"),
    ])
    ctx = _FakeContext(unlocked=True, components=[], anchors=[])
    r = _client(ctx, monkeypatch, repo=repo).get("/api/assurance/aibom/scan")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"
    body = r.json()
    ids = {c["entity_id"] for c in body["candidates"]}
    assert "APP@1" in ids  # AI name pattern matched
    assert "APP@2" not in ids  # no AI signal
    assert "GSN@n" not in ids  # diagram-only excluded despite AI name


def test_scan_honours_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRepo([
        _FakeEntity(f"APP@{i}", f"GPT model {i}", "application-component") for i in range(5)
    ])
    ctx = _FakeContext(unlocked=True, components=[], anchors=[])
    r = _client(ctx, monkeypatch, repo=repo).get("/api/assurance/aibom/scan?limit=2")
    assert r.json()["count"] == 2


def test_scan_no_repo_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeContext(unlocked=True, components=[], anchors=[])
    monkeypatch.setattr(_REPO, lambda: None)
    r = _client(ctx, monkeypatch).get("/api/assurance/aibom/scan")
    assert r.status_code == 200
    assert r.json()["candidates"] == []


# ── Roles ─────────────────────────────────────────────────────────────────────

def test_roles_match_canonical_backend_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infrastructure.assurance._aibom_exporter import AI_BOM_ROLES

    ctx = _FakeContext(unlocked=True, components=[], anchors=[])
    r = _client(ctx, monkeypatch).get("/api/assurance/aibom/roles")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"
    # The endpoint is the single source the GUI consumes — it must mirror the exporter.
    assert r.json()["roles"] == list(AI_BOM_ROLES)


# ── Export ────────────────────────────────────────────────────────────────────

def test_export_emits_cyclonedx_16(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeContext(unlocked=True, components=[], anchors=[])
    r = _client(ctx, monkeypatch).post("/api/assurance/aibom/export", json={
        "ai_components": [{"name": "claude-opus", "ai_role": "machine-learning-model"}],
        "notes": "draft ML-BOM",
    })
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"
    body = r.json()
    assert body["component_count"] == 1
    assert body["bom"]["bomFormat"] == "CycloneDX"
    assert body["bom"]["specVersion"] == "1.6"
    assert body["bom"]["components"][0]["name"] == "claude-opus"


def test_export_tolerates_malformed_body(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeContext(unlocked=True, components=[], anchors=[])
    r = _client(ctx, monkeypatch).post("/api/assurance/aibom/export", json={
        "ai_components": ["not-a-dict", 42],
    })
    assert r.status_code == 200
    assert r.json()["component_count"] == 0
