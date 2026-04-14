"""parse_existing.py — Parse existing entity/diagram files for editing.

Extracts structured components from entity .md files so that edit operations
can merge partial updates and re-format via the canonical formatter.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml  # type: ignore[import-untyped]


@dataclass
class ParsedEntity:
    """Structured representation of an existing entity file."""

    frontmatter: dict[str, object]
    summary: str | None
    properties: dict[str, str]
    notes: str | None
    display_archimate: dict[str, str]
    raw_text: str  # original file content for fallback


@dataclass
class ParsedOutgoing:
    """Structured representation of an existing .outgoing.md file."""

    frontmatter: dict[str, object]
    connections: list[dict[str, str]]  # each has connection_type, target_entity, description
    raw_text: str


@dataclass
class ParsedDiagram:
    """Structured representation of an existing diagram .puml file."""

    frontmatter: dict[str, object]
    puml_body: str  # everything after the frontmatter closing ---
    raw_text: str


def parse_entity_file(path: Path) -> ParsedEntity:
    """Parse an entity .md file into structured components."""
    text = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)

    # Extract sections by markers
    content_section = _extract_between(text, "<!-- §content -->", "<!-- §display -->")
    display_section = _extract_after(text, "<!-- §display -->")

    summary = _extract_summary(content_section, frontmatter.get("name", ""))
    properties = _extract_properties(content_section)
    notes = _extract_notes(content_section)
    display_archimate = _extract_display_archimate(display_section)

    return ParsedEntity(
        frontmatter=frontmatter,
        summary=summary,
        properties=properties,
        notes=notes,
        display_archimate=display_archimate,
        raw_text=text,
    )


def parse_outgoing_file(path: Path) -> ParsedOutgoing:
    """Parse an .outgoing.md file into structured components."""
    text = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)

    connections_section = _extract_after(text, "<!-- §connections -->")
    connections = _parse_connection_sections(connections_section)

    return ParsedOutgoing(
        frontmatter=frontmatter,
        connections=connections,
        raw_text=text,
    )


def parse_diagram_file(path: Path) -> ParsedDiagram:
    """Parse a diagram .puml file into structured components."""
    text = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)

    # PUML body is everything after the closing --- of frontmatter
    fm_end = _frontmatter_end_pos(text)
    puml_body = text[fm_end:] if fm_end else text

    return ParsedDiagram(
        frontmatter=frontmatter,
        puml_body=puml_body,
        raw_text=text,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict[str, object]:
    """Extract YAML frontmatter from between --- markers."""
    m = re.match(r"^---\n(.*?\n)---\n", text, re.DOTALL)
    if not m:
        return {}
    return yaml.safe_load(m.group(1)) or {}


def _frontmatter_end_pos(text: str) -> int:
    """Return the character position right after the closing --- of frontmatter."""
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return m.end() if m else 0


def _extract_between(text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between two markers (exclusive of markers)."""
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start == -1 or end == -1:
        return ""
    return text[start + len(start_marker) : end]


def _extract_after(text: str, marker: str) -> str:
    """Extract text after a marker (exclusive of marker)."""
    pos = text.find(marker)
    if pos == -1:
        return ""
    return text[pos + len(marker) :]


def _extract_summary(content_section: str, entity_name: str) -> str | None:
    """Extract the summary paragraph(s) between the heading and ## Properties."""
    lines = content_section.strip().splitlines()
    collecting = False
    summary_lines: list[str] = []

    for line in lines:
        if line.startswith("## ") and not collecting:
            # This is the entity heading — start collecting after it
            collecting = True
            continue
        if collecting:
            if line.startswith("## "):
                # Hit the next section (Properties, Notes, etc.)
                break
            summary_lines.append(line)

    text = "\n".join(summary_lines).strip()
    return text if text else None


def _extract_properties(content_section: str) -> dict[str, str]:
    """Extract key-value pairs from the Properties table."""
    props: dict[str, str] = {}
    lines = content_section.splitlines()
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped == "## Properties":
            in_table = True
            continue
        if in_table and stripped.startswith("## "):
            break
        if in_table and stripped.startswith("|") and "---" not in stripped:
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if len(cells) >= 2 and cells[0] not in ("Attribute", "(none)"):
                props[cells[0]] = cells[1]

    return props


def _extract_notes(content_section: str) -> str | None:
    """Extract content from the Notes section."""
    lines = content_section.splitlines()
    in_notes = False
    notes_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "## Notes":
            in_notes = True
            continue
        if in_notes:
            if stripped.startswith("## "):
                break
            notes_lines.append(line)

    text = "\n".join(notes_lines).strip()
    return text if text else None


def _extract_display_archimate(display_section: str) -> dict[str, str]:
    """Extract the archimate display YAML block."""
    m = re.search(r"```yaml\n(.*?)```", display_section, re.DOTALL)
    if not m:
        return {}
    parsed = yaml.safe_load(m.group(1))
    return {str(k): str(v) for k, v in parsed.items()} if parsed else {}


def _parse_connection_sections(connections_text: str) -> list[dict[str, str]]:
    """Parse H3 connection sections from the connections area of an .outgoing.md file."""
    connections: list[dict[str, str]] = []
    # Split by ### headers
    sections = re.split(r"^### ", connections_text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # First line is the header: "{connection_type} → {target_entity}"
        first_line, *rest = section.split("\n", 1)
        m = re.match(r"^(.+?)\s*→\s*(.+)$", first_line.strip())
        if not m:
            continue

        connection_type = m.group(1).strip()
        target_entity = m.group(2).strip()
        description = rest[0].strip() if rest else ""

        connections.append({
            "connection_type": connection_type,
            "target_entity": target_entity,
            "description": description,
        })

    return connections
