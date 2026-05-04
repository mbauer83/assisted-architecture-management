"""Application startup wiring for the module registry."""

from __future__ import annotations

from functools import lru_cache

from src.domain.module_registry import ModuleRegistry
from src.ontologies.archimate_next import module as archimate_next_module


def build_module_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register_ontology(archimate_next_module)
    return registry


@lru_cache(maxsize=1)
def get_module_registry() -> ModuleRegistry:
    return build_module_registry()
