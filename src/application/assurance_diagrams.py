"""Derived diagram projectors for the assurance store.

Produces PUML text from live assurance-store data.  Called by the HTTP read
router; never persisted (ephemeral, exposure-policy filtered before call).

Supported diagram IDs:
  control-structure  — block diagram of control-structure-nodes + their edges
  uca-matrix         — UCA enumeration note diagram per control-action source
"""

from __future__ import annotations

from typing import Any

AVAILABLE_DIAGRAMS: list[dict[str, str]] = [
    {
        "diagram_id": "control-structure",
        "title": "Control Structure",
        "description": "Block diagram of control-structure nodes with control-action and feedback edges.",
    },
    {
        "diagram_id": "uca-matrix",
        "title": "UCA Matrix",
        "description": "Unsafe Control Actions enumerated per control-action, grouped by UCA type.",
    },
]


def _safe_alias(node_id: str) -> str:
    """Convert a node ID to a valid PlantUML alias."""
    return "N_" + node_id.replace("@", "_").replace(".", "_").replace("-", "_")


def _quote(text: str) -> str:
    """Wrap text in double-quotes, escaping embedded quotes."""
    return '"' + text.replace('"', "'") + '"'


def render_control_structure(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> str:
    """Render a control-structure PUML block diagram.

    Only control-structure-node entities are rendered as blocks.
    Edge types control-action and feedback carry their name as label;
    other edges are rendered as plain arrows.
    """
    lines: list[str] = ["@startuml", "skinparam rectangle {", "  BackgroundColor #EBF5FB", "  BorderColor #2E86C1", "}"]

    cs_nodes = [n for n in nodes if str(n.get("node_type", "")) == "control-structure-node"]
    cs_ids = {str(n["node_id"]) for n in cs_nodes}

    for node in cs_nodes:
        alias = _safe_alias(str(node["node_id"]))
        name = _quote(str(node.get("name", node["node_id"])))
        role = str(node.get("node_role", "")).replace("-", " ")
        role_suffix = f"\\n<<{role}>>" if role else ""
        lines.append(f'rectangle {name}{role_suffix if role_suffix else ""} as {alias}')

    for edge in edges:
        src = str(edge.get("source_id", ""))
        tgt = str(edge.get("target_id", ""))
        if src not in cs_ids or tgt not in cs_ids:
            continue
        src_alias = _safe_alias(src)
        tgt_alias = _safe_alias(tgt)
        conn_type = str(edge.get("conn_type", ""))
        label = str(edge.get("name", conn_type or ""))
        if conn_type == "feedback":
            arrow = "-->"
            label_part = f" : {_quote(label)}" if label else ""
            lines.append(f"{tgt_alias} {arrow} {src_alias}{label_part}")
        elif conn_type == "control-action":
            label_part = f" : {_quote(label)}" if label else ""
            lines.append(f"{src_alias} --> {tgt_alias}{label_part}")
        else:
            label_part = f" : {_quote(conn_type)}" if conn_type else ""
            lines.append(f"{src_alias} --> {tgt_alias}{label_part}")

    if not cs_nodes:
        lines.append('note "No control-structure nodes found." as N1')

    lines.append("@enduml")
    return "\n".join(lines)


def render_uca_matrix(nodes: list[dict[str, Any]]) -> str:
    """Render unsafe control actions grouped by source (control-action name or node_id).

    Grouped by the `uca_type` field; source node is the UCA's associated
    control action (stored as a node field or inferred from name).
    """
    ucas = [n for n in nodes if str(n.get("node_type", "")) == "unsafe-control-action"]

    lines: list[str] = ["@startuml", "title UCA Matrix"]

    if not ucas:
        lines += ['note "No unsafe control actions found." as N1', "@enduml"]
        return "\n".join(lines)

    by_type: dict[str, list[dict[str, Any]]] = {}
    for uca in ucas:
        uca_type = str(uca.get("uca_type", "unspecified")) or "unspecified"
        by_type.setdefault(uca_type, []).append(uca)

    for idx, (uca_type, group) in enumerate(by_type.items()):
        alias = f"UCA_{idx}"
        lines.append(f"note as {alias}")
        lines.append(f"  **{uca_type}**")
        for uca in group:
            name = str(uca.get("name", uca["node_id"]))
            lines.append(f"  — {name}")
        lines.append("end note")

    lines.append("@enduml")
    return "\n".join(lines)
