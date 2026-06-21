"""Tests for the assurance diagram projectors.

Verifies PUML output correctness for control-structure and uca-matrix diagrams,
including empty-store edge-cases and edge filtering.
"""

from __future__ import annotations

from src.application.assurance_diagrams import (
    AVAILABLE_DIAGRAMS,
    bowtie_nodes,
    render_bowtie,
    render_control_structure,
    render_uca_matrix,
    uca_matrix_nodes,
)


def _cs_node(nid: str, name: str, role: str = "") -> dict[str, object]:
    return {"node_id": nid, "node_type": "control-structure-node", "name": name, "node_role": role}


def _edge(src: str, tgt: str, conn_type: str, name: str = "") -> dict[str, object]:
    return {"source_id": src, "target_id": tgt, "conn_type": conn_type, "name": name}


def _uca(nid: str, name: str, uca_type: str = "commission") -> dict[str, object]:
    return {"node_id": nid, "node_type": "unsafe-control-action", "name": name, "uca_type": uca_type}


# ── AVAILABLE_DIAGRAMS ────────────────────────────────────────────────────────

def test_available_diagrams_contains_required_ids() -> None:
    ids = {d["diagram_id"] for d in AVAILABLE_DIAGRAMS}
    assert "bowtie" in ids
    assert "control-structure" in ids
    assert "uca-matrix" in ids


# ── render_control_structure ──────────────────────────────────────────────────

def test_control_structure_empty_renders_note() -> None:
    puml = render_control_structure([], [])
    assert "@startuml" in puml
    assert "@enduml" in puml
    assert "No control-structure nodes found" in puml


def test_control_structure_single_node() -> None:
    puml = render_control_structure([_cs_node("N1", "Controller")], [])
    assert "Controller" in puml
    assert "rectangle" in puml


def test_control_structure_includes_control_actions_and_their_edges() -> None:
    nodes = [
        _cs_node("N1", "Controller"),
        {"node_id": "CA1", "node_type": "control-action", "name": "Apply brake"},
    ]
    edges = [_edge("N1", "CA1", "issues")]
    puml = render_control_structure(nodes, edges)
    assert "control" in puml
    assert "Apply brake" in puml
    assert "issues" in puml


def test_control_structure_node_role_in_output() -> None:
    puml = render_control_structure([_cs_node("N1", "Braking", "controller")], [])
    assert "controller" in puml


def test_control_structure_control_action_edge() -> None:
    nodes = [_cs_node("N1", "Ctrl"), _cs_node("N2", "Proc")]
    edges = [_edge("N1", "N2", "control-action", "Apply brake")]
    puml = render_control_structure(nodes, edges)
    assert "-->" in puml
    assert "Apply brake" in puml


def test_control_structure_feedback_edge_reversed() -> None:
    nodes = [_cs_node("N1", "Ctrl"), _cs_node("N2", "Proc")]
    edges = [_edge("N1", "N2", "feedback", "Speed signal")]
    puml = render_control_structure(nodes, edges)
    assert "-->" in puml
    assert "Speed signal" in puml
    lines = puml.splitlines()
    feedback_line = next((line for line in lines if "Speed signal" in line), "")
    src_alias = "N_N2"
    tgt_alias = "N_N1"
    assert src_alias in feedback_line and tgt_alias in feedback_line


def test_control_structure_edge_between_non_cs_nodes_excluded() -> None:
    cs_node = _cs_node("N1", "Controller")
    non_cs = {"node_id": "N2", "node_type": "hazard", "name": "Hazard"}
    edges = [_edge("N1", "N2", "leads-to")]
    puml = render_control_structure([cs_node, non_cs], edges)
    assert "leads-to" not in puml


def test_control_structure_alias_safe() -> None:
    node = _cs_node("NOD@1234567890.AbCdEf", "My Node")
    puml = render_control_structure([node], [])
    assert "NOD@1234567890.AbCdEf" not in puml
    assert "N_NOD_1234567890_AbCdEf" in puml


# ── render_uca_matrix ─────────────────────────────────────────────────────────

def test_uca_matrix_empty_renders_note() -> None:
    puml = render_uca_matrix([])
    assert "No unsafe control actions found" in puml
    assert "@startuml" in puml
    assert "@enduml" in puml


def test_uca_matrix_single_uca() -> None:
    puml = render_uca_matrix([_uca("U1", "Brake applied too early", "wrong-timing")])
    assert "wrong-timing" in puml
    assert "Brake applied too early" in puml


def test_uca_matrix_grouped_by_uca_type() -> None:
    ucas = [
        _uca("U1", "UCA omission 1", "omission"),
        _uca("U2", "UCA omission 2", "omission"),
        _uca("U3", "UCA commission 1", "commission"),
    ]
    puml = render_uca_matrix(ucas)
    assert "omission" in puml
    assert "commission" in puml
    assert "UCA omission 1" in puml
    assert "UCA omission 2" in puml
    assert "UCA commission 1" in puml


def test_uca_matrix_non_uca_nodes_ignored() -> None:
    nodes = [
        _uca("U1", "A UCA", "omission"),
        {"node_id": "N1", "node_type": "hazard", "name": "Not a UCA"},
    ]
    puml = render_uca_matrix(nodes)
    assert "Not a UCA" not in puml
    assert "A UCA" in puml


def test_uca_matrix_unspecified_uca_type_fallback() -> None:
    uca = {"node_id": "U1", "node_type": "unsafe-control-action", "name": "Unknown UCA", "uca_type": ""}
    puml = render_uca_matrix([uca])
    assert "unspecified" in puml
    assert "Unknown UCA" in puml


def test_uca_matrix_projection_includes_actions_and_ucas_only() -> None:
    nodes = [
        {"node_id": "CA1", "node_type": "control-action", "name": "Brake"},
        _uca("U1", "Brake omitted"),
        {"node_id": "H1", "node_type": "hazard", "name": "Collision"},
    ]
    assert [n["node_id"] for n in uca_matrix_nodes(nodes)] == ["CA1", "U1"]


def test_bowtie_projection_maps_assurance_causal_chain() -> None:
    nodes = [
        _uca("U1", "Brake omitted"),
        {"node_id": "H1", "node_type": "hazard", "name": "Collision"},
        {"node_id": "L1", "node_type": "loss", "name": "Injury"},
        {"node_id": "CA1", "node_type": "control-action", "name": "Brake"},
    ]
    projected = bowtie_nodes(nodes)
    assert [n["node_id"] for n in projected] == ["U1", "H1", "L1"]
    puml = render_bowtie(projected, [
        _edge("U1", "H1", "violates"),
        _edge("H1", "L1", "leads-to"),
    ])
    assert "<<threat>>" in puml
    assert "<<top-event>>" in puml
    assert "<<consequence>>" in puml
    assert "violates" in puml
