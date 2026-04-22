"""GUI helper: PUML body generation and ephemeral preview rendering.

Used by the GUI REST server to build ArchiMate diagram PUML from a set of
entity + connection records chosen via the create-diagram form, and to render
transient PNG/SVG previews without persisting any files to the model.

Both the PUML generation and the PlantUML rendering reuse the same conventions
as the ``model_create_diagram`` / ``model_verify_file`` MCP tools (shared library
code from ``src.common``).
"""
from __future__ import annotations

import base64
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from src.common.archimate_relation_rendering import display_connection_label, render_archimate_relation
from src.common.model_query_parsing import normalize_puml_alias
from src.common.model_query_types import ConnectionRecord, EntityRecord
from src.common.ontology_loader import (
    CONNECTION_TYPES,
    DOMAIN_DISPLAY,
    DOMAIN_GROUPING,
    DOMAIN_ORDER,
    ELEMENT_TYPE_HAS_SPRITE,
    ENTITY_TYPES,
)


def _parse_archimate_block(raw: str) -> dict:
    """Parse the archimate display block, stripping markdown code fences first.

    ``display_blocks["archimate"]`` is stored as ``'```yaml\\n...\\n```'`` — the
    fences must be removed before calling ``yaml.safe_load``.
    """
    import yaml as _yaml

    text = re.sub(r"^```(?:yaml)?\n", "", raw.strip(), count=1)
    text = re.sub(r"\n```$", "", text, count=1)
    try:
        return _yaml.safe_load(text) or {}
    except Exception:
        return {}


_JUNCTION_TYPES = frozenset({"and-junction", "or-junction"})
_ENTITY_TYPE_ORDER = list(ENTITY_TYPES)


def _entity_archimate_element_type(entity: EntityRecord) -> str:
    arch_data = _parse_archimate_block(entity.display_blocks.get("archimate", ""))
    element_type = str(arch_data.get("element-type") or "").strip()
    if element_type:
        return element_type
    info = ENTITY_TYPES.get(entity.artifact_type)
    return info.archimate_element_type if info else ""


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


def _type_group_label(entity: EntityRecord) -> str:
    element_type = _entity_archimate_element_type(entity)
    if element_type:
        return _pluralize_label(element_type)
    return _pluralize_label(entity.artifact_type.replace("-", " ").title())


def _insert_arrow_direction(arrow: str, direction: str) -> str:
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


def _ordered_type_groups(entities: list[EntityRecord]) -> list[tuple[str, list[EntityRecord]]]:
    grouped: dict[str, list[EntityRecord]] = defaultdict(list)
    labels: dict[str, str] = {}
    for entity in entities:
        grouped[entity.artifact_type].append(entity)
        labels.setdefault(entity.artifact_type, _type_group_label(entity))
    ordered_types = [t for t in _ENTITY_TYPE_ORDER if t in grouped]
    for artifact_type in grouped:
        if artifact_type not in ordered_types:
            ordered_types.append(artifact_type)
    return [(labels[artifact_type], grouped[artifact_type]) for artifact_type in ordered_types]


