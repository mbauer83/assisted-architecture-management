"""Application startup wiring for the module registry."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from src.application.startup_validation import validate_registry_consistency
from src.diagram_types import register_default_diagram_types
from src.domain.module_registry import ModuleRegistry
from src.ontologies.archimate_next import module as archimate_next_module
from src.ontologies.sysml_v2_min import module as sysml_v2_min_module

if TYPE_CHECKING:
    from fastapi import Request

_MODULE_REGISTRY_STATE_KEY = "module_registry"


def build_module_registry() -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register_ontology(archimate_next_module)
    registry.register_ontology(sysml_v2_min_module)
    register_default_diagram_types(registry)
    validate_registry_consistency(registry)
    return registry


def install_module_registry(app: Any, *, registry: ModuleRegistry | None = None) -> ModuleRegistry:
    """Attach the module registry to FastAPI app state for dependency-based access."""
    resolved = registry or get_module_registry()
    setattr(app.state, _MODULE_REGISTRY_STATE_KEY, resolved)
    return resolved


def module_registry_from_app(app: Any) -> ModuleRegistry:
    """Return the module registry installed on a FastAPI application."""
    registry = getattr(app.state, _MODULE_REGISTRY_STATE_KEY, None)
    if not isinstance(registry, ModuleRegistry):
        raise RuntimeError("Module registry has not been installed on the FastAPI application")
    return registry


def module_registry_dependency(request: Request) -> ModuleRegistry:
    """FastAPI dependency exposing the installed module registry."""
    return module_registry_from_app(request.app)


@lru_cache(maxsize=1)
def get_module_registry() -> ModuleRegistry:
    return build_module_registry()
