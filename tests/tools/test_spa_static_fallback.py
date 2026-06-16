"""SPA history-fallback static serving: deep links resolve to index.html; assets/api do not."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from src.infrastructure.backend._spa_static import SPAStaticFiles


def _app(dist: Path) -> FastAPI:
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body><main>app shell</main></body></html>", encoding="utf-8")
    (dist / "assets" / "index-abc.js").write_text("console.log('app')", encoding="utf-8")
    app = FastAPI()

    @app.get("/api/stats")
    def stats() -> dict[str, int]:
        return {"n": 1}

    app.mount("/", SPAStaticFiles(directory=str(dist), html=True), name="static")
    return app


def test_root_serves_index(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<main>" in resp.text


def test_deep_link_falls_back_to_index(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    for route in ("/entities", "/entities/groups", "/documents", "/assurance/analyses"):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert "<main>" in resp.text, route


def test_real_asset_is_served_not_index(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    resp = client.get("/assets/index-abc.js")
    assert resp.status_code == 200
    assert "console.log" in resp.text


def test_missing_asset_still_404s(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    # A missing file with an extension must not be masked by index.html.
    assert client.get("/assets/missing.js").status_code == 404


def test_unknown_api_path_is_not_rewritten(tmp_path: Path) -> None:
    client = TestClient(_app(tmp_path))
    # api/ paths must 404 rather than fall back to the SPA shell.
    assert client.get("/api/does-not-exist").status_code == 404
