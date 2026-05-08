"""Shared helpers for registry-backed diagram-kind lookups."""

from __future__ import annotations

from functools import lru_cache

from src.domain.ontology_protocol import DiagramKindModule


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


def get_diagram_kind(name: str) -> DiagramKindModule:
    """Return the registered diagram kind named *name*."""
    return _registry().get_diagram_kind(name)


def find_diagram_kind(name: str) -> DiagramKindModule | None:
    """Return the registered diagram kind named *name*, if any."""
    return _registry().find_diagram_kind(name)


def diagram_kind_domain(name: str) -> str | None:
    """Infer the primary non-common domain exposed by a diagram kind."""
    kind = find_diagram_kind(name)
    if kind is None:
        return None
    domains = {
        info.hierarchy[0]
        for info in kind.effective_entity_types().values()
        if not info.internal and info.hierarchy
    }
    non_common = {domain for domain in domains if domain != "common"}
    if len(non_common) == 1:
        return next(iter(non_common))
    if len(non_common) == 0 and len(domains) == 1:
        return next(iter(domains))
    return None


def domain_order() -> list[str]:
    """Return ontology-driven domain ordering."""
    return _registry().domain_order()
