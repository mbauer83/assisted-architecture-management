"""Tests for scope-projection/v1 generic dispatcher strategy.

C4-specific projection tests have moved to tests/diagram_types/test_c4_projection.py.
The c4.scope-projection strategy is now registered from src.diagram_types.c4._projection
when the C4 module loads, not from the generic derivation package.
"""

from __future__ import annotations

# Loading the C4 projection module triggers c4.scope-projection registration.
import src.diagram_types.c4._projection  # noqa: F401
from src.application.derivation.scope_projection import derive as generic_derive
from src.application.derivation.strategy_registry import lookup_strategy
from src.domain.view_derivations import SourceModelSnapshot
from tests.application.derivation._fixtures import FakeQuery, _connection, _entity

_SNAP_ROOT = SourceModelSnapshot(repo_scope="both", root_entity_id="ROOT")
_SNAP_NO_ROOT = SourceModelSnapshot(repo_scope="both")


# ---------------------------------------------------------------------------
# Registration checks
# ---------------------------------------------------------------------------


def test_scope_projection_v1_registered() -> None:
    spec = lookup_strategy("scope-projection", 1)
    assert spec is not None
    assert spec.supported_filters == frozenset({"repo_scope"})


def test_c4_scope_projection_v1_registered() -> None:
    """c4.scope-projection registered by the C4 module, not the generic package."""
    spec = lookup_strategy("c4.scope-projection", 1)
    assert spec is not None
    assert spec.supported_filters == frozenset({"repo_scope"})


# ---------------------------------------------------------------------------
# scope-projection/v1 generic dispatcher
# ---------------------------------------------------------------------------


def test_generic_scope_projection_dispatches_to_c4() -> None:
    root = _entity("ROOT", "application-component")
    child = _entity("CHILD", "service")
    struct = _connection("ROOT---CHILD@@archimate-composition", "ROOT", "CHILD", "archimate-composition")
    query = FakeQuery([root, child], [struct])

    params: dict[str, object] = {
        "projection_id": "c4",
        "projection_version": 1,
        "diagram_type": "c4-container",
    }
    result = generic_derive(params, _SNAP_ROOT, query)

    assert "CHILD" in result.entity_ids


def test_generic_scope_projection_unknown_projection_returns_empty() -> None:
    query = FakeQuery([], [])
    params: dict[str, object] = {"projection_id": "no-such-projection", "projection_version": 1}
    result = generic_derive(params, _SNAP_ROOT, query)
    assert result.entity_ids == frozenset()


def test_generic_scope_projection_missing_projection_id_returns_empty() -> None:
    query = FakeQuery([], [])
    result = generic_derive({}, _SNAP_ROOT, query)
    assert result.entity_ids == frozenset()
