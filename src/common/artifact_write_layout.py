"""Auto-layout engine for PlantUML diagrams.

Analyzes diagram structure (groupings, elements, connections) and inserts
layout optimizations for ortho routing:

- Hidden links spread elements within groupings (orthogonal to main flow)
- Arrow direction hints guide inter-layer connection routing
- Direction selection uses heuristics based on group/element counts
"""

import re
from dataclasses import dataclass, field


@dataclass
class _GroupInfo:
    """A top-level rectangle grouping and its contained element aliases."""

    label: str
    aliases: list[str] = field(default_factory=list)
    index: int = 0


def _parse_groupings(puml: str) -> list[_GroupInfo]:
    """Extract top-level rectangle groupings and their nested element aliases.

    Handles arbitrary nesting depth — all element aliases within a top-level
    grouping are collected regardless of sub-grouping structure.
    """
    lines = puml.split("\n")
    result: list[_GroupInfo] = []
    current: _GroupInfo | None = None
    depth = 0
    group_idx = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("'") or not stripped:
            continue

        # Top-level grouping: rectangle "..." <<...>> ... {
        if depth == 0 and "rectangle" in stripped and "{" in stripped:
            m = re.match(r'rectangle\s+"([^"]+)"', stripped)
            if m:
                current = _GroupInfo(label=m.group(1), index=group_idx)
                group_idx += 1
                result.append(current)

        # Element with alias inside a grouping (has `as ALIAS`, no trailing `{`)
        # Note: sprite labels like <$name{scale=0.9}> contain `{` mid-line, so we
        # only exclude lines where `{` appears at the end (container openings).
        # Strip quoted strings before searching to avoid matching "as" inside label text
        # (e.g. "AI-Assisted Development as Dominant Production Mode").
        elif current is not None and depth > 0:
            without_quotes = re.sub(r'"[^"]*"', '""', stripped)
            m = re.search(r"\bas\s+(\w+)", without_quotes)
            if m and not re.search(r"\{\s*$", stripped):
                current.aliases.append(m.group(1))

        depth += stripped.count("{") - stripped.count("}")

        if current is not None and depth == 0:
            current = None

    return result


def _detect_direction(puml: str) -> str | None:
    """Detect an existing direction directive in the PUML body."""
    m = re.search(r"(top to bottom|left to right)\s+direction", puml)
    return m.group(1) if m else None


def _select_direction(groups: list[_GroupInfo]) -> str:
    """Select optimal direction based on diagram structure metrics.

    Heuristics:
    - >= 2 top-level groupings or max elements per group <= 5: top to bottom
      (standard ArchiMate layered layout, elements spread horizontally)
    - <= 1 grouping with many (>= 6) elements: left to right
    """
    n_groups = len(groups)
    max_elems = max((len(g.aliases) for g in groups), default=0)

    if n_groups <= 1 and max_elems >= 6:
        return "left to right"
    return "top to bottom"


# Regex matching a connection line:  ALIAS <arrow> ALIAS [: label]
# Arrow must start and end with a connector character.
_CONN_LINE_RE = re.compile(
    r"^(\s*)"  # (1) leading whitespace
    r"(\w+)"  # (2) source alias
    r"(\s+)"  # (3) space
    r"([-.*|o<>][^\s]*?[-.*|o<>])"  # (4) arrow (bracket/direction/color inside)
    r"(\s+)"  # (5) space
    r"(\w+)"  # (6) target alias
    r"(\s*(?::\s*.*)?)$"  # (7) optional : label
)

_MACRO_CONN_RE = re.compile(
    r"^(\s*)"
    r"(Rel_[A-Za-z0-9]+)"
    r"(?:_(Up|Down|Left|Right))?"
    r"\(\s*(\w+)\s*,\s*(\w+)(.*)\)\s*$"
)


def _insert_arrow_direction(arrow: str, direction: str) -> str:
    """Insert a direction hint into PlantUML arrow syntax.

    Returns the arrow unchanged if it already contains a direction keyword
    or is a hidden link.
    """
    if "[hidden]" in arrow:
        return arrow
    if re.search(r"(up|down|left|right)", arrow):
        return arrow

    # Bracket syntax: -[#color]-> → -[#color]down->
    m = re.match(r"(.*\])(.+)", arrow)
    if m:
        return m.group(1) + direction + m.group(2)

    # Dot arrow: ..> → .down.>
    if arrow.startswith("."):
        return "." + direction + arrow[1:]

    # Dash arrow: --> → -down->, -|> → -down-|>, -- → -down-
    if arrow.startswith("-"):
        rest = arrow[1:]
        sep = "" if rest.startswith("-") else "-"
        return "-" + direction + sep + rest

    return arrow


