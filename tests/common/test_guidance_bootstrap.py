"""Tests for app_bootstrap's guidance-overlay wiring (WU-B2).

Covers: tier precedence (enterprise < engagement) via the real repo-root resolution seam,
and the "no workspace configured" fallback that keeps current (pre-guidance) behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure import app_bootstrap
from src.ontologies.archimate_4._loader import _PACKAGE_DIR, load_archimate_4_module


def _write_cache(repo_root: Path, text: str) -> None:
    cache_dir = repo_root / ".arch-repo" / "guidance-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "archimate-4.guidance.yaml").write_text(text, encoding="utf-8")


class TestLoadArchimateGuidanceOverlay:
    def test_no_workspace_configured_returns_empty_overlay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_bootstrap, "resolve_workspace_repo_roots", lambda: None)
        overlay = app_bootstrap._load_archimate_guidance_overlay()
        assert overlay.is_empty()

    def test_engagement_cache_wins_over_enterprise_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        engagement_root = tmp_path / "engagement"
        enterprise_root = tmp_path / "enterprise"
        _write_cache(
            enterprise_root,
            """
            meta_ontologies:
              archimate-4:
                entity_types:
                  stakeholder: {create_when: "enterprise", never_create_when: "n"}
            """,
        )
        _write_cache(
            engagement_root,
            """
            meta_ontologies:
              archimate-4:
                entity_types:
                  stakeholder: {create_when: "engagement", never_create_when: "n"}
            """,
        )
        monkeypatch.setattr(
            app_bootstrap, "resolve_workspace_repo_roots", lambda: (engagement_root, enterprise_root)
        )

        overlay = app_bootstrap._load_archimate_guidance_overlay()
        module = load_archimate_4_module(_PACKAGE_DIR, guidance=overlay)

        assert module.entity_types["stakeholder"].create_when == "engagement"

    def test_absent_caches_matches_current_behavior(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Real repo roots but no guidance-cache files yet — module ships its own text."""
        engagement_root = tmp_path / "engagement"
        enterprise_root = tmp_path / "enterprise"
        monkeypatch.setattr(
            app_bootstrap, "resolve_workspace_repo_roots", lambda: (engagement_root, enterprise_root)
        )

        overlay = app_bootstrap._load_archimate_guidance_overlay()
        assert overlay.is_empty()

        with_overlay = load_archimate_4_module(_PACKAGE_DIR, guidance=overlay)
        without_overlay = load_archimate_4_module(_PACKAGE_DIR)
        assert (
            with_overlay.entity_types["stakeholder"].create_when
            == without_overlay.entity_types["stakeholder"].create_when
        )
