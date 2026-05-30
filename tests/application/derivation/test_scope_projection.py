"""Tests for scope-projection/v1 and c4.scope-projection/v1 strategies."""

from __future__ import annotations

import src.application.derivation  # noqa: F401 — triggers registration
from src.application.derivation.c4_scope_projection import derive as c4_derive
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
    spec = lookup_strategy("c4.scope-projection", 1)
    assert spec is not None
    assert spec.supported_filters == frozenset({"repo_scope"})


# ---------------------------------------------------------------------------
# c4-system-context
# ---------------------------------------------------------------------------


def test_system_context_includes_root() -> None:
    root = _entity("ROOT", "application-component")
    query = FakeQuery([root], [])

    result = c4_derive({"diagram_type": "c4-system-context"}, _SNAP_ROOT, query)

    assert "ROOT" in result.entity_ids


def test_system_context_includes_neighbor_system() -> None:
    root = _entity("ROOT", "application-component")
    ext = _entity("EXT", "application-component")
    conn = _connection("ROOT---EXT@@archimate-serving", "ROOT", "EXT", "archimate-serving")
    query = FakeQuery([root, ext], [conn])

    result = c4_derive({"diagram_type": "c4-system-context"}, _SNAP_ROOT, query)

    assert "EXT" in result.entity_ids
    assert "ROOT---EXT@@archimate-serving" in result.connection_ids


def test_system_context_includes_person_neighbor() -> None:
    root = _entity("ROOT", "application-component")
    actor = _entity("ACTOR", "business-actor")
    conn = _connection("ACTOR---ROOT@@archimate-serving", "ACTOR", "ROOT", "archimate-serving")
    query = FakeQuery([root, actor], [conn])

    result = c4_derive({"diagram_type": "c4-system-context"}, _SNAP_ROOT, query)

    assert "ACTOR" in result.entity_ids


def test_system_context_excludes_non_projected_type() -> None:
    root = _entity("ROOT", "application-component")
    artifact = _entity("ART", "artifact")  # not in _CONTEXT_PROJ_TYPES
    conn = _connection("ROOT---ART@@archimate-serving", "ROOT", "ART", "archimate-serving")
    query = FakeQuery([root, artifact], [conn])

    result = c4_derive({"diagram_type": "c4-system-context"}, _SNAP_ROOT, query)

    assert "ART" not in result.entity_ids


def test_system_context_no_root_returns_empty() -> None:
    query = FakeQuery([], [])
    result = c4_derive({"diagram_type": "c4-system-context"}, _SNAP_NO_ROOT, query)
    assert result.entity_ids == frozenset()


# ---------------------------------------------------------------------------
# c4-container
# ---------------------------------------------------------------------------


def test_container_internal_child_included() -> None:
    root = _entity("ROOT", "application-component")
    child = _entity("CHILD", "application-component")
    struct = _connection("ROOT---CHILD@@archimate-composition", "ROOT", "CHILD", "archimate-composition")
    query = FakeQuery([root, child], [struct])

    result = c4_derive({"diagram_type": "c4-container"}, _SNAP_ROOT, query)

    assert "CHILD" in result.entity_ids
    # Root is NOT a visible node for c4-container
    assert "ROOT" not in result.entity_ids


def test_container_root_excluded_from_candidates() -> None:
    root = _entity("ROOT", "application-component")
    query = FakeQuery([root], [])

    result = c4_derive({"diagram_type": "c4-container"}, _SNAP_ROOT, query)

    assert "ROOT" not in result.entity_ids


def test_container_data_object_internal() -> None:
    root = _entity("ROOT", "application-component")
    db = _entity("DB", "data-object")
    conn = _connection("ROOT---DB@@archimate-aggregation", "ROOT", "DB", "archimate-aggregation")
    query = FakeQuery([root, db], [conn])

    result = c4_derive({"diagram_type": "c4-container"}, _SNAP_ROOT, query)

    assert "DB" in result.entity_ids


