"""Tests for the GSN (Goal Structuring Notation) diagram type module."""

from __future__ import annotations

from pathlib import Path

from src.diagram_types.gsn import module as gsn_module


def test_module_name() -> None:
    assert str(gsn_module.name) == "gsn"


def test_module_class_is_assurance() -> None:
    assert gsn_module.module_class == "assurance"


def test_requires_confidential_store() -> None:
    requires = list(getattr(gsn_module, "requires", []))
    assert "confidential_store" in requires


def test_accepts_no_entity_types() -> None:
    from src.domain.module_types import EntityTypeName

    assert gsn_module.accepts_entity_type(EntityTypeName("application-component")) is False


def test_accepts_no_connection_types() -> None:
    from src.domain.module_types import ConnectionTypeName

    assert gsn_module.accepts_connection_type(ConnectionTypeName("archimate-composition")) is False


def test_write_guidance_has_content() -> None:
    guidance = gsn_module.write_guidance()
    assert "gsn" in guidance.when_to_use.lower() or "goal" in guidance.when_to_use.lower()
    assert guidance.when_not_to_use


def test_renderer_empty_entities_produces_skeleton() -> None:
    renderer = gsn_module.renderer
    body = renderer.render_body("empty", [], [], "gsn", Path("/"))
    assert "@startuml" in body
    assert "@enduml" in body


def test_renderer_goal_node() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [{"node_id": "G1", "name": "System is safe", "gsn_type": "goal"}],
        "edges": [],
    }
    body = renderer.render_body(
        "test-gsn", [], [], "gsn", Path("/fake"), diagram_entities=diagram_entities
    )
    assert "@startuml" in body
    assert "@enduml" in body
    assert "G: System is safe" in body
    assert "rectangle" in body
    assert "#D0E8FF" in body


def test_renderer_strategy_node() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [{"node_id": "S1", "name": "By hazard decomposition", "gsn_type": "strategy"}],
        "edges": [],
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "S: By hazard decomposition" in body
    assert "card" in body
    assert "#E8E0FF" in body


def test_renderer_solution_node() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [{"node_id": "Sn1", "name": "Test Report T-001", "gsn_type": "solution"}],
        "edges": [],
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "Sn: Test Report T-001" in body
    assert "database" in body
    assert "#D0FFD8" in body


def test_renderer_context_node() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [{"node_id": "C1", "name": "Safety concern", "gsn_type": "context"}],
        "edges": [],
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "C: Safety concern" in body
    assert "usecase" in body
    assert "#FFFFD0" in body


def test_renderer_assumption_node() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [{"node_id": "A1", "name": "Normal operation", "gsn_type": "assumption"}],
        "edges": [],
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "A: Normal operation" in body
    assert "#FFE8D0" in body


def test_renderer_justification_node() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [{"node_id": "J1", "name": "Industry standard", "gsn_type": "justification"}],
        "edges": [],
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "J: Industry standard" in body
    assert "#FFD0E8" in body


def test_renderer_supported_by_edge() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [
            {"node_id": "G1", "name": "Goal", "gsn_type": "goal"},
            {"node_id": "Sn1", "name": "Evidence", "gsn_type": "solution"},
        ],
        "edges": [{"source_id": "G1", "target_id": "Sn1", "conn_type": "supported-by"}],
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "G1 --> Sn1" in body
    assert "supported-by" in body


def test_renderer_in_context_of_edge_uses_dashed_arrow() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [
            {"node_id": "G1", "name": "Goal", "gsn_type": "goal"},
            {"node_id": "C1", "name": "Context", "gsn_type": "context"},
        ],
        "edges": [{"source_id": "G1", "target_id": "C1", "conn_type": "in-context-of"}],
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "..>" in body
    assert "in-context-of" in body


def test_renderer_full_gsn_argument() -> None:
    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": [
            {"node_id": "G_TOP", "name": "System is acceptably safe", "gsn_type": "goal"},
            {"node_id": "S1", "name": "By hazard decomposition", "gsn_type": "strategy"},
            {"node_id": "G_H1", "name": "H1 is controlled", "gsn_type": "goal"},
            {"node_id": "Sn1", "name": "Test report", "gsn_type": "solution"},
            {"node_id": "C1", "name": "Safety context", "gsn_type": "context"},
        ],
        "edges": [
            {"source_id": "G_TOP", "target_id": "S1", "conn_type": "supported-by"},
            {"source_id": "S1", "target_id": "G_H1", "conn_type": "supported-by"},
            {"source_id": "G_H1", "target_id": "Sn1", "conn_type": "supported-by"},
            {"source_id": "G_TOP", "target_id": "C1", "conn_type": "in-context-of"},
        ],
    }
    body = renderer.render_body(
        "full-gsn", [], [], "gsn", Path("/fake"), diagram_entities=diagram_entities
    )
    assert "System is acceptably safe" in body
    assert "By hazard decomposition" in body
    assert "H1 is controlled" in body
    assert "Test report" in body
    assert "Safety context" in body
    assert "top to bottom direction" in body


def test_inject_includes_noop() -> None:
    body = gsn_module.renderer.inject_includes("@startuml\n@enduml", Path("/fake"))
    assert body == "@startuml\n@enduml"


def test_collect_references_returns_empty() -> None:
    from src.domain.ontology_protocol import DiagramRendererReferences

    result = gsn_module.renderer.collect_references("gsn", Path("/fake"))
    assert isinstance(result, DiagramRendererReferences)


def test_renderer_json_string_nodes() -> None:
    """diagram_entities nodes/edges can be JSON strings."""
    import json

    renderer = gsn_module.renderer
    diagram_entities = {
        "nodes": json.dumps([{"node_id": "G1", "name": "Claim", "gsn_type": "goal"}]),
        "edges": json.dumps([]),
    }
    body = renderer.render_body(
        "test", [], [], "gsn", Path("/"), diagram_entities=diagram_entities
    )
    assert "Claim" in body
