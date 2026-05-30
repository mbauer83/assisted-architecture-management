"""Strategy registry for view derivation strategies.

Each registered StrategySpec declares the strategy name, version, and
the set of pre_filter keys that strategy supports. Verifier rule E412
rejects any pre_filter key not listed in supported_filters.

This module is populated by strategy-implementing modules (Phase 2 task #10).
At Phase 2 task #9 (this module), the registry starts empty: any diagram
with a view_derivations entry using a non-empty strategy will trigger E411.
No diagrams carry view_derivations yet, so no existing files break.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategySpec:
    name: str
    version: int
    supported_filters: frozenset[str]


_registry: dict[tuple[str, int], StrategySpec] = {}


def register_strategy(spec: StrategySpec) -> None:
    """Register a strategy spec by (name, version) key."""
    _registry[(spec.name, spec.version)] = spec


def lookup_strategy(name: str, version: int) -> StrategySpec | None:
    """Return the registered StrategySpec for (name, version), or None."""
    return _registry.get((name, version))


def registered_strategies() -> list[StrategySpec]:
    """Return all registered strategy specs."""
    return list(_registry.values())
