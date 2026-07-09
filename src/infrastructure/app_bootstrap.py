"""Application startup wiring for the module registry and runtime catalogs."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Request

from src.application.derivation.strategy_registry import DerivationStrategyCatalogBuilder
from src.application.runtime_catalogs import RuntimeCatalogs
from src.application.startup_validation import validate_registry_consistency
from src.config.settings import datatype_type_references_blocking
from src.config.workspace_paths import resolve_workspace_repo_roots
from src.diagram_types import register_default_diagram_types
from src.domain.catalogs import ConnectionSemanticsImpl, DiagramTypeCatalogImpl, OntologyCatalogImpl
from src.domain.guidance import GuidanceOverlay
from src.domain.module_catalog import ModuleCatalog, ModuleCatalogBuilder
from src.domain.module_filter import is_module_enabled
from src.domain.module_registry import ModuleRegistry
from src.domain.ontology_protocol import OntologyModule
from src.infrastructure.assurance.capability import make_capability
from src.infrastructure.guidance_cache import load_guidance_overlay_for_repos
from src.infrastructure.rendering._svg_sprite_convert import browser_markup_to_plantuml_svg as _svg_convert
from src.ontologies.archimate_4._loader import _PACKAGE_DIR as _ARCH_PACKAGE_DIR
from src.ontologies.archimate_4._loader import META_ONTOLOGY_ALIAS as _ARCHIMATE_META_ALIAS
from src.ontologies.archimate_4._loader import load_archimate_4_module
from src.ontologies.assurance import module as assurance_module
from src.ontologies.sysml_v2_min import module as sysml_v2_min_module


def _load_archimate_guidance_overlay() -> GuidanceOverlay:
    """Merge the enterprise and engagement guidance caches for the archimate-4 meta-ontology.

    No workspace configured (e.g. code generation, most unit tests) ⇒ empty overlay, which
    is a no-op — entities keep whatever ``create_when``/``never_create_when`` text the
    module ships inline. A guidance import takes effect on the next backend restart, since
    this runs once at process/module-import time (consistent with the existing
    ``@lru_cache`` registry pattern).
    """
    roots = resolve_workspace_repo_roots()
    if roots is None:
        return GuidanceOverlay()
    engagement_root, enterprise_root = roots
    return load_guidance_overlay_for_repos(
        _ARCHIMATE_META_ALIAS, enterprise_root=enterprise_root, engagement_root=engagement_root
    )


_archimate_4_module = load_archimate_4_module(
    _ARCH_PACKAGE_DIR, svg_converter=_svg_convert, guidance=_load_archimate_guidance_overlay()
)
_archimate_matrix_abbreviations = _archimate_4_module.matrix_abbreviations

_MODULE_REGISTRY_STATE_KEY = "module_registry"
_RUNTIME_CATALOGS_STATE_KEY = "runtime_catalogs"
_logger = logging.getLogger(__name__)

_ALL_ONTOLOGY_MODULES = (_archimate_4_module, sysml_v2_min_module, assurance_module)

_DEFAULT_ASSURANCE_DB = Path(__file__).resolve().parents[2] / ".arch-assurance" / "store.db"


def _inject_capability_sentinels(registered_names: set[str]) -> None:
    """Add synthetic capability names before module deps are checked.

    confidential_store: present when the keychain key + DB file are available.
    """
    capability = make_capability(_DEFAULT_ASSURANCE_DB)
    if capability.enabled:
        registered_names.add("confidential_store")
        _logger.info("confidential_store capability available at %s", _DEFAULT_ASSURANCE_DB)


def build_module_registry(*, complete_vocabulary: bool = False) -> ModuleRegistry:
    """Assemble the module registry from the configured ontology and diagram-type modules.

    complete_vocabulary: register every module and diagram type unconditionally, ignoring
    optional runtime capabilities (e.g. the confidential assurance store) and local YAML
    overrides. Code generation and schema export use this so the emitted vocabulary is the
    full, stable superset regardless of the environment it runs in — otherwise the output
    would differ between a machine that has the assurance store and one that does not.
    """
    from src.config.settings import module_overrides  # noqa: PLC0415

    overrides = module_overrides()
    registry = ModuleRegistry()
    registered_names: set[str] = set()

    _inject_capability_sentinels(registered_names)

    for om in _ALL_ONTOLOGY_MODULES:
        if complete_vocabulary or is_module_enabled(om, overrides, registered_names):
            registry.register_ontology(om)
            registered_names.add(om.name)
        else:
            _logger.info("Ontology module %r skipped (disabled or unsatisfied requires)", om.name)

    if complete_vocabulary:
        register_default_diagram_types(registry)
    else:
        register_default_diagram_types(registry, overrides=overrides, registered_names=registered_names)
    validate_registry_consistency(registry)
    return registry


def build_module_catalog(registry: ModuleRegistry) -> ModuleCatalog:
    """Convert a ModuleRegistry snapshot into an immutable ModuleCatalog."""
    builder = ModuleCatalogBuilder()
    for om in registry.all_ontologies().values():
        builder.register_ontology(om)
    for dt in registry.all_diagram_types().values():
        builder.register_diagram_type(dt)
    return builder.build()


def _build_derivation_catalog():
    from src.application.derivation import (  # noqa: PLC0415
        explicit_selection,
        incident_connections,
        local_neighborhood,
        path_projection,
    )
    from src.diagram_types.c4._projection import MANIFEST as _c4_manifest  # noqa: PLC0415

    builder = DerivationStrategyCatalogBuilder()
    builder.register(explicit_selection.SPEC, explicit_selection.derive)
    builder.register(local_neighborhood.SPEC, local_neighborhood.derive)
    builder.register(incident_connections.SPEC, incident_connections.derive)
    builder.register(path_projection.SPEC, path_projection.derive)
    for spec, fn in _c4_manifest.strategies:
        builder.register(spec, fn)
    return builder.build()


def build_runtime_catalogs(registry: ModuleRegistry) -> RuntimeCatalogs:
    """Build a frozen RuntimeCatalogs from a fully-built ModuleRegistry."""
    module_catalog = build_module_catalog(registry)
    return RuntimeCatalogs(
        module_catalog=module_catalog,
        ontology=OntologyCatalogImpl(module_catalog, _archimate_matrix_abbreviations),
        connections=ConnectionSemanticsImpl(module_catalog),
        diagram_types=DiagramTypeCatalogImpl(module_catalog),
        derivation=_build_derivation_catalog(),
        datatype_type_references_blocking=datatype_type_references_blocking(),
    )


def install_module_registry(app: Any, *, registry: ModuleRegistry | None = None) -> ModuleRegistry:
    """Attach the module registry and runtime catalogs to FastAPI app state."""
    resolved = registry or get_module_registry()
    setattr(app.state, _MODULE_REGISTRY_STATE_KEY, resolved)
    setattr(app.state, _RUNTIME_CATALOGS_STATE_KEY, build_runtime_catalogs(resolved))
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


def runtime_catalogs_from_app(app: Any) -> RuntimeCatalogs:
    """Return the RuntimeCatalogs installed on a FastAPI application."""
    catalogs = getattr(app.state, _RUNTIME_CATALOGS_STATE_KEY, None)
    if not isinstance(catalogs, RuntimeCatalogs):
        raise RuntimeError("RuntimeCatalogs have not been installed on the FastAPI application")
    return catalogs


def runtime_catalogs_dependency(request: Request) -> RuntimeCatalogs:
    """FastAPI dependency exposing the installed RuntimeCatalogs."""
    return runtime_catalogs_from_app(request.app)


@lru_cache(maxsize=1)
def get_module_registry() -> ModuleRegistry:
    return build_module_registry()


_META_ONTOLOGY_ALIASES: dict[str, str] = {
    "archimate-4": "archimate-4-0",
    "sysml-v2": "sysml_v2_min",
}


def registered_meta_ontology_values(registry: ModuleRegistry) -> frozenset[str]:
    """Return meta-ontology aliases whose backing ontology modules are active."""
    return frozenset(
        alias for alias, module_name in _META_ONTOLOGY_ALIASES.items() if registry.find_ontology(module_name)
    )


def resolve_meta_ontology_artifact_types(
    meta_ontology: str, registry: ModuleRegistry
) -> frozenset[str] | None:
    """Return allowed artifact type names for a meta-ontology shortname, or None for no filter."""
    if not meta_ontology:
        return None
    module_name = _META_ONTOLOGY_ALIASES.get(meta_ontology)
    if not module_name:
        return frozenset()
    om = registry.find_ontology(module_name)
    return frozenset(om.entity_types.keys()) if om else frozenset()


def resolve_meta_ontology_module(meta_ontology: str, registry: ModuleRegistry) -> OntologyModule | None:
    """Return the registered OntologyModule backing a meta-ontology alias, or None if the
    alias is unknown or its module is inactive. Used where a caller needs the full module
    (entity AND connection type vocabulary), not just the entity-type subset."""
    module_name = _META_ONTOLOGY_ALIASES.get(meta_ontology)
    return registry.find_ontology(module_name) if module_name else None