def test_container_external_neighbor_software_system() -> None:
    root = _entity("ROOT", "application-component")
    child = _entity("CHILD", "service")
    ext = _entity("EXT", "application-component")
    struct = _connection("ROOT---CHILD@@archimate-composition", "ROOT", "CHILD", "archimate-composition")
    dep = _connection("CHILD---EXT@@archimate-serving", "CHILD", "EXT", "archimate-serving")
    query = FakeQuery([root, child, ext], [struct, dep])

    result = c4_derive({"diagram_type": "c4-container"}, _SNAP_ROOT, query)

    assert "CHILD" in result.entity_ids
    assert "EXT" in result.entity_ids
    assert "CHILD---EXT@@archimate-serving" in result.connection_ids


def test_container_person_neighbor() -> None:
    root = _entity("ROOT", "application-component")
    child = _entity("CHILD", "service")
    actor = _entity("ACTOR", "role")
    struct = _connection("ROOT---CHILD@@archimate-composition", "ROOT", "CHILD", "archimate-composition")
    dep = _connection("ACTOR---CHILD@@archimate-serving", "ACTOR", "CHILD", "archimate-serving")
    query = FakeQuery([root, child, actor], [struct, dep])

    result = c4_derive({"diagram_type": "c4-container"}, _SNAP_ROOT, query)

    assert "ACTOR" in result.entity_ids


def test_container_non_structural_root_neighbor_included() -> None:
    """Neighbors of root itself via dependency types are included as external nodes."""
    root = _entity("ROOT", "application-component")
    ext = _entity("EXT", "service")
    dep = _connection("ROOT---EXT@@archimate-flow", "ROOT", "EXT", "archimate-flow")
    query = FakeQuery([root, ext], [dep])

    result = c4_derive({"diagram_type": "c4-container"}, _SNAP_ROOT, query)

    assert "EXT" in result.entity_ids


# ---------------------------------------------------------------------------
# c4-component
# ---------------------------------------------------------------------------


def test_component_internal_component() -> None:
    root = _entity("ROOT", "application-component")
    comp = _entity("COMP", "application-component")
    struct = _connection("ROOT---COMP@@archimate-composition", "ROOT", "COMP", "archimate-composition")
    query = FakeQuery([root, comp], [struct])

    result = c4_derive({"diagram_type": "c4-component"}, _SNAP_ROOT, query)

    assert "COMP" in result.entity_ids
    assert "ROOT" not in result.entity_ids


def test_component_function_internal() -> None:
    root = _entity("ROOT", "application-component")
    fn_entity = _entity("FN", "function")
    struct = _connection("ROOT---FN@@archimate-aggregation", "ROOT", "FN", "archimate-aggregation")
    query = FakeQuery([root, fn_entity], [struct])

    result = c4_derive({"diagram_type": "c4-component"}, _SNAP_ROOT, query)

    assert "FN" in result.entity_ids


def test_component_neighbor_software_system() -> None:
    root = _entity("ROOT", "application-component")
    comp = _entity("COMP", "service")
    ext = _entity("EXT", "application-component")
    struct = _connection("ROOT---COMP@@archimate-composition", "ROOT", "COMP", "archimate-composition")
    dep = _connection("COMP---EXT@@archimate-serving", "COMP", "EXT", "archimate-serving")
    query = FakeQuery([root, comp, ext], [struct, dep])

    result = c4_derive({"diagram_type": "c4-component"}, _SNAP_ROOT, query)

    assert "COMP" in result.entity_ids
    assert "EXT" in result.entity_ids
    assert "COMP---EXT@@archimate-serving" in result.connection_ids


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


# ---------------------------------------------------------------------------
# Unknown diagram_type
# ---------------------------------------------------------------------------


def test_unknown_diagram_type_returns_empty() -> None:
    root = _entity("ROOT", "application-component")
    query = FakeQuery([root], [])
    result = c4_derive({"diagram_type": "c4-deployment"}, _SNAP_ROOT, query)
    assert result.entity_ids == frozenset()
    assert result.connection_ids == frozenset()
