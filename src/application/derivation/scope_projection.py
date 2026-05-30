"""scope-projection/v1 strategy + module projection registry.

The module projection registry maps (projection_id, projection_version) to
a derive function with the same signature as any strategy derive function.
scope-projection/v1 reads projection_id + projection_version from params and
delegates to the registered module projection.

To register a module projection:
    from src.application.derivation.scope_projection import register_module_projection
    register_module_projection("c4", 1, my_derive_fn)

Supported pre_filters: repo_scope
"""

from __future__ import annotations

from src.application.derivation.strategy_registry import StrategySpec, register_strategy
from src.application.derivation.types import CandidateSet, DeriveFn, ModelQuery
from src.domain.view_derivations import SourceModelSnapshot

# --------------------------------------------------------------------------
# Module projection registry
# --------------------------------------------------------------------------

_module_projections: dict[tuple[str, int], DeriveFn] = {}


def register_module_projection(
    projection_id: str,
    projection_version: int,
    fn: DeriveFn,
) -> None:
    """Register a module projection for use by scope-projection/v1."""
    _module_projections[(projection_id, projection_version)] = fn


def lookup_module_projection(
    projection_id: str,
    projection_version: int,
) -> DeriveFn | None:
    """Return the registered module projection derive function, or None."""
    return _module_projections.get((projection_id, projection_version))


# --------------------------------------------------------------------------
# scope-projection/v1
# --------------------------------------------------------------------------

_SUPPORTED_FILTERS = frozenset({"repo_scope"})


def derive(
    params: dict[str, object],
    snapshot: SourceModelSnapshot,
    query: ModelQuery,
) -> CandidateSet:
    """scope-projection/v1: dispatch to a registered module projection by projection_id."""
    projection_id_raw = params.get("projection_id")
    projection_id = str(projection_id_raw) if projection_id_raw is not None else ""

    pv_raw = params.get("projection_version", 1)
    projection_version = int(pv_raw) if isinstance(pv_raw, (int, float)) else 1

    if not projection_id:
        return CandidateSet()

    fn = lookup_module_projection(projection_id, projection_version)
    if fn is None:
        return CandidateSet()

    return fn(params, snapshot, query)


register_strategy(
    StrategySpec(
        name="scope-projection",
        version=1,
        supported_filters=_SUPPORTED_FILTERS,
    ),
    derive_fn=derive,
)
