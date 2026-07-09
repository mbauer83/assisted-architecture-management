from __future__ import annotations

from pathlib import Path

from src.domain.guidance import GuidanceKey
from src.infrastructure.guidance_cache import (
    ensure_guidance_cache_gitignored,
    guidance_cache_root,
    load_guidance_cache_file,
    load_guidance_overlay_for_repos,
)

_ALIAS = "archimate-4"


def _write_cache(repo_root: Path, text: str) -> None:
    cache_dir = guidance_cache_root(repo_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{_ALIAS}.guidance.yaml").write_text(text, encoding="utf-8")


def _key(type_name: str) -> GuidanceKey:
    return GuidanceKey(module_alias=_ALIAS, concept_kind="entity", type_name=type_name)


class TestLoadGuidanceCacheFile:
    def test_absent_file_returns_empty_overlay(self, tmp_path: Path) -> None:
        overlay = load_guidance_cache_file(tmp_path, _ALIAS)
        assert overlay.is_empty()

    def test_present_file_parses_into_overlay(self, tmp_path: Path) -> None:
        _write_cache(
            tmp_path,
            """
            meta_ontologies:
              archimate-4:
                entity_types:
                  stakeholder:
                    create_when: "c"
                    never_create_when: "n"
            """,
        )
        overlay = load_guidance_cache_file(tmp_path, _ALIAS)
        entry = overlay.get(_key("stakeholder"))
        assert entry is not None
        assert entry.create_when == "c"

    def test_malformed_yaml_top_level_returns_empty_overlay(self, tmp_path: Path) -> None:
        _write_cache(tmp_path, "- just\n- a\n- list\n")
        assert load_guidance_cache_file(tmp_path, _ALIAS).is_empty()


class TestLoadGuidanceOverlayForRepos:
    def test_both_roots_none_like_returns_empty(self, tmp_path: Path) -> None:
        overlay = load_guidance_overlay_for_repos(_ALIAS, enterprise_root=None, engagement_root=None)
        assert overlay.is_empty()

    def test_engagement_overrides_enterprise(self, tmp_path: Path) -> None:
        enterprise_root = tmp_path / "enterprise"
        engagement_root = tmp_path / "engagement"
        _write_cache(
            enterprise_root,
            """
            meta_ontologies:
              archimate-4:
                entity_types:
                  stakeholder: {create_when: "enterprise", never_create_when: "enterprise-never"}
            """,
        )
        _write_cache(
            engagement_root,
            """
            meta_ontologies:
              archimate-4:
                entity_types:
                  stakeholder: {create_when: "engagement", never_create_when: "engagement-never"}
            """,
        )
        overlay = load_guidance_overlay_for_repos(
            _ALIAS, enterprise_root=enterprise_root, engagement_root=engagement_root
        )
        entry = overlay.get(_key("stakeholder"))
        assert entry is not None
        assert entry.create_when == "engagement"

    def test_disjoint_keys_from_both_tiers_survive(self, tmp_path: Path) -> None:
        enterprise_root = tmp_path / "enterprise"
        engagement_root = tmp_path / "engagement"
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
                  capability: {create_when: "engagement", never_create_when: "n"}
            """,
        )
        overlay = load_guidance_overlay_for_repos(
            _ALIAS, enterprise_root=enterprise_root, engagement_root=engagement_root
        )
        assert overlay.get(_key("stakeholder")) is not None
        assert overlay.get(_key("capability")) is not None

    def test_missing_engagement_root_falls_back_to_enterprise_only(self, tmp_path: Path) -> None:
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
        overlay = load_guidance_overlay_for_repos(_ALIAS, enterprise_root=enterprise_root, engagement_root=None)
        entry = overlay.get(_key("stakeholder"))
        assert entry is not None
        assert entry.create_when == "enterprise"


class TestEnsureGuidanceCacheGitignored:
    def test_creates_cache_dir_and_gitignore_entry(self, tmp_path: Path) -> None:
        cache_root = ensure_guidance_cache_gitignored(tmp_path)
        assert cache_root == guidance_cache_root(tmp_path)
        assert cache_root.is_dir()
        gitignore = tmp_path / ".arch-repo" / ".gitignore"
        assert gitignore.read_text(encoding="utf-8").splitlines() == ["guidance-cache/"]

    def test_idempotent_does_not_duplicate_entry(self, tmp_path: Path) -> None:
        ensure_guidance_cache_gitignored(tmp_path)
        ensure_guidance_cache_gitignored(tmp_path)
        gitignore = tmp_path / ".arch-repo" / ".gitignore"
        assert gitignore.read_text(encoding="utf-8").splitlines() == ["guidance-cache/"]

    def test_preserves_existing_gitignore_entries(self, tmp_path: Path) -> None:
        arch_repo = tmp_path / ".arch-repo"
        arch_repo.mkdir(parents=True)
        (arch_repo / ".gitignore").write_text("transactions/\n", encoding="utf-8")

        ensure_guidance_cache_gitignored(tmp_path)

        lines = (arch_repo / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert lines == ["transactions/", "guidance-cache/"]
