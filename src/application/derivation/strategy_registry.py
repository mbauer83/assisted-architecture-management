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


# ── Immutable catalog + its builder ──────────────────────────────────────────


class DerivationStrategyCatalog:
    """Immutable snapshot of registered derivation strategies.

    Produced by ``DerivationStrategyCatalogBuilder.build()``.
    """

    def __init__(
        self,
        specs: dict[tuple[str, int], StrategySpec],
        fns: dict[tuple[str, int], "DeriveFn"],
    ) -> None:
        self._specs = specs
        self._fns = fns

    def lookup_strategy(self, name: str, version: int) -> StrategySpec | None:
        return self._specs.get((name, version))

    def lookup_derive_fn(self, name: str, version: int) -> "DeriveFn | None":
        return self._fns.get((name, version))

    def registered_strategies(self) -> list[StrategySpec]:
        return list(self._specs.values())


class DerivationStrategyCatalogBuilder:
    """Mutable builder for derivation strategies; ``.build()`` seals it."""

    def __init__(self) -> None:
        self._specs: dict[tuple[str, int], StrategySpec] = {}
        self._fns: dict[tuple[str, int], "DeriveFn"] = {}
        self._built = False

    def _check_not_built(self) -> None:
        if self._built:
            raise RuntimeError("DerivationStrategyCatalogBuilder has already been built")

    def register(self, spec: StrategySpec, derive_fn: "DeriveFn | None" = None) -> None:
        self._check_not_built()
        self._specs[(spec.name, spec.version)] = spec
        if derive_fn is not None:
            self._fns[(spec.name, spec.version)] = derive_fn

    def build(self) -> DerivationStrategyCatalog:
        self._built = True
        return DerivationStrategyCatalog(dict(self._specs), dict(self._fns))
