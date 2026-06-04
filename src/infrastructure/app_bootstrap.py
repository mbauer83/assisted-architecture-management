"""Application startup wiring for the module registry."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.application.startup_validation import validate_registry_consistency
from src.diagram_types import register_default_diagram_types
from src.domain.module_filter import is_module_enabled
from src.domain.module_registry import ModuleRegistry
from src.infrastructure.assurance.capability import make_capability
from src.ontologies.archimate_next import module as archimate_next_module
from src.ontologies.assurance import module as assurance_module
from src.ontologies.sysml_v2_min import module as sysml_v2_min_module

if TYPE_CHECKING:
    from fastapi import Request

_MODULE_REGISTRY_STATE_KEY = "module_registry"
_logger = logging.getLogger(__name__)

_ALL_ONTOLOGY_MODULES = (archimate_next_module, sysml_v2_min_module, assurance_module)

_DEFAULT_ASSURANCE_DB = Path(__file__).resolve().parents[2] / ".arch-assurance" / "store.db"


def _inject_capability_sentinels(registered_names: set[str]) -> None:
    """Add synthetic capability names before module deps are checked.

    confidential_store: present when the keychain key + DB file are available.
    """
    capability = make_capability(_DEFAULT_ASSURANCE_DB)
    if capability.enabled:
        registered_names.add("confidential_store")
        _logger.info("confidential_store capability available at %s", _DEFAULT_ASSURANCE_DB)


def build_module_registry() -> ModuleRegistry:
    from src.config.settings import module_overrides  # noqa: PLC0415

    overrides = module_overrides()
    registry = ModuleRegistry()
    registered_names: set[str] = set()

    _inject_capability_sentinels(registered_names)

    for om in _ALL_ONTOLOGY_MODULES:
        if is_module_enabled(om, overrides, registered_names):
            registry.register_ontology(om)
            registered_names.add(om.name)
        else:
            _logger.info("Ontology module %r skipped (disabled or unsatisfied requires)", om.name)

    register_default_diagram_types(registry, overrides=overrides, registered_names=registered_names)
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
