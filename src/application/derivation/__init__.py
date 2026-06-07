"""Derivation package — view-derivation strategies and registry.

Importing this package registers all built-in strategies as a side effect
of loading the strategy modules. The verifier's E411/E412 rules import
``lookup_strategy`` from here (not from ``strategy_registry`` directly)
so that auto-registration runs before validation.

Note: c4.scope-projection is registered by src.diagram_types.c4._projection
when any C4 diagram-type package is loaded (via c4/_type.py). It is no longer
registered from this package.
"""

from __future__ import annotations

from src.application.derivation.strategy_registry import (
    StrategySpec,
    lookup_derive_fn,
    lookup_strategy,
    register_strategy,
    registered_strategies,
)
from src.application.derivation.types import CandidateSet, DeriveFn, ModelQuery

# Import strategy modules to trigger self-registration.
from . import (  # noqa: E402, F401
    explicit_selection,
    incident_connections,
    local_neighborhood,
    path_projection,
    scope_projection,
)

__all__ = [
    "CandidateSet",
    "DeriveFn",
    "ModelQuery",
    "StrategySpec",
    "explicit_selection",
    "incident_connections",
    "local_neighborhood",
    "path_projection",
    "scope_projection",
    "lookup_derive_fn",
    "lookup_strategy",
    "register_strategy",
    "registered_strategies",
]
