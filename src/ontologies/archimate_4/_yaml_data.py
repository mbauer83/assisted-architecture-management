"""YAML data-file loaders for the archimate-4 module: the specialization catalog and the
named-profile registry. Kept out of ``_loader.py`` so the module loader stays within the
source-length policy and the file-reading is one small, testable place."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.domain.profile_registry import ProfileRegistry, profile_registry_from_mapping
from src.domain.specializations import SpecializationCatalog, specialization_catalog_from_mapping


def load_module_specializations(package_dir: Path, module_alias: str) -> SpecializationCatalog:
    path = package_dir / "specializations.yaml"
    if not path.exists():
        return SpecializationCatalog.empty()
    loaded: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Invalid specialization declarations in {path}: top-level YAML value must be a mapping")
    return specialization_catalog_from_mapping(loaded, module_alias=module_alias)


def load_module_profiles(package_dir: Path) -> ProfileRegistry:
    path = package_dir / "profiles.yaml"
    if not path.exists():
        return ProfileRegistry.empty()
    return profile_registry_from_mapping(yaml.safe_load(path.read_text(encoding="utf-8")), label=str(path))
