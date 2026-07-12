from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

import src.infrastructure.guidance_cache as guidance_cache_module
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


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / ".config" / "arch-repo"
    monkeypatch.setattr(guidance_cache_module, "_CONFIG_DIR", config_dir)
    return config_dir / guidance_cache_module.GUIDANCE_CACHE_DIRNAME


class TestRunImportHappyPath:
    def test_writes_cache_and_sidecar(self, source_file: Path, _isolated_cache_dir: Path) -> None:
        summaries = cli.run_import(source=str(source_file), module=None, dry_run=False, strict=False, allow_http=False)
        assert len(summaries) == 1
        assert summaries[0].matched_keys == ("entity_types.stakeholder",)
        assert summaries[0].unmatched_keys == ("entity_types.not-a-real-type",)

        cache_file = _isolated_cache_dir / "archimate-4.guidance.yaml"
        assert cache_file.is_file()
        cached = yaml.safe_load(cache_file.read_text(encoding="utf-8"))
        assert cached["meta_ontologies"]["archimate-4"]["entity_types"]["stakeholder"]["create_when"] == (
            "TEST-ONLY create_when text for stakeholder"
        )
        assert "not-a-real-type" not in cached["meta_ontologies"]["archimate-4"].get("entity_types", {})

    def test_dry_run_writes_nothing(self, source_file: Path, _isolated_cache_dir: Path) -> None:
        summaries = cli.run_import(source=str(source_file), module=None, dry_run=True, strict=False, allow_http=False)
        assert summaries[0].matched_keys == ("entity_types.stakeholder",)
        assert not _isolated_cache_dir.exists()

    def test_module_filter_restricts_to_one_alias(self, tmp_path: Path, _isolated_cache_dir: Path) -> None:
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
            source=str(source), module="archimate-4", dry_run=False, strict=False, allow_http=False
        )
        assert [s.alias for s in summaries] == ["archimate-4"]

    def test_strict_mode_raises_on_unknown_key(self, source_file: Path, _isolated_cache_dir: Path) -> None:
        with pytest.raises(GuidanceImportError, match="not-a-real-type"):
            cli.run_import(source=str(source_file), module=None, dry_run=False, strict=True, allow_http=False)


class TestProvenanceSidecar:
    def test_sidecar_content(self, source_file: Path, _isolated_cache_dir: Path) -> None:
        cli.run_import(source=str(source_file), module=None, dry_run=False, strict=False, allow_http=False)
        sidecar_file = _isolated_cache_dir / "archimate-4.guidance.meta.yaml"
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
        self, source_file: Path, _isolated_cache_dir: Path
    ) -> None:
        """Import writes the cache; a fresh app_bootstrap import (restart-equivalent) must
        pick it up and surface it through get_type_guidance — regardless of which
        engagement/enterprise repo happens to be active, since guidance is deployment-level."""
        cli.run_import(source=str(source_file), module=None, dry_run=False, strict=False, allow_http=False)

        from src.infrastructure import app_bootstrap
        from src.infrastructure.write.artifact_write import type_guidance

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
            importlib.reload(app_bootstrap)
            app_bootstrap.get_module_registry.cache_clear()
            type_guidance._registry.cache_clear()
