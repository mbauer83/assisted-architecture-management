"""Derived diagram projectors for the assurance store.

Produces PUML text from live assurance-store data.  Called by the HTTP read
router; never persisted (ephemeral, exposure-policy filtered before call).

Supported diagram IDs:
  bowtie             — causal chain from UCAs/scenarios through hazards to losses
  control-structure  — block diagram of control-structure nodes/actions + their edges
  uca-matrix         — interactive UCA grid data (rendered by the frontend)
"""

from __future__ import annotations

from typing import Any

AVAILABLE_DIAGRAMS: list[dict[str, str]] = [
    {
        "diagram_id": "bowtie",
        "title": "Bowtie",
        "description": "Threat pathways, hazards, controls, and consequences from the assurance store.",
    },
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

ASSURANCE_SURFACE_DIAGRAM_TYPES = frozenset({"bowtie", "control-structure", "uca-matrix"})


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

    Control-structure nodes and control actions are rendered. Only edges whose
    endpoints are present in the projection are included.
    """
    lines: list[str] = ["@startuml", "skinparam rectangle {", "  BackgroundColor #EBF5FB", "  BorderColor #2E86C1", "}"]

    cs_nodes = [
        n for n in nodes
        if str(n.get("node_type", "")) in {"control-structure-node", "control-action"}
    ]
    cs_ids = {str(n["node_id"]) for n in cs_nodes}

    for node in cs_nodes:
        alias = _safe_alias(str(node["node_id"]))
        name = _quote(str(node.get("name", node["node_id"])))
        role = str(node.get("node_role") or "").replace("-", " ")
        role_suffix = f"\\n<<{role}>>" if role else ""
        keyword = "control" if str(node.get("node_type", "")) == "control-action" else "rectangle"
        lines.append(f'{keyword} {name}{role_suffix if role_suffix else ""} as {alias}')

    for edge in edges:
        src = str(edge.get("source_id", ""))
        tgt = str(edge.get("target_id", ""))
        if src not in cs_ids or tgt not in cs_ids:
            continue
        src_alias = _safe_alias(src)
        tgt_alias = _safe_alias(tgt)
        conn_type = str(edge.get("conn_type", ""))
        label = str(edge.get("name") or edge.get("label") or conn_type)
        if conn_type == "feedback":
            arrow = "-->"
            label_part = f" : {_quote(label)}" if label else ""
            lines.append(f"{tgt_alias} {arrow} {src_alias}{label_part}")
        elif conn_type in {"issues", "acts-on", "control-action"}:
            label_part = f" : {_quote(label)}" if label else ""
            lines.append(f"{src_alias} --> {tgt_alias}{label_part}")
        else:
            label_part = f" : {_quote(conn_type)}" if conn_type else ""
            lines.append(f"{src_alias} --> {tgt_alias}{label_part}")

    if not cs_nodes:
        lines.append('note "No control-structure nodes found." as N1')

    lines.append("@enduml")
    return "\n".join(lines)


_BOWTIE_NODE_ROLES = {
    "unsafe-control-action": "threat",
    "loss-scenario": "threat",
    "assurance-constraint": "barrier_left",
    "hazard": "top_event",
    "loss": "consequence",
}

_BOWTIE_ROLE_STYLE = {
    "threat": ("component", "#FFD0D0", "<<threat>>"),
    "barrier_left": ("card", "#D0FFD0", "<<barrier>>"),
    "top_event": ("component", "#FFB060", "<<top-event>>"),
    "consequence": ("component", "#FFD0D0", "<<consequence>>"),
}


def bowtie_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return assurance nodes participating in the store-grounded bowtie projection."""
    return [n for n in nodes if str(n.get("node_type", "")) in _BOWTIE_NODE_ROLES]


def render_bowtie(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    """Render the assurance causal chain as a selectable bowtie projection."""
    projected = bowtie_nodes(nodes)
    projected_ids = {str(n["node_id"]) for n in projected}
    ordered = sorted(
        projected,
        key=lambda n: (
            ("threat", "barrier_left", "top_event", "consequence").index(
                _BOWTIE_NODE_ROLES[str(n.get("node_type", ""))]
            ),
            str(n.get("name", "")),
        ),
    )
    lines = ["@startuml", "left to right direction"]
    for node in ordered:
        role = _BOWTIE_NODE_ROLES[str(node.get("node_type", ""))]
        keyword, colour, stereotype = _BOWTIE_ROLE_STYLE[role]
        lines.append(
            f"{keyword} {_quote(str(node.get('name', node['node_id'])))} "
            f"{stereotype} as {_safe_alias(str(node['node_id']))} {colour}"
        )
    for edge in edges:
        source_id = str(edge.get("source_id", ""))
        target_id = str(edge.get("target_id", ""))
        if source_id not in projected_ids or target_id not in projected_ids:
            continue
        label = str(edge.get("label") or edge.get("name") or edge.get("conn_type") or "")
        suffix = f" : {_quote(label)}" if label else ""
        lines.append(f"{_safe_alias(source_id)} --> {_safe_alias(target_id)}{suffix}")
    if not projected:
        lines.append('note "No bowtie assurance nodes found." as N1')
    lines.append("@enduml")
    return "\n".join(lines)


def uca_matrix_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return control actions and UCAs used by the interactive matrix."""
    return [
        n for n in nodes
        if str(n.get("node_type", "")) in {"control-action", "unsafe-control-action"}
    ]


def render_uca_matrix(nodes: list[dict[str, Any]]) -> str:
    """Retain the text projector for exports and backwards-compatible tests.

    The assurance GUI uses ``uca_matrix_nodes`` plus concern edges to render
    the selectable grid; it does not use this PlantUML note representation.
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
