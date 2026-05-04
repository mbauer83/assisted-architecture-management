from __future__ import annotations

from src.infrastructure.app_bootstrap import build_module_registry
from src.infrastructure.diagram_kinds import diagram_kind_domain
from src.infrastructure.gui.routers.diagrams import (
    get_diagram_kind_connection_types,
    get_diagram_kind_entity_types,
)


def test_default_registry_registers_matrix_diagram_kind() -> None:
    registry = build_module_registry()

    matrix = registry.find_diagram_kind("matrix")

    assert matrix is not None
    assert "goal" in matrix.effective_entity_types()
    assert "archimate-flow" in matrix.effective_connection_types()


def test_diagram_kind_domain_is_registry_derived() -> None:
    assert diagram_kind_domain("archimate-business") == "business"
    assert diagram_kind_domain("archimate-layered") is None
    assert diagram_kind_domain("matrix") is None


def test_diagram_kind_entity_types_endpoint_excludes_internal_types() -> None:
    items = get_diagram_kind_entity_types("archimate-business")

    assert items
    assert any(item["artifact_type"] == "business-actor" for item in items)
    assert all(item["artifact_type"] != "global-artifact-reference" for item in items)


def test_diagram_kind_connection_types_endpoint_exposes_effective_vocabulary() -> None:
    items = get_diagram_kind_connection_types("matrix")

    flow_item = next(item for item in items if item["connection_type"] == "archimate-flow")

    assert flow_item["conn_lang"] == "archimate"
    assert "flow" in flow_item["classifications"]