def generate_archimate_puml_body(
    name: str,
    entity_records: list[EntityRecord],
    connection_records: list[ConnectionRecord],
    *,
    diagram_type: str = "archimate-business",
) -> str:
    """Return a self-contained ``@startuml … @enduml`` block (no frontmatter).

    The block includes ``!include`` directives for the archimate stereotype and
    glyph definition files so that it renders correctly out-of-the-box — both
    via ``create_diagram`` (which de-duplicates includes if already present) and
    via ``render_puml_preview`` / ``render_puml_svg``.

    Entities are grouped by domain; composition/aggregation children are nested
    inside their parent declarations.  Junction entities render as circles.
    ArchiMate connections render via PlantUML ArchiMate relation macros when
    available; other connections fall back to infix arrow syntax.
    """
    diagram_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-") or "diagram"
    is_archimate = "archimate" in diagram_type.lower()

    lines: list[str] = [f"@startuml {diagram_name}"]
    if is_archimate:
        lines.append("!include ../_archimate-stereotypes.puml")
    lines.append("")
    lines.append(f"title {name}")
    lines.append("")

    alias_by_id = {
        e.artifact_id: normalize_puml_alias(e.display_alias)
        for e in entity_records
        if e.display_alias
    }
    entity_by_alias = {
        normalize_puml_alias(e.display_alias): e
        for e in entity_records
        if e.display_alias
    }

    # Build composition/aggregation hierarchy for visual nesting
    children_map: dict[str, list[EntityRecord]] = defaultdict(list)
    comp_children: set[str] = set()
    for conn in connection_records:
        ct = CONNECTION_TYPES.get(conn.conn_type)
        if ct and ct.conn_dir in ("composition", "aggregation"):
            src_alias = alias_by_id.get(conn.source)
            tgt_alias = alias_by_id.get(conn.target)
            if src_alias and tgt_alias and tgt_alias in entity_by_alias:
                children_map[src_alias].append(entity_by_alias[tgt_alias])
                comp_children.add(tgt_alias)

    def _render_entity(entity: EntityRecord, indent: str) -> list[str]:
        alias = normalize_puml_alias(entity.display_alias)
        if not alias:
            return []
        if entity.artifact_type in _JUNCTION_TYPES:
            return [f'{indent}circle " " as {alias}']
        arch_data = _parse_archimate_block(entity.display_blocks.get("archimate", ""))
        element_type = arch_data.get("element-type", "")
        label = arch_data.get("label", entity.name).replace('"', "'")
        children = children_map.get(alias, [])
        if element_type and ELEMENT_TYPE_HAS_SPRITE.get(element_type, False):
            decl = (
                f'{indent}rectangle "<$archimate_{element_type}{{scale=1.5}}> {label}"'
                f" <<{element_type}>> as {alias}"
            )
        elif element_type:
            decl = f'{indent}rectangle "{label}" <<{element_type}>> as {alias}'
        else:
            decl = f'{indent}rectangle "{label}" as {alias}'
        if not children:
            return [decl]
        inner = indent + "  "
        result = [f"{decl} {{"]
        child_aliases = [normalize_puml_alias(c.display_alias) for c in children if c.display_alias]
        for child in children:
            result.extend(_render_entity(child, inner))
        for i in range(len(child_aliases) - 1):
            result.append(f"{inner}{child_aliases[i]} -[hidden]right- {child_aliases[i + 1]}")
        result.append(f"{indent}}}")
        return result

    domain_entities: dict[str, list[EntityRecord]] = defaultdict(list)
    for entity in entity_records:
        alias = normalize_puml_alias(entity.display_alias)
        if alias and alias not in comp_children:
            domain_entities[(entity.domain or "").lower()].append(entity)

    ordered_domains = [d for d in DOMAIN_ORDER if d in domain_entities]
    for d in sorted(domain_entities):
        if d not in DOMAIN_ORDER:
            ordered_domains.append(d)

    single_domain = len(ordered_domains) == 1
    group_index_by_alias: dict[str, int] = {}

    if single_domain and ordered_domains:
        domain = ordered_domains[0]
        grouping = DOMAIN_GROUPING.get(domain, "Grouping")
        lines.insert(3, "top to bottom direction")
        lines.insert(4, "")

        top_level_entities = domain_entities[domain]
        type_groups = _ordered_type_groups(top_level_entities)
        prev_anchor_alias: str | None = None
        for idx, (label, entities_in_group) in enumerate(type_groups):
            lines.append(f'rectangle "{label}" <<{grouping}>> {{')
            for entity in entities_in_group:
                lines.extend(_render_entity(entity, "  "))
                alias = normalize_puml_alias(entity.display_alias)
                if alias:
                    group_index_by_alias[alias] = idx
            lines.append("}")

            top_aliases = [
                normalize_puml_alias(entity.display_alias)
                for entity in entities_in_group
                if entity.display_alias
            ]
            axis = "right" if idx % 2 == 0 else "down"
            for i in range(len(top_aliases) - 1):
                lines.append(f"{top_aliases[i]} -[hidden]{axis}- {top_aliases[i + 1]}")
            if prev_anchor_alias and top_aliases:
                lines.append(f"{prev_anchor_alias} -[hidden]down- {top_aliases[0]}")
            if top_aliases:
                prev_anchor_alias = top_aliases[-1]
            lines.append("")
    else:
        for domain in ordered_domains:
            grouping = DOMAIN_GROUPING.get(domain)
            display = DOMAIN_DISPLAY.get(domain, domain.title())
            indent = "  " if grouping else ""
            if grouping:
                lines.append(f'rectangle "{display}" <<{grouping}>> {{')
            for entity in domain_entities[domain]:
                lines.extend(_render_entity(entity, indent))
            if grouping:
                lines.append("}")
            lines.append("")

    conn_lines: list[str] = []
    for conn in connection_records:
        ct = CONNECTION_TYPES.get(conn.conn_type)
        # Composition/aggregation shown structurally via nesting — skip as connection lines
        if ct and ct.conn_dir in ("composition", "aggregation"):
            continue
        src = alias_by_id.get(conn.source)
        tgt = alias_by_id.get(conn.target)
        if src and tgt:
            direction: str | None = None
            if single_domain:
                src_group = group_index_by_alias.get(src)
                tgt_group = group_index_by_alias.get(tgt)
                if src_group is not None and tgt_group is not None and src_group != tgt_group:
                    direction = "down" if src_group < tgt_group else "up"
            macro_line = render_archimate_relation(src, tgt, conn.conn_type, direction=direction, label_text="")
            if macro_line is not None:
                conn_lines.append(macro_line)
                continue
            arrow = ct.puml_arrow if ct else "-->"
            if direction:
                arrow = _insert_arrow_direction(arrow, direction)
            conn_lines.append(f"{src} {arrow} {tgt} : <<{display_connection_label(conn.conn_type)}>>")
    if conn_lines:
        lines.append("' Connections")
        lines.extend(conn_lines)
        lines.append("")

    lines.append("@enduml")
    return "\n".join(lines)


