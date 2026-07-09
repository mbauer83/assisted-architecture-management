from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

from src.infrastructure.cli import arch_import_guidance as cli
from src.infrastructure.guidance_import import GuidanceImportError

_SYNTHETIC_SOURCE = """
guidance_format: 1
meta_ontologies:
  archimate-4:
    entity_types:
      stakeholder:
        create_when: "TEST-ONLY create_when text for stakeholder"
        never_create_when: "TEST-ONLY never_create_when text for stakeholder"
      not-a-real-type:
        create_when: "should be dropped — unknown type"
        never_create_when: ""
"""


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "source.guidance.yaml"
    path.write_text(_SYNTHETIC_SOURCE, encoding="utf-8")
    return path


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    engagement_root = tmp_path / "engagement"
    enterprise_root = tmp_path / "enterprise"
    engagement_root.mkdir()
    enterprise_root.mkdir()
    monkeypatch.setattr(cli, "resolve_workspace_repo_roots", lambda: (engagement_root, enterprise_root))
    return engagement_root, enterprise_root


class TestRunImportHappyPath:
    def test_writes_cache_and_sidecar_for_engagement_scope(
        self, source_file: Path, workspace: tuple[Path, Path]
    ) -> None:
        engagement_root, enterprise_root = workspace
        summaries = cli.run_import(
            source=str(source_file), module=None, repo_scope="engagement", dry_run=False, strict=False,
            allow_http=False,
        )
        assert len(summaries) == 1
        assert summaries[0].matched_keys == ("entity_types.stakeholder",)
        assert summaries[0].unmatched_keys == ("entity_types.not-a-real-type",)

        cache_file = engagement_root / ".arch-repo" / "guidance-cache" / "archimate-4.guidance.yaml"
        assert cache_file.is_file()
        cached = yaml.safe_load(cache_file.read_text(encoding="utf-8"))
        assert cached["meta_ontologies"]["archimate-4"]["entity_types"]["stakeholder"]["create_when"] == (
            "TEST-ONLY create_when text for stakeholder"
        )
        assert "not-a-real-type" not in cached["meta_ontologies"]["archimate-4"].get("entity_types", {})

        # nothing written to the enterprise root
        assert not (enterprise_root / ".arch-repo").exists()

    def test_repo_scope_enterprise_targets_enterprise_root(
        self, source_file: Path, workspace: tuple[Path, Path]
    ) -> None:
        engagement_root, enterprise_root = workspace
        cli.run_import(
            source=str(source_file), module=None, repo_scope="enterprise", dry_run=False, strict=False,
            allow_http=False,
        )
        assert (enterprise_root / ".arch-repo" / "guidance-cache" / "archimate-4.guidance.yaml").is_file()
        assert not (engagement_root / ".arch-repo").exists()

    def test_dry_run_writes_nothing(self, source_file: Path, workspace: tuple[Path, Path]) -> None:
        engagement_root, enterprise_root = workspace
        summaries = cli.run_import(
            source=str(source_file), module=None, repo_scope="engagement", dry_run=True, strict=False,
            allow_http=False,
        )
        assert summaries[0].matched_keys == ("entity_types.stakeholder",)
        assert not (engagement_root / ".arch-repo").exists()

    def test_module_filter_restricts_to_one_alias(self, tmp_path: Path, workspace: tuple[Path, Path]) -> None:
        source = tmp_path / "multi.guidance.yaml"
        source.write_text(
            """
            guidance_format: 1
            meta_ontologies:
              archimate-4:
                entity_types:
                  stakeholder: {create_when: "a4", never_create_when: ""}
              sysml-v2:
                entity_types:
                  part-definition: {create_when: "sysml", never_create_when: ""}
            """,
            encoding="utf-8",
        )
        summaries = cli.run_import(
            source=str(source), module="archimate-4", repo_scope="engagement", dry_run=False, strict=False,
            allow_http=False,
        )
        assert [s.alias for s in summaries] == ["archimate-4"]

    def test_strict_mode_raises_on_unknown_key(self, source_file: Path, workspace: tuple[Path, Path]) -> None:
        with pytest.raises(GuidanceImportError, match="not-a-real-type"):
            cli.run_import(
                source=str(source_file), module=None, repo_scope="engagement", dry_run=False, strict=True,
                allow_http=False,
            )


class TestProvenanceSidecar:
    def test_sidecar_content(self, source_file: Path, workspace: tuple[Path, Path]) -> None:
        engagement_root, _ = workspace
        cli.run_import(
            source=str(source_file), module=None, repo_scope="engagement", dry_run=False, strict=False,
            allow_http=False,
        )
        sidecar_file = engagement_root / ".arch-repo" / "guidance-cache" / "archimate-4.guidance.meta.yaml"
        assert sidecar_file.is_file()
        sidecar = yaml.safe_load(sidecar_file.read_text(encoding="utf-8"))
        assert sidecar["source"] == str(source_file)
        assert isinstance(sidecar["sha256"], str) and len(sidecar["sha256"]) == 64
        assert sidecar["guidance_format"] == 1
        assert sidecar["matched_count"] == 1
        assert sidecar["unmatched_count"] == 1
        assert sidecar["unmatched_keys"] == ["entity_types.not-a-real-type"]
        assert "imported_at" in sidecar


class TestRestartEquivalentRebootstrap:
    def test_imported_guidance_surfaces_after_rebootstrap(
        self, source_file: Path, workspace: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Import writes the cache; a fresh app_bootstrap import (restart-equivalent) must
        pick it up and surface it through get_type_guidance."""
        engagement_root, enterprise_root = workspace
        cli.run_import(
            source=str(source_file), module=None, repo_scope="engagement", dry_run=False, strict=False,
            allow_http=False,
        )

        from src.config import workspace_paths
        from src.infrastructure import app_bootstrap
        from src.infrastructure.write.artifact_write import type_guidance

        # Patch the source module's attribute, not app_bootstrap's imported name — reload()
        # re-executes app_bootstrap's `from ... import resolve_workspace_repo_roots` line,
        # which would otherwise re-bind past a patch applied directly to app_bootstrap.
        monkeypatch.setattr(
            workspace_paths, "resolve_workspace_repo_roots", lambda: (engagement_root, enterprise_root)
        )
        try:
            importlib.reload(app_bootstrap)
            app_bootstrap.get_module_registry.cache_clear()
            type_guidance._registry.cache_clear()

            result = type_guidance.get_type_guidance(filter=["stakeholder"])
            entries = result["entity_types"]
            assert isinstance(entries, list)
            entry = next(e for e in entries if e["name"] == "stakeholder")
            assert entry["create_when"] == "TEST-ONLY create_when text for stakeholder"
        finally:
            monkeypatch.undo()
            importlib.reload(app_bootstrap)
            app_bootstrap.get_module_registry.cache_clear()
            type_guidance._registry.cache_clear()
