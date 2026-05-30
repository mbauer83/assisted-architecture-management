"""Strategy registry for view derivation strategies.

Each registered StrategySpec declares the strategy name, version, and
the set of pre_filter keys that strategy supports. Verifier rule E412
rejects any pre_filter key not listed in supported_filters.

An optional derive_fn can be stored alongside the spec so task 11
(refresh/diff) can dispatch to the right implementation by (name, version).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.derivation.types import DeriveFn


@dataclass(frozen=True)
class StrategySpec:
    name: str
    version: int
    supported_filters: frozenset[str]


_registry: dict[tuple[str, int], StrategySpec] = {}
_derive_fns: dict[tuple[str, int], "DeriveFn"] = {}


def register_strategy(spec: StrategySpec, derive_fn: "DeriveFn | None" = None) -> None:
    """Register a strategy spec (and optionally its derive function) by (name, version) key."""
    _registry[(spec.name, spec.version)] = spec
    if derive_fn is not None:
        _derive_fns[(spec.name, spec.version)] = derive_fn


def lookup_strategy(name: str, version: int) -> StrategySpec | None:
    """Return the registered StrategySpec for (name, version), or None."""
    return _registry.get((name, version))


def lookup_derive_fn(name: str, version: int) -> "DeriveFn | None":
    """Return the registered derive function for (name, version), or None."""
    return _derive_fns.get((name, version))


def registered_strategies() -> list[StrategySpec]:
    """Return all registered strategy specs."""
    return list(_registry.values())
