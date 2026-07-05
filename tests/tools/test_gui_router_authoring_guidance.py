"""Tests for GET /api/authoring-guidance (the REST wrapper around get_type_guidance).

Covers: entity_type/domain CSV filters, diagram_type guidance, pair-legality via target,
error passthrough for unknown types, and REST/domain-function parity.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.infrastructure.gui.routers.authoring_guidance import router as authoring_guidance_router
from src.infrastructure.write.artifact_write.type_guidance import get_type_guidance


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(authoring_guidance_router)
    return TestClient(app)


class TestEntityTypeAndDomainFilters:
    def test_entity_type_filter_matches_domain_function(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"entity_type": "requirement"})
        assert resp.status_code == 200
        assert resp.json() == get_type_guidance(filter=["requirement"])

    def test_domain_filter_matches_domain_function(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"domain": "motivation"})
        assert resp.status_code == 200
        assert resp.json() == get_type_guidance(filter=["motivation"])

    def test_no_params_returns_all_entity_types(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance")
        assert resp.status_code == 200
        body = resp.json()
        assert "entity_types" in body
        assert body["total"] > 0

    def test_csv_entity_type_filter(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"entity_type": "requirement,goal"})
        assert resp.status_code == 200
        names = {e["name"] for e in resp.json()["entity_types"]}
        assert names == {"requirement", "goal"}


class TestDiagramTypeGuidance:
    def test_diagram_type_returns_guidance_block(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"diagram_type": "activity"})
        assert resp.status_code == 200
        body = resp.json()
        assert "diagram_type_guidance" in body
        assert body["diagram_type_guidance"]["name"] == "activity"

    def test_unknown_diagram_type_returns_error(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"diagram_type": "not-a-type"})
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestPairLegality:
    def test_target_with_entity_type_returns_pair_guidance(self, client: TestClient) -> None:
        resp = client.get(
            "/api/authoring-guidance", params={"entity_type": "requirement", "target": "goal"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pair_guidance"]["source"] == "requirement"
        assert body["pair_guidance"]["target"] == "goal"

    def test_target_without_filter_returns_error(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"target": "goal"})
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestInternalTypesExcluded:
    """Internal entity types (promotion-created only, e.g. global-artifact-reference) must never
    be offered by any authoring-guidance surface — the create path rejects them outright."""

    def test_domain_guidance_never_lists_internal_types(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"domain": "common"})
        names = {e["name"] for e in resp.json()["entity_types"]}
        assert "global-artifact-reference" not in names
        assert "process" in names

    def test_unfiltered_guidance_never_lists_internal_types(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance")
        names = {e["name"] for e in resp.json()["entity_types"]}
        assert "global-artifact-reference" not in names

    def test_explicit_request_for_internal_type_is_not_honored(self, client: TestClient) -> None:
        resp = client.get("/api/authoring-guidance", params={"entity_type": "global-artifact-reference"})
        body = resp.json()
        listed = {e["name"] for e in body.get("entity_types", [])}
        assert "global-artifact-reference" not in listed
