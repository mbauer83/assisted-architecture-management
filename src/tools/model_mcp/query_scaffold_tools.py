"""query_scaffold_tools.py — model_diagram_scaffold MCP tool.

Generates a ready-to-edit PlantUML skeleton from a list of entity IDs:
all entity declarations, all known connections between them, visible domain
groupings for 90° routing, and hidden layout chains within each group.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.tools.model_mcp.context import (
    RepoPreset,
    RepoScope,
    repo_cached,
    resolve_repo_roots,
    roots_key,
)
from src.common.ontology_loader import CONNECTION_TYPES, DOMAIN_GROUPING, ENTITY_TYPES
from src.common.model_query_parsing import extract_archimate_label_alias


# conn_dir → PUML arrow (derived from ontology at module load)
_ARROW: dict[str, str] = {
    ct.conn_dir: ct.puml_arrow
    for ct in CONNECTION_TYPES.values()
    if ct.conn_lang == "archimate" and ct.conn_dir
}

# conn_dir → PUML stereotype label (absent → no label)
_LABEL: dict[str, str] = {
    "triggering": "<<Triggering>>",
    "flow": "<<Flow>>",
    "influence": "<<Influence>>",
    "assignment": "<<Assignment>>",
}

from src.common.ontology_loader import DOMAIN_ORDER as _DOMAIN_ORDER_LOWER
_DOMAIN_ORDER = [d.title() for d in _DOMAIN_ORDER_LOWER]


def _extract_prose(text: str | None) -> str | None:
    """Return the first prose sentence from a content string, stripping code blocks."""
    if not text:
        return None
    import re
    cleaned = re.sub(r"```[\s\S]*?```", "", text).strip()
    for line in cleaned.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "|", "-", ">")):
            return line[:80]
    return None


def _domain(artifact_type: str) -> str:
    info = ENTITY_TYPES.get(artifact_type)
    return info.archimate_domain if info else "Common"


_JUNCTION_TYPES = frozenset({"and-junction", "or-junction"})


def _entity_decl(artifact_type: str, label: str, alias: str) -> str:
    if artifact_type in _JUNCTION_TYPES:
        return f'circle " " as {alias}'
    info = ENTITY_TYPES.get(artifact_type)
    if not info or not info.archimate_element_type:
        return f'rectangle "{label}" as {alias}'
    et = info.archimate_element_type
    if info.has_sprite:
        return f'rectangle "<$archimate_{et}{{scale=1.5}}> {label}" <<{et}>> as {alias}'
    return f'rectangle "{label}" <<{et}>> as {alias}'


def _conn_line(src: str, conn_dir: str, tgt: str, note: str | None = None) -> str:
    arrow = _ARROW.get(conn_dir, "-->")
    label = _LABEL.get(conn_dir, "")
    parts = [src, arrow, tgt]
    if label:
        parts.append(f": {label}")
    line = " ".join(parts)
    if note:
        line += f"  ' {note}"
    return line


def _emit_entity(
    e: dict,
    children: list[dict],
    indent: str,
    children_map: dict[str, list[dict]],
) -> list[str]:
    """Return PUML lines for one entity, recursively nesting composition children."""
    decl = _entity_decl(e["artifact_type"], e["display_label"], e["display_alias"])
    if not children:
        return [f"{indent}{decl}"]
    child_aliases = [c["display_alias"] for c in children]
    lines = [f"{indent}{decl} {{"]
    inner = indent + "  "
    for child in children:
        lines.extend(_emit_entity(child, children_map.get(child["display_alias"], []), inner, children_map))
    for i in range(len(child_aliases) - 1):
        lines.append(f"{inner}{child_aliases[i]} -[hidden]right- {child_aliases[i + 1]}")
    lines.append(f"{indent}}}")
    return lines


def _build_puml(
    *,
    entities: list[dict],
    connections: list[dict],
    name: str,
    direction: str,
) -> str:
    alias_to_entity = {e["display_alias"]: e for e in entities}

    # Build composition/aggregation hierarchy for visual nesting
    children_map: dict[str, list[dict]] = {}
    comp_children: set[str] = set()
    for conn in connections:
        if conn["conn_dir"] in ("composition", "aggregation"):
            child_alias = conn["target_alias"]
            if child_alias in alias_to_entity:
                children_map.setdefault(conn["source_alias"], []).append(alias_to_entity[child_alias])
                comp_children.add(child_alias)

    # Top-level per domain — exclude direct composition children
    by_domain: dict[str, list[dict]] = {}
    for e in entities:
        if e["display_alias"] not in comp_children:
            by_domain.setdefault(_domain(e["artifact_type"]), []).append(e)

    dir_kw = "top to bottom" if direction == "top_to_bottom" else "left to right"
    multi = len(by_domain) > 1
    ordered = [d for d in _DOMAIN_ORDER if d in by_domain] + [d for d in by_domain if d not in _DOMAIN_ORDER]

    lines: list[str] = [
        f"@startuml {name.lower().replace(' ', '-')}",
        "!include ../_archimate-stereotypes.puml",
        "",
        f"{dir_kw} direction",
        "",
        f"title {name}",
        "",
    ]

    for domain in ordered:
        elems = by_domain[domain]
        indent = "  " if multi else ""
        if multi:
            grouping = DOMAIN_GROUPING.get(domain.lower(), "Grouping")
            lines.append(f'rectangle "{domain}" <<{grouping}>> {{')
        for e in elems:
            lines.extend(_emit_entity(e, children_map.get(e["display_alias"], []), indent, children_map))
        if multi:
            lines.append("}")
        lines.append("")

    # Hidden chains for top-level elements within each domain group
    hidden_dir = "right" if direction == "top_to_bottom" else "down"
    layout_lines: list[str] = []
    for domain in ordered:
        tl_aliases = [e["display_alias"] for e in by_domain[domain]]
        for i in range(len(tl_aliases) - 1):
            layout_lines.append(f"{tl_aliases[i]} -[hidden]{hidden_dir}- {tl_aliases[i + 1]}")
    if layout_lines:
        lines.append("' --- Layout: spread top-level elements ---")
        lines.extend(layout_lines)
        lines.append("")

    # Non-structural connections (composition/aggregation shown via nesting)
    non_comp = [c for c in connections if c["conn_dir"] not in ("composition", "aggregation")]
    if non_comp:
        lines.append("' --- Connections ---")
        for c in non_comp:
            lines.append(_conn_line(c["source_alias"], c["conn_dir"], c["target_alias"], c.get("description")))
        lines.append("")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def model_diagram_scaffold(
    *,
    entity_ids: list[str],
    diagram_name: str = "Architecture Diagram",
    direction: Literal["top_to_bottom", "left_to_right"] = "top_to_bottom",
    repo_root: str | None = None,
    repo_preset: RepoPreset | None = None,
    enterprise_root: str | None = None,
    repo_scope: RepoScope = "both",
) -> dict[str, object]:
    """Generate a PUML scaffold for model_create_diagram.

    Looks up each entity by ID, discovers all connections between the given
    entities, groups them by ArchiMate domain, and returns a ready-to-edit
    @startuml…@enduml block.  Pass the returned ``puml`` string directly to
    model_create_diagram(puml=...) after making any layout adjustments.
    """
    roots = resolve_repo_roots(
        repo_scope=repo_scope,
        repo_root=repo_root,
        repo_preset=repo_preset,
        enterprise_root=enterprise_root,
    )
    repo = repo_cached(roots_key(roots))

    entities: list[dict] = []
    not_found: list[str] = []
    missing_alias: list[str] = []
    id_set: set[str] = set(entity_ids)

    for eid in entity_ids:
        rec = repo.read_artifact(eid, mode="full")
        if rec is None:
            not_found.append(eid)
            continue
        blocks = rec.get("display_blocks") or {}
        raw_label, alias = extract_archimate_label_alias(blocks)  # type: ignore[arg-type]
        label = raw_label or str(rec.get("name") or eid)
        if not alias:
            missing_alias.append(eid)
            continue
        entities.append({
            "artifact_id": eid,
            "artifact_type": str(rec.get("artifact_type") or ""),
            "name": str(rec.get("name") or ""),
            "display_alias": alias,
            "display_label": label,
        })

    # Collect connections where both endpoints are in the requested set
    alias_to_id = {e["display_alias"]: e["artifact_id"] for e in entities}
    id_to_alias = {e["artifact_id"]: e["display_alias"] for e in entities}

    connections: list[dict] = []
    seen: set[str] = set()
    for eid in id_set & set(id_to_alias):
        for conn_rec in repo.find_connections_for(eid, direction="outbound"):
            if conn_rec.target not in id_set:
                continue
            src_alias = id_to_alias.get(conn_rec.source, "")
            tgt_alias = id_to_alias.get(conn_rec.target, "")
            if not src_alias or not tgt_alias:
                continue
            key = f"{conn_rec.artifact_id}"
            if key in seen:
                continue
            seen.add(key)
            ct = CONNECTION_TYPES.get(conn_rec.conn_type)
            conn_dir = ct.conn_dir if ct else conn_rec.conn_type
            connections.append({
                "source_alias": src_alias,
                "conn_dir": conn_dir,
                "target_alias": tgt_alias,
                "description": _extract_prose(conn_rec.content_text),
            })

    puml = _build_puml(
        entities=entities,
        connections=connections,
        name=diagram_name,
        direction=direction,
    )

    return {
        "puml": puml,
        "entities_included": [
            {"artifact_id": e["artifact_id"], "alias": e["display_alias"],
             "name": e["name"], "type": e["artifact_type"]}
            for e in entities
        ],
        "connections_included": [
            {"source_alias": c["source_alias"], "conn_dir": c["conn_dir"],
             "target_alias": c["target_alias"]}
            for c in connections
        ],
        "entities_not_found": not_found,
        "entities_missing_alias": missing_alias,
    }


def register_query_scaffold_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="model_diagram_scaffold",
        title="Model Query: Diagram Scaffold",
        description=(
            "Generate a ready-to-edit @startuml…@enduml scaffold from a list of entity IDs. "
            "Returns entity declarations, all existing connections between them, "
            "visible domain groupings (for 90° routing), and hidden layout chains. "
            "Pass the returned puml directly to model_create_diagram after adjusting layout. "
            "Use direction='left_to_right' for process sequences; "
            "direction='top_to_bottom' (default) for layered cross-domain views."
        ),
        structured_output=True,
    )(model_diagram_scaffold)