def optimize_puml_layout(puml_body: str) -> str:
    """Optimize PlantUML diagram layout for ortho routing.

    Analyzes the grouping/element/connection structure and inserts:
    1. A direction directive (if not already present)
    2. Hidden links to spread elements within each grouping
    3. Arrow direction hints on inter-grouping connections

    Idempotent: returns the body unchanged if hidden links already exist
    or if the diagram has no groupings to optimize.

    Args:
        puml_body: PUML content including @startuml/@enduml markers.

    Returns:
        Optimized PUML body.
    """
    groups = _parse_groupings(puml_body)

    if not groups or "[hidden]" in puml_body:
        return puml_body

    # Only optimize groups that have 2+ elements to spread
    spreadable = [g for g in groups if len(g.aliases) >= 2]
    if not spreadable:
        return puml_body

    # --- Direction ---
    existing_dir = _detect_direction(puml_body)
    direction = existing_dir or _select_direction(groups)
    spread_dir = "right" if direction == "top to bottom" else "down"
    flow_dir = "down" if direction == "top to bottom" else "right"
    reverse_dir = "up" if direction == "top to bottom" else "left"

    # Alias → grouping index for arrow direction hints
    alias_to_group: dict[str, int] = {}
    for g in groups:
        for alias in g.aliases:
            alias_to_group[alias] = g.index

    lines = puml_body.split("\n")

    # --- Phase 1: Insert direction directive if missing ---
    if existing_dir is None:
        insert_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "@startuml" in stripped or stripped.startswith("!include"):
                insert_idx = i + 1
        lines.insert(insert_idx, "")
        lines.insert(insert_idx + 1, f"{direction} direction")

    # --- Phase 2: Add arrow direction hints to inter-grouping connections ---
    for i, line in enumerate(lines):
        m = _CONN_LINE_RE.match(line)
        if m:
            src_alias = m.group(2)
            arrow = m.group(4)
            tgt_alias = m.group(6)

            src_group = alias_to_group.get(src_alias)
            tgt_group = alias_to_group.get(tgt_alias)

            if src_group is None or tgt_group is None:
                continue
            if src_group == tgt_group:
                continue  # Intra-grouping — don't add layer hints

            hint = flow_dir if src_group < tgt_group else reverse_dir
            new_arrow = _insert_arrow_direction(arrow, hint)
            if new_arrow != arrow:
                lines[i] = (
                    m.group(1)
                    + m.group(2)
                    + m.group(3)
                    + new_arrow
                    + m.group(5)
                    + m.group(6)
                    + m.group(7)
                )
            continue

        macro = _MACRO_CONN_RE.match(line)
        if not macro:
            continue

        src_alias = macro.group(4)
        tgt_alias = macro.group(5)
        src_group = alias_to_group.get(src_alias)
        tgt_group = alias_to_group.get(tgt_alias)
        if src_group is None or tgt_group is None or src_group == tgt_group:
            continue
        if macro.group(3):
            continue
        hint = flow_dir if src_group < tgt_group else reverse_dir
        lines[i] = (
            macro.group(1)
            + macro.group(2)
            + "_"
            + hint.title()
            + "("
            + src_alias
            + ", "
            + tgt_alias
            + macro.group(6)
            + ")"
        )

    # --- Phase 3: Generate hidden links block ---
    # In TB mode, elements within groupings need horizontal spread (hidden right links).
    # In LR mode, elements already stack vertically by default — adding hidden down
    # links is redundant and can over-constrain Graphviz, causing layout failures.
    if direction == "top to bottom" and spreadable:
        hidden_block: list[str] = [
            "",
            "' --- Auto-layout: spread elements within groupings ---",
        ]
        for g in spreadable:
            for j in range(len(g.aliases) - 1):
                hidden_block.append(f"{g.aliases[j]} -[hidden]{spread_dir}- {g.aliases[j + 1]}")
        hidden_block.append("")

        # Insert after the last top-level closing brace (between declarations and connections)
        insert_at = len(lines) - 1  # fallback: before @enduml
        depth = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            depth += stripped.count("{") - stripped.count("}")
            if depth == 0 and "}" in stripped:
                insert_at = i + 1

        for j, hline in enumerate(hidden_block):
            lines.insert(insert_at + j, hline)

    return "\n".join(lines)
