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
from pathlib import Path

from src.common.model_query_types import ConnectionRecord, EntityRecord
from src.common.ontology_loader import (
    CONNECTION_TYPES,
    DOMAIN_DISPLAY,
    DOMAIN_GROUPING,
    DOMAIN_ORDER,
    ELEMENT_TYPE_HAS_SPRITE,
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

    Each entity is rendered using its archimate ``element-type`` and ``label``
    from the ``§display / archimate`` block (markdown code fences stripped before
    parsing).  Falls back to the raw name when no archimate block is present.
    Connections use the canonical ``SRC --> TGT : <<conn_type>>`` format.
    """
    from collections import defaultdict

    diagram_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-") or "diagram"
    is_archimate = "archimate" in diagram_type.lower()

    lines: list[str] = [f"@startuml {diagram_name}"]
    if is_archimate:
        lines.append("!include ../_archimate-stereotypes.puml")
    lines.append("")
    lines.append(f"title {name}")
    lines.append("")

    domain_entities: dict[str, list[EntityRecord]] = defaultdict(list)
    for entity in entity_records:
        domain_entities[(entity.domain or "").lower()].append(entity)

    ordered_domains = [d for d in DOMAIN_ORDER if d in domain_entities]
    for d in sorted(domain_entities):
        if d not in DOMAIN_ORDER:
            ordered_domains.append(d)

    for domain in ordered_domains:
        grouping = DOMAIN_GROUPING.get(domain)
        display = DOMAIN_DISPLAY.get(domain, domain.title())
        indent = "  " if grouping else ""
        if grouping:
            lines.append(f'rectangle "{display}" <<{grouping}>> {{')
        for entity in domain_entities[domain]:
            alias = entity.display_alias
            if not alias:
                continue
            arch_data = _parse_archimate_block(entity.display_blocks.get("archimate", ""))
            element_type = arch_data.get("element-type", "")
            label = arch_data.get("label", entity.name).replace('"', "'")
            if element_type and ELEMENT_TYPE_HAS_SPRITE.get(element_type, False):
                lines.append(
                    f'{indent}rectangle "<$archimate_{element_type}{{scale=1.5}}> {label}"'
                    f" <<{element_type}>> as {alias}"
                )
            elif element_type:
                lines.append(f'{indent}rectangle "{label}" <<{element_type}>> as {alias}')
            else:
                lines.append(f'{indent}rectangle "{label}" as {alias}')
        if grouping:
            lines.append("}")
        lines.append("")

    alias_by_id = {e.artifact_id: e.display_alias for e in entity_records}
    conn_lines: list[str] = []
    for conn in connection_records:
        src = alias_by_id.get(conn.source)
        tgt = alias_by_id.get(conn.target)
        if src and tgt:
            arrow = CONNECTION_TYPES[conn.conn_type].puml_arrow if conn.conn_type in CONNECTION_TYPES else "-->"
            conn_lines.append(f"{src} {arrow} {tgt} : <<{conn.conn_type}>>")
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
    from src.common.settings import render_dpi

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
                "java", "-Djava.awt.headless=true", "-jar", str(jar.resolve()),
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