def _render_puml(
    puml_body: str, repo_root: Path, fmt: str
) -> tuple[str | None, list[str]]:
    """Core PlantUML render pipeline.

    *fmt* is ``"png"`` or ``"svg"``.  Returns ``(result, warnings)`` where
    *result* is a ``data:image/png;base64,…`` data-URL for PNG, raw SVG text
    for SVG, or ``None`` on failure.  No files are written to the model.
    """
    from src.common.model_verifier_syntax import find_plantuml_jar
    from src.common.settings import plantuml_limit_size, render_dpi

    warnings: list[str] = []
    jar = find_plantuml_jar()
    if jar is None:
        return None, ["plantuml.jar not found; render skipped"]

    diag_dir = repo_root / "diagram-catalog" / "diagrams"
    if not diag_dir.exists():
        return None, [f"Diagram directory not found: {diag_dir}"]

    render_body = re.sub(r"@startuml\s+\S+", "@startuml", puml_body, count=1)
    includes: list[str] = []
    if "_archimate-stereotypes.puml" not in render_body:
        includes.append("!include ../_archimate-stereotypes.puml")
    if "_archimate-glyphs.puml" not in render_body:
        includes.append("!include ../_archimate-glyphs.puml")
    if includes:
        insert = "\n".join(includes) + "\n"
        render_body = re.sub(r"(@startuml)\n", r"\1\n" + insert, render_body, count=1)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".puml", dir=diag_dir, delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(render_body)
            tmp_path = Path(tmp.name)

        with tempfile.TemporaryDirectory() as out_dir:
            cmd = [
                "java", "-Djava.awt.headless=true", f"-DPLANTUML_LIMIT_SIZE={plantuml_limit_size()}", "-jar", str(jar.resolve()),
                f"-t{fmt}",
            ]
            if fmt == "png":
                cmd.append(f"-Sdpi={render_dpi()}")
            cmd += ["-o", out_dir, tmp_path.name]
            proc = subprocess.run(
                cmd, cwd=str(diag_dir), capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                warnings.append(f"PlantUML render failed: {proc.stderr[:300]}")
                return None, warnings
            outputs = list(Path(out_dir).glob(f"*.{fmt}"))
            if not outputs:
                warnings.append(f"PlantUML produced no {fmt.upper()} output")
                return None, warnings
            if fmt == "png":
                return (
                    "data:image/png;base64,"
                    + base64.b64encode(outputs[0].read_bytes()).decode(),
                    warnings,
                )
            return outputs[0].read_text(encoding="utf-8"), warnings

    except (OSError, subprocess.TimeoutExpired) as exc:
        warnings.append(f"Render error: {exc}")
        return None, warnings
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def render_puml_preview(
    puml_body: str, repo_root: Path
) -> tuple[str | None, list[str]]:
    """Render *puml_body* to PNG. Returns ``(data:image/png;base64,…, warnings)``."""
    return _render_puml(puml_body, repo_root, "png")


def render_puml_svg(
    puml_body: str, repo_root: Path
) -> tuple[str | None, list[str]]:
    """Render *puml_body* to SVG. Returns ``(svg_text, warnings)``."""
    return _render_puml(puml_body, repo_root, "svg")
