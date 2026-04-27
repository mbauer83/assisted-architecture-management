"""query_scaffold_tools.py — artifact_diagram_scaffold MCP tool.

Generates a ready-to-edit PlantUML skeleton from a list of entity IDs:
all entity declarations, all known connections between them, visible domain
groupings for 90° routing, and hidden layout chains within each group.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.application.artifact_parsing import extract_archimate_label_alias
from src.domain.archimate_relation_rendering import render_archimate_relation
from src.domain.ontology_loader import CONNECTION_TYPES, DOMAIN_GROUPING, ENTITY_TYPES
from src.domain.ontology_loader import DOMAIN_ORDER as _DOMAIN_ORDER_LOWER
from src.infrastructure.mcp.artifact_mcp.context import (
    RepoScope,
    repo_cached,
    resolve_repo_roots,
    roots_key,
)
from src.infrastructure.mcp.artifact_mcp.tool_annotations import READ_ONLY

# conn_short_name → PUML arrow (archimate connections only)
_ARROW: dict[str, str] = {
    ct.artifact_type.split("-", 1)[1]: ct.puml_arrow
    for ct in CONNECTION_TYPES.values()
    if ct.conn_lang == "archimate"
}

# conn_dir → PUML stereotype label (absent → no label)
_LABEL: dict[str, str] = {
    "triggering": "<<Triggering>>",
    "flow": "<<Flow>>",
    "influence": "<<Influence>>",
    "assignment": "<<Assignment>>",
}

_DOMAIN_ORDER = [d.title() for d in _DOMAIN_ORDER_LOWER]
_ENTITY_TYPE_ORDER = list(ENTITY_TYPES)


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
    return info.domain_dir.capitalize() if info else "Common"


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


def _conn_type_from_dir(conn_dir: str) -> str:
    return f"archimate-{conn_dir}"


def _pluralize_label(label: str) -> str:
    words = label.split()
    if not words:
        return label
    last = words[-1]
    lower = last.lower()
    if lower.endswith(("s", "x", "z")) or lower.endswith(("ch", "sh")):
        last = last + "es"
    elif lower.endswith("y") and (len(lower) == 1 or lower[-2] not in "aeiou"):
        last = last[:-1] + "ies"
    else:
        last = last + "s"
    words[-1] = last
    return " ".join(words)


def _type_group_label(artifact_type: str) -> str:
    info = ENTITY_TYPES.get(artifact_type)
    if info and info.archimate_element_type:
        return _pluralize_label(info.archimate_element_type)
    return _pluralize_label(artifact_type.replace("-", " ").title())


def _insert_arrow_direction(arrow: str, direction: str) -> str:
    import re

    if "[hidden]" in arrow or re.search(r"(up|down|left|right)", arrow):
        return arrow
    match = re.match(r"(.*\])(.+)", arrow)
    if match:
        return match.group(1) + direction + match.group(2)
    if arrow.startswith("."):
        return "." + direction + arrow[1:]
    if arrow.startswith("-"):
        rest = arrow[1:]
        sep = "" if rest.startswith("-") else "-"
        return "-" + direction + sep + rest
    return arrow


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
        lines.extend(
            _emit_entity(child, children_map.get(child["display_alias"], []), inner, children_map)
        )
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
                children_map.setdefault(conn["source_alias"], []).append(
                    alias_to_entity[child_alias]
                )
                comp_children.add(child_alias)

    # Top-level per domain — exclude direct composition children
    by_domain: dict[str, list[dict]] = {}
    for e in entities:
        if e["display_alias"] not in comp_children:
            by_domain.setdefault(_domain(e["artifact_type"]), []).append(e)

    dir_kw = "top to bottom" if direction == "top_to_bottom" else "left to right"
    multi = len(by_domain) > 1
    ordered = [d for d in _DOMAIN_ORDER if d in by_domain] + [
        d for d in by_domain if d not in _DOMAIN_ORDER
    ]

    lines: list[str] = [
        f"@startuml {name.lower().replace(' ', '-')}",
        "!include ../_archimate-stereotypes.puml",
        "",
        f"{dir_kw} direction",
        "",
        f"title {name}",
        "",
    ]

    layout_lines: list[str] = []
    group_index_by_alias: dict[str, int] = {}
    if len(ordered) == 1:
        domain = ordered[0]
        grouping = DOMAIN_GROUPING.get(domain.lower(), "Grouping")
        lines[3] = "top to bottom direction"
        type_groups: dict[str, list[dict]] = {}
        for e in by_domain[domain]:
            type_groups.setdefault(e["artifact_type"], []).append(e)
        ordered_types = [t for t in _ENTITY_TYPE_ORDER if t in type_groups]
        for artifact_type in type_groups:
            if artifact_type not in ordered_types:
                ordered_types.append(artifact_type)
        prev_anchor_alias: str | None = None
        for idx, artifact_type in enumerate(ordered_types):
            elems = type_groups[artifact_type]
            lines.append(f'rectangle "{_type_group_label(artifact_type)}" <<{grouping}>> {{')
            for e in elems:
                lines.extend(
                    _emit_entity(e, children_map.get(e["display_alias"], []), "  ", children_map)
                )
                group_index_by_alias[e["display_alias"]] = idx
            lines.append("}")
            tl_aliases = [e["display_alias"] for e in elems]
            hidden_dir = "right" if idx % 2 == 0 else "down"
            for i in range(len(tl_aliases) - 1):
                layout_lines.append(f"{tl_aliases[i]} -[hidden]{hidden_dir}- {tl_aliases[i + 1]}")
            if prev_anchor_alias and tl_aliases:
                layout_lines.append(f"{prev_anchor_alias} -[hidden]down- {tl_aliases[0]}")
            if tl_aliases:
                prev_anchor_alias = tl_aliases[-1]
            lines.append("")
    else:
        for domain in ordered:
            elems = by_domain[domain]
            indent = "  " if multi else ""
            if multi:
                grouping = DOMAIN_GROUPING.get(domain.lower(), "Grouping")
                lines.append(f'rectangle "{domain}" <<{grouping}>> {{')
            for e in elems:
                lines.extend(
                    _emit_entity(e, children_map.get(e["display_alias"], []), indent, children_map)
                )
            if multi:
                lines.append("}")
            lines.append("")

        hidden_dir = "right" if direction == "top_to_bottom" else "down"
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
            conn_dir = c["conn_dir"]
            if len(ordered) == 1:
                src_group = group_index_by_alias.get(c["source_alias"])
                tgt_group = group_index_by_alias.get(c["target_alias"])
                direction_hint: str | None = None
                if src_group is not None and tgt_group is not None and src_group != tgt_group:
                    direction_hint = "down" if src_group < tgt_group else "up"
                line = render_archimate_relation(
                    c["source_alias"],
                    c["target_alias"],
                    _conn_type_from_dir(conn_dir),
                    direction=direction_hint,
                    label_text="",
                )
                if line is None:
                    arrow = _ARROW.get(conn_dir, "-->")
                    if direction_hint:
                        arrow = _insert_arrow_direction(arrow, direction_hint)
                    label = _LABEL.get(conn_dir, "")
                    parts = [c["source_alias"], arrow, c["target_alias"]]
                    if label:
                        parts.append(f": {label}")
                    line = " ".join(parts)
                if c.get("description"):
                    line += f"  ' {c['description']}"
                lines.append(line)
            else:
                line = render_archimate_relation(
                    c["source_alias"],
                    c["target_alias"],
                    _conn_type_from_dir(conn_dir),
                    label_text="",
                )
                if line is None:
                    line = _conn_line(
                        c["source_alias"], c["conn_dir"], c["target_alias"], c.get("description")
                    )
                    lines.append(line)
                    continue
                if c.get("description"):
                    line += f"  ' {c['description']}"
                lines.append(line)
        lines.append("")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def artifact_diagram_scaffold(
    *,
    entity_ids: list[str],
    diagram_name: str = "Architecture Diagram",
    direction: Literal["top_to_bottom", "left_to_right"] = "top_to_bottom",
    repo_root: str | None = None,
    repo_scope: RepoScope = "both",
) -> dict[str, object]:
    """Generate a PUML scaffold for artifact_create_diagram.

    Looks up each entity by ID, discovers all connections between the given
    entities, groups them by ArchiMate domain, and returns a ready-to-edit
    @startuml…@enduml block.  Pass the returned ``puml`` string directly to
    artifact_create_diagram(puml=...) after making any layout adjustments.
    """
    roots = resolve_repo_roots(
        repo_scope=repo_scope,
        repo_root=repo_root,
        repo_preset=None,
        enterprise_root=None,
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
        entities.append(
            {
                "artifact_id": eid,
                "artifact_type": str(rec.get("artifact_type") or ""),
                "name": str(rec.get("name") or ""),
                "display_alias": alias,
                "display_label": label,
            }
        )

    # Collect connections where both endpoints are in the requested set
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
            conn_dir = conn_rec.conn_type.split("-", 1)[1]
            connections.append(
                {
                    "source_alias": src_alias,
                    "conn_dir": conn_dir,
                    "target_alias": tgt_alias,
                    "description": _extract_prose(conn_rec.content_text),
                }
            )

    puml = _build_puml(
        entities=entities,
        connections=connections,
        name=diagram_name,
        direction=direction,
    )

    return {
        "puml": puml,
        "entities_included": [
            {
                "artifact_id": e["artifact_id"],
                "alias": e["display_alias"],
                "name": e["name"],
                "type": e["artifact_type"],
            }
            for e in entities
        ],
        "connections_included": [
            {
                "source_alias": c["source_alias"],
                "conn_dir": c["conn_dir"],
                "target_alias": c["target_alias"],
            }
            for c in connections
        ],
        "entities_not_found": not_found,
        "entities_missing_alias": missing_alias,
    }


def register_query_scaffold_tools(mcp: FastMCP) -> None:
    mcp.tool(
        name="artifact_diagram_scaffold",
        title="Artifact Query: Diagram Scaffold",
        description=(
            "Generate a ready-to-edit @startuml…@enduml scaffold from a list of entity IDs. "
            "Returns entity declarations, all existing connections between them, "
            "visible domain groupings (for 90° routing), and hidden layout chains. "
            "Pass the returned puml directly to artifact_create_diagram after adjusting layout. "
            "Use direction='left_to_right' for process sequences; "
            "direction='top_to_bottom' (default) for layered cross-domain views."
        ),
        annotations=READ_ONLY,
        structured_output=True,
    )(artifact_diagram_scaffold)
