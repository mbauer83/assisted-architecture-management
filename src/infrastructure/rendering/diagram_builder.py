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
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from src.application.artifact_parsing import normalize_puml_alias
from src.config.repo_paths import DIAGRAM_CATALOG, DIAGRAMS
from src.domain.artifact_types import ConnectionRecord, EntityRecord
from src.domain.module_types import ConnectionTypeName, ElementClassName
from src.infrastructure.diagram_type_registry import get_diagram_type
from src.infrastructure.rendering._diagram_layout import (
    build_visual_nesting,
)
from src.infrastructure.rendering.puml_safety import strip_leading_puml_frontmatter


@lru_cache(maxsize=1)
def _registry():
    from src.infrastructure.app_bootstrap import get_module_registry  # noqa: PLC0415

    return get_module_registry()


@lru_cache(maxsize=None)
def _junction_types() -> frozenset[str]:
    return frozenset(_registry().entity_types_with_class(ElementClassName("junction")))


@lru_cache(maxsize=None)
def _nesting_conn_types() -> frozenset[str]:
    return frozenset(_registry().connection_types_with_class("nesting"))


@lru_cache(maxsize=None)
def _flow_conn_types() -> frozenset[str]:
    return frozenset(_registry().connection_types_with_class("dynamic"))


def _load_sprite_map(repo_root: Path) -> dict[str, str]:
    """Return {element_type_name: full_sprite_line} from _archimate-glyphs.puml."""
    glyphs_path = repo_root / DIAGRAM_CATALOG / "_archimate-glyphs.puml"
    sprites: dict[str, str] = {}
    try:
        for line in glyphs_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("sprite $archimate_"):
                m = re.match(r"sprite \$archimate_(\w+)", line)
                if m:
                    sprites[m.group(1)] = line
    except OSError:
        pass
    return sprites


def _load_stereotype_map(repo_root: Path) -> tuple[str, dict[str, str]]:
    """Parse _archimate-stereotypes.puml into (header, {TypeName: skinparam_block}).

    The header is all content before the first ``skinparam rectangle<<`` — it
    contains the Archimate stdlib include, hide stereotype, global skinparams,
    and layout directives that every diagram needs.  Each block map entry is the
    complete ``skinparam rectangle<<Type>> { ... }`` text for one element type.
    """
    stereo_path = repo_root / DIAGRAM_CATALOG / "_archimate-stereotypes.puml"
    try:
        content = stereo_path.read_text(encoding="utf-8")
    except OSError:
        return "", {}
    first = content.find("skinparam rectangle<<")
    if first == -1:
        return content, {}
    header = content[:first].rstrip("\n") + "\n"
    blocks: dict[str, str] = {}
    for m in re.finditer(r"(skinparam rectangle<<(\w+)>>\s*\{[^}]+\})", content[first:]):
        blocks[m.group(2)] = m.group(1)
    return header, blocks


def _strip_puml_comments(text: str) -> str:
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("'")]
    return "\n".join(lines).strip("\n")


def inject_archimate_includes(puml_body: str, repo_root: Path) -> str:
    from src.infrastructure.rendering.generic_puml_renderer import inject_archimate_includes as _inject

    return _inject(puml_body, repo_root)


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


@lru_cache(maxsize=1)
def _entity_type_order() -> list[str]:
    return list(_registry().all_entity_types())


def _entity_stereotype_key(entity: EntityRecord) -> str:
    """Return the PlantUML stereotype key for *entity*.

    Derived from ``artifact_type`` using snake_case convention.
    """
    return entity.artifact_type.replace("-", "_")


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
    ordered_types = [t for t in _entity_type_order() if t in grouped]
    for artifact_type in grouped:
        if artifact_type not in ordered_types:
            ordered_types.append(artifact_type)
    return [(labels[artifact_type], grouped[artifact_type]) for artifact_type in ordered_types]


def _build_visual_nesting(
    entity_records: list[EntityRecord],
    connection_records: list[ConnectionRecord],
    alias_by_id: dict[str, str],
    entity_by_alias: dict[str, EntityRecord],
) -> tuple[dict[str, list[EntityRecord]], set[str]]:
    entity_order = {
        normalize_puml_alias(entity.display_alias): index
        for index, entity in enumerate(entity_records)
        if entity.display_alias
    }
    structural_edges: list[tuple[str, str]] = []
    neighbor_edges: list[tuple[str, str]] = []
    for conn in connection_records:
        src_alias = alias_by_id.get(conn.source)
        tgt_alias = alias_by_id.get(conn.target)
        if not src_alias or not tgt_alias:
            continue
        ct = _registry().all_connection_types().get(ConnectionTypeName(conn.conn_type))
        if ct and ct.artifact_type in _nesting_conn_types() and tgt_alias in entity_by_alias:
            structural_edges.append((src_alias, tgt_alias))
            continue
        neighbor_edges.append((src_alias, tgt_alias))

    children_map, nested_aliases = build_visual_nesting(
        item_by_alias=entity_by_alias,
        structural_edges=structural_edges,
        neighbor_edges=neighbor_edges,
        junction_aliases={
            alias for alias, entity in entity_by_alias.items() if entity.artifact_type in _junction_types()
        },
    )
    for parent_alias, children in children_map.items():
        children.sort(
            key=lambda entity: entity_order.get(normalize_puml_alias(entity.display_alias), len(entity_order))
        )
    return children_map, nested_aliases


