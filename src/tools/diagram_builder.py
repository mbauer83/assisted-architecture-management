"""GUI helper: PUML body generation and ephemeral preview rendering.

Used by the GUI REST server to build ArchiMate diagram PUML from a set of
entity + connection records chosen via the create-diagram form, and to render
a transient PNG preview without persisting any files to the model.

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
    via ``render_puml_preview``.

    Each entity is rendered using its archimate ``element-type`` and ``label``
    from the ``§display / archimate`` block (markdown code fences stripped before
    parsing).  Falls back to the raw name when no archimate block is present.
    Connections use the canonical ``SRC --> TGT : <<conn_type>>`` format.
    """
    diagram_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-") or "diagram"
    is_archimate = "archimate" in diagram_type.lower()

    lines: list[str] = [f"@startuml {diagram_name}"]
    if is_archimate:
        lines.append("!include ../_archimate-stereotypes.puml")
        lines.append("!include ../_archimate-glyphs.puml")
    lines.append("")
    lines.append(f"title {name}")
    lines.append("")

    for entity in entity_records:
        alias = entity.display_alias
        if not alias:
            continue
        arch_data = _parse_archimate_block(entity.display_blocks.get("archimate", ""))
        element_type = arch_data.get("element-type", "")
        label = arch_data.get("label", entity.name).replace('"', "'")
        if element_type:
            lines.append(
                f'rectangle "<$archimate_{element_type}{{scale=1.5}}> {label}"'
                f" <<{element_type}>> as {alias}"
            )
        else:
            lines.append(f'rectangle "{label}" as {alias}')

    lines.append("")

    alias_by_id = {e.artifact_id: e.display_alias for e in entity_records}
    conn_lines: list[str] = []
    for conn in connection_records:
        src = alias_by_id.get(conn.source)
        tgt = alias_by_id.get(conn.target)
        if src and tgt:
            conn_lines.append(f"{src} --> {tgt} : <<{conn.conn_type}>>")
    if conn_lines:
        lines.append("' Connections")
        lines.extend(conn_lines)
        lines.append("")

    lines.append("@enduml")
    return "\n".join(lines)


def render_puml_preview(
    puml_body: str, repo_root: Path
) -> tuple[str | None, list[str]]:
    """Render *puml_body* to PNG using PlantUML, entirely in temporary files.

    Returns ``(data_url, warnings)`` where *data_url* is a
    ``data:image/png;base64,…`` string on success, or ``None`` on failure.
    No files are written to the model repository.
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

    # Strip diagram name so PlantUML uses the temp-file stem as its output name
    render_body = re.sub(r"@startuml\s+\S+", "@startuml", puml_body, count=1)

    # Inject archimate stereotype / glyph includes when absent (same as create_diagram)
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
            dpi = render_dpi()
            proc = subprocess.run(
                [
                    "java", "-Djava.awt.headless=true", "-jar", str(jar.resolve()),
                    "-tpng", f"-Sdpi={dpi}", "-o", out_dir, tmp_path.name,
                ],
                cwd=str(diag_dir),
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                warnings.append(f"PlantUML render failed: {proc.stderr[:300]}")
                return None, warnings
            pngs = list(Path(out_dir).glob("*.png"))
            if not pngs:
                warnings.append("PlantUML produced no PNG output")
                return None, warnings
            data_url = (
                "data:image/png;base64,"
                + base64.b64encode(pngs[0].read_bytes()).decode()
            )
            return data_url, warnings

    except (OSError, subprocess.TimeoutExpired) as exc:
        warnings.append(f"Render error: {exc}")
        return None, warnings
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
