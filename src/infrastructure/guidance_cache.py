"""Reads repo-local, gitignored guidance-cache files into a domain GuidanceOverlay (D2/D3a).

Writing the cache files (the import CLI) is WU-B4; this module is the read side consumed at
bootstrap, plus the scaffolded ``.arch-repo/.gitignore`` registration the write side needs.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from src.domain.guidance import GuidanceOverlay, guidance_overlay_from_mapping

GUIDANCE_CACHE_DIRNAME = "guidance-cache"


def guidance_cache_root(repo_root: Path) -> Path:
    return repo_root / ".arch-repo" / GUIDANCE_CACHE_DIRNAME


def load_guidance_cache_file(repo_root: Path, module_alias: str) -> GuidanceOverlay:
    """Read ``<repo_root>/.arch-repo/guidance-cache/<module_alias>.guidance.yaml``.

    Returns an empty overlay when the file is absent — the default, license-safe state.
    """
    cache_file = guidance_cache_root(repo_root) / f"{module_alias}.guidance.yaml"
    if not cache_file.is_file():
        return GuidanceOverlay()
    data = yaml.safe_load(cache_file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return GuidanceOverlay()
    return guidance_overlay_from_mapping(data)


def load_guidance_overlay_for_repos(
    module_alias: str, *, enterprise_root: Path | None, engagement_root: Path | None
) -> GuidanceOverlay:
    """Merge per D2 precedence: module-inline (caller's own fallback) < enterprise cache <
    engagement cache. Either root may be ``None`` (no workspace configured for that tier).
    """
    enterprise_overlay = (
        load_guidance_cache_file(enterprise_root, module_alias) if enterprise_root is not None else GuidanceOverlay()
    )
    engagement_overlay = (
        load_guidance_cache_file(engagement_root, module_alias) if engagement_root is not None else GuidanceOverlay()
    )
    return GuidanceOverlay.merge(enterprise_overlay, engagement_overlay)


def ensure_guidance_cache_gitignored(repo_root: Path) -> Path:
    """Idempotently record ``guidance-cache/`` in the repo's tracked ``.arch-repo/.gitignore``
    and return the (created) cache directory.

    Mirrors ``m4_transaction.ensure_transactions_root``'s ignore-registration idiom: the
    entry is added once, the first time anything is about to be written into the cache dir.
    """
    cache_root = guidance_cache_root(repo_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    arch_repo = repo_root / ".arch-repo"
    gitignore = arch_repo / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    entry = f"{GUIDANCE_CACHE_DIRNAME}/"
    if entry not in lines:
        with gitignore.open("a", encoding="utf-8") as handle:
            handle.write(f"{entry}\n")
    return cache_root
