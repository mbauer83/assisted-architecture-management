"""Module registry discovery endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from src.infrastructure.app_bootstrap import get_module_registry

router = APIRouter()


@router.get("/api/modules")
def list_modules() -> list[dict[str, object]]:
    """Return metadata for every registered (enabled + satisfied) ontology module."""
    registry = get_module_registry()
    return [
        {
            "name": om.name,
            "module_class": om.module_class,
            "enabled": bool(getattr(om, "enabled", True)),
            "requires": list(getattr(om, "requires", [])),
            "entity_type_count": len(om.entity_types),
            "connection_type_count": len(om.connection_types),
        }
        for om in sorted(registry.all_ontologies().values(), key=lambda m: m.name)
    ]