def generate_archimate_puml_body(
    name: str,
    entity_records: list[EntityRecord],
    connection_records: list[ConnectionRecord],
    *,
    diagram_type: str = "archimate-business",
    repo_root: Path = Path("."),
    diagram_entities: dict[str, object] | None = None,
    diagram_connections: list[dict[str, object]] | None = None,
    edge_labels: dict[str, str] | None = None,
) -> str:
    diagram_type_mod = get_diagram_type(diagram_type)
    extra: dict[str, object] = {}
    if edge_labels:
        extra["edge_labels"] = edge_labels
    return diagram_type_mod.renderer.render_body(
        name,
        entity_records,
        connection_records,
        diagram_type,
        repo_root,
        diagram_entities=diagram_entities,
        diagram_connections=diagram_connections,
        **extra,
    )


def _prepare_preview_body(
    puml_body: str,
    repo_root: Path,
    diagram_type: str | None,
) -> str:
    if diagram_type is None:
        return puml_body
    return get_diagram_type(diagram_type).renderer.inject_includes(puml_body, repo_root)


def _render_puml(
    puml_body: str,
    repo_root: Path,
    fmt: str,
    diagram_type: str | None = None,
) -> tuple[str | None, list[str]]:
    """Core PlantUML render pipeline.

    *fmt* is ``"png"`` or ``"svg"``.  Returns ``(result, warnings)`` where
    *result* is a ``data:image/png;base64,…`` data-URL for PNG, raw SVG text
    for SVG, or ``None`` on failure.  No files are written to the model.
    """
    from src.application.verification.artifact_verifier_syntax import find_graphviz_dot, find_plantuml_jar
    from src.config.settings import plantuml_limit_size, render_dpi

    warnings: list[str] = []
    jar = find_plantuml_jar()
    if jar is None:
        return None, ["plantuml.jar not found; render skipped"]

    diag_dir = repo_root / DIAGRAM_CATALOG / DIAGRAMS
    if not diag_dir.exists():
        return None, [f"Diagram directory not found: {diag_dir}"]

    render_body = strip_leading_puml_frontmatter(puml_body)
    render_body = re.sub(r"@startuml\s+\S+", "@startuml", render_body, count=1)
    render_body = _prepare_preview_body(render_body, repo_root, diagram_type)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".puml", dir=diag_dir, delete=False, encoding="utf-8") as tmp:
            tmp.write(render_body)
            tmp_path = Path(tmp.name)

        with tempfile.TemporaryDirectory() as out_dir:
            env = None
            dot = find_graphviz_dot()
            if dot is not None:
                env = {**os.environ, "GRAPHVIZ_DOT": str(dot)}
            cmd = [
                "java",
                "-Djava.awt.headless=true",
                f"-DPLANTUML_LIMIT_SIZE={plantuml_limit_size()}",
                "-jar",
                str(jar.resolve()),
                f"-t{fmt}",
            ]
            if fmt == "png":
                cmd.append(f"-Sdpi={render_dpi()}")
            cmd += ["-o", out_dir, tmp_path.name]
            proc = subprocess.run(
                cmd,
                cwd=str(diag_dir),
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
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
                    "data:image/png;base64," + base64.b64encode(outputs[0].read_bytes()).decode(),
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
    puml_body: str,
    repo_root: Path,
    diagram_type: str | None = None,
) -> tuple[str | None, list[str]]:
    """Render *puml_body* to PNG. Returns ``(data:image/png;base64,…, warnings)``."""
    return _render_puml(puml_body, repo_root, "png", diagram_type)


def render_puml_svg(
    puml_body: str,
    repo_root: Path,
    diagram_type: str | None = None,
) -> tuple[str | None, list[str]]:
    """Render *puml_body* to SVG. Returns ``(svg_text, warnings)``."""
    return _render_puml(puml_body, repo_root, "svg", diagram_type)
